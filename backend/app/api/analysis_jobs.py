import json
from datetime import datetime
from hashlib import sha256
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from backend.app.db.database import get_db
from backend.app.core.auth import get_current_user
from backend.app.core.rate_limit import enforce_user_rate_limit
from backend.app.core.encryption_config import get_encryption_keyring
from backend.app.db.models import AnalysisJob, Clause, Document, Extraction, User
from backend.app.services.clause_splitter import split_clauses_with_snapshot
from backend.app.services.analysis_provider_factory import resolve_provider_name
from backend.app.services.nested_json_encryption import decrypt_confirmation_snapshot
from backend.app.services.scalar_encryption import (
    ScalarEncryptionError,
    ScalarDecryptionError,
    encrypt_clause_body,
)
from backend.app.services.document_metadata_encryption import (
    encrypt_unclassified_sections,
)
from backend.app.services.scalar_metadata_encryption import (
    decrypt_extraction_filename_display,
    encrypt_clause_title,
    encrypt_document_filename,
)


router = APIRouter(tags=["analysis-jobs"])
ANALYSIS_CONTRACT_VERSION = "analysis-provider-request.v1"


def _parse_if_match_version(if_match: str | None) -> int:
    if if_match is None:
        raise HTTPException(
            status_code=400,
            detail="If-Match header is required.",
        )

    version_token = if_match.strip()
    if version_token.startswith("W/"):
        version_token = version_token[2:]
    if version_token.startswith('"') and version_token.endswith('"'):
        version_token = version_token[1:-1]
    try:
        return int(version_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="The If-Match value is invalid.",
        ) from exc


def _snapshot_checksum(items: list[dict[str, object]]) -> str:
    from hashlib import sha256

    hasher = sha256()
    for item in items:
        hasher.update(str(item["final_text"]).encode("utf-8"))
        hasher.update(b"\n")
    return hasher.hexdigest()


def _request_fingerprint(
    *,
    owner_id: str,
    document_id: str,
    source_type: str,
    source_id: str,
    source_revision: int | None,
    source_hashes: list[str],
) -> str:
    payload = {
        "analysis_contract_version": ANALYSIS_CONTRACT_VERSION,
        "document_id": document_id,
        "owner_id": owner_id,
        "provider": resolve_provider_name(),
        "source_hashes": sorted(source_hashes),
        "source_id": source_id,
        "source_revision": source_revision,
        "source_type": source_type,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _enqueue_analysis_job(
    db: Session,
    *,
    document_id: str,
    request_fingerprint: str,
) -> AnalysisJob:
    existing = db.scalar(
        select(AnalysisJob).where(
            AnalysisJob.active_dedupe_key == request_fingerprint,
            AnalysisJob.status.in_(("pending", "running")),
        )
    )
    if existing is not None:
        return existing

    job = AnalysisJob(
        id=str(uuid4()),
        document_id=document_id,
        status="pending",
        attempt_count=0,
        max_attempts=3,
        available_at=datetime.utcnow(),
        request_fingerprint=request_fingerprint,
        active_dedupe_key=request_fingerprint,
    )
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(AnalysisJob).where(
                AnalysisJob.active_dedupe_key == request_fingerprint,
                AnalysisJob.status.in_(("pending", "running")),
            )
        )
        if existing is None:
            raise
        return existing
    db.refresh(job)
    return job


def _get_extraction_ready_for_analysis(
    extraction_id: str,
    db: Session,
    current_user: User,
    *,
    if_match: str | None,
) -> Extraction:
    statement = (
        select(Extraction)
        .options(selectinload(Extraction.pages))
        .where(
            Extraction.id == extraction_id,
            Extraction.owner_id == current_user.id,
        )
    )
    extraction = db.scalar(statement)

    if extraction is None:
        raise HTTPException(
            status_code=404,
            detail="Extraction not found.",
        )

    request_version = _parse_if_match_version(if_match)

    extra_data = extraction.extra_data or {}

    if extraction.status != "confirmed":
        raise HTTPException(
            status_code=409,
            detail="confirmation_required",
        )

    if (extra_data.get("review_status") or "").lower() != "confirmed":
        raise HTTPException(
            status_code=409,
            detail="confirmation_required",
        )

    try:
        snapshot_version = int(extra_data.get("snapshot_version", 0))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=409,
            detail="The extraction snapshot revision is unavailable.",
        ) from exc

    if request_version != snapshot_version:
        raise HTTPException(
            status_code=409,
            detail="extraction revision mismatch",
        )

    stored_snapshot = extra_data.get("confirmation_snapshot")
    if not isinstance(stored_snapshot, list) or not stored_snapshot:
        raise HTTPException(
            status_code=409,
            detail="confirmation_required",
        )

    try:
        snapshot = decrypt_confirmation_snapshot(
            stored_snapshot,
            extraction_id=extraction.id,
            owner_id=current_user.id,
            snapshot_version=snapshot_version,
            keyring=get_encryption_keyring(),
        )
    except ScalarDecryptionError as exc:
        raise HTTPException(
            status_code=500,
            detail="The extraction snapshot could not be decrypted.",
        ) from exc

    page_numbers: list[int] = []
    page_ids: list[str] = []
    for item in snapshot:
        page_number = item.get("page_number")
        page_id = item.get("page_id")
        final_text = item.get("final_text")

        if not isinstance(page_number, int) or page_number < 1:
            raise HTTPException(
                status_code=409,
                detail="extraction_review_incomplete",
            )
        if not isinstance(page_id, str) or not page_id.strip():
            raise HTTPException(
                status_code=409,
                detail="extraction_review_incomplete",
            )
        if not isinstance(final_text, str) or not final_text.strip():
            raise HTTPException(
                status_code=409,
                detail="invalid_confirmation_snapshot",
            )

        page_numbers.append(page_number)
        page_ids.append(page_id)

    if sorted(page_numbers) != list(range(1, len(page_numbers) + 1)):
        raise HTTPException(
            status_code=409,
            detail="extraction_review_incomplete",
        )
    if len(set(page_ids)) != len(page_ids):
        raise HTTPException(
            status_code=409,
            detail="extraction_review_incomplete",
        )

    expected_checksum = _snapshot_checksum(snapshot)
    stored_checksum = extra_data.get("confirmation_checksum")
    if stored_checksum != expected_checksum:
        raise HTTPException(
            status_code=409,
            detail="stale_extraction_revision",
        )

    return extraction


def _load_or_create_analysis_document(
    db: Session,
    extraction: Extraction,
    current_user_id: str,
) -> str:
    statement = (
        select(Document)
        .options(selectinload(Document.clauses))
        .where(Document.id == extraction.id)
    )
    document = db.scalar(statement)
    if document is not None and document.owner_id != current_user_id:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    extraction_data = extraction.extra_data or {}
    stored_snapshot = extraction_data.get("confirmation_snapshot")
    if not isinstance(stored_snapshot, list) or not stored_snapshot:
        raise HTTPException(
            status_code=409,
            detail="invalid_confirmation_snapshot",
        )

    encryption_keyring = get_encryption_keyring()
    try:
        snapshot = decrypt_confirmation_snapshot(
            stored_snapshot,
            extraction_id=extraction.id,
            owner_id=current_user_id,
            snapshot_version=extraction_data.get("snapshot_version"),
            keyring=encryption_keyring,
        )
    except ScalarDecryptionError as exc:
        raise HTTPException(
            status_code=500,
            detail="The extraction snapshot could not be decrypted.",
        ) from exc

    split_result = split_clauses_with_snapshot(
        snapshot,
        document_id=extraction.id,
    )
    clauses_data = split_result["clauses"]

    if document is None:
        try:
            filename = decrypt_extraction_filename_display(
                extraction.filename_display_encrypted,
                record_id=extraction.id,
                owner_id=current_user_id,
                keyring=encryption_keyring,
            )
            if not isinstance(filename, str):
                raise ScalarEncryptionError("Invalid filename.")
            filename_encrypted = encrypt_document_filename(
                filename,
                record_id=extraction.id,
                owner_id=current_user_id,
                keyring=encryption_keyring,
            )
            unclassified_sections = encrypt_unclassified_sections(
                split_result["unclassified_sections"],
                document_id=extraction.id,
                owner_id=current_user_id,
                keyring=encryption_keyring,
            )
        except ScalarEncryptionError as exc:
            raise HTTPException(
                status_code=500,
                detail="Unable to prepare document content.",
            ) from exc
        document = Document(
            id=extraction.id,
            owner_id=current_user_id,
            filename_encrypted=filename_encrypted,
            content_type=extraction.source_type,
            size_bytes=extraction.size_bytes,
            character_count=int(extraction_data.get("final_total_text_length", 0)),
            status="processed",
            unclassified_sections=unclassified_sections,
            document_warnings=extraction.warnings,
        )
        db.add(document)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=404,
                detail="Document not found.",
            ) from exc

    if not document.clauses:
        for clause_data in clauses_data:
            body = str(clause_data["text"])
            clause_id = str(uuid4())
            encrypted_body = encrypt_clause_body(
                body,
                clause_id=clause_id,
                owner_id=current_user_id,
                keyring=encryption_keyring,
            )
            title = clause_data.get("title")
            title_encrypted = encrypt_clause_title(
                title,
                clause_id=clause_id,
                owner_id=current_user_id,
                keyring=encryption_keyring,
            )
            clause = Clause(
                id=clause_id,
                clause_id=clause_data["clause_id"],
                reference_id=clause_data["reference_id"],
                source_hash=clause_data["source_hash"],
                ordinal=clause_data["ordinal"],
                marker=clause_data["marker"],
                clause_type=clause_data["clause_type"],
                title_encrypted=title_encrypted,
                body_encrypted=encrypted_body,
                warnings=list(clause_data.get("warnings") or []),
            )
            clause.start_offset = clause_data.get("start_offset")
            clause.end_offset = clause_data.get("end_offset")
            clause.page_start = clause_data.get("page_start")
            clause.page_end = clause_data.get("page_end")
            clause.block_ids = clause_data.get("block_ids", [])
            clause.clause_level = clause_data.get("clause_level")
            clause.split_method = split_result["split_method"]
            document.clauses.append(clause)
        db.flush()

    return document.id


@router.post(
    "/documents/{document_id}/analysis-jobs",
    dependencies=[Depends(enforce_user_rate_limit("analysis_job"))],
)
def create_analysis_job(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    statement = (
        select(Document)
        .options(selectinload(Document.clauses))
        .where(
            Document.id == document_id,
            Document.owner_id == current_user.id,
        )
    )
    document = db.scalar(statement)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    fingerprint = _request_fingerprint(
        owner_id=current_user.id,
        document_id=document_id,
        source_type="document",
        source_id=document_id,
        source_revision=None,
        source_hashes=[clause.source_hash for clause in document.clauses],
    )
    job = _enqueue_analysis_job(
        db,
        document_id=document_id,
        request_fingerprint=fingerprint,
    )

    return {"job_id": job.id, "document_id": job.document_id, "status": job.status}


@router.post(
    "/extractions/{extraction_id}/analysis-jobs",
    dependencies=[Depends(enforce_user_rate_limit("analysis_job"))],
)
def create_extraction_analysis_job(
    extraction_id: str,
    if_match: str | None = Header(default=None, alias="If-Match"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    extraction = _get_extraction_ready_for_analysis(
        extraction_id,
        db,
        current_user,
        if_match=if_match,
    )

    document_id = _load_or_create_analysis_document(
        db,
        extraction,
        current_user.id,
    )
    statement = (
        select(Clause)
        .where(Clause.document_id == document_id)
        .order_by(Clause.ordinal)
    )
    clauses = db.scalars(statement).all()

    if not clauses:
        raise HTTPException(
            status_code=409,
            detail="stale_extraction_revision",
        )

    extraction_data = extraction.extra_data or {}
    fingerprint = _request_fingerprint(
        owner_id=current_user.id,
        document_id=document_id,
        source_type="extraction",
        source_id=extraction.id,
        source_revision=int(extraction_data["snapshot_version"]),
        source_hashes=[clause.source_hash for clause in clauses],
    )
    job = _enqueue_analysis_job(
        db,
        document_id=document_id,
        request_fingerprint=fingerprint,
    )

    return {
        "job_id": job.id,
        "document_id": job.document_id,
        "status": job.status,
    }


@router.get("/analysis-jobs/{job_id}")
def get_analysis_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    statement = (
        select(AnalysisJob)
        .join(Document)
        .where(
            AnalysisJob.id == job_id,
            Document.owner_id == current_user.id,
        )
    )
    job = db.scalar(statement)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Analysis job not found.",
        )

    return {
        "job_id": job.id,
        "document_id": job.document_id,
        "status": job.status,
    }
