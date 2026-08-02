from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.core.observability import evaluate_synthetic_alerts


def main() -> None:
    synthetic_snapshot = {
        "api_errors_total": 3,
        "authentication_failure_total": 3,
        "cleanup_failure_total": 1,
        "rate_limit_block_total": 3,
        "readiness_failure_total": 1,
        "worker_stale_recovery_total": 2,
        "worker_terminal_failure_total": 1,
    }
    result = {
        "contract": "synthetic-only-not-production-approved",
        "alerts": [
            asdict(candidate)
            for candidate in evaluate_synthetic_alerts(synthetic_snapshot)
        ],
    }
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
