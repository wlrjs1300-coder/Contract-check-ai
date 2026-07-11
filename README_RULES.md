# ContractCheck AI 규칙 문서 안내

이 문서 세트는 ContractCheck AI 프로젝트를 버전 단위로 관리하고, 공개 GitHub 저장소에 정제된 코드와 문서만 남기기 위한 기준입니다.

## 프로젝트명

ContractCheck AI

## 부제

개인정보 보호형 계약서 사전점검 서비스

## 핵심 원칙

- 모든 작업은 버전 단위로 나누어 진행한다.
- 버전별 작업 내용, 검증 내용, 릴리스 기록은 체크리스트 MD 파일로 남긴다.
- 공개 저장소에는 최종 코드, 설계 문서, 검증 기록만 포함한다.
- 작업 중간 산출물, 임시 메모, 검토 전 초안은 공개 저장소에 포함하지 않는다.
- 원본 계약서, 개인정보, API Key, Secret, Token은 절대 커밋하지 않는다.
- 브랜치, 커밋, PR, 태그 규칙을 지킨다.
- 일반 작업은 작업 브랜치에서 `develop`으로 PR을 생성하고 병합한다.
- 큰 단계가 안정적으로 마무리되었을 때만 `develop`에서 `main`으로 PR을 생성한다.
- 태그는 검증 완료 후 main 브랜치에 병합된 커밋 기준으로만 생성한다.

## 핵심 운영 파일

```text
README_RULES.md
.gitignore
.github/pull_request_template.md
docs/
```

## 주요 규칙 문서

- `docs/01-versioning-rules.md`: 버전 관리 규칙과 전체 로드맵을 정의한다.
- `docs/02-git-rules.md`: 브랜치, 커밋, PR, 태그 규칙을 정의한다.
- `docs/03-security-rules.md`, `docs/04-public-records-rules.md`: 커밋 금지 항목과 공개 기록 기준을 정의한다.
- `docs/06-checklist-template.md`: 버전별 체크리스트 작성 기준을 정의한다.
- `docs/08-review-workflow-rules.md`: 작업 시작 전과 완료 후 확인할 검토 기준을 문서/기획, 설계, 구현, 릴리스 단계로 나누어 정의한다.
- `docs/09-tech-stack.md`: MVP 기술스택과 방향을 정의한다.

## 실제 폴더 구조 기준 문서

현재 저장소의 실제 폴더·파일 구조는 `docs/05-folder-structure.md`를 단일 기준으로 한다.

README_RULES.md는 전체 폴더 트리를 별도로 나열하지 않는다. 구조가 바뀔 때는 `docs/05-folder-structure.md`만 갱신하면 되도록, 두 문서에서 같은 트리를 중복 관리하지 않는다.

## 사용 방법

1. 프로젝트 루트에 이 문서 세트를 복사한다.
2. `.gitignore` 기준에 맞게 비공개 파일과 민감정보가 제외되는지 확인한다.
3. 작업을 시작하기 전 `docs/` 규칙 문서와 `docs/05-folder-structure.md`를 확인한다.
4. 각 버전 작업은 `docs/checklists/`에 체크리스트를 만든 뒤 진행한다.
5. 일반 작업은 작업 브랜치에서 `develop`으로 PR을 생성하고 병합한다.
6. 큰 단계 또는 정식 릴리스가 안정적으로 마무리되면 `develop`에서 `main`으로 PR을 생성한다.
7. 태그는 `main` 병합 후 안정 버전 기준으로만 생성한다.

## 공개 저장소에 올리지 않는 자료

아래 자료는 로컬에서만 관리하고 GitHub에는 올리지 않는다.

```text
private-docs/
raw-notes/
temp-analysis/
local-contracts/
```
