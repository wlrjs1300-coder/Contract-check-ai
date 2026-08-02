# Synthetic pilot runbook

## 목적과 승인 경계

이 절차는 production급 애플리케이션 경계를 합성 계정과 UTF-8 TXT 합성 계약으로
검증하는 제한적 rehearsal이다. production 배포, 실제 계약서·개인정보 처리,
실제 Provider 또는 외부 observability 사용 승인이 아니다.

`APP_ENV=pilot`은 HTTPS, Host, CORS, Secret, MySQL, debug/reload, trusted proxy와
request boundary를 production과 동일하게 fail-closed로 검사한다. 차이는
명시적인 `ANALYSIS_PROVIDER=synthetic`만 허용한다는 점이다. production에서는
synthetic와 fake Provider가 계속 금지된다. synthetic OCR/PDF adapter는 test
전용이며 pilot에서는 사용할 수 없다.

## 환경 inventory

공개 routing 설정은 `APP_ENV`, `ANALYSIS_PROVIDER`, `PILOT_PROJECT_NAME`,
`PILOT_API_HOST`, `PILOT_API_PORT`, CORS/proxy/Host와 request boundary 변수다.

MySQL password와 `DATABASE_URL`, JWT, data encryption keyring, email lookup
HMAC key는 runtime에서만 생성하고 untracked 임시 env file로 주입한다. 실제
`.env`를 만들거나 읽지 않으며 Secret 값은 출력하지 않는다.

## Compose와 migration gate

`compose.yaml`과 `compose.pilot.yaml`을 고유 project name으로 결합한다. override는
DB host 3306 publish를 제거하고 pilot 전용 named volume과 network를 사용한다.
기존 Compose volume, container와 network를 재사용하거나 삭제하지 않는다.

실행 순서는 DB health, migration one-shot, API, worker이다. API와 worker는
migration 성공 전에 시작하지 않는다. API는 기존 `--no-proxy-headers`를
유지하고 애플리케이션의 trusted proxy 검증만 사용한다.

```powershell
python scripts/validate_synthetic_pilot_boundaries.py
python scripts/synthetic_pilot_rehearsal.py
```

## Smoke와 연계 검증

rehearsal은 health/readiness, HTTPS와 Host, forwarded scheme, CORS, 합성 사용자
두 명의 등록·로그인·`/auth/me`, UTF-8 TXT upload, owner read, cross-owner
일반 404, analysis job 처리와 결과 조회를 검사한다. 실제 Provider endpoint나
credential은 사용하지 않는다.

observability, Secret lifecycle, MySQL backup과 restore rehearsal을 하위 절차로
호출한다. API와 worker log는 메모리에서만 검사하고 합성 email/password/token,
filename/body marker, ID, DB URL, Secret/key material이 발견되면 중단한다.
로그 전문, Docker inspect 원문, response body 전문과 raw exception은 출력하거나
저장소 artifact로 남기지 않는다.

## 실패·중단과 폐기

Docker/Compose, DB health, migration/Alembic, health/readiness, ingress/CORS,
Secret/SQLite/provider/OCR 경계, 인증·ownership·upload·worker/job/result,
연계 rehearsal, 로그 비노출 또는 cleanup 중 하나라도 실패하면 최종 상태는
`FAIL`이다. 출력은 단계, PASS/FAIL, safe error code와 aggregate count로 제한한다.

성공과 실패 모두에서 고유 project에 `down --volumes --remove-orphans`를 실행하고
runtime 임시 directory와 env file을 제거한다. cleanup 실패도 전체 실패다.
기존 Compose 자원, 사용자 `.env`, 작업 파일과 tracked source는 삭제하지 않는다.

증적에는 aggregate 결과와 safe code만 기록한다. 실제 값, 로컬 경로, raw log,
dump 또는 stack trace를 포함하지 않는다.

## 완료로 주장할 수 없는 항목

- production 배포와 production 전환
- 실제 계약서·개인정보 사용 승인
- 실제 외부 Provider 승인
- 실제 Secret manager/KMS 운영
- 실제 외부 observability와 alert channel
- retention, on-call, incident response, WORM/hash-chain 완료
