# 기술스택 확정

## 1. 문서 목적

본 문서는 ContractCheck AI의 포트폴리오용 MVP 구현에 사용할 기술스택과 선택 근거, 제외 범위, 향후 확장 후보를 정리한다.

ContractCheck AI는 개인정보 보호형 계약서 사전점검 서비스이며, 전체 공식 지원 계획은 근로계약서와 주택 임대차계약서를 유지한다.

v1.0 최초 구현과 기술 검증은 근로계약서 1종을 우선하며, 주택 임대차계약서는 후속 구현 대상으로 둔다. 상세 근거는 `docs/planning/user-scenarios.md`를 따른다.

## 2. 기술 선택 기준

- 포트폴리오 MVP에서 실제 구현과 설명이 가능한 기술을 우선한다.
- 계약서 원문, 개인정보, Secret이 저장소와 로그에 남지 않도록 설계한다.
- 단순 CRUD가 아니라 업로드, 텍스트 추출, 조항 분할, 위험 분석, 결과 저장 및 조회 흐름을 구현할 수 있어야 한다.
- 특정 AI 공급자에 핵심 도메인 코드가 직접 종속되지 않도록 한다.
- 과도한 마이크로서비스, Kubernetes, 필수 Docker 구성은 현재 단계에서 제외한다.
- 패키지 세부 버전은 지금 확정하지 않고, 안정 버전과 호환성 검증 후 lock 파일 또는 의존성 파일에서 고정한다.

## 3. 전체 기술스택 요약표

| 영역 | 확정 기술 | MVP 적용 범위 |
|---|---|---|
| Frontend | React + Vite + TypeScript | 화면 구현, API 연동, 결과 조회 |
| UI | Bootstrap 5 + CSS | 기본 레이아웃, 폼, 버튼, 테이블, 상태 표시 |
| Backend | FastAPI + Python | REST API, 파일 처리, 분석 작업 orchestration |
| ORM | SQLAlchemy | DB 모델과 쿼리 관리 |
| Migration | Alembic | DB 스키마 변경 관리 |
| Validation | Pydantic | 요청/응답 데이터 검증 |
| ASGI Server | Uvicorn | FastAPI 로컬 실행 및 배포 실행 |
| Database | MySQL | 메타데이터, 조항, 분석 결과 저장 |
| Authentication | JWT | MVP access token 기반 인증 |
| AI Integration | 서비스 계층 + provider adapter | 외부 AI API 교체 가능 구조 |
| File Handling | 서버 로컬 임시 저장 후 원본 삭제 | 업로드 처리, 텍스트 추출 후 삭제 |
| API Style | REST | 프론트엔드와 백엔드 통신 |
| Documentation | Markdown | 규칙, 체크리스트, 설계 기록 |
| Version Control | Git + GitHub | branch, commit, PR, tag 기반 관리 |
| Deployment | Vercel, Render 또는 Railway, 관리형 MySQL | MVP 배포 후보 |
| Frontend Test | Vitest | 주요 컴포넌트와 유틸 테스트 |
| Backend Test | pytest, FastAPI TestClient 또는 httpx | API, 서비스, 분석 흐름 테스트 |
| Code Quality | ESLint, Ruff | 프론트엔드/백엔드 정적 점검 |
| Env Management | `.env`, `.env.example` | Secret 분리, 키 이름만 예시화 |

## 4. 프론트엔드

### 선택 기술

- React
- Vite
- TypeScript
- Bootstrap 5
- CSS
- React 기본 상태 관리와 Context

### 사용 목적

- 계약서 업로드 화면, 분석 진행 화면, 결과 대시보드, 조항 상세 화면을 구현한다.
- 백엔드 REST API와 통신해 분석 작업 상태와 결과를 표시한다.

### 선택 이유

- React와 Vite는 MVP 화면을 빠르게 구성하고 빌드할 수 있다.
- TypeScript는 API 응답, 분석 결과, 위험도 표시 데이터 구조를 명확히 다루는 데 유리하다.
- Bootstrap 5와 CSS는 별도 디자인 시스템 없이도 기본 UI를 안정적으로 구성할 수 있다.

### 대안

- Next.js
- Vue
- Tailwind CSS
- Redux
- Zustand

### 지금 선택하지 않은 이유

- Next.js는 서버 렌더링이나 라우팅 중심 기능이 필요해질 때 검토해도 충분하다.
- Tailwind CSS는 별도 스타일링 체계를 도입해야 하므로 현재 MVP에서는 Bootstrap 5와 CSS로 충분하다.
- Redux와 Zustand는 전역 상태가 복잡해질 때 검토한다.

### MVP 적용 범위

- React 기본 상태와 Context로 사용자 상태, 분석 상태, 결과 표시 상태를 관리한다.
- 복잡한 클라이언트 캐싱이나 대규모 전역 상태 관리는 2차 단계에서 검토한다.

## 5. 백엔드

### 선택 기술

- FastAPI
- Python
- SQLAlchemy
- Alembic
- Pydantic
- Uvicorn
- FastAPI BackgroundTasks

### 사용 목적

- 인증, 계약서 업로드, 텍스트 추출, 조항 분할, 분석 요청, 결과 조회 API를 제공한다.
- 분석 작업 상태와 결과를 DB에 저장한다.

### 선택 이유

- FastAPI는 REST API 구현, Pydantic 기반 검증, 자동 API 문서화에 적합하다.
- Python 생태계는 문서 처리, 텍스트 처리, AI API 연동에 유리하다.
- SQLAlchemy와 Alembic은 MySQL 기반 스키마와 마이그레이션을 관리하기 좋다.

### 대안

- Django
- Flask
- Node.js Express
- NestJS

### 지금 선택하지 않은 이유

- Django는 기본 기능이 풍부하지만 이번 MVP에는 구조가 무거울 수 있다.
- Flask는 단순하지만 데이터 검증과 API 구조를 직접 구성해야 할 범위가 늘어난다.
- Node.js 계열은 프론트엔드와 언어를 통일할 수 있지만, 현재 문서/AI 처리 흐름에는 Python 기반이 더 자연스럽다.

### MVP 적용 범위

- FastAPI REST API를 기본으로 구현한다.
- BackgroundTasks는 로컬 MVP 검증 단계의 간단한 비동기 처리에 한해 허용한다.
- 실제 사용자 업로드 운영 단계에서는 프로세스 종료나 배포 환경 재시작 시 작업 유실 가능성이 있으므로 한계로 기록한다.

## 6. 데이터베이스

### 선택 기술

- MySQL
- 개발 환경: 로컬 MySQL
- 운영 환경: 관리형 MySQL

### 사용 목적

- 사용자, 문서 메타데이터, 분석 작업 상태, 조항, 분석 결과를 저장한다.

### 선택 이유

- MySQL은 포트폴리오에서 설명하기 쉽고 운영형 DB 경험을 보여주기 좋다.
- 관계형 데이터 구조는 문서, 조항, 분석 결과 간 관계를 명확히 표현할 수 있다.

### 대안

- PostgreSQL
- SQLite
- MongoDB

### 지금 선택하지 않은 이유

- PostgreSQL도 적합하지만 현재 기준 문서에서 MySQL을 방향으로 잡고 있다.
- SQLite는 로컬 실험에는 편하지만 배포 환경과 차이가 크다.
- MongoDB는 조항과 분석 결과 저장에는 가능하지만 관계형 모델링 학습 효과가 줄어든다.

### MVP 적용 범위

- 원본 계약서 파일과 원본 전체 텍스트는 DB에 저장하지 않는다.
- 문서 메타데이터, 분석 작업 상태, 마스킹된 조항, 분석 결과만 저장한다.

## 7. 인증

### 선택 기술

- JWT
- access token 중심 MVP 인증
- Argon2 또는 bcrypt 계열 비밀번호 해시

### 사용 목적

- 사용자 로그인 상태를 관리하고 사용자별 분석 이력을 조회한다.

### 선택 이유

- JWT는 프론트엔드와 백엔드를 분리한 REST 구조에서 구현과 설명이 쉽다.
- access token 중심 구조는 MVP에서 인증 흐름을 단순하게 유지할 수 있다.
- 비밀번호는 평문 저장을 금지하고 안전한 해시를 사용한다.

### 대안

- 세션 기반 인증
- OAuth
- refresh token 기반 인증

### 지금 선택하지 않은 이유

- 세션 기반 인증은 서버 상태 관리가 필요하다.
- OAuth는 MVP 핵심 흐름에 비해 설정과 설명 범위가 커진다.
- refresh token은 필요성과 보안 설계가 확정된 뒤 2차 단계에서 검토한다.

### MVP 적용 범위

- 회원가입, 로그인, access token 발급, 인증 필요 API 보호까지 구현한다.
- refresh token, 소셜 로그인, 세션 관리 고도화는 2차 단계에서 검토한다.
- JWT access token의 만료시간은 짧게 유지하는 방향을 원칙으로 한다.
- 실제 만료시간 값은 v0.2 인증/보안 설계 단계에서 확정한다.
- 클라이언트 저장 위치는 보안 검토 후 확정한다.
- localStorage는 XSS 노출 위험이 있으므로 무조건 기본값으로 확정하지 않는다.
- httpOnly cookie 사용 여부도 CSRF 대응과 함께 검토한다.
- refresh token 미도입 상태에서 로그아웃/강제 무효화는 짧은 access token 만료시간과 서버 측 보완 정책을 함께 검토한다.

## 8. AI 연동 구조

### 선택 기술

- 외부 AI API를 추상화한 서비스 계층
- provider adapter 구조
- JSON 스키마 검증
- reference_id 검증
- 출력 안전성 검증(금지 표현, 법률 확정·보장 의미 검사)

### 사용 목적

- 마스킹된 조항 텍스트를 분석하고 위험 조항, 위험도, 설명, 검토 필요 항목을 구조화된 결과로 변환한다.

### 선택 이유

- 특정 AI 공급자를 핵심 도메인 코드에 직접 결합하지 않으면 API 교체와 테스트가 쉬워진다.
- 모델명과 API 키를 환경변수로 분리하면 배포 환경별 설정이 가능하다.
- JSON 스키마와 reference_id 검증은 분석 결과와 원문 조항 간 매핑 오류를 줄인다.

### 대안

- 특정 공급자 SDK 직접 호출
- 규칙 기반 분석만 사용
- 자체 모델 운영

### 지금 선택하지 않은 이유

- 공급자 SDK 직접 호출은 교체 가능성을 낮춘다.
- 규칙 기반 분석만으로는 위험 조항 설명 품질이 제한된다.
- 자체 모델 운영은 MVP 범위를 벗어난다.

### MVP 적용 범위

- AI 호출은 서비스 계층을 통해 수행한다.
- 실패, 재시도, timeout 처리 원칙을 기록하고 기본 예외 처리를 구현한다.
- 실제 API 키는 `.env`에만 둔다.
- AI 호출 timeout 값, 최대 재시도 횟수, 재시도 가능한 오류 범위, 재시도 간격 또는 backoff 방식은 현재 구체값을 확정하지 않는다.
- 위 항목은 실제 AI 공급자와 운영 환경을 정한 뒤 확정한다.
- MVP에서는 provider adapter 인터페이스와 실제 공급자 구현체 1개로 시작한다. 복수 공급자의 동시 구현은 MVP 필수 범위가 아니다.
- 특정 공급자에 핵심 도메인 코드가 종속되지 않도록 유지하되, 공급자 교체 가능 구조를 이유로 초기 구현을 여러 구현체로 과도하게 확장하지 않는다.
- AI 응답은 다음 순서로 처리하는 방향을 원칙으로 둔다: AI 응답 생성 → JSON 스키마 검증 → reference_id 검증 → 금지 표현 및 법률 확정·보장 의미 검사 → 검증 실패 시 차단, 재작성, 재시도 또는 실패 처리 → 안전한 결과만 표시 및 저장.
- 안전성 검증을 통과하지 못한 결과는 저장 후 검증하는 방식이 아니라, 검증을 먼저 통과한 결과만 표시·저장하는 방향을 원칙으로 둔다.
- 출력 안전성 검증의 구체적인 구현 방식(필터 로직, 금지어 목록 등)은 v0.2.1 기술 스파이크와 v0.5.3에서 확정한다.
- AI 공급자 데이터 정책(입력 데이터 학습 사용 여부, 기본 저장 여부, 저장 기간, 보관 비활성화 가능 여부, 민감정보 처리 조건, 처리 지역, 하위 처리자, 공급자 장애 및 전환 가능성 포함)은 v0.2.1 기술 스파이크 또는 v0.2.2 개인정보·보안 통합 설계에서 확인한다.
- 특정 AI 공급자명이나 실제 정책 내용은 현재 확정하지 않는다.

## 9. 파일 처리 및 개인정보 보호

### 선택 기술

- 서버 로컬 임시 저장
- 허용 확장자 및 크기 제한
- 안전한 파일명 생성
- 처리 후 원본 삭제
- 삭제 실패 로깅
- 경로 조작 방지
- pypdf 6.14.2 기반 텍스트 PDF 직접 추출

### 사용 목적

- 업로드된 계약서를 임시로 처리하고 텍스트 추출 후 원본 파일을 제거한다.
- v0.6.1에서는 텍스트 레이어 PDF를 페이지별로 직접 추출한다.

### 선택 이유

- 로컬 임시 저장은 MVP에서 구현과 검증이 단순하다.
- 원본 파일을 영구 저장하지 않는 방향은 개인정보 보호 원칙과 맞다.
- 안전한 파일명과 경로 검증은 임의 경로 접근 위험을 줄인다.
- pypdf는 BSD-3-Clause의 순수 Python 패키지로 Windows와 Linux 후보에서 동일하게 설치할 수 있고, 현재 필요한 페이지별 text 추출 경계가 작다.

### 대안

- 클라우드 스토리지 영구 저장
- DB BLOB 저장
- 사용자별 장기 파일 보관

### 지금 선택하지 않은 이유

- 원본 계약서의 장기 저장은 개인정보 보호 부담이 크다.
- DB BLOB 저장은 백업과 접근 제어 부담을 키운다.
- 장기 파일 보관은 MVP 핵심 가치가 아니다.

### MVP 적용 범위

- 업로드 파일은 임시 디렉터리에 저장한다.
- 원본은 저장소 밖 전용 temp root의 요청별 무작위 디렉터리와 서버 생성 파일명으로 저장한다.
- 처리 성공·실패 후 원본 파일을 삭제하고 cleanup 성공을 검증한다.
- cleanup 실패 시 extraction 성공과 DB 저장을 차단한다.
- DB에는 원본 파일 BLOB과 temp path를 저장하지 않는다. 기존 TXT 조항 본문과 v0.6.1 페이지별 추출 텍스트는 각 후속 흐름에 필요한 데이터로 구분해 저장한다.
- v0.6.1 extraction resource는 Phase 5 사용자 확인을 위해 페이지별 추출 텍스트를 저장하되 원본 BLOB과 temp path를 저장하지 않는다.
- 이미지 OCR, bbox, confidence와 스캔 PDF OCR은 현재 적용 범위가 아니다.

## 10. 테스트 및 코드 품질

### 선택 기술

- Frontend: Vitest
- Backend: pytest
- API Test: FastAPI TestClient 또는 httpx
- Frontend Quality: ESLint
- Backend Quality: Ruff

### 사용 목적

- 주요 유틸, 컴포넌트, API, 서비스 흐름을 검증한다.
- 기본적인 코드 스타일과 잠재 오류를 점검한다.

### 선택 이유

- Vitest는 Vite 기반 프론트엔드와 잘 맞는다.
- pytest는 FastAPI/Python 테스트에 널리 쓰인다.
- Ruff는 Python lint와 format 점검을 빠르게 수행할 수 있다.

### 대안

- Jest
- unittest
- flake8
- black 단독 사용

### 지금 선택하지 않은 이유

- Jest는 Vite 환경에서 추가 설정 부담이 있다.
- unittest는 가능하지만 pytest가 테스트 작성 경험이 더 간결하다.
- flake8/black 조합 대신 Ruff로 초기 구성을 단순화한다.

### MVP 적용 범위

- 최소 단위 테스트와 핵심 API 통합 테스트를 작성한다.
- 분석 응답 검증, 파일 처리, 인증 흐름은 우선 테스트 대상으로 둔다.

## 11. 환경변수 및 Secret 관리

### 선택 기술

- `.env`
- `.env.example`
- 배포 환경 변수 설정

### 사용 목적

- DB 접속 정보, JWT Secret, AI API Key, 모델명, timeout 값을 코드와 분리한다.

### 선택 이유

- 로컬 개발과 배포 환경 설정을 분리할 수 있다.
- 실제 Secret 커밋 금지 원칙과 맞다.

### 대안

- 코드 내 상수
- 별도 Secret 관리 서비스

### 지금 선택하지 않은 이유

- 코드 내 상수는 공개 저장소에 Secret이 유출될 위험이 있다.
- 별도 Secret 관리 서비스는 현재 MVP 배포 복잡도에 비해 과하다.

### MVP 적용 범위

- `.env`는 커밋하지 않는다.
- `.env.example`에는 키 이름만 기록하고 실제 값을 넣지 않는다.
- 배포 환경에서는 플랫폼의 환경변수 기능을 사용한다.

## 12. 배포 구성

### 선택 기술

- Frontend: Vercel
- Backend: Render 또는 Railway
- Database: 배포 환경에서 제공하는 관리형 MySQL

### 사용 목적

- 포트폴리오 MVP를 외부에서 확인 가능한 형태로 배포한다.

### 선택 이유

- Vercel은 Vite 기반 프론트엔드 배포가 단순하다.
- Render와 Railway는 FastAPI 백엔드 배포 후보로 적합하다.
- 관리형 MySQL은 직접 서버 운영 부담을 줄인다.

### 대안

- AWS
- Fly.io
- 자체 VPS
- Docker 기반 직접 배포

### 지금 선택하지 않은 이유

- AWS와 VPS는 운영 범위가 커진다.
- Docker는 배포 재현성이 필요해질 때 도입해도 된다.
- 현재 단계에서는 구현 전 기술 방향 확정이 목적이다.

### MVP 적용 범위

- 실제 배포 시 Render 또는 Railway 중 하나를 최종 선택한다.
- 개발 단계에서는 Docker를 필수로 하지 않는다.

## 13. 개발 환경과 운영 환경 차이

| 구분 | 개발 환경 | 운영 환경 |
|---|---|---|
| Frontend | Vite dev server | Vercel |
| Backend | Uvicorn local server | Render 또는 Railway |
| Database | 로컬 MySQL | 관리형 MySQL |
| Env | 로컬 `.env` | 플랫폼 환경변수 |
| File | 로컬 임시 디렉터리 | 서버 임시 저장소 |
| Secret | 로컬 비공개 파일 | 배포 환경변수 |

운영 환경에서는 원본 파일 삭제 실패, API timeout, 배포 환경 재시작으로 인한 작업 유실 가능성을 별도 이슈로 관리한다.

## 14. 현재 제외 기술

- 결제
- OCR
- 관리자 페이지
- 전자서명
- 계약서 자동 생성
- 법률 자문 기능
- ERP 수준의 복잡한 기능
- Kubernetes
- 마이크로서비스 구조
- 필수 Docker 구성
- 필수 Redis/Celery 구성
- OCR 라이브러리

## 15. 2차 확장 후보

- Celery 또는 RQ: 비동기 작업 안정화가 필요해지는 단계에서 검토
- Redis: 작업 큐, 캐시, rate limit이 필요해지는 단계에서 검토
- Docker: 배포 재현성과 개발 환경 통일이 필요해지는 단계에서 검토
- refresh token: 인증 보안 설계를 확정한 뒤 검토
- Redux 또는 Zustand: 전역 상태 복잡도가 증가할 경우 검토
- 클라우드 스토리지: 원본이 아닌 안전한 산출물 보관이 필요할 때 검토
- 더 정교한 권한 관리: 사용자 역할이 늘어날 때 검토

## 16. 버전 고정 원칙

- 현재 문서에서는 패키지 세부 버전을 확정하지 않는다.
- 안정 버전과 호환성을 검증한 뒤 `package-lock`, `requirements`, `pyproject.toml` 등 실제 의존성 파일에서 고정한다.
- 보안 취약점과 호환성 이슈가 있는 버전은 사용하지 않는다.
- 주요 런타임 버전은 개발 환경 세팅 단계에서 검증 후 기록한다.

## 17. 최종 확정 사항

- Frontend는 React + Vite + TypeScript를 사용한다.
- UI는 Bootstrap 5 + CSS를 사용한다.
- Backend는 FastAPI + Python을 사용한다.
- ORM은 SQLAlchemy, migration은 Alembic을 사용한다.
- Database는 MySQL을 사용한다.
- 인증은 JWT access token 중심으로 구현한다.
- AI 연동은 서비스 계층과 provider adapter로 분리한다.
- 원본 계약서는 서버 로컬 임시 저장 후 처리 완료 시 삭제한다.
- DB에는 원본 파일을 저장하지 않고 메타데이터, 조항, 분석 결과만 저장한다.
- 테스트는 Vitest와 pytest를 사용한다.
- 코드 품질 도구는 ESLint와 Ruff를 사용한다.
- 배포 방향은 Vercel, Render 또는 Railway, 관리형 MySQL로 둔다.

## 18. 미확정 사항

- Render와 Railway 중 백엔드 최종 배포 플랫폼
- 관리형 MySQL 제공자
- AI 공급자와 모델명
- refresh token 도입 여부
- JWT access token 만료시간
- 토큰 클라이언트 저장 위치
- localStorage 또는 httpOnly cookie 사용 여부
- 로그아웃 및 토큰 강제 무효화 방식
- AI 호출 timeout 값
- AI 호출 최대 재시도 횟수
- 재시도 가능한 오류 범위
- 재시도 간격 또는 backoff 방식
- 비동기 작업 큐 도입 시점
- Docker 도입 시점
- 업로드 파일 크기 제한의 구체 값
- 허용 파일 확장자의 최종 목록
