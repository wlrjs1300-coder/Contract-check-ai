from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.analysis_result_schema import ALLOWED_SEVERITIES

client = TestClient(app)


def test_synthetic_customer_value_fields_in_analysis_results() -> None:
    upload_response = client.post(
        "/documents/upload",
        files={
            "file": (
                "customer-value.sample.txt",
                "1. 자동 갱신 및 해지 조건이 포함된 계약 예시\n2. 계약일은 서면 통지로만 종료할 수 있습니다.",
                "text/plain",
            )
        },
    )
    assert upload_response.status_code == 200
    document_id = upload_response.json()["document_id"]

    create_response = client.post(f"/documents/{document_id}/analysis-jobs")
    assert create_response.status_code == 200

    result_response = client.get(f"/documents/{document_id}/analysis-results")
    result = result_response.json()

    assert result["document_id"] == document_id
    assert result["analysis_summary"]["total_findings"] >= 1
    assert "findings" in result
    assert len(result["items"]) == len(result["findings"])

    first = result["findings"][0]
    assert "finding_id" in first
    assert first["category"] in {"automatic_renewal", "termination", "contract_clarity", "payment"}
    assert first["risk_type"] in {"termination", "obligation", "governance", "financial"}
    assert first["severity"] in {"critical", "high", "medium", "low", "info"}
    assert isinstance(first["questions_to_ask"], list)
    assert "question_id" in first["questions_to_ask"][0]
    assert "question" in first["questions_to_ask"][0]
    assert "related_evidence_ids" in first["questions_to_ask"][0]
    assert isinstance(first["questions_to_ask"][0]["related_evidence_ids"], list)
    assert first["risk_reason"]
    assert first["practical_impact"]
    assert first["recommendation"]



def test_customer_value_summary_present_in_results_response() -> None:
    upload_response = client.post(
        "/documents/upload",
        files={
        "file": (
                "customer-value-2.sample.txt",
                "1. 해지 통지 조건이 명확히 표시된 계약 예시\n2. 자동 갱신을 원치 않을 경우 사전 고지 가능합니다.",
                "text/plain",
            )
        },
    )
    assert upload_response.status_code == 200
    document_id = upload_response.json()["document_id"]

    response = client.post(f"/documents/{document_id}/analysis-jobs")
    assert response.status_code == 200
    assert response.json()["status"] == "completed"

    result = client.get(f"/documents/{document_id}/analysis-results").json()
    summary = result["analysis_summary"]

    assert summary["total_findings"] == len(result["items"]) == len(result["findings"])
    top_priorities = summary["top_priorities"]
    assert isinstance(top_priorities, list)
    assert len(top_priorities) <= 3
    if top_priorities:
        entry = top_priorities[0]
        assert set(entry) == {"finding_id", "severity", "title", "action_priority"}
        assert entry["severity"] in ALLOWED_SEVERITIES
        assert entry["action_priority"] in {
            "before_signing",
            "negotiate",
            "clarify",
            "monitor",
            "expert_review",
            "informational",
        }
        assert (
            summary["critical_count"]
            + summary["high_count"]
            + summary["medium_count"]
            + summary["low_count"]
            + summary["info_count"]
            == summary["total_findings"]
        )

    assert {
        "overall_risk_level",
        "critical_count",
        "high_count",
        "medium_count",
        "low_count",
        "info_count",
        "top_priorities",
        "expert_review_recommended",
    }.issubset(summary)


def test_findings_alias_keeps_items_compatibility() -> None:
    upload_response = client.post(
        "/documents/upload",
        files={
                "file": (
                "compat.sample.txt",
                "1. 동일한 출력 구조를 유지한 테스트 텍스트\n2. 위험도가 높은 조항을 포함합니다.",
                "text/plain",
            )
        },
    )
    assert upload_response.status_code == 200
    document_id = upload_response.json()["document_id"]

    client.post(f"/documents/{document_id}/analysis-jobs")

    result = client.get(f"/documents/{document_id}/analysis-results").json()
    assert result["items"] == result["findings"]
