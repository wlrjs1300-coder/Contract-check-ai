from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from backend.app.db.models import AnalysisJob
from backend.app.core.encryption_config import get_encryption_keyring
from backend.app.services.scalar_encryption import encrypt_clause_body
from backend.tests.support import TEST_USER_ID
from backend.app.services.analysis_result_schema import AnalysisResultData
from backend.app.services.analysis_pipeline import (
    run_analysis_pipeline,
)
from backend.tests.test_analysis_pipeline import _create_document_and_clause
from backend.app.services.analysis_provider import AnalysisProviderInput


class CallTrackingProvider:
    def __init__(self) -> None:
        self.call_count = 0

    def analyze_clause(
        self,
        provider_input: AnalysisProviderInput,
    ) -> object:
        self.call_count += 1
        raise AssertionError("Provider must not be called in this test.")


def test_run_analysis_pipeline_blocks_provider_on_masking_token_collision(
    db_session: Session,
    monkeypatch,
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
            "masked_text": text,
            "entities": [],
            "token_collision_avoided": False,
        }

    monkeypatch.setattr(
        "backend.app.services.analysis_pipeline.detect_and_mask",
        fake_detect_and_mask,
    )

    provider = CallTrackingProvider()

    with pytest.raises(ValueError, match="provider_redaction_token_collision"):
        run_analysis_pipeline(
            db_session,
            job,
            [clause],
            provider=provider,
        )

    assert provider.call_count == 0


def test_run_analysis_pipeline_blocks_request_residual_from_path(
    db_session: Session,
    monkeypatch,
) -> None:
    document, clause = _create_document_and_clause(db_session)
    path_body = "첨부파일 경로: C:\\\\secret\\\\contract.txt"
    clause.body_encrypted = encrypt_clause_body(
        path_body,
        clause_id=clause.id,
        owner_id=TEST_USER_ID,
        keyring=get_encryption_keyring(),
    )
    db_session.commit()

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
            "masked_text": text,
            "entities": [],
            "token_collision_avoided": True,
        }

    monkeypatch.setattr(
        "backend.app.services.analysis_pipeline.detect_and_mask",
        fake_detect_and_mask,
    )

    provider = CallTrackingProvider()

    with pytest.raises(ValueError, match="provider_data_minimization_failed"):
        run_analysis_pipeline(
            db_session,
            job,
            [clause],
            provider=provider,
        )

    assert provider.call_count == 0


def test_run_analysis_pipeline_blocks_output_pii_in_facts(
    db_session: Session,
) -> None:
    document, clause = _create_document_and_clause(db_session)

    class FactOutputProvider:
        def analyze_clause(
            self,
            provider_input: AnalysisProviderInput,
        ):
            return AnalysisResultData(
                reference_id=provider_input.reference_id,
                display_label="주의",
                summary="정상입니다.",
                expert_review_recommended=False,
                extracted_facts=[
                    {
                        "label": "연락처",
                        "value": "연락처: 010-1234-5678",
                    }
                ],
            )

    job = AnalysisJob(
        id=str(uuid4()),
        document_id=document.id,
        status="queued",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    with pytest.raises(ValueError, match="provider_output_pii_detected"):
        run_analysis_pipeline(
            db_session,
            job,
            [clause],
            provider=FactOutputProvider(),
        )
