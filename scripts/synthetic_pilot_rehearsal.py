from __future__ import annotations

import base64
from dataclasses import dataclass
import http.client
import ipaddress
import json
from pathlib import Path
import secrets as synthetic_secrets
import socket
import subprocess
import sys
import tempfile
import time
from uuid import uuid4


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILES = ("compose.yaml", "compose.pilot.yaml")
PROJECT_PREFIX = "contract-check-pilot-"
PILOT_SUBNET_CANDIDATES = tuple(
    ipaddress.ip_network(f"10.240.{octet}.0/24") for octet in range(256)
)
RFC1918_NETWORKS = tuple(
    ipaddress.ip_network(value)
    for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)


@dataclass(frozen=True)
class StageResult:
    stage: str
    status: str
    safe_error_code: str
    aggregate_count: int = 0


class PilotRehearsalError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__("Synthetic pilot rehearsal failed.")
        self.code = code


def generate_project_name() -> str:
    return f"{PROJECT_PREFIX}{synthetic_secrets.token_hex(6)}"


def validate_project_name(project_name: str) -> None:
    suffix = project_name.removeprefix(PROJECT_PREFIX)
    if (
        not project_name.startswith(PROJECT_PREFIX)
        or len(suffix) != 12
        or any(character not in "0123456789abcdef" for character in suffix)
    ):
        raise PilotRehearsalError("PILOT_PROJECT_NAME_INVALID")


def _result(
    stage: str,
    status: str,
    safe_error_code: str = "NONE",
    aggregate_count: int = 0,
) -> StageResult:
    return StageResult(stage, status, safe_error_code, aggregate_count)


def _run(
    command: list[str],
    *,
    env_file: Path | None = None,
    timeout: int = 180,
) -> subprocess.CompletedProcess[str]:
    if env_file is not None and command[:2] == ["docker", "compose"]:
        command = [*command[:2], "--env-file", str(env_file), *command[2:]]
    return subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
        text=True,
        timeout=timeout,
    )


def _compose_command(project_name: str, *arguments: str) -> list[str]:
    validate_project_name(project_name)
    command = ["docker", "compose", "--project-name", project_name]
    for compose_file in COMPOSE_FILES:
        command.extend(["-f", compose_file])
    command.extend(arguments)
    return command


def _available_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _runtime_values(
    project_name: str,
    port: int,
    network_subnet: ipaddress.IPv4Network,
) -> dict[str, str]:
    if (
        network_subnet.prefixlen != 24
        or not any(network_subnet.subnet_of(scope) for scope in RFC1918_NETWORKS)
        or network_subnet.is_loopback
        or network_subnet.is_link_local
        or network_subnet.is_multicast
        or network_subnet.is_unspecified
    ):
        raise PilotRehearsalError("PILOT_NETWORK_SUBNET_UNAVAILABLE")
    subnet = str(network_subnet)
    mysql_password = synthetic_secrets.token_urlsafe(32)
    mysql_root_password = synthetic_secrets.token_urlsafe(32)
    encryption_key = base64.b64encode(synthetic_secrets.token_bytes(32)).decode()
    return {
        "PILOT_PROJECT_NAME": project_name,
        "PILOT_API_PORT": str(port),
        "PILOT_NETWORK_SUBNET": subnet,
        "MYSQL_DATABASE": "pilot_db",
        "MYSQL_USER": "pilot_user",
        "MYSQL_PASSWORD": mysql_password,
        "MYSQL_ROOT_PASSWORD": mysql_root_password,
        "DATABASE_URL": (
            f"mysql+pymysql://pilot_user:{mysql_password}@contract-db:3306/pilot_db"
        ),
        "DATA_ENCRYPTION_ACTIVE_KEY_ID": "pilot-key-v1",
        "DATA_ENCRYPTION_KEYS_JSON": json.dumps(
            [
                {
                    "key_id": "pilot-key-v1",
                    "key": encryption_key,
                    "status": "active",
                }
            ],
            separators=(",", ":"),
        ),
        "JWT_SECRET": synthetic_secrets.token_urlsafe(48),
        "EMAIL_LOOKUP_HMAC_KEY": base64.b64encode(
            synthetic_secrets.token_bytes(32)
        ).decode(),
        "CORS_ALLOWED_ORIGINS": "https://pilot.example.invalid",
        "ANALYSIS_PROVIDER": "synthetic",
        "MAX_UPLOAD_BYTES": str(20 * 1024 * 1024),
        "MAX_EXTRACTED_CHARACTERS": "2000000",
        "MAX_DOCUMENT_PAGES": "100",
        "RATE_LIMIT_LOGIN": "10",
        "RATE_LIMIT_REGISTER": "5",
        "RATE_LIMIT_UPLOAD": "10",
        "RATE_LIMIT_EXTRACTION": "20",
        "RATE_LIMIT_ANALYSIS_JOB": "10",
        "RATE_LIMIT_WINDOW_SECONDS": "60",
        "TRUST_PROXY_HEADERS": "true",
        "TRUSTED_PROXY_CIDRS": subnet,
        "REQUIRE_HTTPS": "true",
        "ALLOWED_HOSTS": "pilot.example.invalid",
    }


def _write_env_file(directory: Path, values: dict[str, str]) -> Path:
    env_file = directory / "pilot-runtime.env"
    lines = [f"{key}={value}" for key, value in values.items()]
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return env_file


def _request(
    port: int,
    method: str,
    path: str,
    *,
    body: bytes | None = None,
    token: str | None = None,
    origin: str | None = None,
    forwarded_https: bool = True,
    forwarded_for: str = "192.0.2.10",
    host: str = "pilot.example.invalid",
    content_type: str = "application/json",
) -> tuple[int, dict[str, str], bytes]:
    headers = {"Host": host, "Content-Type": content_type}
    if forwarded_https:
        headers["X-Forwarded-Proto"] = "https"
        headers["X-Forwarded-For"] = forwarded_for
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    if origin is not None:
        headers["Origin"] = origin
    if method == "OPTIONS":
        headers["Access-Control-Request-Method"] = "POST"
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        response_body = response.read()
        return response.status, dict(response.getheaders()), response_body
    finally:
        connection.close()


def _json_request(
    port: int,
    method: str,
    path: str,
    payload: dict[str, object] | None = None,
    **kwargs: object,
) -> tuple[int, dict[str, str], dict[str, object]]:
    body = None if payload is None else json.dumps(payload).encode()
    status, headers, response_body = _request(
        port,
        method,
        path,
        body=body,
        **kwargs,
    )
    try:
        parsed = json.loads(response_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        parsed = {}
    return status, headers, parsed


def _multipart_document(filename: str, content: bytes) -> tuple[str, bytes]:
    boundary = f"pilot-{uuid4().hex}"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: text/plain\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
    return f"multipart/form-data; boundary={boundary}", body


def _wait_for_health(port: int) -> None:
    for _ in range(30):
        try:
            status, _, _ = _request(
                port,
                "GET",
                "/health",
            )
            if status == 200:
                return
        except OSError:
            pass
        time.sleep(2)
    raise PilotRehearsalError("PILOT_API_HEALTH_FAILED")


def _run_child_rehearsal(script_name: str) -> None:
    result = _run([sys.executable, f"scripts/{script_name}"], timeout=600)
    if result.returncode != 0 or '"status":"FAIL"' in result.stdout:
        raise PilotRehearsalError("PILOT_LINKED_REHEARSAL_FAILED")


def _docker_resource_snapshot() -> frozenset[str]:
    resources: set[str] = set()
    for resource_type, command in (
        ("container", ["docker", "ps", "--all", "--quiet"]),
        ("network", ["docker", "network", "ls", "--quiet"]),
        ("volume", ["docker", "volume", "ls", "--quiet"]),
    ):
        completed = _run(command, timeout=30)
        if completed.returncode != 0:
            raise PilotRehearsalError("DOCKER_RESOURCE_SNAPSHOT_FAILED")
        resources.update(
            f"{resource_type}:{identifier}"
            for identifier in completed.stdout.splitlines()
            if identifier.strip()
        )
    return frozenset(resources)


def _docker_network_subnets() -> tuple[ipaddress.IPv4Network, ...]:
    listed = _run(["docker", "network", "ls", "--quiet"], timeout=30)
    identifiers = [value for value in listed.stdout.splitlines() if value.strip()]
    if listed.returncode != 0:
        raise PilotRehearsalError("PILOT_NETWORK_SUBNET_UNAVAILABLE")
    if not identifiers:
        return ()
    inspected = _run(["docker", "network", "inspect", *identifiers], timeout=30)
    if inspected.returncode != 0:
        raise PilotRehearsalError("PILOT_NETWORK_SUBNET_UNAVAILABLE")
    try:
        networks = json.loads(inspected.stdout)
        if not isinstance(networks, list):
            raise ValueError
        subnets: list[ipaddress.IPv4Network] = []
        for network in networks:
            configs = network["IPAM"]["Config"]
            if configs is None:
                continue
            if not isinstance(configs, list):
                raise ValueError
            for config in configs:
                value = config.get("Subnet")
                if value is None:
                    continue
                parsed = ipaddress.ip_network(value, strict=False)
                if isinstance(parsed, ipaddress.IPv4Network):
                    subnets.append(parsed)
        return tuple(subnets)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise PilotRehearsalError("PILOT_NETWORK_SUBNET_UNAVAILABLE") from None


def _select_pilot_subnet(
    existing_subnets: tuple[ipaddress.IPv4Network, ...],
) -> ipaddress.IPv4Network:
    for candidate in PILOT_SUBNET_CANDIDATES:
        if not any(candidate.overlaps(existing) for existing in existing_subnets):
            return candidate
    raise PilotRehearsalError("PILOT_NETWORK_SUBNET_UNAVAILABLE")


def _project_resource_count(project_name: str) -> int:
    validate_project_name(project_name)
    count = 0
    project_filter = f"label=com.docker.compose.project={project_name}"
    for command in (
        ["docker", "ps", "--all", "--quiet", "--filter", project_filter],
        ["docker", "network", "ls", "--quiet", "--filter", project_filter],
        ["docker", "volume", "ls", "--quiet", "--filter", project_filter],
    ):
        completed = _run(command, timeout=30)
        if completed.returncode != 0:
            raise PilotRehearsalError("PILOT_CLEANUP_FAILED")
        count += sum(bool(value.strip()) for value in completed.stdout.splitlines())
    return count


def _cleanup_is_complete(
    project_name: str,
    original_resources: frozenset[str],
) -> bool:
    current_resources = _docker_resource_snapshot()
    return original_resources <= current_resources and _project_resource_count(project_name) == 0


def _restart_count(project_name: str, env_file: Path, service: str) -> int:
    container = _run(
        _compose_command(project_name, "ps", "--quiet", service),
        env_file=env_file,
    )
    identifier = container.stdout.strip()
    if container.returncode != 0 or not identifier:
        raise PilotRehearsalError("PILOT_SERVICE_STATE_INVALID")
    inspected = _run(
        ["docker", "inspect", "--format", "{{.RestartCount}}", identifier],
        timeout=30,
    )
    try:
        return int(inspected.stdout.strip())
    except (TypeError, ValueError):
        raise PilotRehearsalError("PILOT_SERVICE_STATE_INVALID") from None


def _database_port_is_published(project_name: str, env_file: Path) -> bool:
    container = _run(
        _compose_command(project_name, "ps", "--quiet", "contract-db"),
        env_file=env_file,
    )
    identifier = container.stdout.strip()
    if container.returncode != 0 or not identifier:
        raise PilotRehearsalError("PILOT_SERVICE_STATE_INVALID")
    inspected = _run(
        [
            "docker",
            "inspect",
            "--format",
            "{{json .NetworkSettings.Ports}}",
            identifier,
        ],
        timeout=30,
    )
    try:
        ports = json.loads(inspected.stdout)
    except (TypeError, json.JSONDecodeError):
        raise PilotRehearsalError("PILOT_SERVICE_STATE_INVALID") from None
    return ports.get("3306/tcp") is not None


def _exercise_api(port: int) -> tuple[dict[str, str], int]:
    if _request(
        port,
        "GET",
        "/auth/me",
        forwarded_https=False,
    )[0] != 426:
        raise PilotRehearsalError("PILOT_HTTPS_BOUNDARY_FAILED")
    if _request(
        port,
        "GET",
        "/auth/me",
        forwarded_for="untrusted-forwarded-value",
    )[0] != 426:
        raise PilotRehearsalError("PILOT_FORWARDED_BOUNDARY_FAILED")
    if _request(
        port,
        "GET",
        "/health",
        host="blocked.example.invalid",
    )[0] != 400:
        raise PilotRehearsalError("PILOT_HOST_BOUNDARY_FAILED")
    ready_status, _, _ = _json_request(port, "GET", "/ready")
    if ready_status != 200:
        raise PilotRehearsalError("PILOT_READINESS_FAILED")

    preflight_status, cors_headers, _ = _request(
        port,
        "OPTIONS",
        "/auth/login",
        origin="https://pilot.example.invalid",
    )
    if (
        preflight_status != 200
        or cors_headers.get("access-control-allow-origin")
        != "https://pilot.example.invalid"
    ):
        raise PilotRehearsalError("PILOT_CORS_BOUNDARY_FAILED")
    blocked_cors, blocked_headers, _ = _request(
        port,
        "OPTIONS",
        "/auth/login",
        origin="https://blocked.example.invalid",
    )
    if blocked_cors < 400 or "access-control-allow-origin" in blocked_headers:
        raise PilotRehearsalError("PILOT_CORS_BOUNDARY_FAILED")

    run_id = synthetic_secrets.token_hex(8)
    password_a = synthetic_secrets.token_urlsafe(24)
    password_b = synthetic_secrets.token_urlsafe(24)
    email_a = f"pilot-a-{run_id}@example.invalid"
    email_b = f"pilot-b-{run_id}@example.invalid"
    identities = ((email_a, password_a), (email_b, password_b))
    tokens = []
    for email, password in identities:
        status, _, _ = _json_request(
            port,
            "POST",
            "/auth/register",
            {"email": email, "password": password},
        )
        if status != 200:
            raise PilotRehearsalError("PILOT_REGISTRATION_FAILED")
        status, _, body = _json_request(
            port,
            "POST",
            "/auth/login",
            {"email": email, "password": password},
        )
        if status != 200 or not isinstance(body.get("access_token"), str):
            raise PilotRehearsalError("PILOT_LOGIN_FAILED")
        tokens.append(str(body["access_token"]))
    if _json_request(port, "GET", "/auth/me", token=tokens[0])[0] != 200:
        raise PilotRehearsalError("PILOT_AUTH_ME_FAILED")

    filename = f"synthetic-pilot-{run_id}.txt"
    contract = (
        "1. SYNTHETIC PILOT DATA ONLY\n"
        "This synthetic clause is for isolated pilot validation only.\n"
        "It is unrelated to any real person, company, or agreement.\n"
    ).encode("utf-8")
    content_type, upload_body = _multipart_document(filename, contract)
    upload_status, _, upload_response = _request(
        port,
        "POST",
        "/documents/upload",
        body=upload_body,
        token=tokens[0],
        content_type=content_type,
    )
    if upload_status != 200:
        raise PilotRehearsalError("PILOT_UPLOAD_FAILED")
    upload_payload = json.loads(upload_response)
    document_id = upload_payload.get("document_id")
    if not isinstance(document_id, str):
        raise PilotRehearsalError("PILOT_UPLOAD_FAILED")
    if _json_request(
        port, "GET", f"/documents/{document_id}", token=tokens[0]
    )[0] != 200:
        raise PilotRehearsalError("PILOT_DOCUMENT_READ_FAILED")
    if _json_request(
        port, "GET", f"/documents/{document_id}", token=tokens[1]
    )[0] != 404:
        raise PilotRehearsalError("PILOT_OWNERSHIP_BOUNDARY_FAILED")

    job_status, _, job_body = _json_request(
        port,
        "POST",
        f"/documents/{document_id}/analysis-jobs",
        token=tokens[0],
    )
    job_id = job_body.get("job_id")
    if job_status != 200 or not isinstance(job_id, str):
        raise PilotRehearsalError("PILOT_JOB_CREATE_FAILED")
    terminal = None
    for _ in range(60):
        status, _, body = _json_request(
            port,
            "GET",
            f"/analysis-jobs/{job_id}",
            token=tokens[0],
        )
        if status == 200 and body.get("status") in {"completed", "failed"}:
            terminal = body.get("status")
            break
        time.sleep(1)
    if terminal != "completed":
        raise PilotRehearsalError("PILOT_JOB_TERMINAL_FAILED")
    results_status, _, results = _json_request(
        port,
        "GET",
        f"/documents/{document_id}/analysis-results",
        token=tokens[0],
    )
    if results_status != 200:
        raise PilotRehearsalError("PILOT_RESULT_READ_FAILED")
    if results.get("status") != "completed":
        raise PilotRehearsalError("PILOT_RESULT_STATUS_INVALID")
    if not isinstance(results.get("items"), list) or not results["items"]:
        raise PilotRehearsalError("PILOT_SYNTHETIC_RESULT_MISSING")

    failed_auth = _json_request(
        port,
        "POST",
        "/auth/login",
        {"email": email_a, "password": synthetic_secrets.token_urlsafe(24)},
    )[0]
    if failed_auth != 401:
        raise PilotRehearsalError("PILOT_AUTH_FAILURE_EVENT_FAILED")

    markers = {
        "email_a": email_a,
        "email_b": email_b,
        "password_a": password_a,
        "password_b": password_b,
        "token_a": tokens[0],
        "token_b": tokens[1],
        "filename": filename,
        "contract_marker": "SYNTHETIC PILOT DATA ONLY",
    }
    return markers, 2


def _logs_are_safe(logs: str, markers: dict[str, str], runtime: dict[str, str]) -> bool:
    forbidden = list(markers.values())
    forbidden.extend(
        runtime[key]
        for key in (
            "DATABASE_URL",
            "JWT_SECRET",
            "EMAIL_LOOKUP_HMAC_KEY",
            "DATA_ENCRYPTION_KEYS_JSON",
        )
    )
    return not any(marker and marker in logs for marker in forbidden)


def run_rehearsal() -> tuple[StageResult, ...]:
    results: list[StageResult] = []
    project_name = generate_project_name()
    validate_project_name(project_name)
    port = _available_port()
    temporary_directory = tempfile.TemporaryDirectory(
        prefix="contract-check-pilot-runtime-"
    )
    runtime: dict[str, str] = {}
    env_file: Path | None = None
    cleanup_ok = False
    original_resources: frozenset[str] = frozenset()
    try:
        docker = _run(["docker", "info"], timeout=30)
        if docker.returncode != 0:
            raise PilotRehearsalError("DOCKER_UNAVAILABLE")
        original_resources = _docker_resource_snapshot()
        network_subnet = _select_pilot_subnet(_docker_network_subnets())
        runtime = _runtime_values(project_name, port, network_subnet)
        env_file = _write_env_file(Path(temporary_directory.name), runtime)
        results.append(_result("preflight", "PASS"))

        config = _run(
            _compose_command(project_name, "config", "--quiet"),
            env_file=env_file,
        )
        if config.returncode != 0:
            raise PilotRehearsalError("PILOT_COMPOSE_CONFIG_FAILED")
        results.append(_result("compose_config", "PASS"))

        started = _run(
            _compose_command(
                project_name,
                "up",
                "--build",
                "--detach",
                "contract-db",
                "migrate",
                "api",
                "worker",
            ),
            env_file=env_file,
            timeout=600,
        )
        if started.returncode != 0:
            raise PilotRehearsalError("PILOT_SERVICE_START_FAILED")
        if _database_port_is_published(project_name, env_file):
            raise PilotRehearsalError("PILOT_DB_PORT_PUBLISHED")
        _wait_for_health(port)
        results.append(_result("pilot_services", "PASS", aggregate_count=4))

        markers, account_count = _exercise_api(port)
        results.append(_result("pilot_api_smoke", "PASS", aggregate_count=account_count))

        for script in (
            "observability_rehearsal.py",
            "secret_rotation_rehearsal.py",
            "mysql_backup_rehearsal.py",
            "mysql_restore_rehearsal.py",
        ):
            _run_child_rehearsal(script)
        results.append(_result("linked_rehearsals", "PASS", aggregate_count=4))

        logs = _run(
            _compose_command(project_name, "logs", "--no-color", "api", "worker"),
            env_file=env_file,
        )
        if logs.returncode != 0 or not _logs_are_safe(logs.stdout, markers, runtime):
            raise PilotRehearsalError("PILOT_LOG_BOUNDARY_FAILED")
        if "analysis_worker_started" not in logs.stdout:
            raise PilotRehearsalError("PILOT_WORKER_START_EVENT_MISSING")
        if any(
            _restart_count(project_name, env_file, service) != 0
            for service in ("api", "worker")
        ):
            raise PilotRehearsalError("PILOT_RESTART_LOOP_DETECTED")
        results.append(_result("log_boundary", "PASS"))
    except (OSError, subprocess.SubprocessError, ValueError, PilotRehearsalError) as exc:
        code = exc.code if isinstance(exc, PilotRehearsalError) else "PILOT_REHEARSAL_FAILED"
        results.append(_result("pilot_rehearsal", "FAIL", code))
    finally:
        try:
            cleanup = _run(
                _compose_command(
                    project_name,
                    "down",
                    "--volumes",
                    "--remove-orphans",
                    "--timeout",
                    "30",
                ),
                env_file=env_file,
                timeout=180,
            )
            cleanup_ok = cleanup.returncode == 0
            if cleanup_ok:
                cleanup_ok = _cleanup_is_complete(project_name, original_resources)
        except (OSError, subprocess.SubprocessError, PilotRehearsalError):
            cleanup_ok = False
        temporary_directory.cleanup()
        results.append(
            _result(
                "cleanup",
                "PASS" if cleanup_ok else "FAIL",
                "NONE" if cleanup_ok else "PILOT_CLEANUP_FAILED",
            )
        )
    if any(result.status == "FAIL" for result in results):
        results.append(_result("final", "FAIL", "PILOT_NOT_COMPLETED"))
    else:
        results.append(_result("final", "PASS"))
    return tuple(results)


def main() -> int:
    results = run_rehearsal()
    print(
        json.dumps(
            {"results": [result.__dict__ for result in results]},
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 1 if any(result.status == "FAIL" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
