# Secret lifecycle runbook

## 목적

ContractCheck AI가 사용하는 Secret의 분류, 서비스별 최소 주입 범위, 교체 영향과 synthetic rehearsal 절차를 제품 중립적으로 정의한다. 이 문서는 실제 Secret 값, 외부 Secret 저장소, KMS 제품 또는 production rotation 완료 기록이 아니다.

## 적용 범위

Backend runtime, MySQL 초기화 credential과 향후 Provider credential 계약에 적용한다. 실제 `.env`, 실제 credential 파일, Frontend bundle, image build argument와 source에는 Backend Secret을 넣지 않는다. `VITE_API_BASE_URL`은 공개 Frontend 설정이며 Secret이 아니다.

## Secret 분류

| 이름 | 목적 | lifecycle 특성 |
|---|---|---|
| `DATABASE_URL` | Backend DB 연결 credential 포함 가능 | 연결 전환·drain·재시작·rollback 필요 |
| `MYSQL_PASSWORD` | MySQL application user 초기화 | 기존 DB의 password rotation 수단이 아님 |
| `MYSQL_ROOT_PASSWORD` | MySQL root 초기화 | Backend에 주입 금지 |
| `JWT_SECRET` | access token 서명·검증 | 교체 즉시 기존 token 무효화 |
| `EMAIL_LOOKUP_HMAC_KEY` | email lookup hash | dual lookup 또는 migration 없이 단순 교체 금지 |
| `DATA_ENCRYPTION_KEYS_JSON` | 저장 암호화 key material | active/decrypt-only key 동시 유지 |
| `DATA_ENCRYPTION_ACTIVE_KEY_ID` | active key 선택 metadata | key material이 아니지만 keyring과 원자적으로 변경 |
| `PROVIDER_API_KEY` | 향후 Provider credential 계약 | 현재 adapter 미연결, 실제 값과 호출 금지 |

inventory는 이름, 목적, 서비스, 상태와 교체 영향만 포함하며 값·길이·원문·hash를 반환하지 않는다.

## 서비스별 주입 범위

| 서비스 | 필요한 Secret |
|---|---|
| `contract-db` | `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD` |
| `migrate` | `DATABASE_URL` |
| `api` | `DATABASE_URL`, `JWT_SECRET`, `EMAIL_LOOKUP_HMAC_KEY`, `DATA_ENCRYPTION_KEYS_JSON`, `DATA_ENCRYPTION_ACTIVE_KEY_ID` |
| `worker` | `DATABASE_URL`, `DATA_ENCRYPTION_KEYS_JSON`, `DATA_ENCRYPTION_ACTIVE_KEY_ID` |
| Frontend | 없음 |

Compose build argument에는 Secret을 전달하지 않는다. 실제 주입 수단은 배포 플랫폼 검토 후 확정하며 특정 cloud, Vault, KMS 또는 Secret manager를 이 문서가 승인하지 않는다.

## 초기 provision

1. 실제 값이 아닌 inventory 이름과 서비스 소유자를 확정한다.
2. 환경 밖의 승인된 주입 경로, 접근자, 복구 담당자와 폐기 책임을 정한다.
3. Secret은 서로 독립된 강한 값으로 provision한다.
4. startup validation은 누락, 잘못된 형식과 weak/placeholder 값을 safe error로 거부해야 한다.
5. 로그, exception, shell history, build metadata와 검증 결과에 값이 남지 않는지 확인한다.

## 교체 전 준비

- 변경 대상, 소비 서비스, 현재 상태, rollback 가능 시점과 관측 지표를 inventory로 확인한다.
- DB와 저장 암호화 교체 전에는 inventory 및 복구 가능한 backup을 별도 승인한다.
- 실제 데이터 row 재암호화나 production credential 변경은 이 runbook의 synthetic rehearsal 범위 밖이다.
- `provisioned`, `active`, `rotation_pending`, `retired`, `revoked`를 공통 운영 metadata로 사용할 수 있지만 모든 Secret에 동일 전이를 강제하지 않는다.
- `decrypt_only`는 data encryption keyring, `compatibility`는 DB/HMAC처럼 전환 호환 기간이 필요한 계약에만 사용한다.

## JWT Secret 교체

현재 refresh token은 없고 access token만 있다. 새 `JWT_SECRET`으로 API를 재시작하면 이전 key로 발급된 access token은 즉시 검증에 실패하며 사용자는 다시 로그인해야 한다. 이 동작을 허용할 maintenance window와 rollback 기준을 먼저 승인한다. old/new dual verification은 현재 계약이 아니며 임의로 추가하지 않는다.

## 데이터 암호화 keyring 교체

1. 새 32-byte key를 새 key ID와 `active` 상태로 추가한다.
2. 기존 active key는 `decrypt_only`로 유지한다.
3. `DATA_ENCRYPTION_ACTIVE_KEY_ID`를 새 active key ID로 맞춘다.
4. 새 쓰기가 새 key ID를 사용하고 기존 envelope가 decrypt-only key로 복호화되는지 확인한다.
5. 실제 row inventory, 재암호화, backup/restore 검증이 완료되기 전 기존 key를 제거·retire·revoke하지 않는다.

decrypt-only key는 신규 암호화에 사용할 수 없다. active key 누락, active key 제거 또는 unknown envelope key ID는 fail-closed다.

## Email lookup HMAC key 제한

`EMAIL_LOOKUP_HMAC_KEY`는 저장된 `email_lookup_hash`와 직접 연결된다. key를 바꾸면 같은 email의 hash가 달라지므로 현재 구현에서는 단순 교체할 수 없다. 별도 dual lookup/dual write 또는 migration 설계, 중복·불일치 차단, rollback과 cutover 검증 전에는 변경하지 않는다.

## DB credential 교체

DB 사용자 credential을 먼저 준비하고 DB가 old/new credential을 허용하는 호환 구간을 설계한다. API·worker connection drain, `DATABASE_URL` 전환, migration 연결 확인, 서비스 재시작과 rollback 순서를 플랫폼별로 검증해야 한다. Compose의 MySQL 초기화 변수 변경만으로 기존 named volume credential이 교체된다고 간주하지 않는다.

## Provider credential 후속 계약

현재 실제 Provider adapter와 credential 주입은 없다. `PROVIDER_API_KEY`는 inventory의 미래 계약일 뿐 Compose나 `.env.example`에 활성 값으로 추가하지 않는다. adapter, outbound 승인과 provider별 rotation 절차가 별도 검토되기 전 실제 credential 생성·호출을 금지한다.

## rollback 조건

- startup validation 또는 readiness 실패
- 신규 JWT 발급·검증 실패
- 기존 암호문 복호화 실패 또는 신규 key ID 불일치
- email lookup 불일치
- DB 연결 오류 증가, connection drain 실패 또는 migration 연결 실패
- Secret material이 stdout/stderr, 로그, exception 또는 결과 JSON에 나타난 정황

노출 정황이 있으면 단순 rollback으로 끝내지 않고 해당 Secret을 revoked 후보로 격리하고 별도 incident 절차로 재발급 여부를 판단한다.

## 폐기·revocation

사용 중인 token, 암호문, hash 또는 DB 연결이 없다는 inventory 증거 없이 Secret을 삭제하지 않는다. 특히 decrypt-only encryption key는 모든 관련 row 재암호화와 backup 검증 전 폐기 금지다. retired는 정상 사용 종료, revoked는 노출 또는 신뢰 상실로 인한 사용 금지를 뜻하며 실제 폐기 기록은 외부 운영 통제에서 관리한다.

## synthetic rehearsal

저장소 루트에서 다음을 실행한다.

```powershell
.\backend\.venv\Scripts\python.exe scripts\secret_rotation_rehearsal.py
```

rehearsal은 runtime에서 생성한 synthetic 값만 사용해 필수/weak Secret 거부, JWT 교체 전후 token 영향, active/decrypt-only keyring 전환과 HMAC hash 변경을 확인한다. 실제 DB, 실제 row, 외부 network와 실제 credential은 사용하지 않는다. 출력은 단계, `PASS`/`FAIL`, safe error code뿐이다.

## 검증 체크리스트

- `scripts/validate_secret_boundaries.py`가 tracked file 검사를 통과한다.
- `.env.example`에는 변수 이름과 빈 값만 있다.
- Compose 주입 범위가 위 표와 일치하고 build args가 없다.
- Backend Secret이 Frontend에 전달되지 않는다.
- 전체 Backend 테스트, Ruff와 `pip check`가 통과한다.
- Compose config가 필수값을 주입한 검증 환경에서 통과한다.
- rehearsal 출력과 structured log에 Secret material이 없다.

## 금지 사항

- 실제 `.env` 또는 credential 파일 생성·commit
- Secret 원문, DB URL, token, key material, hash 원문 출력
- source, Frontend 변수, image layer 또는 build argument에 Secret 포함
- 실제 production rotation, 실제 row 재암호화 또는 실제 DB credential 변경
- 특정 외부 Secret/KMS 제품을 검증 없이 운영 표준으로 선언

## 미완료 범위

외부 Secret 저장소, KMS, 접근 승인·rotation 자동화, 실제 DB dual credential 절차, 실제 row inventory·재암호화·backup/restore와 Provider credential 계약은 미확정이다. 이 문서와 synthetic rehearsal은 production 준비 완료나 실제 계약서·개인정보 사용 승인을 의미하지 않는다.
