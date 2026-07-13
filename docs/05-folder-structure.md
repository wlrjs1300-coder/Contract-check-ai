# 폴더 구조 규칙

## 1. 목적

ContractCheck AI 프로젝트의 폴더 구조를 일관되게 관리한다.

현재 실제 저장소 구조와 향후 목표 구조를 구분하여, 아직 생성되지 않은 파일이나 폴더를 현재 존재하는 항목처럼 오해하지 않도록 한다.

## 2. 현재 실제 구조

현재 저장소에는 다음 항목이 존재한다.

```text
contract-check-ai/
├── .github/
│   └── pull_request_template.md
├── docs/
│   ├── checklists/
│   │   ├── v0.0/
│   │   │   ├── v0.0.1-project-direction.md
│   │   │   ├── v0.0.2-repository-rules.md
│   │   │   ├── v0.0.3-security-public-records.md
│   │   │   ├── v0.0.4-tech-stack.md
│   │   │   ├── v0.0.5-checklist-governance.md
│   │   │   └── v0.0.6-version-plan.md
│   │   └── v0.1/
│   │       ├── v0.1.1-service-overview.md
│   │       ├── v0.1.2-mvp-scope.md
│   │       ├── v0.1.3-supported-contract-scope.md
│   │       ├── v0.1.4-user-scenarios.md
│   │       ├── v0.1.5-service-responsibility-policy.md
│   │       └── v0.1.6-planning-alignment.md
│   │   └── v0.2/
│   │       └── v0.2.1-core-validation.md
│   ├── planning/
│   │   ├── service-overview.md
│   │   ├── mvp-scope.md
│   │   ├── supported-contract-scope.md
│   │   ├── user-scenarios.md
│   │   └── service-responsibility-policy.md
│   ├── 00-project-context.md
│   ├── 01-versioning-rules.md
│   ├── 02-git-rules.md
│   ├── 03-security-rules.md
│   ├── 04-public-records-rules.md
│   ├── 05-folder-structure.md
│   ├── 06-checklist-template.md
│   ├── 07-adr-template.md
│   ├── 08-review-workflow-rules.md
│   └── 09-tech-stack.md
├── spikes/
│   └── v0.2.1-core-validation/
│       ├── README.md
│       ├── config/
│       │   └── experiment.example.json
│       ├── data/
│       │   └── fixtures/
│       │       ├── README.md
│       │       ├── employment-contract-01.sample.txt
│       │       ├── employment-contract-02.sample.txt
│       │       ├── clause-split-edge-01.sample.txt
│       │       ├── clause-split-edge-02.sample.txt
│       │       ├── clause-split-expected.sample.json
│       │       ├── pii-employment-01.sample.txt
│       │       ├── pii-employment-02.sample.txt
│       │       ├── pii-edge-01.sample.txt
│       │       ├── pii-edge-02.sample.txt
│       │       └── pii-masking-expected.sample.json
│       ├── reports/
│       │   ├── pr-2-clause-split.md
│       │   └── pr-3-pii-masking.md
│       ├── schemas/
│       │   └── result_schema.md
│       └── scripts/
│           ├── generate_synthetic_data.py
│           ├── clause_split/
│               ├── split_clauses.py
│               └── evaluate_clause_split.py
│           └── pii_masking/
│               ├── detect_and_mask.py
│               └── evaluate_pii_masking.py
├── .gitignore
└── README_RULES.md
```

현재 실제 보안 규칙 문서는 다음 파일이다.

- `docs/03-security-rules.md`
- `docs/04-public-records-rules.md`

## 2.1 스파이크 구조

v0.2.1 핵심 기술 스파이크는 제품 코드와 분리된 `spikes/` 아래에서 관리한다.

현재 Git 추적 대상 스파이크 파일은 다음과 같다.

- `spikes/v0.2.1-core-validation/README.md`
- `spikes/v0.2.1-core-validation/config/experiment.example.json`
- `spikes/v0.2.1-core-validation/schemas/result_schema.md`
- `spikes/v0.2.1-core-validation/scripts/generate_synthetic_data.py`
- `spikes/v0.2.1-core-validation/scripts/clause_split/split_clauses.py`
- `spikes/v0.2.1-core-validation/scripts/clause_split/evaluate_clause_split.py`
- `spikes/v0.2.1-core-validation/scripts/pii_masking/detect_and_mask.py`
- `spikes/v0.2.1-core-validation/scripts/pii_masking/evaluate_pii_masking.py`
- `spikes/v0.2.1-core-validation/data/fixtures/README.md`
- `spikes/v0.2.1-core-validation/data/fixtures/*.sample.txt`
- `spikes/v0.2.1-core-validation/data/fixtures/clause-split-expected.sample.json`
- `spikes/v0.2.1-core-validation/data/fixtures/pii-masking-expected.sample.json`
- `spikes/v0.2.1-core-validation/reports/pr-2-clause-split.md`
- `spikes/v0.2.1-core-validation/reports/pr-3-pii-masking.md`

`spikes/**/reports/`는 각 스파이크의 검토·결론 보고서를 두는 경로이며, 계획된 실험 보고서는 Git 추적 대상으로 둘 수 있다.

다음 경로는 Git 제외 대상이다.

- `spikes/**/data/generated/`
- `spikes/**/outputs/raw/`
- `spikes/**/outputs/summary/`
- `spikes/**/.env`
- `spikes/**/*.local.*`

`outputs/summary/`는 로컬 실행 결과 요약을 둘 수 있는 Git 제외 산출물 경로이며, 현재 Git 추적 구조로 표시하지 않는다.

스파이크 코드는 기술 검증을 위한 실험 기반 코드이며 제품 코드로 자동 승격되지 않는다. 실험 결과를 정식 설계나 제품 구현에 반영하려면 별도 검토, 문서화, PR이 필요하다.

## 2.2 서비스 기획 문서 구조

v0.1 서비스 기획 단계에서는 `docs/planning/`에 서비스 기획 산출물을 둔다.

현재 실제 생성된 기획 문서는 다음과 같다.

- `service-overview.md`
- `mvp-scope.md`
- `supported-contract-scope.md`
- `user-scenarios.md`
- `service-responsibility-policy.md`

후속 v0.1 단계에서 필요하면 다음 문서를 추가할 수 있다.
아래 파일은 아직 생성된 파일로 취급하지 않는다.

현재 별도로 확정된 추가 예정 문서는 없다.

## 3. 향후 목표 구조

아래 항목은 구현, 설계, 개발 환경 세팅 단계에서 필요할 때 생성할 목표 구조이다.
현재 존재하는 파일이나 폴더로 취급하지 않는다.

```text
contract-check-ai/
├── README.md
├── .env.example
├── frontend/
├── backend/
│   └── tests/
│       └── fixtures/
└── docs/
    ├── decisions/
    ├── api/
    ├── db/
    ├── security/
    └── samples/
```

## 4. 향후 프론트엔드 폴더 구조

프론트엔드 구현 단계에서 `frontend/`를 생성할 때 다음 구조를 기준으로 검토한다.

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

## 5. 향후 백엔드 폴더 구조

백엔드 구현 단계에서 `backend/`를 생성할 때 다음 구조를 기준으로 검토한다.

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
│   ├── repositories/
│   └── utils/
├── migrations/
└── tests/
    └── fixtures/
```

## 6. 향후 문서 폴더 구조

설계 단계에서 필요할 때 다음 문서 폴더를 생성한다.

```text
docs/
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

`docs/security/`는 상세 보안 설계 문서용 목표 구조이다.
현재의 공통 보안 규칙은 `docs/03-security-rules.md`와 `docs/04-public-records-rules.md`를 기준으로 한다.

## 7. 비공개 로컬 폴더

다음 폴더는 로컬에서만 사용하고 공개 GitHub에는 올리지 않는다.

```text
private-docs/
raw-notes/
temp-analysis/
local-contracts/
review-notes/
```

## 8. 업로드/임시 파일 폴더

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

최상위 `reports/`는 로컬 보고서와 임시 산출물을 위한 경로이며 기본적으로 Git에 커밋하지 않는다.
최상위 `reports/` 미커밋 정책은 `spikes/**/reports/`의 승인된 실험 보고서에는 적용되지 않는다.

## 9. 폴더 관리 원칙

- 현재 구조와 향후 목표 구조를 구분하여 기록한다.
- 문서와 코드는 분리한다.
- 체크리스트는 버전별로 관리한다.
- 의사결정 기록은 필요할 때 `docs/decisions/`에 ADR 형식으로 둔다.
- 상세 보안 설계 문서는 필요할 때 `docs/security/`에 둔다.
- 작업 중간 자료와 비공개 검토 자료는 공개 저장소에 두지 않는다.
