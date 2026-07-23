# ADR-013: JWT 인증 및 사용자 소유권 기반 API 격리

## 상태

accepted

## 배경

리소스 식별자만으로 접근을 허용하면 타 사용자 데이터에 접근하는 IDOR 위험이 생긴다. v0.7.4는 사용자 인증과 부모 리소스 기반 소유권 판정을 적용해 API 경계를 사용자별로 격리한다.

## 결정

1. PyJWT HS256 기반 bearer token 인증을 사용한다.
2. `User`를 인증 주체로 두고 `Document`와 `Extraction`에 `owner_id`를 저장한다.
3. `AnalysisJob`은 연결된 `Document`를 통해 소유권을 상속한다.
4. `Clause`, `AnalysisResultItem`, `ExtractionPage`에는 `owner_id`를 중복 저장하지 않고 부모 리소스 경계를 따른다.
5. 인증된 사용자의 cross-user `Document`, `Extraction`, `AnalysisJob` 접근은 missing resource와 동일한 고정 `404`로 처리한다.
6. production schema 변경은 Alembic migration을 기준으로 한다.

## 공개 및 보호 경로

공개 경로는 다음으로 제한한다.

- `/health`
- OpenAPI 문서
- `/auth/register`
- `/auth/login`

그 밖의 보호 API는 현재 사용자 인증과 리소스 소유권 검증을 거친다. 테스트용 인증 override는 production 기능이 아니다.

## JWT 계약

- `JWT_SECRET`은 UTF-8 기준 최소 32바이트다.
- TTL은 5분 이상 60분 이하이며 기본값은 15분이다.
- 필수 claim은 `sub`, `iat`, `exp`, `jti`, `iss`, `aud`, `ver`이다.
- issuer, audience, signature를 검증한다.
- `sub`와 `jti`는 canonical lowercase UUID 문자열만 허용한다.
- `iat`, `exp`, `ver`는 정확한 `int` 타입만 허용하고 외부 입력을 형 변환하지 않는다.
- `exp > iat`, 미래 `iat` 제한, 사용자 `auth_version` 일치, 활성 사용자 여부를 검증한다.
- token payload에는 email, `owner_id`, resource ID를 포함하지 않는다.

## 비밀번호 계약

- pwdlib Argon2로 해시한다.
- 12자 이상 128자 이하만 허용하고 null byte를 거부한다.
- 앞뒤 공백을 임의로 제거하지 않는다.
- 평문 비밀번호를 저장하지 않는다.
- 존재하지 않는 email도 dummy Argon2 verify를 실행한다.
- 로그인 실패 응답은 계정 존재 여부와 관계없이 동일하다.

## 오류 경계

- 인증 실패: `401`
- authenticated cross-user resource: `404`
- 내부 오류: 세부 정보를 노출하지 않는 일반 `500` 계약
- DB `IntegrityError`: raw SQL, DB 오류, 식별자, 소유자 정보 비노출

동일 ID의 타 사용자 `Document`가 존재하는 extraction 기반 분석 요청은 해당 문서를 재사용하거나 같은 PK로 새 문서를 생성하지 않고 일반 `404`로 차단한다.

## migration 결정

revision 체인은 `0001_current_schema_baseline` → `0002_auth_ownership`이다. `0002_auth_ownership` 실행 전 legacy `documents` 또는 `extractions` row가 있으면 사용자 및 소유권 schema를 생성하기 전에 중단한다. 자동 backfill이나 임의 사용자 배정은 수행하지 않는다.

## 결과

- `Document`와 `Extraction`의 소유권이 DB에 직접 저장된다.
- `AnalysisJob`은 `Document` join으로 권한을 판정한다.
- 하위 리소스는 부모 경계를 통해 격리된다.
- cross-user 리소스의 존재 및 내용은 API 응답에 노출되지 않는다.
- SQLite 테스트에서도 외래 키 제약을 활성화한다.

## 범위 외

- refresh token
- token blacklist 및 revocation
- rate limiting 및 account lockout
- 운영 비밀번호 정책
- 관리자 및 RBAC
- 실제 개인정보 pilot 승인
