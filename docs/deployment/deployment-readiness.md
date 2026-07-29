# ContractCheck AI 배포 준비 조건

## 문서 목적

현재 기술 검증 MVP를 외부에서 시연하기 전에 필요한 조건과 미준비 항목을 플랫폼에 종속되지 않게 정리한다. 이 문서는 실제 배포 승인이나 특정 플랫폼 확정을 의미하지 않는다.

## 현재 배포 가능 범위

현재 코드는 다음 범위의 제한된 합성 데이터 시연 후보로 검토할 수 있다.

- React 정적 Frontend build
- FastAPI API와 Uvicorn 실행
- UTF-8 TXT 한 파일, 최대 1 MiB 업로드
- SQLite 단일 인스턴스
- 합성 Provider 기반 분석 흐름
- `GET /health` 상태 확인

실제 계약서나 실제 개인정보를 처리하는 공개 서비스로는 배포할 수 없다. 인증과 사용자별 접근 제어가 없고 분리된 조항 본문이 DB에 저장되기 때문이다.

## 배포 전 필수 조건

- [ ] 시연 범위를 합성 데이터로 제한하고 사용자 화면에 현재 상태 표시
- [ ] Frontend와 Backend 배포 주소 확정
- [ ] Backend의 `CORS_ALLOWED_ORIGINS`를 실제 Frontend origin으로 제한
- [ ] Frontend의 `VITE_API_BASE_URL`을 공개 가능한 Backend HTTPS 주소로 설정
- [ ] Backend DB의 영속성, 접근 권한, backup과 복구 정책 확정
- [ ] 업로드 문서, 조항 본문과 로그의 보관·삭제 정책 확정
- [ ] 실제 비밀값을 Backend 전용 Secret 관리 기능에 저장
- [ ] HTTPS 적용과 HTTP 요청 차단 확인
- [ ] 프로세스 재시작 정책과 health check 연동
- [ ] 오류 응답, 로그와 모니터링에서 문서 내용 미노출 확인
- [ ] 배포 후 전체 smoke test 수행
- [ ] 실제 계약서 입력 차단 또는 별도 승인 절차 마련

## Frontend 배포 고려사항

- `npm.cmd run build` 결과를 정적 자산으로 배포한다.
- SPA의 현재 단일 화면 진입과 정적 자산 경로를 확인한다.
- `VITE_API_BASE_URL`은 build 시 브라우저 코드에 포함될 수 있는 공개 API 주소이며 Secret이 아니다.
- 어떠한 API Key, credential 또는 운영 비밀값도 `VITE_` 변수에 저장하지 않는다.
- Backend와 다른 origin을 사용하므로 CORS 설정을 함께 검증한다.
- 네트워크 실패, Backend 재시작과 잘못된 응답에서도 내부 정보를 노출하지 않는지 확인한다.
- 실제 screen reader, 키보드 전체 흐름과 전문 색상 대비를 배포 전 수동 검증한다.

## Backend 배포 고려사항

- Python과 `backend/requirements.txt`에 맞는 실행 환경을 사용한다.
- 애플리케이션 import 경로가 유지되도록 저장소 루트에서 Uvicorn을 실행한다.
- 프로세스 수와 SQLite 연결 방식의 호환성을 검토한다.
- `GET /health`를 상태 확인에 사용하되 DB와 의존 서비스 준비 상태까지 보장하는 endpoint로 확대 해석하지 않는다.
- 업로드 크기 제한은 애플리케이션의 1 MiB뿐 아니라 reverse proxy와 플랫폼 제한도 확인한다.
- 운영 오류에 stack trace, 조항 본문, 마스킹 전 텍스트와 Provider 원시 응답을 남기지 않는다.
- 현재 분석은 요청 안에서 동기 실행되므로 요청 timeout과 프로세스 재시작 영향을 검토한다.

## DB 고려사항

현재 SQLite는 단일 인스턴스 기술 검증에 적합하다. 다중 인스턴스, 동시 쓰기, 무중단 배포와 장기 운영을 전제로 한 구성이 아니다.

- Backend 기본값은 `sqlite:///./contract_check.db`다.
- DB에는 문서 메타데이터뿐 아니라 분리된 조항 본문이 저장된다.
- 사용자별 접근 제어와 데이터 소유권 모델이 없다.
- schema migration 도구와 운영 migration 절차가 없다.
- backup, restore, retention과 안전한 삭제 정책이 없다.
- 임시 filesystem을 사용하는 배포 환경에서는 재시작 시 DB가 사라질 수 있다.

외부 공개 전에는 영속 저장소 선택과 migration, backup·restore, 암호화, 최소 권한, 보관 기간과 삭제 절차를 별도 설계해야 한다.

## 환경변수

| 이름 | 현재 목적 | 기본값 | 운영 원칙 |
|---|---|---|---|
| `DATABASE_URL` | SQLAlchemy 연결 주소 | `sqlite:///./contract_check.db` | Backend에서만 설정하고 DB credential이 포함되면 Secret으로 관리 |
| `CORS_ALLOWED_ORIGINS` | 허용 Frontend origin | `http://localhost:5173` | 실제 HTTPS Frontend origin만 명시 |
| `VITE_API_BASE_URL` | 공개 API 기본 주소 | `http://localhost:8000` | 공개 가능한 HTTPS URL만 사용, Secret 금지 |

실제 `.env`는 커밋하지 않는다. 배포 환경에서는 플랫폼 또는 조직의 환경변수·Secret 관리 기능을 사용한다.

## CORS

- 운영에서는 실제 배포된 Frontend origin만 명시적으로 허용한다.
- wildcard origin은 사용하지 않는다. 현재 코드도 wildcard를 거부한다.
- origin에는 path, query와 fragment를 넣지 않는다.
- 허용 method는 현재 `GET`, `POST`, header는 `Accept`, `Content-Type`으로 제한되어 있다.
- 현재 `allow_credentials=False`이며 CORS는 인증·인가를 대체하지 않는다.
- preview 주소를 허용해야 한다면 무제한 pattern 대신 승인된 origin 관리 절차가 필요하다.

## 파일 업로드 제한

- `.txt` 한 파일만 지원한다.
- 최대 크기는 `1 * 1024 * 1024` bytes다.
- Backend는 UTF-8과 UTF-8 BOM 입력을 처리한다.
- PDF와 OCR은 지원하지 않는다.
- 애플리케이션 검증 전에 proxy 또는 플랫폼이 더 작은 제한을 적용하지 않는지 확인한다.
- 파일명에도 개인정보가 있을 수 있으므로 로그와 분석 도구에 불필요하게 전달하지 않는다.

## 로그와 개인정보

- 계약서 원문, 분리된 조항 본문과 마스킹 전 텍스트를 로그에 남기지 않는다.
- Provider 최소 입력과 원시 응답도 운영 로그에 남기지 않는다.
- 식별자, 상태, 안전한 오류 코드와 시간 정보만 필요한 범위에서 기록한다.
- 로그 접근 권한, 보관 기간, 삭제, 전송 암호화와 사고 대응 절차를 정한다.
- 오류 추적 서비스 도입 시 request body와 Frontend 사용자 입력 수집을 비활성화하거나 마스킹한다.
- 실제 개인정보 탐지가 완전하지 않을 수 있음을 전제로 한다.

## HTTPS와 Secret 관리

- Frontend와 Backend 모두 HTTPS를 사용한다.
- HTTP에서 HTTPS로의 전환과 mixed content 오류를 확인한다.
- DB credential과 향후 Backend Provider credential은 Backend 전용 Secret으로 관리한다.
- Secret을 source, build artifact, Frontend bundle, 로그와 문서에 넣지 않는다.
- Secret 접근 권한과 교체 절차를 최소 권한 원칙으로 관리한다.

## 프로세스 재시작과 헬스 체크

- Backend 프로세스의 자동 재시작과 종료 신호 처리 방식을 정한다.
- 현재 동기 분석은 서버 재시작 후 복구되지 않는다.
- 작업 생성 후 프로세스가 종료되면 사용자에게 안정적인 작업 복구를 제공할 수 없다.
- health check 성공을 분석 작업 복구나 DB 쓰기 가능 상태의 보장으로 해석하지 않는다.
- 배포 후 `/health`, CORS와 핵심 API smoke test를 별도로 수행한다.

## 비동기 작업 한계

분석 파이프라인은 작업 생성 HTTP 요청 안에서 동기 실행된다. `queued`와 `processing` 상태가 응답에서 관찰되지 않을 수 있으며 Frontend는 장시간 자동 폴링하지 않는다.

운영 분석 시간이 요청 timeout을 넘을 수 있다면 durable queue, worker, idempotency, 재시도·backoff, 취소, timeout, 상태 복구와 실패 사유 저장을 별도로 설계해야 한다. 이번 공개 준비에서는 이를 구현하지 않는다.

## 무료 배포 환경의 한계

특정 플랫폼을 확정하지 않는다. 무료 또는 제한형 환경을 검토할 때 다음을 확인한다.

- 유휴 상태 전환과 첫 요청 지연
- ephemeral filesystem과 SQLite 데이터 유실
- process·memory·CPU·request timeout 제한
- background worker 지원 여부
- custom domain과 HTTPS 지원 범위
- 환경변수와 Secret 관리 기능
- 로그 보관 및 개인정보 처리 조건
- 네트워크와 DB 연결 제한

가격, 정책과 지원 범위는 변경될 수 있으므로 플랫폼 선택 시점에 공식 조건을 다시 확인한다.

## 배포 후 검증 항목

- [ ] Frontend 첫 화면과 정적 자산 로드
- [ ] `/health` 응답
- [ ] 실제 Frontend origin의 CORS preflight와 API 요청
- [ ] 명백한 합성 TXT 업로드와 조항 표시
- [ ] 합성 분석 작업과 결과 조회
- [ ] 새 문서 선택 시 이전 상태 초기화
- [ ] 지원하지 않는 형식, 빈 파일과 초과 크기 오류
- [ ] Backend 중단과 복구 후 재시도
- [ ] 내부 오류, 본문과 식별자 미노출
- [ ] 작은 화면과 키보드·screen reader·색상 대비
- [ ] 로그에 원문과 개인정보가 없는지 확인
- [ ] DB persistence와 재시작 동작 확인

## 현재 미준비 항목

- 실제 배포 플랫폼과 운영 주소
- 운영 DB와 migration
- 인증·인가와 사용자별 접근 제어
- 문서·조항 보관 및 삭제 정책
- 운영 Secret 관리와 교체 절차
- HTTPS·도메인·certificate 구성
- 요청 제한, abuse 방지와 업로드 격리
- 운영 로그·모니터링·경보와 사고 대응
- 동기 분석 timeout과 작업 재시작 복구
- 실제 Provider 승인과 데이터 처리 계약
- 실제 screen reader·전문 대비 측정

## 준비 판단

**합성 데이터로 제한한 기술 시연은 조건부 준비 가능**하다. 실제 계약서와 실제 개인정보 처리는 인증, 접근 제어, 데이터 보관·삭제, 운영 DB, HTTPS와 보안 검토를 완료하기 전까지 금지한다.
