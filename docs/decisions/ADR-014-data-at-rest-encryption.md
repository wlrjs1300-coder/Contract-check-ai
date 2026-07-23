# ADR-014: Data-at-Rest Encryption and Key Management

## 상태

proposed for v0.7.5 implementation

## 배경

계약 원문과 그로부터 파생된 분석 문장은 개인정보와 계약상 민감정보를 포함할 수 있다. v0.7.5는 application layer에서 저장 암호화를 실제 구현하고, keyring, rotation 기반, fail-closed 오류 계약, migration과 테스트를 함께 제공해야 한다. 현재 문서는 그 구현 기준을 정한다.

## 확정된 원칙

- application-layer authenticated encryption을 사용한다.
- key lifecycle은 active·decrypt_only·retired 상태로 구분하며, runtime keyring에는 active와 decrypt_only key만 유지한다.
- 오류는 fail-closed로 처리한다.
- raw key는 app state, DB, 로그, 예외, API 응답에 노출하지 않는다.
- `AES-256-GCM`을 우선 사용한다.
- field-level 또는 sensitive-subfield-level encryption을 적용한다.
- raw Provider request/response, raw token mapping, raw PII와 중복 원문은 저장하지 않는다.
- 전체 `extra_data` 투명 암호화보다 service layer의 명시적 암복호화를 우선한다.

## 구현 전 확정 필요

- 정확한 encrypted 컬럼과 envelope 저장 타입
- migration revision과 upgrade/downgrade 구조
- scalar 필드별 ORM 적용 방식
- `Document.filename`과 `Extraction.filename_display` 처리
- AESGCM 결합 payload를 저장하는 컬럼 형식
- `owner_id` AAD 정책의 구현 상세
- 제한된 재암호화 helper의 범위와 transaction 단위

## 소유권 경계

- `User`는 인증 주체이다.
- `Document`, `Extraction`은 `owner_id`를 직접 저장한다.
- `AnalysisJob`과 `Clause`는 `Document.owner_id`를 따른다.
- `AnalysisResultItem`은 `AnalysisJob`을 거쳐 `Document.owner_id`를 따른다.
- `ExtractionPage`는 `Extraction.owner_id`를 따른다.
- 하위 리소스의 암복호화 context에는 검증된 부모 관계에서 얻은 소유자 값을 사용한다.

## Envelope 결정 초안

```json
{
  "enc_version": 1,
  "key_id": "synthetic-key-v1",
  "algorithm": "AES-256-GCM",
  "nonce": "...",
  "ciphertext": "..."
}
```

- `nonce`는 Base64로 저장한다.
- `ciphertext`는 AESGCM이 반환한 ciphertext와 authentication tag 결합값 전체를 Base64로 저장한다.
- plaintext AAD는 envelope에 저장하지 않는다.
- envelope 필드는 strict type과 allowlist로 검증하며 누락·추가 필드를 fail-closed 처리한다.
- AAD는 서버가 `resource_type`, `record_id`, `field_name`, `owner_id`, `schema_version`으로 매번 재구성한다.
- 외부에서 제공되거나 DB에 저장된 AAD 문자열은 복호화 입력으로 신뢰하지 않는다.

## AAD와 소유권 이전

v0.7.5에서는 소유권 이전 기능을 지원하지 않으므로 `owner_id`를 AAD에 포함하는 정책을 권장한다.

장점:

- 다른 소유자 context에서 복호화를 차단한다.
- ciphertext를 다른 사용자 row로 복사하는 공격에 대한 방어를 강화한다.
- 소유권, record, field의 결합 무결성을 제공한다.

단점:

- 소유권 이전 시 반드시 재암호화해야 한다.
- 소유자 변경과 ciphertext 재생성을 원자적으로 처리해야 한다.
- 소유자 값만 변경하면 기존 ciphertext를 복호화할 수 없다.

따라서 소유자 값만 변경하는 작업을 금지한다. 향후 이전 기능을 도입하기 전 재암호화 transaction, rollback, 감사 절차를 설계해야 한다.

canonical AAD는 UTF-8 canonical JSON을 우선 검토하며 key 정렬, 공백 제거, 타입 변환 금지, 누락 값 금지를 적용한다.

## 대안 비교

### Application-layer envelope

- 장점: 필드별 통제, key rotation, AAD 결합, raw DB 노출 감소
- 단점: 서비스·migration·테스트 복잡도 증가

### DB 또는 disk 전체 암호화만 적용

- 장점: 적용이 단순함
- 단점: 애플리케이션·DB 권한 탈취와 필드별 경계를 충분히 통제하지 못함

### 전체 JSON 투명 암호화

- 장점: 초기 구현이 단순해 보임
- 단점: 운영 메타데이터 조회, nested migration, 이중 암호화, 부분 변경이 어려움

application-layer envelope와 명시적 service 경계를 선택한다. disk·backup 암호화는 방어 계층으로 추가할 수 있지만 이를 대체하지 않는다.

## Rotation 결정

- active key는 encrypt/decrypt 가능하다.
- decrypt_only key는 기존 ciphertext 복호화만 가능하다.
- retired key는 runtime keyring에서 제거하며 해당 `key_id`를 사용하는 ciphertext가 없어야 한다.
- 신규 쓰기는 active key만 사용한다.
- envelope의 `key_id`로 기존 key를 선택한다.
- key usage inspection과 제한된 단건 또는 batch 재암호화 helper를 v0.7.5 범위에 둔다.
- background bulk worker, KMS 자동 rotation, multi-region orchestration, backup 전체 재암호화는 후속 범위이다.

retired 전에는 사용 row 0건, backup·snapshot 영향, 재암호화 완료, 감사 기록, rollback 가능성을 확인한다.

## 결과

v0.7.5는 설계뿐 아니라 코드, migration, 테스트까지 구현한다. 다만 완료 후에도 실제 개인정보 사용과 보관형 실운영에는 데이터 생명주기, backup, 운영 key custody, 감사 및 별도 보안 승인이 필요하다.

## 후속 작업

- 운영 KMS 또는 vault 연동
- background bulk re-encryption worker
- backup과 snapshot의 key lifecycle 통합
- multi-region rotation orchestration
- 소유권 이전 transaction과 rollback 설계

