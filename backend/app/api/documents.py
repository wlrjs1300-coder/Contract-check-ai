from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.db.database import get_db
from backend.app.core.auth import get_current_user
from backend.app.core.encryption_config import EncryptionKeyring, get_encryption_keyring
from backend.app.db.models import (
    AnalysisJob,
    AnalysisResultItem,
    Clause,
    Document,
    Extraction,
)
from backend.app.db.models import User
from backend.app.services.clause_splitter import split_clauses
from backend.app.services.evidence_linking import calculate_snapshot_hash
from backend.app.services.scalar_encryption import (
    ScalarEncryptionError,
    ScalarDecryptionError,
    decrypt_clause_body,
    decrypt_analysis_result_summary,
    encrypt_clause_body,
)


router = APIRouter(prefix="/documents", tags=["documents"])

MAX_FILE_SIZE = 1 * 1024 * 1024
ALLOWED_SUFFIXES = {".txt"}


def _serialize_clause(
    clause: Clause,
    *,
    owner_id: str,
    keyring: EncryptionKeyring,
) -> dict[str, object]:
    try:
        body = decrypt_clause_body(
            clause.body_encrypted,
            clause_id=clause.id,
            owner_id=owner_id,
            keyring=keyring,
        )
    except ScalarDecryptionError as exc:
        raise HTTPException(
            status_code=500,
            detail="Stored encrypted data is unavailable.",
        ) from exc

    return {
        "clause_id": clause.clause_id,
        "reference_id": clause.reference_id,
        "source_hash": clause.source_hash,
        "ordinal": clause.ordinal,
        "marker": clause.marker,
        "clause_type": clause.clause_type,
        "title": clause.title,
        "body": body,
        "warnings": clause.warnings,
    }


def _serialize_document(
    document: Document,
    *,
    keyring: EncryptionKeyring,
) -> dict[str, object]:
    clauses = sorted(document.clauses, key=lambda clause: clause.ordinal)
    owner_id = document.owner_id

    return {
        "document_id": document.id,
        "filename": document.filename,
        "content_type": document.content_type,
        "size_bytes": document.size_bytes,
        "character_count": document.character_count,
        "status": document.status,
        "clause_count": len(clauses),
        "clauses": [
            _serialize_clause(clause, owner_id=owner_id, keyring=keyring)
            for clause in clauses
        ],
        "unclassified_sections": document.unclassified_sections,
        "document_warnings": document.document_warnings,
    }


def _snapshot_hash(snapshot: list[dict[str, object]]) -> str:
    return calculate_snapshot_hash(snapshot)


def _analysis_value(item: AnalysisResultItem) -> dict[str, object]:
    extra = item.extra_data or {}
    analysis_value = extra.get("analysis_value")
    if isinstance(analysis_value, dict):
        return analysis_value
    return {}


def _analysis_summary_from_items(
    *,
    items: list[AnalysisResultItem],
    current_snapshot_hash: str | None,
) -> dict[str, object]:
    severity_order = ["critical", "high", "medium", "low", "info"]
    action_priority_order = [
        "before_signing",
        "negotiate",
        "clarify",
        "monitor",
        "expert_review",
        "informational",
    ]
    severity_rank = {
        severity: len(severity_order) - idx
        for idx, severity in enumerate(severity_order)
    }
    action_rank = {
        action: len(action_priority_order) - idx
        for idx, action in enumerate(action_priority_order)
    }

    if not items:
        return {
            "overall_risk_level": "info",
            "overall_display_label": "safe",
            "total_findings": 0,
            "critical_count": 0,
            "high_count": 0,
            "medium_count": 0,
            "low_count": 0,
            "info_count": 0,
            "top_priorities": [],
            "key_dates": [],
            "key_amounts": [],
            "key_obligations": [],
            "missing_terms_count": 0,
            "ambiguity_count": 0,
            "expert_review_recommended": False,
            "snapshot_version": None,
            "snapshot_stale": False,
        }

    severities = [str(_analysis_value(item).get("severity", "info")) for item in items]
    critical = sum(1 for severity in severities if severity == "critical")
    high = sum(1 for severity in severities if severity == "high")
    medium = sum(1 for severity in severities if severity == "medium")
    low = sum(1 for severity in severities if severity == "low")
    info = sum(1 for severity in severities if severity == "info")

    if critical:
        overall_risk = "critical"
    elif high:
        overall_risk = "high"
    elif medium:
        overall_risk = "medium"
    elif low:
        overall_risk = "low"
    else:
        overall_risk = "info"

    total_status_count = critical + high + medium + low + info
    if total_status_count != len(items):
        raise ValueError("severity count does not match total findings.")

    sorted_priorities = sorted(
        items,
        key=lambda item: (
            severity_rank.get(
                str(_analysis_value(item).get("severity", "info")),
                0,
            ),
            action_rank.get(
                str(_analysis_value(item).get("action_priority", "informational")),
                0,
            ),
            str(item.id),
        ),
    )
    top_priorities = [
        {
            "finding_id": str(
                _analysis_value(item).get("finding_id") or item.id
            ),
            "severity": str(_analysis_value(item).get("severity", "info")),
            "title": str(_analysis_value(item).get("title") or item.clause.title or item.id),
            "action_priority": str(_analysis_value(item).get("action_priority", "informational")),
        }
        for item in sorted_priorities[:3]
    ]

    key_dates: list[str] = []
    key_amounts: list[str] = []
    key_obligations: list[str] = []
    missing_terms_count = 0
    ambiguity_count = 0
    for item in items:
        value = _analysis_value(item)
        for fact in value.get("extracted_facts", []):
            if not isinstance(fact, dict):
                continue
            fact_type = str(fact.get("fact_type", ""))
            status = str(fact.get("status", "")).strip().lower()
            if status == "missing":
                missing_terms_count += 1
            elif status == "ambiguous":
                ambiguity_count += 1

            if fact_type in {"contract_start_date", "contract_end_date", "payment_date", "notice_deadline"}:
                date_value = str(fact.get("date_value", "")).strip()
                if date_value:
                    key_dates.append(date_value)
            if fact_type in {"payment_amount", "deposit", "penalty", "late_fee", "interest_rate"}:
                amount_value = str(fact.get("amount_value", "")).strip()
                if amount_value:
                    currency = str(fact.get("currency", "")).strip() or "KRW"
                    key_amounts.append(f"{amount_value} {currency}")
            if fact_type == "obligation":
                obligation_party = str(fact.get("obligation_party", "")).strip()
                if obligation_party:
                    label = str(fact.get("label", "")).strip()
                    key_obligations.append(f"{obligation_party}: {label}".strip())

    snapshot_versions = [
        int(item.extra_data.get("snapshot_version"))
        for item in items
        if isinstance(item.extra_data, dict)
        and isinstance(item.extra_data.get("snapshot_version"), int)
    ]

    return {
        "overall_risk_level": overall_risk,
        "overall_display_label": (
            "warning" if overall_risk in {"critical", "high"} else "safe"
        ),
        "total_findings": len(items),
        "critical_count": critical,
        "high_count": high,
        "medium_count": medium,
        "low_count": low,
        "info_count": info,
        "top_priorities": top_priorities,
        "key_dates": key_dates,
        "key_amounts": key_amounts,
        "key_obligations": key_obligations,
        "missing_terms_count": missing_terms_count,
        "ambiguity_count": ambiguity_count,
        "expert_review_recommended": any(
            item.expert_review_recommended for item in items
        ),
        "snapshot_version": max(snapshot_versions) if snapshot_versions else None,
        "snapshot_stale": any(
            _is_snapshot_stale(item=item, current_snapshot_hash=current_snapshot_hash)
            for item in items
        ),
    }


def _get_document_for_current_user(
    *,
    db: Session,
    document_id: str,
    current_user: User,
) -> Document:
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
    return document

def _is_snapshot_stale(
    item: AnalysisResultItem,
    current_snapshot_hash: str | None,
) -> bool:
    if current_snapshot_hash is None:
        return False
    if not isinstance(item.extra_data, dict):
        return False
    evidence_hash = item.extra_data.get("evidence_snapshot_hash")
    return isinstance(evidence_hash, str) and evidence_hash != current_snapshot_hash


def _serialize_analysis_result_item(
    item: AnalysisResultItem,
    *,
    current_snapshot_hash: str | None,
    owner_id: str,
    keyring: EncryptionKeyring,
) -> dict[str, object]:
    value = _analysis_value(item)
    summary = _resolve_analysis_result_summary(
        item,
        owner_id=owner_id,
        keyring=keyring,
    )
    return {
        "clause_id": item.clause.clause_id,
        "reference_id": item.reference_id,
        "finding_id": item.id,
        "display_label": item.display_label,
        "summary": summary,
        "expert_review_recommended": item.expert_review_recommended,
        "severity": value.get("severity", "info"),
        "title": value.get("title") or item.clause.title,
        "category": value.get("category"),
        "risk_type": value.get("risk_type"),
        "risk_reason": value.get("risk_reason"),
        "practical_impact": value.get("practical_impact"),
        "action_priority": value.get("action_priority"),
        "questions_to_ask": value.get("questions_to_ask", []),
        "negotiation_suggestions": value.get(
            "negotiation_suggestions",
            [],
        ),
        "recommendation": value.get("recommendation", summary),
        "expert_review_reason_codes": value.get("expert_review_reason_codes", []),
        "expert_review_summary": value.get("expert_review_summary", ""),
        "evidence": value.get("evidence", item.extra_data.get("evidence", [])),
        "extracted_facts": value.get("extracted_facts", []),
        "validation_status": value.get("validation_status", "verified"),
        "is_stale": _is_snapshot_stale(item, current_snapshot_hash),
        "snapshot_version": (
            item.extra_data.get("snapshot_version")
            if isinstance(item.extra_data, dict)
            else None
        ),
    }


def _resolve_analysis_result_summary(
    item: AnalysisResultItem,
    *,
    owner_id: str,
    keyring: EncryptionKeyring,
) -> str:
    try:
        return decrypt_analysis_result_summary(
            item.summary_encrypted,
            analysis_job_id=item.analysis_job_id,
            clause_record_id=item.clause_record_id,
            owner_id=owner_id,
            keyring=keyring,
        )
    except ScalarDecryptionError as exc:
        raise HTTPException(
            status_code=500,
            detail="Stored encrypted data is unavailable.",
        ) from exc


def _get_extraction_snapshot(
    document_id: str,
    db: Session,
    current_user: User,
) -> list[dict[str, object]]:
    extraction = db.scalar(
        select(Extraction).where(
            Extraction.id == document_id,
            Extraction.owner_id == current_user.id,
        )
    )
    if extraction is None:
        return []

    extra_data = extraction.extra_data or {}
    snapshot = extra_data.get("confirmation_snapshot")
    if not isinstance(snapshot, list):
        return []

    return [item for item in snapshot if isinstance(item, dict)]


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()

    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail="Only .txt files are allowed.",
        )

    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty.",
        )

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="The uploaded file exceeds the 1 MB limit.",
        )

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file must be UTF-8 encoded.",
        ) from exc

    document_id = str(uuid4())
    clause_result = split_clauses(text, document_id)

    document = Document(
        id=document_id,
        filename=filename,
        owner_id=current_user.id,
        content_type=file.content_type,
        size_bytes=len(content),
        character_count=len(text),
        status="processed",
        unclassified_sections=clause_result["unclassified_sections"],
        document_warnings=clause_result["document_warnings"],
    )

    keyring = get_encryption_keyring()
    for clause_data in clause_result["clauses"]:
        clause_id = str(uuid4())
        body = str(clause_data["body"])
        try:
            body_encrypted = encrypt_clause_body(
                body,
                clause_id=clause_id,
                owner_id=current_user.id,
                keyring=keyring,
            )
        except ScalarEncryptionError as exc:
            raise HTTPException(
                status_code=500,
                detail="Unable to prepare document content.",
            ) from exc
        document.clauses.append(
            Clause(
                id=clause_id,
                clause_id=clause_data["clause_id"],
                reference_id=clause_data["reference_id"],
                source_hash=clause_data["source_hash"],
                ordinal=clause_data["ordinal"],
                marker=clause_data["marker"],
                clause_type=clause_data["clause_type"],
                title=clause_data["title"],
                body_encrypted=body_encrypted,
                warnings=clause_data["warnings"],
            )
        )

    db.add(document)
    db.commit()
    db.refresh(document)

    return _serialize_document(document, keyring=keyring)


@router.get("/{document_id}")
def get_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    document = _get_document_for_current_user(
        db=db,
        document_id=document_id,
        current_user=current_user,
    )
    keyring = get_encryption_keyring()
    return _serialize_document(document, keyring=keyring)


@router.get("/{document_id}/analysis-results")
def get_analysis_results(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    _get_document_for_current_user(
        db=db,
        document_id=document_id,
        current_user=current_user,
    )

    statement = (
        select(AnalysisJob)
        .join(Document)
        .options(
            selectinload(AnalysisJob.result_items).selectinload(
                AnalysisResultItem.clause
            )
        )
        .where(
            AnalysisJob.document_id == document_id,
            Document.owner_id == current_user.id,
        )
        .order_by(AnalysisJob.created_at.desc())
    )
    job = db.scalars(statement).first()

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Analysis result not found.",
        )

    extraction = db.scalar(
        select(Extraction).where(
            Extraction.id == document_id,
            Extraction.owner_id == current_user.id,
        )
    )
    snapshot = _get_extraction_snapshot(
        document_id,
        db=db,
        current_user=current_user,
    )
    current_snapshot_hash: str | None = (
        _snapshot_hash(snapshot) if snapshot else None
    )
    extraction_snapshot_version = None
    if extraction is not None:
        extraction_snapshot_version = (extraction.extra_data or {}).get(
            "snapshot_version"
        )

    items = sorted(
        job.result_items,
        key=lambda item: item.clause.ordinal,
    )

    keyring = get_encryption_keyring()
    item_payloads = [
        _serialize_analysis_result_item(
            item=item,
            current_snapshot_hash=current_snapshot_hash,
            owner_id=current_user.id,
            keyring=keyring,
        )
        for item in items
    ]
    analysis_summary = _analysis_summary_from_items(
        items=items,
        current_snapshot_hash=current_snapshot_hash,
    )

    return {
        "document_id": document_id,
        "job_id": job.id,
        "status": job.status,
        "snapshot_version": extraction_snapshot_version,
        "snapshot_stale": analysis_summary["snapshot_stale"],
        "analysis_summary": analysis_summary,
        "items": item_payloads,
        "findings": item_payloads,
    }
