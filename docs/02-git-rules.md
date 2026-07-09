# Git 운영 규칙

## 1. 목적

본 문서는 ContractCheck AI 프로젝트의 브랜치, 커밋, PR, 태그 운영 규칙을 정의한다.

GitHub 저장소를 포트폴리오로 활용하기 위해, 모든 작업은 버전 단위로 관리하고 검증 기록을 남긴다.

## 2. 기본 브랜치

| 브랜치 | 역할 |
|---|---|
| main | 안정 버전 기록용 브랜치 |
| develop | 작업 누적 및 통합 검토용 브랜치 |
| docs/* | 문서 작업 |
| feature/* | 기능 구현 |
| fix/* | 버그 수정 |
| chore/* | 설정/환경 작업 |
| security/* | 보안 관련 작업 |
| release/* | 릴리스 준비 |

기본 운영은 `develop` 기준으로 작업 브랜치를 만들고 PR 병합하는 방식으로 진행한다.

`main`은 안정 버전 기록용으로 유지한다.
큰 단계가 안정적으로 마무리되면 `develop`에서 `main`으로 PR을 생성하고, 검토 후 병합한다.

## 3. 브랜치 이름 규칙

```text
<type>/v<major>.<minor>.<patch>-<short-description>
```

예시:

```text
docs/v0.0.1-project-direction
docs/v0.0.2-tech-stack
docs/v0.0.3-git-rules
security/v0.0.4-security-rules
feature/v1.0.1-auth
feature/v1.0.2-contract-upload
feature/v1.0.4-pii-masking
fix/v1.0.7-response-parse-error
release/v1.0.0-mvp
```

## 4. 커밋 메시지 규칙

커밋 메시지는 다음 형식을 사용한다.

```text
<type>: <작업 내용>
```

예시:

```text
docs: add v0.0.1 project direction checklist
docs: add git branch and tag rules
chore: initialize project repository
feat: add contract upload endpoint
security: prevent original contract text logging
fix: handle empty extracted text
test: add pii masking test cases
```

## 5. 커밋 타입

| 타입 | 의미 |
|---|---|
| docs | 문서 작성/수정 |
| feat | 기능 추가 |
| fix | 버그 수정 |
| chore | 설정, 환경, 패키지 관리 |
| refactor | 리팩터링 |
| test | 테스트 코드 |
| security | 보안 관련 수정 |
| style | UI/CSS/포맷 수정 |

## 6. PR 제목 규칙

PR 제목은 커밋 메시지와 같은 형식을 사용한다.

```text
<type>: <작업 내용>
```

예시:

```text
docs: complete v0.0.1 project direction checklist
docs: add review workflow rules
docs: add v0.0.2 repository rules checklist
security: update commit protection rules
feat: add contract upload flow
fix: handle empty extracted text
```

PR 본문에는 다음 내용을 작성한다.

- 작업 목적
- 작업 내용
- 변경 파일
- 검증 내용
- 보안 체크
- 남은 이슈

## 7. 태그 규칙

태그는 검증이 끝나고 `main`에 병합된 버전에만 생성한다.

태그 형식:

```text
v<major>.<minor>.<patch>
```

예시:

```text
v0.0.1
v0.0.2
v0.1.1
v1.0.4
```

태그는 반드시 `main` 브랜치 최신 커밋 기준으로 생성한다.
작업 브랜치나 `develop` 브랜치에서 직접 태그를 생성하지 않는다.

태그는 annotated tag를 사용한다.

```bash
git checkout main
git pull origin main
git tag -a v0.0.1 -m "v0.0.1 프로젝트 방향 확정"
git push origin v0.0.1
```

## 8. 태그 생성 기준

| 상황 | 태그 생성 여부 |
|---|---|
| main 병합 후 안정 버전 검증 완료 | 가능 |
| main 병합 전 체크리스트 작성 완료 | 불가 |
| develop 브랜치 검토 완료 | 불가 |
| 작업 중간 저장 | 불가 |
| 실패한 실험 | 불가 |
| PR 검토 전 | 불가 |
| 작업 브랜치 기준 | 불가 |
| develop 브랜치 기준 | 불가 |

## 9. 기본 작업 흐름

```bash
# 1. develop 최신화
git checkout develop
git pull origin develop

# 2. develop에서 작업 브랜치 생성
git checkout -b docs/v0.0.1-project-direction

# 3. 작업 후 상태 확인
git status
git diff

# 4. 스테이징
git add docs/checklists/v0.0/v0.0.1-project-direction.md

# 5. staged 파일 확인
git diff --cached
git diff --cached --name-only

# 6. 커밋
git commit -m "docs: add v0.0.1 project direction checklist"

# 7. 원격 브랜치 push
git push origin docs/v0.0.1-project-direction

# 8. GitHub에서 작업 브랜치 -> develop PR 생성 후 병합

# 9. develop 최신화
git checkout develop
git pull origin develop

# 10. 큰 단계가 안정적으로 마무리되면 develop -> main PR 생성 후 병합

# 11. main 최신화
git checkout main
git pull origin main

# 12. main 병합 후 태그 생성
git tag -a v0.0.1 -m "v0.0.1 프로젝트 방향 확정"

# 13. 태그 push
git push origin v0.0.1
```

## 10. 커밋 전 필수 확인

```bash
git status
git diff --cached
git diff --cached --name-only
git log -1 --pretty=full
```

확인할 항목:

- 의도하지 않은 파일이 포함되지 않았는지
- `.env`, 업로드 파일, 원본 계약서가 포함되지 않았는지
- 자동 삽입된 공동 작성자 문구가 포함되지 않았는지
- 민감정보가 포함되지 않았는지
