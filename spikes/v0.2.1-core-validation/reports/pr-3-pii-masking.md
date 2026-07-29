# ContractCheck AI v0.2.1 PR-3 개인정보 탐지·마스킹 검증 보고서

## 1. 문서 목적

이 문서는 ContractCheck AI v0.2.1 PR-3의 개인정보 탐지·마스킹 기술 스파이크 구현 결과를 기록하는 검증 보고서이다.

이 문서는 다음을 의미하지 않는다.

- 법률 자문
- 실제 개인정보 처리 승인
- 외부 AI 전송 승인
- 서비스 출시 승인
- 개인정보 보호 또는 마스킹 완전성 보장

본 검증은 사전에 승인·동결된 합성 fixture와 expected JSON을 기준으로 로컬 Python 표준 라이브러리 기반 구현이 기대 결과와 일치하는지 확인한 기술 검증이다.

## 2. 검증 범위

### 포함 범위

- 사전 합성 근로계약서형 fixture 4개
- 개인정보 8종의 결정론적 탐지·마스킹
- 동일 값의 동일 마스크 토큰 재사용
- entity_type별 독립 번호 부여
- expected entity span 전체 치환
- false positive exclusion 구간 검증
- masked text residual entity 검증
- 원문 개인정보 비노출 검증
- 로컬 Python 표준 라이브러리 기반 평가

### 제외 범위

- 실제 계약서
- 실제 개인정보
- 실제 주민등록번호
- OCR
- PDF 입력
- 외부 AI
- 네트워크 전송
- 운영 서버
- 서비스 출시
- 법률 판단
- 비정형 자유 문장 NER
- 현재 taxonomy 외 개인정보 유형

## 3. 기준 커밋

### 동결 커밋

- SHA: `68d714a720328cb2df0faed7269d3b93a54cf140`
- 메시지: `test: freeze PII masking fixtures and expectations`

해당 커밋에서 fixture 4개와 expected JSON 1개가 구현 전에 승인·동결되었다.

### 구현 커밋

- SHA: `40da04308691827b3e91e7f65d725ad3c979abb4`
- 메시지: `feat: implement deterministic PII detection and masking`

해당 커밋은 구현 코드 2개 파일만 포함한다.

구현 결과에 맞추기 위해 expected JSON 또는 fixture를 수정하지 않았다.

### 동결 파일 불변 확인

| 파일 | HEAD^ blob SHA | HEAD blob SHA | 동일 여부 |
|---|---|---|---|
| `spikes/v0.2.1-core-validation/data/fixtures/pii-employment-01.sample.txt` | `f6c9645b3e54a019e71f0d69462957bdac130507` | `f6c9645b3e54a019e71f0d69462957bdac130507` | 동일 |
| `spikes/v0.2.1-core-validation/data/fixtures/pii-employment-02.sample.txt` | `426fc5c58d3c9abf17c6e43d8ce1b203db066a74` | `426fc5c58d3c9abf17c6e43d8ce1b203db066a74` | 동일 |
| `spikes/v0.2.1-core-validation/data/fixtures/pii-edge-01.sample.txt` | `5c7d313ae68c99ff11f6633905ff06798c2cc8d2` | `5c7d313ae68c99ff11f6633905ff06798c2cc8d2` | 동일 |
| `spikes/v0.2.1-core-validation/data/fixtures/pii-edge-02.sample.txt` | `6277eb1e4a7f72f4da9cb19d1aef9093620ebbac` | `6277eb1e4a7f72f4da9cb19d1aef9093620ebbac` | 동일 |
| `spikes/v0.2.1-core-validation/data/fixtures/pii-masking-expected.sample.json` | `4df7489fa3476b6cc78e6e9fa67025aa40245b44` | `4df7489fa3476b6cc78e6e9fa67025aa40245b44` | 동일 |

## 4. 구현 파일

### `detect_and_mask.py`

- 텍스트 normalization
- 개인정보 후보 탐지
- 마스크 토큰 할당
- masked text 생성
- 결과 메타데이터 생성

### `evaluate_pii_masking.py`

- expected JSON 로드
- fixture source SHA 검증
- actual/expected entity 비교
- ordinal, entity_type, offset, line, token, source_hash, warnings 비교
- document_warnings 비교
- masked_text_sha256 비교
- exclusion overlap 검증
- expected span 치환 검증
- masked text 재탐지 검증
- 보안 필드 검증
- 최종 PASS/FAIL 및 종료 코드 처리

## 5. 승인된 개인정보 taxonomy

| entity_type | 탐지 방식 | 마스크 토큰 |
|---|---|---|
| `person` | label 기반 | `[PERSON_n]` |
| `phone` | format 기반 | `[PHONE_n]` |
| `email` | format 기반 | `[EMAIL_n]` |
| `address` | label 기반 | `[ADDRESS_n]` |
| `date_of_birth` | label 기반 | `[BIRTH_n]` |
| `national_id_number` | format 기반 | `[RRN_n]` |
| `business_registration_number` | format 기반 | `[BIZ_NO_n]` |
| `account_number` | label 기반 | `[ACCOUNT_n]` |

현재 범위에서는 `postal_code`, `vehicle_number`, `ip_address`, `employee_id`를 탐지 대상으로 포함하지 않는다.

`회사:`는 `person` label로 취급하지 않는다.

label 기반 유형은 자유 문장 전체 NER을 수행하지 않고, 승인된 label 뒤의 제한된 값만 대상으로 한다.

## 6. 동결 데이터 구성

- test_cases: 4
- entity_taxonomy: 8
- expected entities: 26
- expected exclusions: 15
- authorship.method: `independent-human-authored-before-implementation`
- authorship.implementation_consulted: `false`
- authorship.status: `approved-frozen-before-implementation`

동결 파일 경로는 다음과 같다.

- `spikes/v0.2.1-core-validation/data/fixtures/pii-employment-01.sample.txt`
- `spikes/v0.2.1-core-validation/data/fixtures/pii-employment-02.sample.txt`
- `spikes/v0.2.1-core-validation/data/fixtures/pii-edge-01.sample.txt`
- `spikes/v0.2.1-core-validation/data/fixtures/pii-edge-02.sample.txt`
- `spikes/v0.2.1-core-validation/data/fixtures/pii-masking-expected.sample.json`

fixture 원문 내용은 이 보고서에 기록하지 않는다.

## 7. 평가 방법

평가는 다음 순서로 수행했다.

1. expected JSON 로드
2. fixture 로드
3. source SHA 검증
4. `detect_and_mask` 실행
5. expected entity와 actual entity 비교
6. ordinal, entity_type, offset, line, mask token, source hash, warnings 비교
7. document_warnings 비교
8. masked_text_sha256 비교
9. exclusion 구간 overlap 검증
10. expected entity span이 기대 mask token으로 치환되었는지 검증
11. masked text에 탐지기를 다시 실행해 residual entity 검증
12. 원문 값 필드와 원문 stdout 노출 여부 확인

평가기에는 탐지 정규식과 label 목록을 복제하지 않았다. 평가는 expected와 actual 비교 중심으로 작성되었다.

`test_case_id`는 평가 출력 식별 용도로만 사용하며, 구현 분기 조건으로 사용하지 않는다.

## 8. 평가 결과

| 항목 | 결과 |
|---|---|
| test_cases | 4/4 PASS |
| entities | 26/26 |
| exclusions | 15/15 |
| exclusion overlap | 0 |
| residual_entities | 0 |
| masked SHA | 모든 fixture PASS |
| py_compile | PASS |
| git diff --check | PASS |

최종 평가 출력 요약은 다음과 같다.

```text
PII masking evaluation: PASS
test_cases: 4/4
entities: 26/26
exclusions: 15/15
residual_entities: 0
```

## 9. Evaluator 독립성 검증

- 전화번호 탐지 정규식 복제 없음
- 이메일 탐지 정규식 복제 없음
- 주민등록번호 탐지 정규식 복제 없음
- 사업자등록번호 탐지 정규식 복제 없음
- label 목록 복제 없음
- fixture 파일명별 분기 없음
- test_case_id별 구현 분기 없음
- expected offset 하드코딩 없음
- expected hash 하드코딩 없음
- expected JSON 생성·수정 코드 없음
- expected와 actual 비교 중심

`test_case_id`는 평가 결과 출력에서 케이스 식별을 위해 사용된다.

## 10. Residual 이중 검증

### 10.1 Expected span 치환 검증

expected entity span이 expected mask token으로 치환되었는지 확인한다.

이 검증이 실패하면 전체 평가가 FAIL이 된다.

### 10.2 Detector 재실행 검증

masked text를 `detect_entities`에 다시 입력해 residual entity가 0인지 확인한다.

이 검증이 실패하면 전체 평가가 FAIL이 된다.

두 검증 모두 통과했다.

## 11. Security Scope

- 합성 fixture만 사용
- 외부 AI 없음
- 네트워크 호출 없음
- 외부 패키지 설치 없음
- 원문 개인정보 결과 필드 저장 없음
- 원문 개인정보 stdout 출력 없음
- 원문 개인정보 logging 없음
- 임시 파일 자동 생성 없음
- fixture별 하드코딩 없음
- expected offset 하드코딩 없음
- 로컬 절대경로 하드코딩 없음
- 마스크 토큰 일관성 계산을 위해 원문 값은 메모리에서만 일시 사용
- 결과 객체에 `text`, `raw_text`, `value`, `source_value`, `matched_text` 필드 없음

## 12. `--output` 기능 관찰

`detect_and_mask.py`에는 사용자가 `--output`을 명시했을 때 masked JSON을 파일로 쓰는 기능이 있다.

이 기능은 자동 파일 생성 기능이 아니며, 사용자가 명시적으로 옵션을 지정한 경우에만 동작한다.

현재 합성 로컬 스파이크 범위에서는 차단 이슈로 보지 않는다.

다만 실제 데이터 단계에서는 별도 저장·보관·접근통제 정책이 필요하다. 마스킹 결과도 재식별 검토 전까지 개인정보 또는 가명정보일 가능성을 배제하지 않는다.

## 13. Legal Scope

이 보고서는 법률 검토 완료를 의미하지 않는다.

이 보고서는 실제 개인정보 처리 승인을 의미하지 않는다.

이 보고서는 실제 주민등록번호 서버 처리를 허용하지 않는다.

이 보고서는 실제 계약서 업로드를 허용하지 않는다.

마스킹 전 원문을 외부 AI로 전송하는 것은 현재 범위에서 금지된다.

마스킹된 입력의 외부 AI 전송 여부는 현재 보류 상태이다.

서비스 출시는 현재 범위에서 금지된다.

실제 서비스 적용 전 개인정보·보안·법률 표현 검토가 필요하다.

ContractCheck AI는 계약서 사전점검 참고 도구로 정의되며, 법률 전문가를 대체하지 않는다.

## 14. 표현 기준

사용 가능한 표현:

- 확인 필요
- 추가 검토 권장
- 전문가 검토 권고

주의가 필요한 표현:

- 위험 가능성
- 조건 확인 필요
- 추가 확인 필요

사용하지 않는 표현:

- 법률 판단을 확정하는 표현
- 계약 효력이나 결과를 보장하는 표현
- 분쟁 결과를 예측하거나 보장하는 표현
- 안전성을 단정하는 표현

## 15. Known Limits

- 합성 fixture 4개만 검증
- 한국어 근로계약서형 고정 패턴 중심
- 비정형 자유 문장 이름·주소 추론 미지원
- OCR 오류 미검증
- PDF 줄바꿈·레이아웃 미검증
- 다양한 전화번호 형식 미검증
- 다양한 이메일 국제화 형식 미검증
- 실제 주민등록번호 적법성 미검증
- 제3자 개인정보 처리 근거 미검증
- 마스킹 결과의 법적 성격 미확정
- 외부 AI 위탁·국외 이전 미검증
- 저장 기간·파기·접근통제 정책 미확정
- `--output` 결과 파일의 운영 보안 정책 미확정
- 실제 계약서에서의 recall/precision 미검증
- 현재 성공 결과가 실제 서비스 준비 완료를 의미하지 않음

## 16. 최종 판정

### 기술 검증 판정

PASS

근거:

- 동결 expected 유지
- 4/4 test case 통과
- 26/26 entity 일치
- 15/15 exclusion 검증
- exclusion overlap 0
- residual entity 0
- evaluator 독립성 유지
- 원문 개인정보 비노출
- 네트워크 호출 없음

### 승인 범위

승인:

- 합성 fixture 기반 로컬 PII 탐지·마스킹 기술 스파이크 결과 기록
- PR-3 코드 및 평가 결과에 대한 다음 독립 검토 단계 진행

승인하지 않음:

- 실제 개인정보 처리
- 실제 계약서 처리
- 실제 주민등록번호 처리
- 외부 AI 전송
- 정식 서비스 출시

## 17. 다음 단계

1. GPT 보고서 검토
2. Claude 독립 코드·보고서 검토
3. Major 이슈가 있으면 수정 후 재검토
4. Major 이슈 0 확인
5. 사용자 승인 후 push
6. `feature/v0.2.1-pii-masking`에서 `develop`으로 PR 생성
7. CI 및 PR 검증
8. merge commit 방식으로 병합
9. 로컬 develop 동기화 및 clean 확인
10. PR-4 masking usefulness 준비

아직 push 또는 PR 단계가 아니다.
