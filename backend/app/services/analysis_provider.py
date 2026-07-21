from dataclasses import dataclass
from typing import Protocol

from backend.app.services.analysis_result_schema import AnalysisResultData


@dataclass(frozen=True)
class AnalysisProviderInput:
    reference_id: str
    masked_text: str


class AnalysisProvider(Protocol):
    def analyze_clause(
        self,
        provider_input: AnalysisProviderInput,
    ) -> AnalysisResultData:
        ...


def _infer_customer_value_fields(masked_text: str) -> tuple[str, str, str, list[dict[str, str]]]:
    text = masked_text.replace("\n", " ")
    category = "contract_clarity"
    severity = "low"
    action_priority = "informational"
    recommendations = [
        {
            "question_id": "q1",
            "question": "이 조항의 실제 계약 조건을 더 명확히 확인해야 합니다.",
            "purpose": "사용자에게 이해 가능한 핵심 조건을 확인하기 위해",
            "related_evidence_ids": ["evidence-id-placeholder"],
            "priority": "normal",
        }
    ]
    if any(word in text for word in ("갱신", "자동", "renew")):
        category = "automatic_renewal"
        severity = "medium"
        action_priority = "negotiate"
        recommendations.append(
            {
                "question_id": "q2",
                "question": "자동 갱신 조항이 포함되어 있는지 계약서에 명시되어 있는지 확인해 주세요.",
                "purpose": "계약 기간 갱신 조건을 명확하게 하기 위해",
                "related_evidence_ids": ["evidence-id-placeholder"],
                "priority": "high",
            }
        )
    elif any(word in text for word in ("해지", "중도", "위약")):
        category = "termination"
        severity = "high"
        action_priority = "before_signing"
        recommendations.append(
            {
                "question_id": "q2",
                "question": "해지·위약 조항은 손해배상 범위와 예외 조항을 함께 확인해 주세요.",
                "purpose": "해지 조건이 계약자에게 과도한 부담을 주는지 점검",
                "related_evidence_ids": ["evidence-id-placeholder"],
                "priority": "high",
            }
        )
    elif any(word in text for word in ("금액", "대금", "요금")):
        category = "payment"
        severity = "medium"
        action_priority = "clarify"
        recommendations.append(
            {
                "question_id": "q2",
                "question": "금액 조건은 총액/단가/부가세 포함 여부를 별도로 확인해 주세요.",
                "purpose": "계약 금액 및 과금 조건의 누락 가능성을 줄이기 위해",
                "related_evidence_ids": ["evidence-id-placeholder"],
                "priority": "normal",
            }
        )

    return category, severity, action_priority, recommendations


def _risk_type(category: str) -> str:
    if category == "automatic_renewal":
        return "termination"
    if category == "termination":
        return "obligation"
    if category == "payment":
        return "financial"
    return "governance"


def _build_suggestions(category: str, action_priority: str) -> list[dict[str, str]]:
    base = {
        "suggestion_id": f"{category}-suggestion",
        "objective": "대안 조항 초안 제시",
        "suggested_change": "필요 시 조항의 범위와 조건을 제한하는 문구로 조정 제안",
        "fallback_option": "부가 협의 없이 기본 조건으로 계약 진행",
        "related_evidence_ids": ["evidence-id-placeholder"],
        "priority": action_priority,
    }
    return [base]


class SyntheticAnalysisProvider:
    def analyze_clause(
        self,
        provider_input: AnalysisProviderInput,
    ) -> AnalysisResultData:
        category, severity, action_priority, recommendations = (
            _infer_customer_value_fields(provider_input.masked_text)
        )
        evidence_id = f"{provider_input.reference_id}-e001"
        for item in recommendations:
            if isinstance(item, dict) and item.get("related_evidence_ids"):
                item["related_evidence_ids"] = [evidence_id]
        suggestions = _build_suggestions(category, action_priority)
        for item in suggestions:
            if isinstance(item, dict) and item.get("related_evidence_ids"):
                item["related_evidence_ids"] = [evidence_id]

        return AnalysisResultData(
            reference_id=provider_input.reference_id,
            display_label="추가 확인",
            summary="합성 분석 결과입니다.",
            expert_review_recommended=False,
            finding_id=f"{provider_input.reference_id}-finding-001",
            category=category,
            risk_type=_risk_type(category),
            severity=severity,
            title="주요 조항 검토",
            risk_reason="현재 조항에서 잠재 위험과 운영상 유의점을 확인했습니다.",
            practical_impact="계약 체결 전 협의 대상과 조건 조정이 필요할 수 있습니다.",
            action_priority=action_priority,
            questions_to_ask=recommendations,
            negotiation_suggestions=suggestions,
            recommendation="상대 측과 조건 조정 제안을 함께 진행해 주세요.",
            expert_review_reason_codes=[],
            expert_review_summary="",
            confidence_score=0.72,
            evidence=[],
            extracted_facts=[],
            validation_status="verified",
            is_stale=False,
        )


DEFAULT_ANALYSIS_PROVIDER: AnalysisProvider = SyntheticAnalysisProvider()
