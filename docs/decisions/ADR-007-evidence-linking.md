# ADR-007: 페이지 기반 조항 근거 연결(증거) 전략

## 상태

- 수락

## 결정

- Evidence 생성/검증 로직은 `backend/app/services/evidence_linking.py`에서 단일 책임으로 관리한다.
- 분석 결과 저장 전 clause 단위로 evidence 매핑을 검증하며, 하나의 finding에서 실패하면 해당 분석 job이 실패한다.
- quote 매칭은 텍스트 정규화(NFC+LF) 기반으로 수행하되, 다중 일치 시 ambiguous로 처리한다.

## 불변성/성능

- 스냅샷은 페이지 단위로 순서를 유지해 canonical hash를 계산한다.
- 성능 상수: evidence 최대 10개, 후보 최대 50개, source_text 최대 길이 제한 등으로 검증 비용 상한을 둔다.
