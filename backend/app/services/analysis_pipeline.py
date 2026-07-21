import re
from datetime import datetime


from collections.abc import Sequence
from sqlalchemy.exc import OperationalError

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
from backend.app.services.analysis_result_schema import AnalysisResultData
from backend.app.services.evidence_linking import (
    EvidenceValidationError,
    bind_evidence_to_finding,
    calculate_snapshot_hash,
)
from backend.app.services.pii_masking import (
    detect_and_mask,
    detect_entities,
)
from backend.app.services.output_safety import (
    ALLOW,
    check_summary_output,
)
from backend.app.services.provider_execution import (
    DEFAULT_PROVIDER_EXECUTION_POLICY,
    ProviderExecutionPolicy,
    execute_provider,
)


def _normalize_fact_list(values: list[dict[str, object]]) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        raw_value = str(value.get("value", ""))
        raw_normalized = str(value.get("normalized_value", ""))
        raw_date = str(value.get("date_value", ""))
        raw_amount = str(value.get("amount_value", ""))
        raw_currency = str(value.get("currency", ""))
        normalized_value = {
            "fact_id": str(value.get("fact_id", "")),
            "fact_type": str(value.get("fact_type", "")),
            "label": str(value.get("label", "")),
            "value": raw_value,
            "normalized_value": raw_normalized,
            "unit": str(value.get("unit", "")),
            "date_value": raw_date,
            "amount_value": raw_amount,
            "currency": raw_currency,
            "duration_value": str(value.get("duration_value", "")),
            "obligation_party": str(value.get("obligation_party", "")),
            "status": str(value.get("status", "")),
            "evidence": value.get("evidence") if isinstance(value.get("evidence"), list) else [],
            "confidence_score": float(
                value.get("confidence_score", 0.0)
                if isinstance(value.get("confidence_score"), (int, float))
                else 0.0
            ),
        }
        normalized_value = _normalize_fact_fields(normalized_value)
        normalized.append(normalized_value)
    return normalized


def _normalize_fact_fields(fact: dict[str, object]) -> dict[str, object]:
    fact_type = str(fact.get("fact_type", ""))
    if fact_type in {"contract_start_date", "contract_end_date", "payment_date", "notice_deadline"}:
        date_value = _normalize_date_value(str(fact.get("date_value", "")))
        if not date_value:
            date_value = _normalize_date_value(str(fact.get("normalized_value", "")))
        if date_value:
            fact["date_value"] = date_value
            fact["normalized_value"] = date_value
            fact["status"] = fact.get("status", "") or "verified"

    amount_value = _normalize_amount_value(
        str(fact.get("amount_value", "")),
        str(fact.get("value", "")),
        str(fact.get("normalized_value", "")),
        str(fact.get("unit", "")),
    )
    if amount_value:
        fact["amount_value"] = amount_value
        fact["currency"] = fact.get("currency", "KRW") or "KRW"

    if fact_type == "obligation":
        obligation_party = str(fact.get("obligation_party", "")).strip()
        if not obligation_party:
            fact["obligation_party"] = "unspecified"
            fact["status"] = "ambiguous"

    return fact


def _normalize_date_value(value: str) -> str:
    raw = value.strip()
    if not raw:
        return ""

    match = re.match(r"^\s*(\d{4})[.\s년]+\s*(\d{1,2})[.\s월]+\s*(\d{1,2})(?:일)?\s*$", raw)
    if match:
        year, month, day = match.groups()
        try:
            return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
        except ValueError:
            return ""

    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
        try:
            datetime.strptime(raw, "%Y-%m-%d")
            return raw
        except ValueError:
            return ""

    return ""


def _normalize_amount_value(
    amount_value: str,
    value: str,
    normalized_value: str,
    unit: str,
) -> str:
    source = (amount_value or normalized_value or value).strip().replace(" ", "")
    if not source:
        return ""

    if "%" in source:
        return ""

    comma_match = re.match(r"^(\d{1,3}(?:,\d{3})+)(?:원)?$", source)
    if comma_match:
        return comma_match.group(1).replace(",", "")

    if source.endswith("만원"):
        number = source[:-2]
        if number.isdigit():
            return str(int(number) * 10000)
        return ""

    if source.endswith("원") and source[:-1].isdigit():
        return source[:-1]

    if unit == "KRW" and source.isdigit():
        return source

    if amount_value and amount_value.strip().isdigit():
        return amount_value.strip()

    if source.isdigit():
        return source

    return ""


def _extract_evidence_ids(evidence: list[dict[str, object]]) -> set[str]:
    return {
        str(item.get("evidence_id"))
        for item in evidence
        if isinstance(item.get("evidence_id"), str)
        and str(item.get("evidence_id")).strip()
    }


def _ensure_reference_ids(
    entries: list[dict[str, object]],
    *,
    code: str,
    evidence_ids: set[str],
) -> None:
    for entry in entries:
        related_ids = [
            str(value)
            for value in (entry.get("related_evidence_ids", []) or [])
            if isinstance(value, str) and value.strip()
        ]
        if not related_ids:
            raise ValueError(
                f"{code}: related_evidence_ids must be explicitly set."
            )
        missing = [value for value in related_ids if value not in evidence_ids]
        if missing:
            raise ValueError(
                f"{code}: evidence id not in finding evidence: {', '.join(missing)}."
            )


def _ensure_fact_evidence(
    facts: list[dict[str, object]],
    *,
    evidence_ids: set[str],
) -> None:
    for fact in facts:
        if not isinstance(fact, dict):
            raise ValueError("fact_evidence_missing: invalid extracted fact item.")
        evidence_refs = fact.get("evidence")
        if not isinstance(evidence_refs, list) or not evidence_refs:
            raise ValueError("fact_evidence_missing: extracted fact evidence is required.")
        normalized_refs = [
            str(item.get("evidence_id"))
            for item in evidence_refs
            if isinstance(item, dict)
            and isinstance(item.get("evidence_id"), str)
            and str(item.get("evidence_id")).strip()
        ]
        if not normalized_refs:
            raise ValueError(
                "fact_evidence_missing: extracted fact evidence id is required."
            )
        missing = [value for value in normalized_refs if value not in evidence_ids]
        if missing:
            raise ValueError("fact_evidence_missing: extracted fact evidence id is invalid.")


def _normalize_question_list(
    values: list[dict[str, object]],
    evidence: list[dict[str, object]],
) -> list[dict[str, object]]:
    evidence_ids = _extract_evidence_ids(evidence)
    normalized: list[dict[str, object]] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        raw_related_evidence_ids = value.get("related_evidence_ids")
        if not isinstance(raw_related_evidence_ids, list):
            raw_related_evidence_ids = []
        related_ids = [
            str(item_id)
            for item_id in raw_related_evidence_ids
            if isinstance(item_id, str)
            and item_id.strip()
        ]

        normalized.append(
            {
                "question_id": str(value.get("question_id", "")),
                "question": str(value.get("question", "")),
                "purpose": str(value.get("purpose", "")),
                "related_evidence_ids": related_ids,
                "priority": str(value.get("priority", "normal")),
                "id": str(value.get("question_id", "")),
            }
        )
    if normalized:
        _ensure_reference_ids(
            normalized,
            code="question_evidence_missing",
            evidence_ids=evidence_ids,
        )
    return normalized


def _normalize_suggestion_list(
    values: list[dict[str, object]],
    evidence: list[dict[str, object]],
) -> list[dict[str, object]]:
    evidence_ids = _extract_evidence_ids(evidence)

    normalized: list[dict[str, object]] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        raw_related_evidence_ids = value.get("related_evidence_ids")
        if not isinstance(raw_related_evidence_ids, list):
            raw_related_evidence_ids = []
        related_ids = [
            str(item_id)
            for item_id in raw_related_evidence_ids
            if isinstance(item_id, str)
            and item_id.strip()
        ]

        normalized.append(
            {
                "suggestion_id": str(value.get("suggestion_id", "")),
                "objective": str(value.get("objective", "")),
                "suggested_change": str(
                    value.get("suggested_change", "")
                ),
                "fallback_option": str(value.get("fallback_option", "")),
                "related_evidence_ids": related_ids,
                "priority": str(value.get("priority", "normal")),
                "id": str(value.get("suggestion_id", "")),
            }
        )
    if normalized:
        _ensure_reference_ids(
            normalized,
            code="suggestion_evidence_missing",
            evidence_ids=evidence_ids,
        )
    return normalized


def _to_customer_value_payload(
    result_data: AnalysisResultData,
    evidence: list[dict[str, object]],
) -> dict[str, object]:
    evidence_ids = _extract_evidence_ids(evidence)
    normalized_facts = _normalize_fact_list(result_data.extracted_facts)
    _ensure_fact_evidence(normalized_facts, evidence_ids=evidence_ids)

    return {
        "category": result_data.category,
        "risk_type": result_data.risk_type,
        "severity": result_data.severity,
        "title": result_data.title,
        "risk_reason": result_data.risk_reason,
        "practical_impact": result_data.practical_impact,
        "action_priority": result_data.action_priority,
        "questions_to_ask": _normalize_question_list(
            result_data.questions_to_ask
            if isinstance(result_data.questions_to_ask, list)
            else [],
            evidence,
        ),
        "negotiation_suggestions": _normalize_suggestion_list(
            result_data.negotiation_suggestions
            if isinstance(result_data.negotiation_suggestions, list)
            else [],
            evidence,
        ),
        "recommendation": (
            result_data.recommendation
            if result_data.recommendation.strip()
            else result_data.summary
        ),
        "confidence_score": float(result_data.confidence_score),
        "evidence": evidence,
        "extracted_facts": normalized_facts,
        "validation_status": str(result_data.validation_status),
        "expert_review_reason_codes": result_data.expert_review_reason_codes,
        "expert_review_summary": result_data.expert_review_summary,
        "is_stale": bool(result_data.is_stale),
    }


def _ensure_derived_fields_have_evidence(
    result_data: AnalysisResultData,
    evidence: list[dict[str, object]],
) -> None:
    has_derived_content = bool(
        result_data.risk_reason
        or result_data.practical_impact
        or result_data.questions_to_ask
        or result_data.negotiation_suggestions
        or result_data.extracted_facts
    )
    if has_derived_content and not evidence:
        raise ValueError(
            "analysis result requires evidence for customer value fields."
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
    try:
        extraction = db.get(Extraction, document_id)
    except OperationalError:
        db.rollback()
        return [], None, None
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

            _ensure_derived_fields_have_evidence(result_data, evidence)

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
                        "analysis_value": _to_customer_value_payload(
                            result_data=result_data,
                            evidence=evidence,
                        ),
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
