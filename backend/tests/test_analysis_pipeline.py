from uuid import uuid4

import pytest
from sqlalchemy.orm import Session
from backend.app.core.encryption_config import get_encryption_keyring

from backend.app.db.models import AnalysisJob, Clause, Document
from backend.app.services.analysis_provider import AnalysisProviderInput
from backend.app.services.analysis_pipeline import (
    run_analysis_pipeline,
    validate_reference_id,
)
from backend.app.services.scalar_encryption import (
    decrypt_analysis_result_summary,
    decrypt_clause_body,
    encrypt_clause_body,
)
from backend.app.services.analysis_result_schema import AnalysisResultData
from backend.app.services.provider_execution import (
    ProviderAuthenticationError,
    ProviderExecutionPolicy,
    ProviderTimeoutError,
)
from backend.tests.support import TEST_USER_ID


def _create_document_and_clause(
    db: Session,
    *,
    reference_id: str | None = None,
) -> tuple[Document, Clause]:
    document_id = str(uuid4())
    keyring = get_encryption_keyring()
    clause_id = str(uuid4())
    body = "Synthetic clause body."

    document = Document(
        id=document_id,
        owner_id=TEST_USER_ID,
        filename="pipeline.sample.txt",
        content_type="text/plain",
        size_bytes=10,
        character_count=10,
        status="processed",
        unclassified_sections=[],
        document_warnings=[],
    )

    clause = Clause(
        id=clause_id,
        clause_id="clause-001",
        reference_id=(
            reference_id
            if reference_id is not None
            else f"{document_id}:clause:1"
        ),
        source_hash="test-source-hash",
        ordinal=1,
        marker="1.",
        clause_type="normal",
        title=None,
        body_encrypted=encrypt_clause_body(
            body,
            clause_id=clause_id,
            owner_id=TEST_USER_ID,
            keyring=keyring,
        ),
        warnings=[],
    )

    document.clauses.append(clause)
    db.add(document)
    db.commit()
    db.refresh(document)
    db.refresh(clause)

    return document, clause


def test_validate_reference_id_accepts_matching_value(
    db_session: Session,
) -> None:
    document, clause = _create_document_and_clause(db_session)

    validate_reference_id(document.id, clause)


def test_validate_reference_id_rejects_mismatch(
    db_session: Session,
) -> None:
    document, clause = _create_document_and_clause(
        db_session,
        reference_id="invalid-reference-id",
    )

    with pytest.raises(
        ValueError,
        match="Clause reference_id does not match",
    ):
        validate_reference_id(document.id, clause)


def test_run_analysis_pipeline_completes_job(
    db_session: Session,
) -> None:
    document, clause = _create_document_and_clause(db_session)

    job = AnalysisJob(
        id=str(uuid4()),
        document_id=document.id,
        status="queued",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    run_analysis_pipeline(db_session, job, [clause])

    assert job.status == "completed"
    assert len(job.result_items) == 1
    assert job.result_items[0].reference_id == clause.reference_id
    assert (
        job.result_items[0].display_label
        == "\ucd94\uac00 \ud655\uc778"
    )


def test_run_analysis_pipeline_marks_job_failed(
    db_session: Session,
) -> None:
    document, clause = _create_document_and_clause(
        db_session,
        reference_id="invalid-reference-id",
    )

    job = AnalysisJob(
        id=str(uuid4()),
        document_id=document.id,
        status="queued",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    with pytest.raises(ValueError):
        run_analysis_pipeline(db_session, job, [clause])

    db_session.refresh(job)

    assert job.status == "failed"
    assert job.result_items == []



def test_run_analysis_pipeline_rolls_back_partial_results(
    db_session: Session,
) -> None:
    document, first_clause = _create_document_and_clause(db_session)
    keyring = get_encryption_keyring()
    second_clause_id = str(uuid4())
    second_body = "Second synthetic clause body."

    second_clause = Clause(
        id=second_clause_id,
        body_encrypted=encrypt_clause_body(
            second_body,
            clause_id=second_clause_id,
            owner_id=TEST_USER_ID,
            keyring=keyring,
        ),
        clause_id="clause-002",
        reference_id="invalid-reference-id",
        source_hash="second-source-hash",
        ordinal=2,
        marker="2.",
        clause_type="normal",
        title=None,
        warnings=[],
        document_id=document.id,
    )
    db_session.add(second_clause)
    db_session.commit()
    db_session.refresh(second_clause)

    job = AnalysisJob(
        id=str(uuid4()),
        document_id=document.id,
        status="queued",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    with pytest.raises(ValueError):
        run_analysis_pipeline(
            db_session,
            job,
            [first_clause, second_clause],
        )

    failed_job = db_session.get(AnalysisJob, job.id)

    assert failed_job is not None
    assert failed_job.status == "failed"
    assert failed_job.result_items == []


class CustomAnalysisProvider:
    def analyze_clause(
        self,
        clause: Clause,
    ) -> AnalysisResultData:
        return AnalysisResultData(
            reference_id=clause.reference_id,
            display_label="주의",
            summary="custom provider synthetic result",
            expert_review_recommended=True,
            expert_review_reason_codes=["critical_severity"],
            expert_review_summary="요약된 위험이 존재합니다.",
        )


class InvalidAnalysisProvider:
    def analyze_clause(
        self,
        clause: Clause,
    ) -> AnalysisResultData:
        return AnalysisResultData(
            reference_id=clause.reference_id,
            display_label="허용되지 않은 라벨",
            summary="잘못된 provider 결과입니다.",
            expert_review_recommended=False,
        )


class FailingAnalysisProvider:
    def analyze_clause(
        self,
        clause: Clause,
    ) -> AnalysisResultData:
        raise RuntimeError("Synthetic provider failure.")


def test_run_analysis_pipeline_accepts_custom_provider(
    db_session: Session,
) -> None:
    document, clause = _create_document_and_clause(db_session)

    job = AnalysisJob(
        id=str(uuid4()),
        document_id=document.id,
        status="queued",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    run_analysis_pipeline(
        db_session,
        job,
        [clause],
        provider=CustomAnalysisProvider(),
    )

    assert job.status == "completed"
    assert len(job.result_items) == 1
    assert job.result_items[0].display_label == "주의"
    assert (
        decrypt_analysis_result_summary(
            job.result_items[0].summary_encrypted,
            analysis_job_id=job.id,
            clause_record_id=clause.id,
            owner_id=TEST_USER_ID,
            keyring=get_encryption_keyring(),
        )
        == "custom provider synthetic result"
    )
    assert job.result_items[0].expert_review_recommended is True


def test_run_analysis_pipeline_rejects_invalid_provider_result(
    db_session: Session,
) -> None:
    document, clause = _create_document_and_clause(db_session)

    job = AnalysisJob(
        id=str(uuid4()),
        document_id=document.id,
        status="queued",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    with pytest.raises(
        ValueError,
        match="display_label must be one of the allowed labels",
    ):
        run_analysis_pipeline(
            db_session,
            job,
            [clause],
            provider=InvalidAnalysisProvider(),
        )

    failed_job = db_session.get(AnalysisJob, job.id)

    assert failed_job is not None
    assert failed_job.status == "failed"
    assert failed_job.result_items == []


def test_run_analysis_pipeline_handles_provider_failure(
    db_session: Session,
) -> None:
    document, clause = _create_document_and_clause(db_session)

    job = AnalysisJob(
        id=str(uuid4()),
        document_id=document.id,
        status="queued",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    with pytest.raises(
        RuntimeError,
        match="Synthetic provider failure",
    ):
        run_analysis_pipeline(
            db_session,
            job,
            [clause],
            provider=FailingAnalysisProvider(),
        )

    failed_job = db_session.get(AnalysisJob, job.id)

    assert failed_job is not None
    assert failed_job.status == "failed"
    assert failed_job.result_items == []


class MismatchedReferenceProvider:
    def analyze_clause(
        self,
        clause: Clause,
    ) -> AnalysisResultData:
        return AnalysisResultData(
            reference_id="different-document:clause:999",
            display_label="추가 확인",
            summary="연결 대상이 잘못된 provider 결과입니다.",
            expert_review_recommended=False,
        )


def test_run_analysis_pipeline_rejects_mismatched_result_reference_id(
    db_session: Session,
) -> None:
    document, clause = _create_document_and_clause(db_session)

    job = AnalysisJob(
        id=str(uuid4()),
        document_id=document.id,
        status="queued",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    with pytest.raises(
        ValueError,
        match=(
            "Provider result reference_id does not match "
            "the current clause"
        ),
    ):
        run_analysis_pipeline(
            db_session,
            job,
            [clause],
            provider=MismatchedReferenceProvider(),
        )

    failed_job = db_session.get(AnalysisJob, job.id)

    assert failed_job is not None
    assert failed_job.status == "failed"
    assert failed_job.result_items == []


class PartiallyMismatchedReferenceProvider:
    def analyze_clause(
        self,
        clause: AnalysisProviderInput,
    ) -> AnalysisResultData:
        reference_id = (
            clause.reference_id
            if clause.reference_id.endswith(":clause:1")
            else "different-document:clause:999"
        )

        return AnalysisResultData(
            reference_id=reference_id,
            display_label="추가 확인",
            summary="부분 처리 후 연결 검증 결과입니다.",
            expert_review_recommended=False,
        )


def test_run_analysis_pipeline_rolls_back_partial_results_on_mismatch(
    db_session: Session,
) -> None:
    document, first_clause = _create_document_and_clause(db_session)
    keyring = get_encryption_keyring()
    second_clause_id = str(uuid4())
    second_body = "Second synthetic clause body."

    second_clause = Clause(
        id=second_clause_id,
        clause_id="clause-002",
        reference_id=f"{document.id}:clause:2",
        source_hash="second-source-hash",
        ordinal=2,
        marker="2.",
        clause_type="normal",
        title=None,
        body_encrypted=encrypt_clause_body(
            second_body,
            clause_id=second_clause_id,
            owner_id=TEST_USER_ID,
            keyring=keyring,
        ),
        warnings=[],
        document_id=document.id,
    )
    db_session.add(second_clause)
    db_session.commit()
    db_session.refresh(second_clause)

    job = AnalysisJob(
        id=str(uuid4()),
        document_id=document.id,
        status="queued",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    with pytest.raises(
        ValueError,
        match=(
            "Provider result reference_id does not match "
            "the current clause"
        ),
    ):
        run_analysis_pipeline(
            db_session,
            job,
            [first_clause, second_clause],
            provider=PartiallyMismatchedReferenceProvider(),
        )

    failed_job = db_session.get(AnalysisJob, job.id)

    assert failed_job is not None
    assert failed_job.status == "failed"
    assert failed_job.result_items == []


class RecordingAnalysisProvider:
    def __init__(self) -> None:
        self.received_inputs: list[AnalysisProviderInput] = []

    def analyze_clause(
        self,
        provider_input: AnalysisProviderInput,
    ) -> AnalysisResultData:
        self.received_inputs.append(provider_input)

        return AnalysisResultData(
            reference_id=provider_input.reference_id,
            display_label="추가 확인",
            summary="마스킹 입력 검증 결과입니다.",
            expert_review_recommended=False,
        )


def test_run_analysis_pipeline_sends_only_masked_text_to_provider(
    db_session: Session,
) -> None:
    document, clause = _create_document_and_clause(db_session)

    original_body = "연락처: 010-1234-5678"
    clause.body_encrypted = encrypt_clause_body(
        original_body,
        clause_id=clause.id,
        owner_id=TEST_USER_ID,
        keyring=get_encryption_keyring(),
    )
    db_session.commit()
    db_session.refresh(clause)

    job = AnalysisJob(
        id=str(uuid4()),
        document_id=document.id,
        status="queued",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    provider = RecordingAnalysisProvider()

    run_analysis_pipeline(
        db_session,
        job,
        [clause],
        provider=provider,
    )

    assert len(provider.received_inputs) == 1

    received_input = provider.received_inputs[0]

    assert received_input.reference_id == clause.reference_id
    assert received_input.masked_text == "연락처: [PHONE_1]"
    assert "010-1234-5678" not in received_input.masked_text

    db_session.refresh(clause)

    assert (
        decrypt_clause_body(
            clause.body_encrypted,
            clause_id=clause.id,
            owner_id=TEST_USER_ID,
            keyring=get_encryption_keyring(),
        )
        == original_body
    )
    assert job.status == "completed"


class CallTrackingProvider:
    def __init__(self) -> None:
        self.call_count = 0

    def analyze_clause(
        self,
        provider_input: AnalysisProviderInput,
    ) -> AnalysisResultData:
        self.call_count += 1

        return AnalysisResultData(
            reference_id=provider_input.reference_id,
            display_label="추가 확인",
            summary="호출 추적 결과입니다.",
            expert_review_recommended=False,
        )


def test_run_analysis_pipeline_blocks_provider_on_residual_pii(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document, clause = _create_document_and_clause(db_session)

    job = AnalysisJob(
        id=str(uuid4()),
        document_id=document.id,
        status="queued",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    def fake_detect_and_mask(
        text: str,
        avoid_preexisting_token_collisions: bool = False,
    ) -> dict[str, object]:
        return {
            "masked_text": "연락처: 010-1234-5678",
        }

    monkeypatch.setattr(
        "backend.app.services.analysis_pipeline.detect_and_mask",
        fake_detect_and_mask,
    )

    provider = CallTrackingProvider()

    with pytest.raises(
        ValueError,
        match="provider_data_minimization_failed",
    ):
        run_analysis_pipeline(
            db_session,
            job,
            [clause],
            provider=provider,
        )

    failed_job = db_session.get(AnalysisJob, job.id)

    assert provider.call_count == 0
    assert failed_job is not None
    assert failed_job.status == "failed"
    assert failed_job.result_items == []


class UnsafeSummaryProvider:
    def __init__(self, summary: str) -> None:
        self.summary = summary

    def analyze_clause(
        self,
        provider_input: AnalysisProviderInput,
    ) -> AnalysisResultData:
        return AnalysisResultData(
            reference_id=provider_input.reference_id,
            display_label="추가 확인",
            summary=self.summary,
            expert_review_recommended=False,
        )


@pytest.mark.parametrize(
    ("summary", "expected_message"),
    [
        (
            "이 조항은 위법이라고 확정합니다.",
            "Provider result summary failed output safety validation",
        ),
        (
            "인용과 판단이 혼합되어 추가 확인이 필요합니다.",
            "Provider result summary failed output safety validation",
        ),
        (
            "담당자 연락처는 010-1234-5678입니다.",
            "provider_output_pii_detected",
        ),
    ],
)
def test_run_analysis_pipeline_blocks_unsafe_provider_summary(
    db_session: Session,
    summary: str,
    expected_message: str,
) -> None:
    document, clause = _create_document_and_clause(db_session)

    job = AnalysisJob(
        id=str(uuid4()),
        document_id=document.id,
        status="queued",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    with pytest.raises(
        ValueError,
        match=expected_message,
    ):
        run_analysis_pipeline(
            db_session,
            job,
            [clause],
            provider=UnsafeSummaryProvider(summary),
        )

    failed_job = db_session.get(AnalysisJob, job.id)

    assert failed_job is not None
    assert failed_job.status == "failed"
    assert failed_job.result_items == []


class PartiallyUnsafeSummaryProvider:
    def analyze_clause(
        self,
        provider_input: AnalysisProviderInput,
    ) -> AnalysisResultData:
        summary = (
            "추가 확인이 필요한 합성 분석 결과입니다."
            if provider_input.reference_id.endswith(":clause:1")
            else "이 조항은 무효라고 확정합니다."
        )

        return AnalysisResultData(
            reference_id=provider_input.reference_id,
            display_label="추가 확인",
            summary=summary,
            expert_review_recommended=False,
        )


def test_run_analysis_pipeline_rolls_back_partial_results_on_unsafe_output(
    db_session: Session,
) -> None:
    document, first_clause = _create_document_and_clause(db_session)
    keyring = get_encryption_keyring()
    second_clause_id = str(uuid4())
    second_body = "Second synthetic clause body."

    second_clause = Clause(
        id=second_clause_id,
        clause_id="clause-002",
        reference_id=f"{document.id}:clause:2",
        source_hash="second-source-hash",
        ordinal=2,
        marker="2.",
        clause_type="normal",
        title=None,
        body_encrypted=encrypt_clause_body(
            second_body,
            clause_id=second_clause_id,
            owner_id=TEST_USER_ID,
            keyring=keyring,
        ),
        warnings=[],
        document_id=document.id,
    )
    db_session.add(second_clause)
    db_session.commit()
    db_session.refresh(second_clause)

    job = AnalysisJob(
        id=str(uuid4()),
        document_id=document.id,
        status="queued",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    with pytest.raises(
        ValueError,
        match="Provider result summary failed output safety validation",
    ):
        run_analysis_pipeline(
            db_session,
            job,
            [first_clause, second_clause],
            provider=PartiallyUnsafeSummaryProvider(),
        )

    failed_job = db_session.get(AnalysisJob, job.id)

    assert failed_job is not None
    assert failed_job.status == "failed"
    assert failed_job.result_items == []


class RetryThenSuccessProvider:
    def __init__(self) -> None:
        self.call_count = 0

    def analyze_clause(
        self,
        provider_input: AnalysisProviderInput,
    ) -> AnalysisResultData:
        self.call_count += 1

        if self.call_count == 1:
            raise ProviderTimeoutError()

        return AnalysisResultData(
            reference_id=provider_input.reference_id,
            display_label="추가 확인",
            summary="재시도 후 생성된 합성 분석 결과입니다.",
            expert_review_recommended=False,
        )


def test_run_analysis_pipeline_retries_provider_then_succeeds(
    db_session: Session,
) -> None:
    document, clause = _create_document_and_clause(db_session)

    job = AnalysisJob(
        id=str(uuid4()),
        document_id=document.id,
        status="queued",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    provider = RetryThenSuccessProvider()

    run_analysis_pipeline(
        db_session,
        job,
        [clause],
        provider=provider,
        provider_policy=ProviderExecutionPolicy(
            max_attempts=2,
        ),
    )

    assert provider.call_count == 2
    assert job.status == "completed"
    assert len(job.result_items) == 1


class AlwaysTimeoutProvider:
    def __init__(self) -> None:
        self.call_count = 0

    def analyze_clause(
        self,
        provider_input: AnalysisProviderInput,
    ) -> AnalysisResultData:
        self.call_count += 1
        raise ProviderTimeoutError()


def test_run_analysis_pipeline_marks_job_failed_after_retry_exhaustion(
    db_session: Session,
) -> None:
    document, clause = _create_document_and_clause(db_session)

    job = AnalysisJob(
        id=str(uuid4()),
        document_id=document.id,
        status="queued",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    provider = AlwaysTimeoutProvider()

    with pytest.raises(ProviderTimeoutError) as exc_info:
        run_analysis_pipeline(
            db_session,
            job,
            [clause],
            provider=provider,
            provider_policy=ProviderExecutionPolicy(
                max_attempts=3,
            ),
        )

    failed_job = db_session.get(AnalysisJob, job.id)

    assert provider.call_count == 3
    assert exc_info.value.reason_code == "PROVIDER_TIMEOUT"
    assert failed_job is not None
    assert failed_job.status == "failed"
    assert failed_job.result_items == []


class ImmediateAuthenticationFailureProvider:
    def __init__(self) -> None:
        self.call_count = 0

    def analyze_clause(
        self,
        provider_input: AnalysisProviderInput,
    ) -> AnalysisResultData:
        self.call_count += 1
        raise ProviderAuthenticationError()


def test_run_analysis_pipeline_does_not_retry_authentication_failure(
    db_session: Session,
) -> None:
    document, clause = _create_document_and_clause(db_session)

    job = AnalysisJob(
        id=str(uuid4()),
        document_id=document.id,
        status="queued",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    provider = ImmediateAuthenticationFailureProvider()

    with pytest.raises(ProviderAuthenticationError):
        run_analysis_pipeline(
            db_session,
            job,
            [clause],
            provider=provider,
            provider_policy=ProviderExecutionPolicy(
                max_attempts=3,
            ),
        )

    failed_job = db_session.get(AnalysisJob, job.id)

    assert provider.call_count == 1
    assert failed_job is not None
    assert failed_job.status == "failed"
    assert failed_job.result_items == []


class PartiallyFailingRetryProvider:
    def __init__(self) -> None:
        self.call_counts: dict[str, int] = {}

    def analyze_clause(
        self,
        provider_input: AnalysisProviderInput,
    ) -> AnalysisResultData:
        reference_id = provider_input.reference_id
        self.call_counts[reference_id] = (
            self.call_counts.get(reference_id, 0) + 1
        )

        if reference_id.endswith(":clause:2"):
            raise ProviderTimeoutError()

        return AnalysisResultData(
            reference_id=reference_id,
            display_label="추가 확인",
            summary="첫 번째 조항의 합성 분석 결과입니다.",
            expert_review_recommended=False,
        )


def test_run_analysis_pipeline_rolls_back_partial_results_after_retry_failure(
    db_session: Session,
) -> None:
    document, first_clause = _create_document_and_clause(db_session)
    keyring = get_encryption_keyring()
    second_clause_id = str(uuid4())
    second_body = "Second synthetic clause body."

    second_clause = Clause(
        id=second_clause_id,
        clause_id="clause-002",
        reference_id=f"{document.id}:clause:2",
        source_hash="second-source-hash",
        ordinal=2,
        marker="2.",
        clause_type="normal",
        title=None,
        body_encrypted=encrypt_clause_body(
            second_body,
            clause_id=second_clause_id,
            owner_id=TEST_USER_ID,
            keyring=keyring,
        ),
        warnings=[],
        document_id=document.id,
    )
    db_session.add(second_clause)
    db_session.commit()
    db_session.refresh(second_clause)

    job = AnalysisJob(
        id=str(uuid4()),
        document_id=document.id,
        status="queued",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    provider = PartiallyFailingRetryProvider()

    with pytest.raises(ProviderTimeoutError):
        run_analysis_pipeline(
            db_session,
            job,
            [first_clause, second_clause],
            provider=provider,
            provider_policy=ProviderExecutionPolicy(
                max_attempts=2,
            ),
        )

    failed_job = db_session.get(AnalysisJob, job.id)

    assert provider.call_counts[first_clause.reference_id] == 1
    assert provider.call_counts[second_clause.reference_id] == 2
    assert failed_job is not None
    assert failed_job.status == "failed"
    assert failed_job.result_items == []
