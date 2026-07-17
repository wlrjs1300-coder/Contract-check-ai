from collections.abc import Sequence

from sqlalchemy.orm import Session

from backend.app.db.models import (
    AnalysisJob,
    AnalysisResultItem,
    Clause,
)
from backend.app.services.analysis_provider import (
    DEFAULT_ANALYSIS_PROVIDER,
    AnalysisProvider,
    AnalysisProviderInput,
)
from backend.app.services.pii_masking import (
    detect_and_mask,
    detect_entities,
)


VALID_JOB_STATUSES = {
    "queued",
    "processing",
    "completed",
    "failed",
}


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
) -> None:
    job.status = "processing"
    db.flush()

    try:
        for clause in clauses:
            validate_reference_id(job.document_id, clause)

            provider_input = build_provider_input(clause)
            result_data = provider.analyze_clause(provider_input)
            result_data.validate()
            validate_result_reference_id(
                clause,
                result_data.reference_id,
            )

            job.result_items.append(
                AnalysisResultItem(
                    clause_record_id=clause.id,
                    reference_id=result_data.reference_id,
                    display_label=result_data.display_label,
                    summary=result_data.summary,
                    expert_review_recommended=(
                        result_data.expert_review_recommended
                    ),
                    extra_data={},
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
