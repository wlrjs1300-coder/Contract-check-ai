# ContractCheck AI 배포 준비 조건

## 문서 목적

현재 기술 검증 MVP를 외부 환경의 제한적 합성 데이터 파일럿 후보로 검토하기 위한 플랫폼 중립 기준을 정의한다. 이 문서는 특정 플랫폼 선정, production 배포 완료, 실제 계약서·개인정보 처리 승인 또는 실제 외부 Provider 사용 승인을 의미하지 않는다.

현재 구현의 기준선은 v0.8.0 release closure와 v0.9.0 운영 준비 로드맵이다. 과거 SQLite와 초기 분석 실행 구조 중심의 배포 문서는 당시 기록이며 현재 실행 구조의 근거로 사용하지 않는다.

## 현재 배포 가능 범위

현재 코드는 다음 요소를 갖춘 제한적 합성 데이터 파일럿 후보이다.

- React 정적 Frontend build와 공개 `VITE_API_BASE_URL`
- FastAPI API와 별도 DB polling worker
- MySQL 8.4 Compose service와 named volume
- Alembic revision `0001`~`0006` 및 migration one-shot
- JWT 인증, 사용자별 ownership과 교차 사용자 접근 차단
- AES-256-GCM 저장 암호화, keyring과 HMAC email lookup
- TXT/PDF·이미지 입력 경계, 임시 원본 cleanup과 orphan sweep
- durable analysis jobs, lease·heartbeat·retry·stale recovery
- `/health` liveness와 DB·migration을 검사하는 `/ready`
- production runtime 설정 fail-closed와 structured operational logging

로컬 Docker Desktop에서 MySQL, migration, API와 worker를 연결한 synthetic smoke는 완료됐다. 이는 실제 배포 환경의 HTTPS, 복구성, Secret custody, 관측성과 운영 책임을 검증한 결과가 아니다.

## 현재 미완료 또는 미확정 범위

- 실제 배포 플랫폼, 운영 주소와 조직별 운영 책임
- 실제 HTTPS/TLS 종단, proxy 배치와 network 접근 통제 검증
- 외부 Secret 저장소, 접근 검토, 교체·폐기·복구 절차
- MySQL backup·restore, 보존·폐기와 복구 rehearsal
- audit/security event 체계, 외부 로그 수집, 지표·경보와 보존
- 실제 외부 Provider adapter, Provider 데이터 처리 조건과 credential
- 실제 계약서·실제 개인정보 사용 승인
- 사용자 삭제·탈퇴·만료 파기와 backup 재등장 방지
- 다중 replica 전역 rate limit과 독립 보안 평가

## 개발 실행과 production 실행의 구분

개발·테스트에서는 `DATABASE_URL`이 없으면 SQLite 기본값을 사용할 수 있고 일부 경계 설정에 안전한 기본값이 적용된다. 이는 로컬 개발 편의를 위한 동작이다.

`APP_ENV=production` 또는 `prod`에서는 다음 조건을 fail-closed로 검사한다.

- `DATABASE_URL`이 명시되고 SQLite가 아닐 것
- JWT, data encryption keyring과 email lookup HMAC key가 유효하고 약한 값이 아닐 것
- `CORS_ALLOWED_ORIGINS`가 명시된 비-local origin이며 wildcard가 아닐 것
- debug와 reload control이 활성화되지 않을 것
- synthetic/fake/default placeholder가 아닌 허용된 Provider 상태일 것
- 업로드·추출·페이지·rate limit 경계값이 모두 명시되고 허용 범위 안일 것
- `REQUIRE_HTTPS=true`이고 `ALLOWED_HOSTS`가 명시될 것
- proxy header 신뢰를 켜면 wildcard가 아닌 `TRUSTED_PROXY_CIDRS`가 존재할 것

현재 production validation이 통과할 수 있다는 사실은 실제 Provider가 연결되거나 production 배포가 승인됐다는 뜻이 아니다.

## 환경변수

### Compose에서 요구하는 변수

| 분류 | 이름 | 사용 서비스 | 운영 원칙 |
|---|---|---|---|
| 실행 설정 | `APP_ENV` | Compose가 API·worker·migrate에 `production` 설정 | Secret 아님 |
| DB 설정/Secret | `DATABASE_URL` | API, worker, migrate | credential 포함 가능, Backend 전용 |
| DB 초기화 | `MYSQL_DATABASE`, `MYSQL_USER` | MySQL | 공개 Frontend에 노출하지 않음 |
| DB Secret | `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD` | MySQL | 전용 Secret 주입 필요 |
| 암호화 Secret | `DATA_ENCRYPTION_KEYS_JSON`, `DATA_ENCRYPTION_ACTIVE_KEY_ID` | API, worker | 실제 key 값 기록·로그 금지 |
| 인증 Secret | `JWT_SECRET` | API | 강한 독립 값 사용 |
| lookup Secret | `EMAIL_LOOKUP_HMAC_KEY` | API | 암호화 key와 분리 |
| 공개 운영 설정 | `CORS_ALLOWED_ORIGINS` | API, migrate | 실제 HTTPS Frontend origin만 허용 |
| Provider 설정 | `ANALYSIS_PROVIDER` | API, worker, migrate | production에서 synthetic/fake 차단 |
| ingress 설정 | `TRUST_PROXY_HEADERS` | API | 기본 불신, production 명시값 필수 |
| ingress 설정 | `TRUSTED_PROXY_CIDRS` | API | 신뢰 활성화 시 IP/CIDR 필수, wildcard 금지 |
| ingress 설정 | `REQUIRE_HTTPS` | API | production에서 `true` 필수 |
| ingress 설정 | `ALLOWED_HOSTS` | API | 명시 Host allowlist, wildcard 금지 |
| 입력 경계 | `MAX_UPLOAD_BYTES`, `MAX_EXTRACTED_CHARACTERS`, `MAX_DOCUMENT_PAGES` | API, worker, migrate | 허용 상한 안의 명시값 |
| 요청 제한 | `RATE_LIMIT_LOGIN`, `RATE_LIMIT_REGISTER`, `RATE_LIMIT_UPLOAD`, `RATE_LIMIT_EXTRACTION`, `RATE_LIMIT_ANALYSIS_JOB`, `RATE_LIMIT_WINDOW_SECONDS` | API, worker, migrate | 현재 limiter는 프로세스 단위 |

### 코드에 존재하는 선택 설정

| 이름 | 목적 | 비고 |
|---|---|---|
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | access token 만료 | 코드의 제한 범위 적용 |
| `ANALYSIS_WORKER_ID`, `ANALYSIS_WORKER_POLL_SECONDS` | worker 식별·poll 주기 | 기본값 존재 |
| `ANALYSIS_JOB_LEASE_SECONDS`, `ANALYSIS_JOB_HEARTBEAT_SECONDS`, `ANALYSIS_JOB_MAX_ATTEMPTS` | durable job lease·retry | 기본값 존재 |
| `EXTRACTION_TEMP_ROOT` | 격리 temp root | 실제 운영 filesystem 경계 검토 필요 |
| `EXTRACTION_ORPHAN_TTL_SECONDS`, `EXTRACTION_ORPHAN_CLEANUP_RETRY_COUNT`, `EXTRACTION_ORPHAN_CLEANUP_RETRY_DELAY_SECONDS` | orphan sweep | 제한된 기본값 존재 |
| `OCR_ADAPTER`, `TESSERACT_CMD` | OCR adapter·실행 경로 | 환경별 의존성 검증 필요 |
| `DEBUG`, `UVICORN_RELOAD` | 개발 control | production에서 활성화 금지 |
| `VITE_API_BASE_URL` | 브라우저의 API base URL | 공개 HTTPS URL, Secret 금지 |

환경변수 이름만 문서화한다. 실제 값은 source, build argument, image layer, Frontend bundle, 명령 기록과 로그에 넣지 않는다. 외부 Secret 저장·주입 제품과 rotation 절차는 v0.9.0 후속 PR에서 결정한다.

## 배포 및 시작 순서

플랫폼과 무관하게 다음 순서를 유지한다.

1. 합성 데이터 전용 환경인지 확인하고 실제 데이터 입력을 차단한다.
2. HTTPS/trusted proxy, 네트워크와 Secret 주입이 아직 승인되지 않았다면 시작하지 않는다.
3. MySQL을 시작하고 DB health가 정상인지 확인한다.
4. migration one-shot으로 `alembic upgrade head`를 실행한다.
5. migration exit code가 0이고 DB revision이 현재 head인지 확인한다.
6. API를 시작한 뒤 worker를 시작한다.
7. `/health`, `/ready`, API·worker 상태와 restart loop 부재를 확인한다.
8. 합성 계정과 합성 문서만 사용해 인증·ownership·job·결과 조회 smoke를 수행한다.
9. 로그에서 Secret, authorization header, email·filename·본문·raw exception 비노출을 확인한다.

DB health 또는 migration이 실패하면 API와 worker를 시작하지 않는다. `/ready`가 503이면 원인을 분석하고 배포 성공으로 기록하지 않는다. worker가 polling을 시작하지 않거나 restart loop에 들어가도 파일럿을 중단한다.

## Health와 readiness

- `/health`는 API process가 응답하는지 확인하는 liveness endpoint이며 `{"status":"ok"}`를 반환한다. DB나 migration 상태를 보장하지 않는다.
- `/ready`는 DB에 `SELECT 1`을 수행하고 `alembic_version`이 현재 단일 head와 일치하는지 확인한다. 정상 시 `{"status":"ready"}`, 실패 시 본문을 최소화한 503 `{"status":"not_ready"}`를 반환한다.
- worker는 HTTP endpoint를 제공하지 않는다. process 상태, restart count와 `analysis_worker_started` 등 structured event로 polling 시작을 확인한다.
- Compose는 DB health 이후 migration, migration 성공 이후 API·worker라는 dependency를 가진다.

## HTTPS, reverse proxy와 CORS

애플리케이션의 플랫폼 중립 ingress 계약은 다음과 같다.

- Compose는 Uvicorn의 proxy header 처리를 `--no-proxy-headers`로 비활성화한다. 원래 연결 peer를 보존해 애플리케이션 trust 판단과 중복되지 않게 한다.
- `TRUST_PROXY_HEADERS=false`가 기본 정책이다. 이때 `X-Forwarded-For`, `X-Forwarded-Proto`, `X-Forwarded-Host`와 표준 `Forwarded`는 scheme, client context와 Host 판정에 영향을 주지 않는다.
- 신뢰를 활성화하면 peer가 `TRUSTED_PROXY_CIDRS` 중 하나에 포함될 때만 `X-Forwarded-For`와 `X-Forwarded-Proto`를 해석한다. wildcard, 빈 항목, malformed IP/CIDR은 거부한다.
- forwarded chain은 512자와 8 hop으로 제한한다. 오른쪽에서 왼쪽으로 신뢰 proxy를 건너뛴 첫 주소를 rate-limit용 보조 client context로 사용하며 malformed chain은 전체를 무시한다.
- `X-Forwarded-Host`는 신뢰 여부와 관계없이 사용하지 않는다. Host는 직접 `Host` header를 `ALLOWED_HOSTS`와 비교하고 wildcard를 허용하지 않는다. CORS origin allowlist와 Host allowlist는 별개다.
- `REQUIRE_HTTPS=true`이면 직접 TLS scheme 또는 신뢰 proxy의 `X-Forwarded-Proto: https`만 인정한다. 그 외 요청은 method/body를 다른 위치로 보내지 않도록 redirect하지 않고 426으로 거부한다.
- Compose의 container-local `/health`와 `/ready` 호출은 forwarded metadata를 사용하지 않는 loopback direct HTTP 호출에 한해 HTTPS·Host 검사 예외다. 다른 endpoint, 비-loopback 요청과 forwarded metadata를 사용한 요청에는 예외가 없다.
- client context는 공개 rate-limit bucket의 보조값일 뿐 인증·인가나 사용자 identity로 사용하지 않는다.

실제 TLS 인증서, 종단 위치, proxy CIDR과 network 접근 통제는 배포 환경에서 별도 확정·검증해야 한다. proxy는 외부에서 기존 forwarded header를 제거하고 검증된 값만 설정해야 한다. 실제 Frontend HTTPS origin의 CORS와 proxy/platform request body limit도 함께 검증한다. 특정 reverse proxy나 hosting 제품은 선정하지 않는다.

Compose 외 방식으로 Uvicorn을 실행할 때도 `--no-proxy-headers`를 명시해야 한다. 현재 Dockerfile 기본 CMD를 직접 사용하는 배포는 이 옵션을 포함하도록 실행 명령을 override하지 않으면 승인된 ingress 계약으로 간주하지 않는다.

## DB, migration과 복구

MySQL 연결과 migration 실행 기반은 구현됐지만 backup/restore 운영 절차는 미완료다. 제한적 파일럿 전에 synthetic DB를 사용해 다음을 별도 검증해야 한다.

- backup 대상과 temp 원본 경로의 backup 제외
- backup 암호화, 접근 권한, 보존·폐기 책임
- 격리 DB restore와 Alembic head 확인
- restore 후 `/ready`, ownership과 암호화 row 정합성
- migration 실패 시 중단·복구 판단과 재실행 조건

실제 데이터 backfill, 무중단 migration, point-in-time recovery와 managed DB 제품은 확정되지 않았다.

제품 중립 backup·restore 순서, repository 밖 artifact 경계, migration 실패 중단과 downgrade 금지는 [MySQL backup/restore runbook](mysql-backup-restore-runbook.md)을 따른다. 격리 synthetic rehearsal은 별도 source/restore DB에서 Alembic head, schema·index·constraint, encrypted envelope, ownership, readiness와 신규 write를 확인하며 기존 Compose `mysql-data` volume을 사용하지 않는다.

이 rehearsal은 실제 retention, offsite backup, artifact 저장 암호화·key custody, PITR, 대용량 성능 또는 production restore 완료를 의미하지 않는다.

## Secret lifecycle

서비스별 최소 주입 범위, JWT·data encryption keyring·email lookup HMAC·DB credential의 서로 다른 교체 영향과 synthetic rehearsal은 [Secret lifecycle runbook](secret-lifecycle-runbook.md)을 따른다. API는 DB·JWT·HMAC·encryption keyring을, worker는 DB·encryption keyring을, migration은 DB 연결만 사용한다. MySQL 초기화 password는 DB 서비스에만 주입하며 Backend Secret을 Frontend나 build argument로 전달하지 않는다.

tracked-file validation과 synthetic rehearsal이 존재해도 외부 Secret 저장소, 실제 credential rotation, 실제 row 재암호화와 폐기 절차가 완료된 것은 아니다. 실제 `.env`, 실제 Secret 값과 특정 Secret/KMS 제품은 저장소에 추가하거나 이 문서에서 임의로 확정하지 않는다.

## 로그와 관측성

현재 구현은 JSON structured operational log와 request correlation을 제공한다. HTTP 완료, ingress 거부, upload 완료·거부, extraction 거부, temp cleanup 실패, rate limit 차단, worker 시작·종료·job 완료·실패가 현재 확인된 이벤트다. 민감 extra key를 거부하고 문자열 식별자를 제한된 문자와 길이로 정규화한다. raw forwarded header, 전체 chain, peer/client IP와 Host는 로그 extra에 허용하지 않는다.

인증 성공·실패와 권한 거부를 목적별 audit/security event로 분류하는 체계, 외부 수집, 보존, 무결성, 접근 통제, 지표·경보는 미완료다. 외부 수집 도구를 도입할 때 request body, authorization header, email, filename, 계약 내용, Provider payload와 raw exception 수집을 차단해야 한다.

## 파일과 데이터 경계

- TXT 직접 분석 흐름은 최대 1 MiB로 제한된다.
- extraction 경로는 production에 명시되는 최대 upload bytes와 코드 상한 20 MiB 중 작은 값을 적용한다.
- PDF는 최대 100페이지이며 추출 문자 상한도 별도 적용한다.
- 임시 원본은 격리된 무작위 request directory에서 처리하고 성공·실패 cleanup과 startup orphan sweep을 수행한다.
- DB에는 암호화된 민감 계약·추출·분석 데이터가 저장될 수 있다. 저장 암호화가 보존·삭제 정책을 대체하지 않는다.

## 제한적 합성 데이터 smoke 기준

- Frontend 정적 자산과 공개 API URL 확인
- MySQL healthy와 migration exit code 0
- Alembic current revision이 repository head와 일치
- API running/healthy, `/health` 200과 `/ready` 200
- worker running, polling 시작과 restart loop 부재
- 합성 사용자 등록·로그인과 JWT 보호 route 확인
- 두 합성 사용자 사이 document·extraction·analysis 접근 차단
- upload·extraction 경계, durable job 생성·처리·결과 조회
- DB 단절 또는 revision mismatch에서 `/ready` 503
- 로그의 credential·token·key·본문·filename·로컬 경로 비노출
- 종료 후 임시 자원 cleanup과 무관 resource 비영향

실제로 실행하지 않은 항목은 통과로 기록하지 않는다.

## 실제 데이터 사용 게이트

v0.9.0 PR-1은 문서 정합화 작업이며 실제 데이터 사용 승인이 아니다. 실제 계약서 또는 실제 개인정보를 사용하려면 별도로 다음을 확정하고 검증해야 한다.

- 처리 목적·법적 근거, 사용자 고지와 승인 주체
- 보존·삭제 기간, 사용자 삭제·탈퇴와 backup 재등장 방지
- HTTPS/trusted proxy와 접근 통제 검토
- Secret custody·rotation·폐기와 incident response
- audit/security event, 외부 관측성의 개인정보 차단
- 실제 Provider 사용 시 데이터 처리 조건과 외부 전송 승인
- 독립 보안·개인정보 검토

그 전에는 명백한 합성 계정·합성 계약 데이터만 사용한다.

## 준비 판단

현재 저장소는 **플랫폼과 운영 통제를 추가 검증할 제한적 합성 데이터 파일럿 후보**다. 애플리케이션의 HTTPS·Host·trusted proxy 계약은 구현됐지만 실제 TLS 종단과 proxy/network 배치는 검증되지 않았다. 외부 Secret 운영, backup/restore, 외부 observability와 실제 배포 플랫폼도 미완료이므로 production 배포 또는 실제 데이터 처리가 준비됐다고 판단하지 않는다.

## PR-5 감사·관측성 현재 상태

operational/audit/security event schema, 비가역 actor 파생값, process-local
metric과 synthetic alert rehearsal이 구현됐다. 허용·금지 필드, event code와
collector 실패 정책은 `audit-observability-runbook.md`를 따른다.

외부 collector 제품, 실제 보존 기간, WORM/hash-chain, 실제 alert channel,
on-call·incident response는 미선정 또는 미연동이다. process-local metric은
multi-replica 집계를 보장하지 않으며 synthetic threshold는 production
승인값이 아니다. 실제 production observability 완료나 실제 계약서·개인정보
사용 승인을 주장하지 않는다.
