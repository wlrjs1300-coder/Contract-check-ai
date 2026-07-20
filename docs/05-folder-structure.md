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
│   │   ├── v0.1/
│   │       ├── v0.1.1-service-overview.md
│   │       ├── v0.1.2-mvp-scope.md
│   │       ├── v0.1.3-supported-contract-scope.md
│   │       ├── v0.1.4-user-scenarios.md
│   │       ├── v0.1.5-service-responsibility-policy.md
│   │       └── v0.1.6-planning-alignment.md
│   │   ├── v0.2/
│   │       └── v0.2.1-core-validation.md
│   │   └── v0.5/
│   │       └── v0.5.0-portfolio-release-prep.md
│   ├── deployment/
│   │   └── deployment-readiness.md
│   ├── portfolio/
│   │   └── project-overview.md
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
├── README.md
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

## 2.3 공개 설명 및 배포 준비 문서 구조

v0.5.0 공개 준비 문서는 다음 경로에서 관리한다.

```text
docs/
├── portfolio/
│   └── project-overview.md
└── deployment/
    └── deployment-readiness.md
```

- `docs/portfolio/`는 포트폴리오 관점의 프로젝트 배경, 담당 범위, 의사결정과 검증 결과를 기록한다.
- `docs/deployment/`는 특정 플랫폼을 확정하지 않고 실제 배포 전 필요한 조건과 미준비 항목을 기록한다.

## 2.4 v0.6 문서 입력·OCR 설계 문서 구조

v0.6 Phase 1의 입력 계약, 기술 결정, 보안 정책, API 계약과 구현 로드맵은 다음 경로에서 관리한다. 이 구조는 설계 문서가 실제 생성되었음을 뜻하며 PDF·이미지·OCR 기능이 구현되었음을 뜻하지 않는다.

```text
docs/
├── architecture/
│   ├── v0.6-document-input-contract.md
│   └── v0.6.2-billing-subscription-domain.md
├── decisions/
│   ├── ADR-006-ocr-strategy.md
│   └── ADR-007-pdf-parser-selection.md
├── api/
│   ├── v0.6-extraction-result-contract.md
│   ├── v0.6.1-text-pdf-extraction-api.md
│   ├── v0.6.2-analysis-result-schema.md
│   └── v0.6.3-image-ocr-api.md
├── product/
│   ├── v0.6.2-customer-value-analysis.md
│   ├── v0.6.2-plans-and-entitlements.md
│   └── v0.6.2-commercial-validation-plan.md
├── security/
│   ├── v0.6-original-document-lifecycle.md
│   └── v0.6-document-upload-threat-model.md
├── roadmaps/
│   └── v0.6-document-input-ocr-roadmap.md
└── checklists/
    └── v0.6/
        ├── v0.6.0-input-security-design.md
        ├── v0.6.1-text-pdf-extraction.md
        ├── v0.6.2-customer-value-entitlements.md
        └── v0.6.3-image-ocr.md
```

- `docs/architecture/`는 지원 입력, 처리 분기, 상태 전이와 분석 시작 조건을 기록한다.
- `docs/decisions/`는 OCR 방식의 후보, 선택 기준, 스파이크와 교체 전략을 ADR로 기록한다.
- `docs/api/`는 구현 전 공통 추출 결과와 오류 응답 계약을 기록한다.
- `docs/security/`는 원본 파일 생명주기와 업로드·OCR 위협 모델을 기록한다.
- `docs/roadmaps/`는 보안 게이트를 포함한 단계별 구현 순서를 기록한다.
- `docs/checklists/v0.6/`는 v0.6 버전별 수행·검증 상태를 기록한다.
- `docs/product/`는 고객 가치, 상품 가설, entitlement와 상품성 검증 계획을 기록한다. v0.6.2 문서는 실제 결제·구독 또는 분석 기능이 구현되었음을 뜻하지 않는다.

v0.6.1 텍스트 PDF 직접 추출 구현에서 추가된 현재 Backend 구조는 다음과 같다.

```text
backend/
├── requirements.txt
├── app/
│   ├── api/
│   │   └── extractions.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── extractions.py
│   ├── services/
│   │   ├── extraction_temp_files.py
│   │   └── pdf_extraction.py
│   ├── db/
│   │   └── models.py
│   └── main.py
└── tests/
    └── test_pdf_extraction.py
```

PDF 테스트는 실행 중 메모리에서 합성 PDF를 만들며 저장소에 바이너리 fixture를 추가하지 않는다.

v0.6.3 이미지 OCR 기반 구현은 `backend/app/services/image_ocr.py`와 `backend/tests/test_image_ocr.py`를 추가한다. 테스트 이미지는 Pillow로 메모리에서 생성하며 바이너리 fixture나 폰트 파일을 저장소에 추가하지 않는다. Pillow는 image decoder·정규화에만 사용하고 실제 OCR engine은 아직 없다.

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

## 4. 현재 프론트엔드 폴더 구조

v0.4 프론트엔드 구현은 다음 구조를 사용한다.

```text
frontend/
├── package.json
├── package-lock.json
├── vite.config.ts
├── tsconfig.json
├── index.html
└── src/
    ├── api/
    │   ├── analysisJobs.ts
    │   ├── analysisResults.ts
    │   ├── config.ts
    │   ├── documents.ts
    │   └── http.ts
    ├── assets/
    ├── components/
    │   ├── AnalysisJobPanel.tsx
    │   ├── AnalysisResultsPanel.tsx
    │   ├── AnalysisStepper.tsx
    │   ├── AppFrame.tsx
    │   ├── ClauseList.tsx
    │   ├── DocumentSummary.tsx
    │   ├── DocumentUploadForm.tsx
    │   ├── TopNavigation.tsx
    │   ├── UnclassifiedSections.tsx
    │   └── WarningList.tsx
    ├── pages/
    │   ├── AnalyzePage.tsx
    │   ├── HomePage.tsx
    │   ├── ResultsPage.tsx
    │   └── ScaffoldPage.tsx
    ├── routes/
    ├── hooks/
    ├── types/
    │   ├── analysisJobs.ts
    │   ├── analysisResults.ts
    │   └── documents.ts
    ├── utils/
    │   ├── analysisJob.ts
    │   ├── analysisResult.ts
    │   └── documentUpload.ts
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
