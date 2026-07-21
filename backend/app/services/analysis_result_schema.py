from dataclasses import dataclass, field
from typing import Any


ALLOWED_DISPLAY_LABELS = {
    "\uc548\uc804",
    "\uc8fc\uc758",
    "\uc704\ud5d8",
    "\ucd94\uac00 \ud655\uc778",
}

ALLOWED_SEVERITIES = {
    "critical",
    "high",
    "medium",
    "low",
    "info",
}

ALLOWED_ACTION_PRIORITIES = {
    "before_signing",
    "clarify",
    "negotiate",
    "monitor",
    "expert_review",
    "informational",
}


ALLOWED_FACT_TYPES = {
    "contract_start_date",
    "contract_end_date",
    "payment_date",
    "notice_deadline",
    "termination_notice_period",
    "payment_amount",
    "deposit",
    "penalty",
    "late_fee",
    "interest_rate",
    "contract_duration",
    "auto_renewal",
    "obligation",
    "inspection_period",
    "warranty_period",
    "liability_limit",
    "governing_law",
    "dispute_resolution",
    "party_name_placeholder",
}

ALLOWED_EXPERT_REVIEW_CODES = {
    "critical_severity",
    "unlimited_liability_suspected",
    "high_penalty",
    "rights_waiver_suspected",
    "intellectual_property_transfer",
    "privacy_responsibility",
    "non_compete_restriction",
    "complex_governing_law",
    "low_ocr_confidence_on_key_clause",
    "multiple_high_findings",
    "key_fact_conflict",
}


ALLOWED_RISK_TYPES = {
    "financial",
    "term",
    "obligation",
    "termination",
    "clarification",
    "governance",
    "operational",
}


DEFAULT_CONFIDENCE_SCORE = 0.8
MAX_TEXT_LENGTH = 500
MAX_LIST_SIZE = 3
MAX_FACTS_SIZE = 10


@dataclass(frozen=True)
class AnalysisResultData:
    reference_id: str
    display_label: str
    summary: str
    expert_review_recommended: bool
    finding_id: str = ""
    category: str = ""
    risk_type: str = ""
    severity: str = "info"
    title: str = ""
    risk_reason: str = ""
    practical_impact: str = ""
    action_priority: str = "informational"
    questions_to_ask: list[dict[str, Any]] = field(
        default_factory=list
    )
    negotiation_suggestions: list[dict[str, Any]] = field(
        default_factory=list
    )
    recommendation: str = ""
    expert_review_reason_codes: list[str] = field(default_factory=list)
    expert_review_summary: str = ""
    confidence_score: float = DEFAULT_CONFIDENCE_SCORE
    evidence: list[dict[str, Any]] = field(default_factory=list)
    extracted_facts: list[dict[str, Any]] = field(
        default_factory=list
    )
    validation_status: str = "verified"
    is_stale: bool = False

    def validate(self) -> None:
        if not self.reference_id.strip():
            raise ValueError("reference_id must not be empty.")

        if self.display_label not in ALLOWED_DISPLAY_LABELS:
            raise ValueError(
                "display_label must be one of the allowed labels."
            )

        if not self.summary.strip():
            raise ValueError("summary must not be empty.")

        if not isinstance(self.expert_review_recommended, bool):
            raise ValueError(
                "expert_review_recommended must be a boolean."
            )

        if self.severity and self.severity not in ALLOWED_SEVERITIES:
            raise ValueError(
                "severity must be one of critical, high, medium, low, info."
            )

        if (
            self.action_priority
            and self.action_priority not in ALLOWED_ACTION_PRIORITIES
        ):
            raise ValueError(
                "action_priority must be one of "
                "before_signing, clarify, negotiate, monitor, "
                "expert_review, informational."
            )

        if self.risk_type and self.risk_type not in ALLOWED_RISK_TYPES:
            raise ValueError("risk_type is not supported.")

        if self.confidence_score < 0 or self.confidence_score > 1:
            raise ValueError("confidence_score must be between 0 and 1.")

        if self.title and len(self.title) > MAX_TEXT_LENGTH:
            raise ValueError("title exceeds max length.")

        if self.summary and len(self.summary) > MAX_TEXT_LENGTH * 2:
            raise ValueError("summary exceeds max length.")

        if self.risk_reason and len(self.risk_reason) > MAX_TEXT_LENGTH:
            raise ValueError("risk_reason exceeds max length.")

        if self.practical_impact and len(self.practical_impact) > MAX_TEXT_LENGTH:
            raise ValueError("practical_impact exceeds max length.")

        if self.recommendation and len(self.recommendation) > MAX_TEXT_LENGTH:
            raise ValueError("recommendation exceeds max length.")

        if any(
            not isinstance(code, str) or not code.strip()
            for code in self.expert_review_reason_codes
        ):
            raise ValueError("expert_review_reason_codes contains invalid value.")

        if self.expert_review_reason_codes:
            for code in self.expert_review_reason_codes:
                if code not in ALLOWED_EXPERT_REVIEW_CODES:
                    raise ValueError("unsupported expert_review_reason_code.")
            if not self.expert_review_summary.strip():
                raise ValueError(
                    "expert_review_summary is required when reason codes exist."
                )
        elif self.expert_review_recommended:
            raise ValueError(
                "expert_review_reason_codes required when expert_review_recommended is true."
            )

        if self.expert_review_summary and len(self.expert_review_summary) > MAX_TEXT_LENGTH:
            raise ValueError("expert_review_summary exceeds max length.")

        if self.validation_status not in {
            "verified",
            "review_required",
            "stale",
        }:
            raise ValueError("validation_status is not supported.")

        if len(self.questions_to_ask) > MAX_LIST_SIZE:
            raise ValueError("questions_to_ask exceeds max list size.")
        if len(self.negotiation_suggestions) > MAX_LIST_SIZE:
            raise ValueError(
                "negotiation_suggestions exceeds max list size."
            )
        if len(self.extracted_facts) > MAX_FACTS_SIZE:
            raise ValueError("extracted_facts exceeds max list size.")
        for fact in self.extracted_facts:
            if not isinstance(fact, dict):
                continue
            fact_type = str(fact.get("fact_type", ""))
            if fact_type and fact_type not in ALLOWED_FACT_TYPES:
                raise ValueError("unsupported fact_type.")
