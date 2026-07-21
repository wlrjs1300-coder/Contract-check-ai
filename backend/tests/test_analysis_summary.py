from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.api import analysis_jobs as analysis_jobs_api


client = TestClient(app)


def test_analysis_summary_rolls_up_by_severity_and_stale() -> None:
    upload_response = client.post(
        "/documents/upload",
        files={
            "file": (
                "summary.sample.txt",
                "1. 자동 갱신 조항이 포함된 조항입니다.\n2. 중도 해지 조건이 포함된 조항입니다.",
                "text/plain",
            )
        },
    )
    assert upload_response.status_code == 200
    document_id = upload_response.json()["document_id"]

    original_run = analysis_jobs_api.run_analysis_pipeline

    def fake_run_analysis_pipeline(*, db, job, clauses, provider=None, provider_policy=None) -> None:
        from backend.app.services.analysis_result_schema import AnalysisResultData
        from backend.app.services.analysis_provider import AnalysisProviderInput

        class SeverityProvider:
            def analyze_clause(
                self,
                provider_input: AnalysisProviderInput,
            ) -> AnalysisResultData:
                severity = "high" if provider_input.reference_id.endswith(":clause:1") else "medium"

                return AnalysisResultData(
                    reference_id=provider_input.reference_id,
                    display_label="주의",
                    summary="요약 테스트 위험도 확인용 요약입니다.",
                    expert_review_recommended=False,
                    category="summary-test",
                    risk_type="governance",
                    severity=severity,
                    title="요약 항목",
                    risk_reason="요약 테스트 리스크",
                    practical_impact="요약 테스트 영향",
                    action_priority="clarify",
                    recommendation="요약 테스트 추천",
                )

        return original_run(db=db, job=job, clauses=clauses, provider=SeverityProvider())

    try:
        setattr(analysis_jobs_api, "run_analysis_pipeline", fake_run_analysis_pipeline)
        create_response = client.post(f"/documents/{document_id}/analysis-jobs")
        assert create_response.status_code == 200
        assert create_response.json()["status"] == "completed"

        result = client.get(f"/documents/{document_id}/analysis-results").json()
    finally:
        setattr(analysis_jobs_api, "run_analysis_pipeline", original_run)

    summary = result["analysis_summary"]
    assert summary["overall_risk_level"] in {"critical", "high", "medium", "low", "info"}
    assert summary["total_findings"] >= 1
    assert summary["high_count"] == 1
    assert summary["medium_count"] in {0, 1}
    assert summary["ambiguity_count"] == 0

    top_priorities = summary["top_priorities"]
    assert len(top_priorities) >= 1
    assert set(top_priorities[0]).issuperset(
        {"finding_id", "severity", "title", "action_priority"},
    )
