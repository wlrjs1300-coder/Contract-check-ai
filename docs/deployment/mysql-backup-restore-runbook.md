# MySQL backup and restore runbook

## 목적

ContractCheck AI의 MySQL application schema와 암호화된 application row를 backup하고 격리 DB에 restore한 뒤 schema, Alembic head, readiness와 핵심 관계를 검증하는 제품 중립 절차를 정의한다. 이 문서는 실제 production backup·restore 완료 기록이나 특정 cloud·managed DB·object storage 제품 승인이 아니다.

## 적용 범위

현재 MySQL 8.4, Alembic migration `0001`~현재 repository head, API·worker·migrate 분리와 application-level AES-256-GCM 저장 암호화에 적용한다. 실제 계약서, 실제 개인정보, 실제 credential과 실제 운영 DB를 rehearsal에 사용하지 않는다.

## 전제 조건

- backup 대상 DB와 환경이 명시적으로 식별되어야 한다.
- schema migration과 application write를 조정할 maintenance 또는 일관성 경계가 승인되어야 한다.
- application credential과 admin/root credential의 역할이 분리되어야 한다.
- artifact를 repository 밖 격리 임시 디렉터리에 만들 권한과 cleanup 방법이 확인되어야 한다.
- 복구 가능한 backup, Secret lifecycle, 담당자와 rollback/forward-fix 판단 권한은 실제 운영 전에 별도 승인되어야 한다.

## Backup 대상

- application schema와 table
- 현재 `alembic_version`
- 암호화된 application row
- 복구에 필요한 index, unique/check constraint와 foreign key

inventory API와 rehearsal 결과는 category와 검증 상태만 반환하며 row 내용, dump payload, credential, 환경값 또는 경로를 반환하지 않는다. application-level 암호화 필드는 dump에서도 envelope ciphertext 상태로 유지되지만 DB의 모든 필드가 application-level 암호화된 것은 아니다. 따라서 실제 backup artifact 자체에도 별도 저장 암호화와 접근 통제가 필요하다.

## Backup 제외 대상

- extraction temp 원본과 임시 filesystem
- application·access·database log
- host local path와 shell history
- Secret, 환경변수 값과 DB credential
- Provider payload 또는 실제 계약서 원문을 별도 export한 파일

temp 원본 경로는 DB backup 대상과 분리한다. raw temp 파일을 DB dump나 archive에 추가하지 않는다.

## 권한과 Secret 경계

`migrate`는 application `DATABASE_URL`만 사용하고 MySQL root password를 받지 않는다. API와 worker에도 root/admin credential을 주입하지 않는다. backup 실행 주체는 schema와 row를 일관되게 읽는 최소 권한을 가져야 하며, root 사용을 기본값으로 가정하지 않는다. restore 대상 생성·권한 부여에 필요한 admin 역할과 dump를 읽고 쓰는 application 역할은 분리한다.

credential을 명령 인자, dump filename, stdout/stderr 또는 log에 기록하지 않는다. rehearsal은 격리 container의 환경에서 synthetic credential만 사용하며 결과에는 단계, `PASS`/`FAIL`, safe error code만 남긴다.

## Backup artifact 경계

- repository 밖 OS 임시 디렉터리에만 생성한다.
- repository 내부, path traversal, symlink와 reparse point를 거부한다.
- 허용 확장자, 비어 있지 않음과 최대 크기를 검증한다.
- 실제 경로와 artifact 내용을 공개 결과에 출력하지 않는다.
- 성공·실패 모두 종료 시 artifact와 임시 환경 파일을 삭제한다.
- `.gitignore`, `.dockerignore`와 `validate_backup_artifacts.py`로 dump·backup artifact의 source/image 유입을 차단한다.

named volume은 container 재생성 사이의 persistence 수단이지 독립적인 backup artifact가 아니다. volume 손상, 잘못된 삭제와 동일 host 장애에 대비한 별도 복구 사본을 제공하지 않는다.

## Backup 절차

1. 대상, backup 가능성, schema write 조정과 복구 담당자를 확인한다.
2. DB health와 현재 Alembic revision을 확인한다.
3. repository 밖 격리 artifact 경로를 만들고 권한·link·size 정책을 확인한다.
4. MySQL 공식 client의 일관성 옵션을 사용해 schema, row, index·constraint와 `alembic_version`을 dump한다.
5. command exit code 0, artifact 존재·비어 있지 않음·최대 크기를 확인한다.
6. 실제 내용을 출력하지 않고 synthetic marker가 plaintext로 노출되지 않는지 rehearsal에서 확인한다.
7. restore 검증이 끝날 때까지 artifact를 격리하고 접근을 제한한다.

실제 환경의 transaction 일관성, table lock, binary log와 대용량 dump 영향은 플랫폼별 후속 검증이 필요하다.

## Restore 절차

1. 원본 DB·container·volume과 다른 빈 격리 DB를 준비한다.
2. 대상이 명시적으로 빈 synthetic 또는 승인된 restore 대상인지 확인한다.
3. 검증된 artifact를 공식 MySQL client로 restore하고 exit code 0을 확인한다.
4. repository head와 restored `alembic_version`을 비교한다.
5. schema parity, 필수 table·index·constraint와 owner foreign-key 관계를 확인한다.
6. 민감 필드가 유효한 encrypted envelope이며 승인된 keyring으로만 복호화되는지 확인한다.
7. readiness service를 실행하고 synthetic 핵심 query 및 신규 write를 확인한다.
8. 검증 종료 후 restore DB, 격리 volume, network와 artifact를 삭제한다.

restore는 원본 DB나 기존 Compose `mysql-data` volume을 수정하지 않아야 한다.

## Migration 실행 순서

1. backup 가능성과 복구 경계를 확인한다.
2. DB health를 확인한다.
3. migration one-shot으로 `alembic upgrade head`를 실행한다.
4. exit code 0을 확인한다.
5. DB revision이 repository 단일 head와 일치하는지 확인한다.
6. API를 시작한다.
7. worker를 시작한다.
8. `/ready`와 핵심 synthetic query를 확인한다.

Compose의 `service_completed_successfully` dependency는 migration 실패 시 API·worker 시작을 차단한다. 이 dependency를 우회해 서비스를 수동 시작하지 않는다.

## 실패·중단 조건

- backup command 또는 artifact validation 실패
- migration exit code가 0이 아님
- Alembic head 불일치 또는 revision table 누락
- restore command 실패
- schema/index/constraint/owner 관계 불일치
- encrypted envelope 검증·복호화 실패 또는 plaintext 노출
- readiness 실패 또는 신규 write 실패
- artifact cleanup 실패

실패를 성공으로 기록하지 않고 API·worker 시작 또는 production 전환을 중단한다. raw DB 오류나 dump output을 공개 결과에 복사하지 않는다.

## Rollback·forward-fix 판단

Alembic downgrade를 자동 rollback으로 사용하지 않는다. 특히 scalar metadata cutover downgrade는 populated DB에서 명시적으로 차단되고, 암호화 row와 schema 변화는 단순 downgrade로 안전하게 복구된다고 보장할 수 없다.

- migration이 commit 전 실패했고 revision이 변하지 않았다면 원인을 수정한 뒤 현재 revision 확인 후 idempotent 재실행을 검토한다.
- 일부 schema가 적용됐거나 write가 시작됐다면 자동 재실행하지 않고 revision과 DB 상태를 먼저 inventory한다.
- 안전하고 additive한 수정은 forward-fix를 검토한다.
- 호환 불가능하거나 데이터 정합성이 깨졌다면 승인된 backup에서 격리 restore 검증 후 복구 전환을 판단한다.

실제 production rollback 선택은 데이터 손실 허용 범위, write freeze, backup 시점과 운영 승인 없이는 확정하지 않는다.

## Restore 검증

- application model table이 모두 존재하고 예상하지 않은 application table이 없음
- restored Alembic revision이 repository head
- encrypted user email과 document filename envelope가 유효
- user-document ownership foreign key와 join 결과가 유지
- email lookup unique index 등 필수 index·constraint 유지
- readiness 성공
- synthetic 핵심 row count·query 성공
- restore 후 신규 encrypted write 성공
- 실제 plaintext 비노출

## Cleanup

rehearsal은 고유 container, network, source/restore volume, app image와 OS 임시 디렉터리를 사용한다. 종료 성공 여부와 관계없이 이 고유 이름만 정리한다. 기존 Compose container, network와 `mysql-data` volume은 조회·삭제·재사용하지 않는다. cleanup 실패는 별도 FAIL이며 수동 확인 전 완료로 기록하지 않는다.

## Synthetic rehearsal

저장소 루트에서 다음을 실행한다.

```powershell
.\backend\.venv\Scripts\python.exe scripts\mysql_backup_rehearsal.py
.\backend\.venv\Scripts\python.exe scripts\mysql_restore_rehearsal.py
```

두 스크립트는 host 3306을 publish하지 않고 고유 Docker network와 volume을 사용한다. runtime에서 생성한 synthetic credential, synthetic user/document와 encryption key만 사용한다. backup script는 migration, synthetic seed와 artifact 경계를 검증하고, restore script는 별도 DB restore 후 Alembic head, schema, envelope, ownership, readiness와 신규 write까지 검증한다.

## 검증 체크리스트

- `scripts/validate_secret_boundaries.py`
- `scripts/validate_backup_artifacts.py`
- 신규 backup contract/rehearsal 집중 테스트
- 전체 Backend 테스트와 Ruff
- `pip check`
- `docker compose config --quiet`
- 격리 synthetic backup 및 restore rehearsal
- `git diff --check`, 공개 안전성 검색과 `git status --short`

## 금지 사항

- 실제 운영 DB 또는 실제 계약서·개인정보 사용
- 실제 production backup 생성·restore
- 기존 `mysql-data` volume 삭제·mount·재사용
- 실제 dump, credential 또는 artifact commit
- artifact 내용·경로, DB URL, Secret과 raw command 오류 출력
- 자동 Alembic downgrade rollback
- retention 기간, PITR, 무중단 migration과 특정 제품을 임의로 확정

## 미완료 범위

실제 retention·법적 보존 기간, offsite 저장소, artifact 저장 암호화와 key custody, PITR, binary log, 대용량 성능, 무중단 migration, disaster recovery RTO/RPO, managed DB 제품과 production 책임자는 미확정이다. synthetic rehearsal 통과는 실제 backup/restore 완료나 실제 데이터 사용 승인이 아니다.
