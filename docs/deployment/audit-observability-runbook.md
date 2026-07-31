# Audit and observability runbook

## 구현 경계

현재 구현은 JSON structured event, process-local counter, synthetic alert 판정과
플랫폼 중립 collector protocol만 제공한다. 외부 collector 제품, 네트워크 전송,
credential, 공개 `/metrics` endpoint, 실제 on-call 연동은 포함하지 않는다.
production observability 완료나 실제 계약서·개인정보 사용 승인을 의미하지 않는다.

## 이벤트 목적과 code

- `operational`: 서비스 요청, readiness, cleanup, worker 상태 등 운영 진단
- `audit`: 인증 성공과 계정 생성처럼 허용된 주체 행동 기록
- `security`: 인증 실패, owner-scoped 접근 미허용, rate limit과 unsafe cleanup

주요 code는 `authentication_succeeded`, `authentication_failed`,
`account_registered`, `resource_access_not_granted`, `rate_limit_exceeded`,
`readiness_failed`, `temporary_cleanup_failed`, `orphan_cleanup_failed`,
`orphan_cleanup_unsafe_skipped`, `analysis_job_retry_scheduled`,
`analysis_job_failed_terminal`, `analysis_job_completed`,
`analysis_job_claim_lost`, `analysis_job_stale_recovered`,
`analysis_job_stale_failed`이다.

## 스키마와 정보 최소화

목적에 따라 다음 중 필요한 필드만 출력한다:
`timestamp`, `event_id`, `event`, `event_category`, `service`, `severity`,
`outcome`, `status`, `request_id`, `correlation_id`, `actor_type`, `actor_id`,
`target_type`, `action_code`, `status_code`, `safe_error_code`,
`block_reason_code`, `job_id`, `worker_id`, `attempt_count`, `duration_ms`,
`metric_key`, `alert_candidate`.

실제 user/resource ID, email, filename, client/peer IP와 forwarded chain,
authorization/cookie/token/password/secret/key, DB URL, request/response body,
계약서·추출·조항·evidence 본문, Provider request/response, raw exception과
stack trace, local/temp/backup artifact path는 금지한다. extra key는 대소문자와
하이픈/underscore 차이를 제거해 검사하며 core field 덮어쓰기를 허용하지 않는다.

인증된 actor는 `contract-check:audit-actor:v1:` 도메인 prefix와 내부 ID를
SHA-256으로 파생한 `actor_` 접두 24자리 digest만 사용한다. 원문을 포함하지
않고 동일 버전에서 안정적이지만 외부 신원 식별자로 사용하지 않는다.

## Metrics

counter는 thread-safe process-local 값이며 replica 간 합산을 보장하지 않는다.

- `api_requests_total`, `api_errors_total`
- `authentication_success_total`, `authentication_failure_total`
- `authorization_not_granted_total`, `rate_limit_block_total`
- `readiness_failure_total`, `cleanup_failure_total`
- `worker_completed_total`, `worker_retry_total`
- `worker_terminal_failure_total`, `worker_stale_recovery_total`
- `event_delivery_failure_total`

개인정보나 high-cardinality label은 지원하지 않는다.

## Synthetic alert와 collector

`python scripts/observability_rehearsal.py`는 readiness/cleanup/terminal worker
failure 1회, stale recovery 2회, 인증 실패/rate limit/API 5xx 3회를 candidate로
판정한다. rehearsal 전용이며 production 승인값이 아니다. 실제 경보는 전송하지
않는다.

기본 sink는 Python logger이며 테스트용 in-memory collector가 있다. 정제되고
JSON 직렬화 가능한 event만 전달하며 header/body를 자동 수집하지 않는다.
collector 실패는 사용자 요청을 무조건 실패시키지 않고
`event_delivery_failure_total`과 안전한 fallback event로 감지한다.

외부 collector 제품과 접근 제어, 실제 보존 기간, WORM/hash-chain/서명,
장기 무결성, 실제 alert channel, on-call과 incident response는 미선정 또는
미구현이다.
