# 폴더 구조 규칙

## 1. 목적

ContractCheck AI 프로젝트의 폴더 구조를 일관되게 관리한다.

프론트엔드, 백엔드, 문서, 보안 정책, 체크리스트를 명확히 분리하여 프로젝트 관리성과 가독성을 높인다.

## 2. 전체 폴더 구조

```text
contract-check-ai/
├── README.md
├── .gitignore
├── .env.example
├── .github/
│   └── pull_request_template.md
├── docs/
│   ├── 00-project-context.md
│   ├── 01-versioning-rules.md
│   ├── 02-git-rules.md
│   ├── 03-security-rules.md
│   ├── 04-public-records-rules.md
│   ├── 05-folder-structure.md
│   ├── 06-checklist-template.md
│   ├── 07-adr-template.md
│   ├── checklists/
│   ├── decisions/
│   ├── api/
│   ├── db/
│   ├── security/
│   └── samples/
├── frontend/
└── backend/
```

## 3. 문서 폴더 구조

```text
docs/
├── 00-project-context.md
├── 01-versioning-rules.md
├── 02-git-rules.md
├── 03-security-rules.md
├── 04-public-records-rules.md
├── 05-folder-structure.md
├── 06-checklist-template.md
├── 07-adr-template.md
├── checklists/
│   ├── v0.0/
│   ├── v0.1/
│   ├── v0.2/
│   ├── v0.3/
│   ├── v0.4/
│   ├── v0.5/
│   ├── v0.6/
│   └── v1.0/
├── decisions/
│   ├── ADR-001-project-direction.md
│   ├── ADR-002-tech-stack.md
│   ├── ADR-003-contract-scope.md
│   └── ADR-004-privacy-first-design.md
├── api/
│   └── api-spec.md
├── db/
│   └── erd.md
├── security/
│   ├── privacy-flow.md
│   ├── pii-masking-policy.md
│   ├── file-retention-policy.md
│   └── log-security-policy.md
└── samples/
    ├── employment-contract.sample.md
    └── housing-lease.sample.md
```

## 4. 프론트엔드 폴더 구조

```text
frontend/
├── package.json
├── vite.config.js
├── index.html
└── src/
    ├── api/
    ├── assets/
    ├── components/
    ├── pages/
    ├── routes/
    ├── hooks/
    ├── utils/
    └── styles/
```

## 5. 백엔드 폴더 구조

```text
backend/
├── requirements.txt
├── app/
│   ├── main.py
│   ├── core/
│   ├── api/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   │   ├── document_service.py
│   │   ├── text_extraction_service.py
│   │   ├── pii_masking_service.py
│   │   ├── clause_splitter_service.py
│   │   └── risk_analysis_service.py
│   ├── repositories/
│   └── utils/
├── migrations/
└── tests/
    └── fixtures/
```

## 6. 비공개 로컬 폴더

다음 폴더는 로컬에서만 사용하고 공개 GitHub에는 올리지 않는다.

```text
private-docs/
├── raw-notes/
├── temp-analysis/
├── local-contracts/
└── review-notes/
```

## 7. 업로드/임시 파일 폴더

다음 폴더는 런타임에서만 사용하고 커밋하지 않는다.

```text
uploads/
storage/
tmp/
temp/
contracts/
originals/
reports/
exports/
downloads/
```

## 8. 폴더 관리 원칙

- 문서와 코드는 분리한다.
- 체크리스트는 버전별로 관리한다.
- 보안 관련 문서는 `docs/security/`에 둔다.
- 의사결정 기록은 `docs/decisions/`에 ADR 형식으로 둔다.
- 작업 중간 자료와 비공개 검토 자료는 공개 저장소에 두지 않는다.
