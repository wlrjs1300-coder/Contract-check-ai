# ADR-016: API 입력 경계 보호와 프로세스 로컬 요청 제한

## 상태

승인

## 결정

인증, 업로드, 추출, 분석 작업 생성과 같이 비용 또는 공격 표면이 큰 쓰기 API에만 요청 제한을 적용한다. 조회 API에는 일괄 적용하지 않는다.

현재 배포 규모에서는 외부 저장소 없이 프로세스 메모리 기반 sliding-window limiter를 사용한다. 공개 인증 API는 client address의 SHA-256 파생값, 인증 API는 사용자 ID의 SHA-256 파생값을 bucket key로 사용한다. Authorization, JWT, 이메일, 원문 body 및 raw IP는 저장하거나 응답·로그에 기록하지 않는다.

limiter는 monotonic clock을 사용하고 lock 내부 작업을 bucket 정리와 timestamp 추가로 제한한다. 만료 bucket을 정리하고 bucket 수에 상한을 둔다.

## 한계와 후속 범위

bucket은 API 프로세스마다 독립적이다. 여러 replica 사이에서 제한 횟수가 공유되지 않으므로 수평 확장 환경의 전역 제한 수단이 아니다. 다중 replica 또는 높은 트래픽이 필요해지면 동일 dependency 경계를 유지한 채 Redis 등의 원자적 distributed limiter로 교체한다. Redis 도입과 distributed limiter 구현은 v0.8.0 범위에서 제외한다.
