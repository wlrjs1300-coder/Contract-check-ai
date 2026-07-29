from __future__ import annotations

from backend.app.core.crypto import (
    build_canonical_aad,
    build_canonical_record_id,
    decrypt,
    encrypt,
)
from backend.app.core.encryption_config import EncryptionKeyring
from backend.app.services.scalar_encryption import (
    ScalarDecryptionError,
    ScalarEncryptionError,
    _ensure_utf8_plaintext,
    _ensure_utf8_text,
    _require_identifier,
)


ANALYSIS_RESULT_SCHEMA_VERSION = "analysis-result-v1"

_VALUE_TEXT_FIELD_NAMES = frozenset(
    {"title", "risk_reason", "practical_impact", "recommendation", "expert_review_summary"}
)

_ANALYSIS_VALUE_PLAINTEXT_KEYS = frozenset(
    {
        "category",
        "risk_type",
        "severity",
        "title",
        "risk_reason",
        "practical_impact",
        "action_priority",
        "questions_to_ask",
        "negotiation_suggestions",
        "recommendation",
        "confidence_score",
        "evidence",
        "extracted_facts",
        "validation_status",
        "expert_review_reason_codes",
        "expert_review_summary",
        "is_stale",
    }
)
_ANALYSIS_VALUE_ENCRYPTED_KEYS = frozenset(
    {
        "category",
        "risk_type",
        "severity",
        "title_encrypted",
        "risk_reason_encrypted",
        "practical_impact_encrypted",
        "action_priority",
        "questions_to_ask",
        "negotiation_suggestions",
        "recommendation_encrypted",
        "confidence_score",
        "evidence",
        "extracted_facts",
        "validation_status",
        "expert_review_reason_codes",
        "expert_review_summary_encrypted",
        "is_stale",
    }
)

_QUESTION_PLAINTEXT_KEYS = frozenset(
    {"question_id", "question", "purpose", "related_evidence_ids", "priority", "id"}
)
_QUESTION_ENCRYPTED_KEYS = frozenset(
    {"question_id", "question_encrypted", "purpose_encrypted", "related_evidence_ids", "priority", "id"}
)

_SUGGESTION_PLAINTEXT_KEYS = frozenset(
    {
        "suggestion_id",
        "objective",
        "suggested_change",
        "fallback_option",
        "related_evidence_ids",
        "priority",
        "id",
    }
)
_SUGGESTION_ENCRYPTED_KEYS = frozenset(
    {
        "suggestion_id",
        "objective_encrypted",
        "suggested_change_encrypted",
        "fallback_option_encrypted",
        "related_evidence_ids",
        "priority",
        "id",
    }
)

_FACT_PLAINTEXT_KEYS = frozenset(
    {
        "fact_id",
        "fact_type",
        "label",
        "value",
        "normalized_value",
        "unit",
        "date_value",
        "amount_value",
        "currency",
        "duration_value",
        "obligation_party",
        "status",
        "evidence",
        "confidence_score",
    }
)
_FACT_ENCRYPTED_KEYS = frozenset(
    {
        "fact_id",
        "fact_type",
        "label_encrypted",
        "value_encrypted",
        "normalized_value_encrypted",
        "unit",
        "date_value_encrypted",
        "amount_value_encrypted",
        "currency",
        "duration_value_encrypted",
        "obligation_party_encrypted",
        "status",
        "evidence",
        "confidence_score",
    }
)


def _value_field_aad(*, analysis_job_id: str, clause_record_id: str, field_name: str, owner_id: str) -> bytes:
    return build_canonical_aad(
        resource_type="analysis_result_item",
        record_id=build_canonical_record_id(
            {
                "analysis_job_id": analysis_job_id,
                "clause_record_id": clause_record_id,
            }
        ),
        field_name=field_name,
        owner_id=owner_id,
        schema_version=ANALYSIS_RESULT_SCHEMA_VERSION,
    )


def _question_field_aad(
    *, analysis_job_id: str, clause_record_id: str, question_id: str, field_name: str, owner_id: str
) -> bytes:
    return build_canonical_aad(
        resource_type="analysis_result_question",
        record_id=build_canonical_record_id(
            {
                "analysis_job_id": analysis_job_id,
                "clause_record_id": clause_record_id,
                "question_id": question_id,
            }
        ),
        field_name=field_name,
        owner_id=owner_id,
        schema_version=ANALYSIS_RESULT_SCHEMA_VERSION,
    )


def _suggestion_field_aad(
    *, analysis_job_id: str, clause_record_id: str, suggestion_id: str, field_name: str, owner_id: str
) -> bytes:
    return build_canonical_aad(
        resource_type="analysis_result_suggestion",
        record_id=build_canonical_record_id(
            {
                "analysis_job_id": analysis_job_id,
                "clause_record_id": clause_record_id,
                "suggestion_id": suggestion_id,
            }
        ),
        field_name=field_name,
        owner_id=owner_id,
        schema_version=ANALYSIS_RESULT_SCHEMA_VERSION,
    )


def _fact_field_aad(
    *, analysis_job_id: str, clause_record_id: str, fact_id: str, field_name: str, owner_id: str
) -> bytes:
    return build_canonical_aad(
        resource_type="analysis_result_fact",
        record_id=build_canonical_record_id(
            {
                "analysis_job_id": analysis_job_id,
                "clause_record_id": clause_record_id,
                "fact_id": fact_id,
            }
        ),
        field_name=field_name,
        owner_id=owner_id,
        schema_version=ANALYSIS_RESULT_SCHEMA_VERSION,
    )


def _require_item_id(value: object, field_name: str, *, error_type: type[Exception]) -> str:
    if type(value) is not str or not value.strip():
        raise error_type(f"Invalid {field_name} value.")
    if value.strip() != value or "\x00" in value:
        raise error_type(f"Invalid {field_name} value.")
    return value


def _encrypt_text(value: object, *, aad: bytes, keyring: EncryptionKeyring) -> dict[str, object]:
    if type(value) is not str:
        raise ScalarEncryptionError("Invalid text value.")
    envelope = encrypt(_ensure_utf8_text(value), aad=aad, keyring=keyring)
    return envelope.to_mapping()


def _decrypt_text(value: object, *, aad: bytes, keyring: EncryptionKeyring) -> str:
    if type(value) is not dict:
        raise ScalarDecryptionError("Invalid encrypted text value.")
    try:
        plaintext = decrypt(value, aad=aad, keyring=keyring)
    except Exception:
        raise ScalarDecryptionError("Unable to decrypt analysis result text.") from None
    return _ensure_utf8_plaintext(plaintext)


def _encrypt_question_list(
    questions: list[dict[str, object]],
    *,
    analysis_job_id: str,
    clause_record_id: str,
    owner_id: str,
    keyring: EncryptionKeyring,
) -> list[dict[str, object]]:
    if type(questions) is not list:
        raise ScalarEncryptionError("Invalid questions_to_ask value.")

    seen_ids: set[str] = set()
    encrypted: list[dict[str, object]] = []
    for question in questions:
        if type(question) is not dict or set(question.keys()) != _QUESTION_PLAINTEXT_KEYS:
            raise ScalarEncryptionError("Invalid question entry.")

        question_id = _require_item_id(
            question.get("question_id"), "question_id", error_type=ScalarEncryptionError
        )
        if question_id in seen_ids:
            raise ScalarEncryptionError("Duplicate question_id value.")
        seen_ids.add(question_id)

        encrypted.append(
            {
                "question_id": question_id,
                "question_encrypted": _encrypt_text(
                    question.get("question"),
                    aad=_question_field_aad(
                        analysis_job_id=analysis_job_id,
                        clause_record_id=clause_record_id,
                        question_id=question_id,
                        field_name="question",
                        owner_id=owner_id,
                    ),
                    keyring=keyring,
                ),
                "purpose_encrypted": _encrypt_text(
                    question.get("purpose"),
                    aad=_question_field_aad(
                        analysis_job_id=analysis_job_id,
                        clause_record_id=clause_record_id,
                        question_id=question_id,
                        field_name="purpose",
                        owner_id=owner_id,
                    ),
                    keyring=keyring,
                ),
                "related_evidence_ids": question.get("related_evidence_ids"),
                "priority": question.get("priority"),
                "id": question.get("id"),
            }
        )
    return encrypted


def _decrypt_question_list(
    questions: list[dict[str, object]],
    *,
    analysis_job_id: str,
    clause_record_id: str,
    owner_id: str,
    keyring: EncryptionKeyring,
) -> list[dict[str, object]]:
    if type(questions) is not list:
        raise ScalarDecryptionError("Invalid questions_to_ask value.")

    seen_ids: set[str] = set()
    decrypted: list[dict[str, object]] = []
    for question in questions:
        if type(question) is not dict or set(question.keys()) != _QUESTION_ENCRYPTED_KEYS:
            raise ScalarDecryptionError("Invalid question entry.")

        question_id = _require_item_id(
            question.get("question_id"), "question_id", error_type=ScalarDecryptionError
        )
        if question_id in seen_ids:
            raise ScalarDecryptionError("Duplicate question_id value.")
        seen_ids.add(question_id)

        decrypted.append(
            {
                "question_id": question_id,
                "question": _decrypt_text(
                    question.get("question_encrypted"),
                    aad=_question_field_aad(
                        analysis_job_id=analysis_job_id,
                        clause_record_id=clause_record_id,
                        question_id=question_id,
                        field_name="question",
                        owner_id=owner_id,
                    ),
                    keyring=keyring,
                ),
                "purpose": _decrypt_text(
                    question.get("purpose_encrypted"),
                    aad=_question_field_aad(
                        analysis_job_id=analysis_job_id,
                        clause_record_id=clause_record_id,
                        question_id=question_id,
                        field_name="purpose",
                        owner_id=owner_id,
                    ),
                    keyring=keyring,
                ),
                "related_evidence_ids": question.get("related_evidence_ids"),
                "priority": question.get("priority"),
                "id": question.get("id"),
            }
        )
    return decrypted


def _encrypt_suggestion_list(
    suggestions: list[dict[str, object]],
    *,
    analysis_job_id: str,
    clause_record_id: str,
    owner_id: str,
    keyring: EncryptionKeyring,
) -> list[dict[str, object]]:
    if type(suggestions) is not list:
        raise ScalarEncryptionError("Invalid negotiation_suggestions value.")

    seen_ids: set[str] = set()
    encrypted: list[dict[str, object]] = []
    for suggestion in suggestions:
        if type(suggestion) is not dict or set(suggestion.keys()) != _SUGGESTION_PLAINTEXT_KEYS:
            raise ScalarEncryptionError("Invalid suggestion entry.")

        suggestion_id = _require_item_id(
            suggestion.get("suggestion_id"), "suggestion_id", error_type=ScalarEncryptionError
        )
        if suggestion_id in seen_ids:
            raise ScalarEncryptionError("Duplicate suggestion_id value.")
        seen_ids.add(suggestion_id)

        def _field(field_name: str) -> dict[str, object]:
            return _encrypt_text(
                suggestion.get(field_name),
                aad=_suggestion_field_aad(
                    analysis_job_id=analysis_job_id,
                    clause_record_id=clause_record_id,
                    suggestion_id=suggestion_id,
                    field_name=field_name,
                    owner_id=owner_id,
                ),
                keyring=keyring,
            )

        encrypted.append(
            {
                "suggestion_id": suggestion_id,
                "objective_encrypted": _field("objective"),
                "suggested_change_encrypted": _field("suggested_change"),
                "fallback_option_encrypted": _field("fallback_option"),
                "related_evidence_ids": suggestion.get("related_evidence_ids"),
                "priority": suggestion.get("priority"),
                "id": suggestion.get("id"),
            }
        )
    return encrypted


def _decrypt_suggestion_list(
    suggestions: list[dict[str, object]],
    *,
    analysis_job_id: str,
    clause_record_id: str,
    owner_id: str,
    keyring: EncryptionKeyring,
) -> list[dict[str, object]]:
    if type(suggestions) is not list:
        raise ScalarDecryptionError("Invalid negotiation_suggestions value.")

    seen_ids: set[str] = set()
    decrypted: list[dict[str, object]] = []
    for suggestion in suggestions:
        if type(suggestion) is not dict or set(suggestion.keys()) != _SUGGESTION_ENCRYPTED_KEYS:
            raise ScalarDecryptionError("Invalid suggestion entry.")

        suggestion_id = _require_item_id(
            suggestion.get("suggestion_id"), "suggestion_id", error_type=ScalarDecryptionError
        )
        if suggestion_id in seen_ids:
            raise ScalarDecryptionError("Duplicate suggestion_id value.")
        seen_ids.add(suggestion_id)

        def _field(field_name: str) -> str:
            return _decrypt_text(
                suggestion.get(f"{field_name}_encrypted"),
                aad=_suggestion_field_aad(
                    analysis_job_id=analysis_job_id,
                    clause_record_id=clause_record_id,
                    suggestion_id=suggestion_id,
                    field_name=field_name,
                    owner_id=owner_id,
                ),
                keyring=keyring,
            )

        decrypted.append(
            {
                "suggestion_id": suggestion_id,
                "objective": _field("objective"),
                "suggested_change": _field("suggested_change"),
                "fallback_option": _field("fallback_option"),
                "related_evidence_ids": suggestion.get("related_evidence_ids"),
                "priority": suggestion.get("priority"),
                "id": suggestion.get("id"),
            }
        )
    return decrypted


def _encrypt_fact_list(
    facts: list[dict[str, object]],
    *,
    analysis_job_id: str,
    clause_record_id: str,
    owner_id: str,
    keyring: EncryptionKeyring,
) -> list[dict[str, object]]:
    if type(facts) is not list:
        raise ScalarEncryptionError("Invalid extracted_facts value.")

    seen_ids: set[str] = set()
    encrypted: list[dict[str, object]] = []
    for fact in facts:
        if type(fact) is not dict or set(fact.keys()) != _FACT_PLAINTEXT_KEYS:
            raise ScalarEncryptionError("Invalid extracted fact entry.")

        fact_id = _require_item_id(fact.get("fact_id"), "fact_id", error_type=ScalarEncryptionError)
        if fact_id in seen_ids:
            raise ScalarEncryptionError("Duplicate fact_id value.")
        seen_ids.add(fact_id)

        def _field(field_name: str) -> dict[str, object]:
            return _encrypt_text(
                fact.get(field_name),
                aad=_fact_field_aad(
                    analysis_job_id=analysis_job_id,
                    clause_record_id=clause_record_id,
                    fact_id=fact_id,
                    field_name=field_name,
                    owner_id=owner_id,
                ),
                keyring=keyring,
            )

        def _optional_field(field_name: str) -> dict[str, object] | None:
            value = fact.get(field_name)
            if value is None:
                return None
            return _field(field_name)

        encrypted_fact = dict(fact)
        for field_name in (
            "label",
            "value",
            "normalized_value",
            "date_value",
            "amount_value",
            "duration_value",
            "obligation_party",
        ):
            encrypted_fact.pop(field_name, None)
        encrypted_fact["fact_id"] = fact_id
        encrypted_fact["label_encrypted"] = _field("label")
        encrypted_fact["value_encrypted"] = _field("value")
        for field_name in (
            "normalized_value",
            "date_value",
            "amount_value",
            "duration_value",
            "obligation_party",
        ):
            encrypted_fact[f"{field_name}_encrypted"] = _optional_field(field_name)
        encrypted.append(encrypted_fact)
    return encrypted


def _decrypt_fact_list(
    facts: list[dict[str, object]],
    *,
    analysis_job_id: str,
    clause_record_id: str,
    owner_id: str,
    keyring: EncryptionKeyring,
) -> list[dict[str, object]]:
    if type(facts) is not list:
        raise ScalarDecryptionError("Invalid extracted_facts value.")

    seen_ids: set[str] = set()
    decrypted: list[dict[str, object]] = []
    for fact in facts:
        if type(fact) is not dict or set(fact.keys()) != _FACT_ENCRYPTED_KEYS:
            raise ScalarDecryptionError("Invalid extracted fact entry.")

        fact_id = _require_item_id(fact.get("fact_id"), "fact_id", error_type=ScalarDecryptionError)
        if fact_id in seen_ids:
            raise ScalarDecryptionError("Duplicate fact_id value.")
        seen_ids.add(fact_id)

        def _field(field_name: str) -> str:
            return _decrypt_text(
                fact.get(f"{field_name}_encrypted"),
                aad=_fact_field_aad(
                    analysis_job_id=analysis_job_id,
                    clause_record_id=clause_record_id,
                    fact_id=fact_id,
                    field_name=field_name,
                    owner_id=owner_id,
                ),
                keyring=keyring,
            )

        def _optional_field(field_name: str) -> str | None:
            value = fact.get(f"{field_name}_encrypted")
            if value is None:
                return None
            return _field(field_name)

        decrypted_fact = dict(fact)
        for field_name in (
            "label",
            "value",
            "normalized_value",
            "date_value",
            "amount_value",
            "duration_value",
            "obligation_party",
        ):
            decrypted_fact.pop(f"{field_name}_encrypted", None)
        decrypted_fact["fact_id"] = fact_id
        decrypted_fact["label"] = _field("label")
        decrypted_fact["value"] = _field("value")
        for field_name in (
            "normalized_value",
            "date_value",
            "amount_value",
            "duration_value",
            "obligation_party",
        ):
            decrypted_fact[field_name] = _optional_field(field_name)
        decrypted.append(decrypted_fact)
    return decrypted


def encrypt_analysis_value(
    value: dict[str, object],
    *,
    analysis_job_id: str,
    clause_record_id: str,
    owner_id: str,
    keyring: EncryptionKeyring,
) -> dict[str, object]:
    if type(value) is not dict or set(value.keys()) != _ANALYSIS_VALUE_PLAINTEXT_KEYS:
        raise ScalarEncryptionError("Invalid analysis_value payload.")

    analysis_job_id = _require_identifier(
        analysis_job_id, "analysis_job_id", error_type=ScalarEncryptionError
    )
    clause_record_id = _require_identifier(
        clause_record_id, "clause_record_id", error_type=ScalarEncryptionError
    )
    owner_id = _require_identifier(owner_id, "owner_id", error_type=ScalarEncryptionError)

    encrypted = {
        key: value[key]
        for key in value
        if key not in _VALUE_TEXT_FIELD_NAMES
    }
    for field_name in _VALUE_TEXT_FIELD_NAMES:
        encrypted[f"{field_name}_encrypted"] = _encrypt_text(
            value.get(field_name),
            aad=_value_field_aad(
                analysis_job_id=analysis_job_id,
                clause_record_id=clause_record_id,
                field_name=field_name,
                owner_id=owner_id,
            ),
            keyring=keyring,
        )

    encrypted["questions_to_ask"] = _encrypt_question_list(
        value["questions_to_ask"],
        analysis_job_id=analysis_job_id,
        clause_record_id=clause_record_id,
        owner_id=owner_id,
        keyring=keyring,
    )
    encrypted["negotiation_suggestions"] = _encrypt_suggestion_list(
        value["negotiation_suggestions"],
        analysis_job_id=analysis_job_id,
        clause_record_id=clause_record_id,
        owner_id=owner_id,
        keyring=keyring,
    )
    encrypted["extracted_facts"] = _encrypt_fact_list(
        value["extracted_facts"],
        analysis_job_id=analysis_job_id,
        clause_record_id=clause_record_id,
        owner_id=owner_id,
        keyring=keyring,
    )

    if set(encrypted.keys()) != _ANALYSIS_VALUE_ENCRYPTED_KEYS:
        raise ScalarEncryptionError("Invalid analysis_value payload.")
    return encrypted


def decrypt_analysis_value(
    value: dict[str, object],
    *,
    analysis_job_id: str,
    clause_record_id: str,
    owner_id: str,
    keyring: EncryptionKeyring,
) -> dict[str, object]:
    if type(value) is not dict or set(value.keys()) != _ANALYSIS_VALUE_ENCRYPTED_KEYS:
        raise ScalarDecryptionError("Invalid analysis_value payload.")

    analysis_job_id = _require_identifier(
        analysis_job_id, "analysis_job_id", error_type=ScalarDecryptionError
    )
    clause_record_id = _require_identifier(
        clause_record_id, "clause_record_id", error_type=ScalarDecryptionError
    )
    owner_id = _require_identifier(owner_id, "owner_id", error_type=ScalarDecryptionError)

    decrypted = {
        key: value[key]
        for key in value
        if key not in {f"{name}_encrypted" for name in _VALUE_TEXT_FIELD_NAMES}
    }
    for field_name in _VALUE_TEXT_FIELD_NAMES:
        decrypted[field_name] = _decrypt_text(
            value.get(f"{field_name}_encrypted"),
            aad=_value_field_aad(
                analysis_job_id=analysis_job_id,
                clause_record_id=clause_record_id,
                field_name=field_name,
                owner_id=owner_id,
            ),
            keyring=keyring,
        )

    decrypted["questions_to_ask"] = _decrypt_question_list(
        value["questions_to_ask"],
        analysis_job_id=analysis_job_id,
        clause_record_id=clause_record_id,
        owner_id=owner_id,
        keyring=keyring,
    )
    decrypted["negotiation_suggestions"] = _decrypt_suggestion_list(
        value["negotiation_suggestions"],
        analysis_job_id=analysis_job_id,
        clause_record_id=clause_record_id,
        owner_id=owner_id,
        keyring=keyring,
    )
    decrypted["extracted_facts"] = _decrypt_fact_list(
        value["extracted_facts"],
        analysis_job_id=analysis_job_id,
        clause_record_id=clause_record_id,
        owner_id=owner_id,
        keyring=keyring,
    )

    if set(decrypted.keys()) != _ANALYSIS_VALUE_PLAINTEXT_KEYS:
        raise ScalarDecryptionError("Invalid analysis_value payload.")
    return decrypted
