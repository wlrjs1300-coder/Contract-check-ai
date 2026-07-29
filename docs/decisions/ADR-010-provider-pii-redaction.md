# ADR-010: Provider PII Redaction Gate

## 상태

- 상태: `accepted` (v0.7.1 완료)
- 작성일: 2026-07-21
- 적용 범위: `feat/v0.7.1-provider-pii-gate`

## 배경

분석 파이프라인에서 조항 본문을 provider로 보내기 전에 마스킹을 수행했지만,
마스킹 충돌, 잔여 PII, 요청 경로 노출, 출력 PII 재생성 가능성이 함께 존재해
실행 중 데이터유출 경로가 남아 있었다.

## 결정

다음 게이트를 `run_analysis_pipeline` 직렬 경로에 적용한다.

1. 조항 본문을 `detect_and_mask`로 마스킹.
2. 마스킹 충돌 발생 시 `provider_redaction_token_collision`로 즉시 실패.
3. 마스킹 결과 잔여 PII 또는 경로 패턴 발견 시 `provider_data_minimization_failed`로 실패.
4. Provider 요청은 최소 필드만 포함 (`masked` 조항 텍스트 + evidence 후보, request metadata).
5. Provider 출력은 `analysis_result` 단계에서 요약안전 검사와 PII 스캔 동시 적용.
6. PII 의심 시 `provider_output_pii_detected`로 실패.
7. 실패는 job 상태 `failed`로 전이하고 결과 저장/확정은 수행하지 않음.

## 이유

- `provider_data_minimization_failed`와 `provider_output_pii_detected`를 통해
  최소성 위반 및 재생성 위험을 fail-closed로 처리.
- 토큰 충돌은 같은 타입 내 임의 치환 동작의 추적성을 깨뜨리므로,
  사후 분석에서 증거 복원 실패 위험이 있어 즉시 차단이 필요.
- 실패를 허용하면 compliance audit에서 추적 불가능 상태가 생기므로,
  미확정 상태에서만 중단하고 재요청을 유도.

## 결과

- TXT/PDF/OCR 경로에서 동일한 PII 게이트 설계를 공유할 수 있는 기반 확보.
- v0.7.6 비식별 데이터 기반 실제 Provider 통합 시 동일 계약을 그대로 재사용 가능.
- 아직 해결 안 된 항목:
  - 마스킹 정책 정확도 완전 보장,
  - 정교한 synthetic 토큰 map 기반 검증(운영 보안 단계),
  - 공급자별 출력 구조에 대한 항목별 신뢰도 점수 체계.
