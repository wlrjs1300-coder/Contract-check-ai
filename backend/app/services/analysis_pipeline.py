from collections.abc import Sequence

from sqlalchemy.orm import Session

from backend.app.db.models import (
    AnalysisJob,
    AnalysisResultItem,
    Clause,
    Extraction,
)
from backend.app.services.analysis_provider import (
    DEFAULT_ANALYSIS_PROVIDER,
    AnalysisProvider,
    AnalysisProviderInput,
)
from backend.app.services.evidence_linking import (
    EvidenceValidationError,
    bind_evidence_to_finding,
    calculate_snapshot_hash,
)
from backend.app.services.output_safety import (
    ALLOW,
    check_summary_output,
)
from backend.app.services.pii_masking import (
    detect_and_mask,
    detect_entities,
)
from backend.app.services.provider_execution import (
    DEFAULT_PROVIDER_EXECUTION_POLICY,
    ProviderExecutionPolicy,
    execute_provider,
)


VALID_JOB_STATUSES = {
    "queued",
    "processing",
    "completed",
    "failed",
}


def _load_confirmation_snapshot(
    db: Session,
    document_id: str,
) -> tuple[list[dict[str, object]], str | None, int | None]:
    extraction = db.get(Extraction, document_id)
    if extraction is None:
        return [], None, None

    extra_data = extraction.extra_data or {}
    snapshot = extra_data.get("confirmation_snapshot")
    if not isinstance(snapshot, list):
        return [], None, None

    snapshot_hash = extra_data.get("confirmation_checksum")
    snapshot_version = extra_data.get("snapshot_version")
    snapshot_list = [dict(item) for item in snapshot]
    return snapshot_list, (
        str(snapshot_hash) if snapshot_hash else calculate_snapshot_hash(snapshot_list)
    ), (
        int(snapshot_version) if isinstance(snapshot_version, int) else None
    )


def validate_reference_id(
    document_id: str,
    clause: Clause,
) -> None:
    expected_reference_id = (
        f"{document_id}:clause:{clause.ordinal}"
    )

    if clause.reference_id != expected_reference_id:
        raise ValueError(
            "Clause reference_id does not match its document and ordinal."
        )


def validate_result_reference_id(
    clause: Clause,
    result_reference_id: str,
) -> None:
    if result_reference_id != clause.reference_id:
        raise ValueError(
            "Provider result reference_id does not match the current clause."
        )


def build_provider_input(
    clause: Clause,
) -> AnalysisProviderInput:
    masking_result = detect_and_mask(
        clause.body,
        avoid_preexisting_token_collisions=True,
    )
    masked_text = masking_result["masked_text"]

    residual_entities = detect_entities(
        masked_text,
        avoid_preexisting_token_collisions=True,
    )

    if residual_entities:
        raise ValueError(
            "Residual personal data remains after masking."
        )

    return AnalysisProviderInput(
        reference_id=clause.reference_id,
        masked_text=masked_text,
    )


def run_analysis_pipeline(
    db: Session,
    job: AnalysisJob,
    clauses: Sequence[Clause],
    provider: AnalysisProvider = DEFAULT_ANALYSIS_PROVIDER,
    provider_policy: ProviderExecutionPolicy = (
        DEFAULT_PROVIDER_EXECUTION_POLICY
    ),
) -> None:
    job.status = "processing"
    db.flush()
    snapshot, snapshot_hash, snapshot_version = _load_confirmation_snapshot(
        db,
        job.document_id,
    )

    try:
        for clause in clauses:
            validate_reference_id(job.document_id, clause)

            provider_input = build_provider_input(clause)
            result_data = execute_provider(
                provider,
                provider_input,
                policy=provider_policy,
            )
            result_data.validate()
            validate_result_reference_id(
                clause,
                result_data.reference_id,
            )

            regenerated_pii = detect_entities(
                result_data.summary,
                avoid_preexisting_token_collisions=True,
            )

            if regenerated_pii:
                raise ValueError(
                    "Provider result summary contains regenerated personal data."
                )

            output_safety = check_summary_output(
                result_data.summary,
            )

            if output_safety["classification"] != ALLOW:
                raise ValueError(
                    "Provider result summary failed output safety validation."
                )

            try:
                evidence = bind_evidence_to_finding(
                    document_id=job.document_id,
                    extraction_id=job.document_id,
                    clause=clause,
                    snapshot=snapshot,
                    snapshot_hash=snapshot_hash,
                    snapshot_version=snapshot_version,
                )
            except EvidenceValidationError as exc:
                raise ValueError(f"{exc.code}: {exc.detail}") from exc

            job.result_items.append(
                AnalysisResultItem(
                    clause_record_id=clause.id,
                    reference_id=result_data.reference_id,
                    display_label=result_data.display_label,
                    summary=result_data.summary,
                    expert_review_recommended=(
                        result_data.expert_review_recommended
                    ),
                    extra_data={
                        "evidence": evidence,
                        "evidence_snapshot_hash": snapshot_hash,
                        "snapshot_version": snapshot_version,
                    },
                )
            )

        job.status = "completed"
        db.commit()
        db.refresh(job)
    except Exception:
        job_id = job.id
        db.rollback()

        failed_job = db.get(AnalysisJob, job_id)

        if failed_job is not None:
            failed_job.status = "failed"
            db.commit()

        raise
