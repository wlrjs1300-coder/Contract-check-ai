from __future__ import annotations

import ipaddress
import json
import subprocess

import pytest

from backend.app.api.extractions import (
    SyntheticOcrAdapter,
    SyntheticPdfRenderer,
    get_ocr_adapter,
    get_pdf_renderer,
)
from scripts import synthetic_pilot_rehearsal as rehearsal


def test_pilot_cannot_enable_synthetic_ocr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "pilot")
    monkeypatch.setenv("OCR_ADAPTER", "synthetic")
    with pytest.raises(RuntimeError, match="test-only"):
        get_ocr_adapter()


def test_pilot_never_selects_synthetic_pdf_renderer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "pilot")
    assert not isinstance(get_pdf_renderer(), SyntheticPdfRenderer)


def test_test_environment_retains_synthetic_ocr_and_pdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.delenv("OCR_ADAPTER", raising=False)
    assert isinstance(get_ocr_adapter(), SyntheticOcrAdapter)
    assert isinstance(get_pdf_renderer(), SyntheticPdfRenderer)


def test_pilot_project_names_are_unique_and_scoped() -> None:
    first = rehearsal.generate_project_name()
    second = rehearsal.generate_project_name()
    rehearsal.validate_project_name(first)
    assert first != second
    with pytest.raises(rehearsal.PilotRehearsalError):
        rehearsal.validate_project_name("contract-check")


def test_log_marker_check_does_not_emit_or_transform_values() -> None:
    markers = {"token": "synthetic-private-marker"}
    runtime = {
        "DATABASE_URL": "synthetic-db-marker",
        "JWT_SECRET": "synthetic-jwt-marker",
        "EMAIL_LOOKUP_HMAC_KEY": "synthetic-hmac-marker",
        "DATA_ENCRYPTION_KEYS_JSON": "synthetic-keyring-marker",
    }
    assert rehearsal._logs_are_safe("safe aggregate log", markers, runtime)
    assert not rehearsal._logs_are_safe(
        "contains synthetic-private-marker",
        markers,
        runtime,
    )


def test_cleanup_preserves_existing_resources_and_allows_unrelated_new_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshots = iter(
        (
            frozenset({"container:existing", "network:existing"}),
            frozenset(
                {"container:existing", "network:existing", "volume:unrelated-new"}
            ),
        )
    )
    monkeypatch.setattr(rehearsal, "_docker_resource_snapshot", lambda: next(snapshots))
    original = rehearsal._docker_resource_snapshot()
    monkeypatch.setattr(rehearsal, "_project_resource_count", lambda project: 0)
    assert rehearsal._cleanup_is_complete(rehearsal.generate_project_name(), original)


def test_cleanup_fails_if_an_existing_resource_was_deleted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        rehearsal, "_docker_resource_snapshot", lambda: frozenset({"network:existing"})
    )
    monkeypatch.setattr(rehearsal, "_project_resource_count", lambda project: 0)
    assert not rehearsal._cleanup_is_complete(
        rehearsal.generate_project_name(),
        frozenset({"container:existing", "network:existing"}),
    )


@pytest.mark.parametrize("resource_type", ["container", "network", "volume"])
def test_cleanup_fails_if_any_project_resource_remains(
    monkeypatch: pytest.MonkeyPatch,
    resource_type: str,
) -> None:
    monkeypatch.setattr(rehearsal, "_docker_resource_snapshot", lambda: frozenset())

    def fake_run(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        command_type = (
            "container"
            if command[1] == "ps"
            else command[1]
        )
        output = "opaque-id\n" if command_type == resource_type else ""
        return subprocess.CompletedProcess(command, 0, output, "")

    monkeypatch.setattr(rehearsal, "_run", fake_run)
    assert not rehearsal._cleanup_is_complete(
        rehearsal.generate_project_name(), frozenset()
    )


def test_cleanup_docker_query_failure_is_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sensitive_identifier = "sensitive-resource-id"

    def failed_run(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 1, sensitive_identifier, sensitive_identifier)

    monkeypatch.setattr(rehearsal, "_run", failed_run)
    with pytest.raises(
        rehearsal.PilotRehearsalError, match="Synthetic pilot rehearsal failed"
    ) as error:
        rehearsal._project_resource_count(rehearsal.generate_project_name())
    assert error.value.code == "PILOT_CLEANUP_FAILED"
    assert sensitive_identifier not in str(error.value)


def test_selects_first_non_overlapping_private_subnet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = ipaddress.ip_network("10.240.0.0/24")
    second = ipaddress.ip_network("10.240.1.0/24")
    monkeypatch.setattr(rehearsal, "PILOT_SUBNET_CANDIDATES", (first, second))
    assert rehearsal._select_pilot_subnet(()) == first
    assert rehearsal._select_pilot_subnet((first,)) == second


def test_all_subnet_candidates_conflicting_fails_safely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = ipaddress.ip_network("10.240.0.0/24")
    monkeypatch.setattr(rehearsal, "PILOT_SUBNET_CANDIDATES", (candidate,))
    with pytest.raises(rehearsal.PilotRehearsalError) as error:
        rehearsal._select_pilot_subnet((ipaddress.ip_network("10.240.0.0/16"),))
    assert error.value.code == "PILOT_NETWORK_SUBNET_UNAVAILABLE"
    assert str(candidate) not in str(error.value)


def test_malformed_docker_network_data_fails_safely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(
        (
            subprocess.CompletedProcess([], 0, "network-id\n", ""),
            subprocess.CompletedProcess([], 0, '[{"IPAM":{"Config":"invalid"}}]', ""),
        )
    )
    monkeypatch.setattr(rehearsal, "_run", lambda command, **kwargs: next(responses))
    with pytest.raises(rehearsal.PilotRehearsalError) as error:
        rehearsal._docker_network_subnets()
    assert error.value.code == "PILOT_NETWORK_SUBNET_UNAVAILABLE"


@pytest.mark.parametrize(
    "subnet",
    ("0.0.0.0/24", "8.8.8.0/24", "127.0.0.0/24", "169.254.1.0/24", "224.0.0.0/24"),
)
def test_runtime_rejects_unsafe_subnets(subnet: str) -> None:
    with pytest.raises(rehearsal.PilotRehearsalError) as error:
        rehearsal._runtime_values(
            rehearsal.generate_project_name(), 8000, ipaddress.ip_network(subnet)
        )
    assert error.value.code == "PILOT_NETWORK_SUBNET_UNAVAILABLE"


def test_compose_subnet_matches_trusted_proxy_without_outputting_value() -> None:
    subnet = ipaddress.ip_network("10.240.42.0/24")
    runtime = rehearsal._runtime_values(rehearsal.generate_project_name(), 8000, subnet)
    assert runtime["PILOT_NETWORK_SUBNET"] == runtime["TRUSTED_PROXY_CIDRS"]
    result = rehearsal.StageResult("preflight", "PASS", "NONE")
    assert str(subnet) not in json.dumps(result.__dict__)


def test_preflight_failure_still_runs_scoped_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[list[str]] = []

    def fake_run(
        command: list[str],
        *,
        env_file=None,
        timeout: int = 180,
    ) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess(command, 1, "", "")

    monkeypatch.setattr(rehearsal, "_run", fake_run)
    results = rehearsal.run_rehearsal()
    assert any(result.stage == "pilot_rehearsal" and result.status == "FAIL" for result in results)
    assert results[-2].stage == "cleanup"
    assert results[-2].status == "FAIL"
    assert results[-1].stage == "final"
    assert results[-1].status == "FAIL"
    cleanup_commands = [command for command in commands if "down" in command]
    assert len(cleanup_commands) == 1
    assert "--volumes" in cleanup_commands[0]
    assert "--remove-orphans" in cleanup_commands[0]
    assert all("contract-check-pilot-" in " ".join(command) for command in cleanup_commands)


def test_main_failure_output_is_safe_and_exit_is_nonzero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        rehearsal,
        "run_rehearsal",
        lambda: (
            rehearsal.StageResult(
                "pilot_rehearsal",
                "FAIL",
                "PILOT_REHEARSAL_FAILED",
            ),
            rehearsal.StageResult("cleanup", "PASS", "NONE"),
            rehearsal.StageResult("final", "FAIL", "PILOT_NOT_COMPLETED"),
        ),
    )
    assert rehearsal.main() == 1
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["results"][-1]["status"] == "FAIL"
    assert "exception" not in output.lower()
    assert "traceback" not in output.lower()
