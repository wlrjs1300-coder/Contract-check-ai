# ADR-007: 텍스트 PDF parser 선택

- Status: Accepted for v0.6.1
- Date: 2026-07-20
- Decision: `pypdf==6.14.2`
- Scope: 텍스트 레이어 PDF의 직접 추출

## Context

v0.6 Phase 2는 PDF 원본을 안전하게 검증하고 페이지별 텍스트를 직접 추출하는 별도 extraction resource가 필요하다. 이미지 OCR, 스캔 PDF OCR, bbox/layout 복원과 실제 분석 연결은 이번 범위가 아니다.

후보는 pypdf와 pdfminer.six다. PyMuPDF는 성능과 layout 기능을 가진 후보지만 공개 패키지가 AGPL-3.0 또는 별도 상용 라이선스이므로 이번 1차 채택에서 제외한다. 프로젝트 배포·공개 방식과 상용 라이선스 적합성을 별도 검토하기 전에는 도입하지 않는다.

## Decision drivers

- 한국어 ToUnicode mapping과 조항 번호 추출
- 페이지 단위 API와 페이지 순서 유지
- 암호화·손상 PDF 감지
- 표와 줄바꿈의 기본 보존
- 20 MiB·100페이지 제한 안의 메모리와 처리 시간
- Windows 개발과 Linux 배포 후보의 동일 설치 방식
- 라이선스와 공급망 검토 가능성
- 순수 Python 여부와 native binary 부재
- 향후 bbox/layout 확장성
- 보안 업데이트 추적
- FastAPI와 SQLAlchemy 구조에 대한 통합 난이도

## Compared options

| 기준 | pypdf 6.14.2 | pdfminer.six 20260107 |
|---|---|---|
| 주 용도 | PDF 읽기·쓰기·페이지 조작·텍스트 추출 | 텍스트·layout 분석 중심 |
| 한국어 | PDF의 올바른 ToUnicode mapping에 의존 | PDF의 font mapping과 layout 분석에 의존 |
| 조항 번호 | 페이지 텍스트에서 유지 가능, 합성 테스트 통과 | 텍스트 추출 가능, 별도 통합 스파이크 필요 |
| 표·줄바꿈 | 단순 직접 추출에는 충분하나 시각적 표 복원은 보장하지 않음 | LAParams와 layout 객체로 더 세밀한 확장 가능 |
| 페이지 순서 | `reader.pages` 순서로 명시적 처리 | 페이지 iterator·page number로 처리 가능 |
| 암호화 | `is_encrypted`로 추출 전 거부 가능 | parser·document 단계의 암호 처리 필요 |
| 손상 파일 | strict parser 오류를 경계에서 일반화 가능 | parser 예외 경계 구성 가능 |
| 메모리·시간 | 작은 순수 Python wheel, 현재 최소 추출 경계가 단순 | layout 분석 범위가 넓고 wheel 크기·통합 범위가 큼 |
| Windows/Linux | `py3-none-any` wheel, Python 3.9 이상 | `py3-none-any` wheel, Python 3.10 이상 |
| 라이선스 | BSD-3-Clause | MIT |
| 순수 Python | 예 | 예 |
| bbox/layout | visitor·추출 mode가 있으나 이번 계약에는 미포함 | layout 객체와 bbox 확장에 유리 |
| FastAPI 통합 | `PdfReader`와 페이지 loop로 작음 | high-level 또는 layout API 선택이 추가로 필요 |
| 보안 업데이트 | 고정 버전과 upstream release를 추적해야 함 | 고정 버전과 upstream release를 추적해야 함 |

두 후보 모두 한국어 정확성을 보장하지 않는다. 결과는 PDF 내부 font encoding과 ToUnicode mapping 품질에 좌우된다. parser 선택은 OCR 품질 또는 법률적 적합성을 의미하지 않는다.

## Local spike

실제 계약서나 실제 개인정보를 사용하지 않고 테스트 실행 중 메모리에서 합성 PDF를 생성했다.

검증 사례:

- 1페이지와 2페이지 한글 텍스트
- `제1조`, `제2조` 번호와 페이지 순서
- 빈 페이지와 전체 빈 PDF
- 암호화·손상 PDF
- 시그니처·MIME 충돌
- 100페이지 초과와 크기 제한
- 저품질 텍스트의 OCR 필요 경고
- parser 예외와 cleanup 실패

pypdf는 최소 모델에 필요한 한국어 ToUnicode text, 조항 번호와 페이지 순서를 추출했고 암호화·구조 오류를 안전한 오류 코드로 분류할 수 있었다. 표의 시각적 셀 구조나 bbox 품질은 검증하지 않았으며 v0.6.1 지원 범위로 주장하지 않는다.

## Decision

v0.6.1의 텍스트 PDF 직접 추출 parser로 `pypdf==6.14.2`를 고정한다.

선택 근거:

- 현재 최소 계약이 페이지별 text와 warning이며 bbox/layout을 요구하지 않는다.
- BSD-3-Clause와 순수 Python·OS 독립 wheel이 현재 Windows/Linux 후보에 적합하다.
- 별도 PDF 생성 dependency 없이 같은 라이브러리와 명시적 합성 객체로 회귀 테스트를 구성할 수 있다.
- `PdfReader(strict=True)`, `is_encrypted`, `reader.pages`, `page.extract_text()`로 경계가 작고 검토 가능하다.
- pdfminer.six의 layout 장점은 Phase 5의 위치 대응 요구가 구체화될 때 별도 비교 가치가 있다.

## Security implications

- PDF는 신뢰할 수 없는 입력이며 확장자·MIME·시그니처·strict parser를 순차 검증한다.
- parser 호출 전에 바이트 제한을 적용하고 parser 뒤 페이지·추출 문자 수를 독립 제한한다.
- parser 내부 예외와 원문·경로를 API에 노출하지 않는다.
- 원본은 저장소 밖 임시 root의 요청별 무작위 디렉터리와 서버 생성 파일명으로 처리한다.
- cleanup 성공 검증 전에는 extraction 레코드와 `review_required` 성공 응답을 만들지 않는다.
- pypdf가 polyglot, 악성 PDF 또는 텍스트 정확성을 완전히 탐지한다고 보장하지 않는다.
- upstream 보안 공지와 고정 버전 업데이트를 정기적으로 검토해야 한다.

## Consequences

- production dependency로 pypdf 6.14.2가 추가된다. 테스트는 같은 dependency를 사용하며 별도 PDF 생성 패키지는 추가하지 않는다.
- 직접 추출 결과는 항상 `review_required`이고 사용자 확인 전 조항 분리·분석으로 이동하지 않는다.
- 빈 페이지나 짧고 의심스러운 텍스트는 `ocr_required` 경고를 만들지만 이번 단계에서 OCR을 실행하지 않는다.
- bbox, confidence, 표 구조 복원과 시각적 읽기 순서는 제공하지 않는다.

## Replacement strategy

parser 세부는 `pdf_extraction` service 안에 격리한다. 향후 layout·bbox 품질이 필요하면 동일 합성 contract test로 pdfminer.six 또는 승인된 다른 parser를 비교한다. 교체 시 API의 페이지 순서, warning, 오류, cleanup과 TXT 회귀 계약을 유지해야 한다.

PyMuPDF를 재검토하려면 AGPL 의무와 상용 라이선스, native binary 공급망, Windows/Linux 배포를 별도 승인한다.

## References

- pypdf PyPI: <https://pypi.org/project/pypdf/>
- pypdf installation: <https://pypdf.readthedocs.io/en/stable/user/installation.html>
- pdfminer.six PyPI: <https://pypi.org/project/pdfminer.six/>
- pdfminer.six high-level API: <https://pdfminersix.readthedocs.io/en/master/reference/highlevel.html>
- PyMuPDF PyPI licensing: <https://pypi.org/project/pymupdf/>
