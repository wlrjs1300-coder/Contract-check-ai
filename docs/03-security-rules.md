# 보안 및 커밋 금지 규칙

## 1. 목적

ContractCheck AI는 계약서 파일을 다루는 프로젝트이므로, 개인정보와 민감정보 보호를 최우선으로 고려한다.

본 문서는 공개 GitHub 저장소에 올라가면 안 되는 파일과 정보, 그리고 커밋 전 확인 규칙을 정의한다.

## 2. 절대 커밋 금지 항목

다음 항목은 어떤 경우에도 공개 저장소에 커밋하지 않는다.

- `.env`
- API Key
- Secret
- Token
- Password
- DB 접속 정보
- JWT Secret
- 원본 계약서 파일
- 업로드된 PDF/DOC/DOCX/HWP/HWPX/TXT 파일
- 개인정보가 포함된 샘플 파일
- 검토 전 입력/출력 원문
- 로그 파일
- 임시 파일
- 로컬 DB 파일
- 개인 메모
- 작업 중간 산출물

검토 전 입력/출력 원문에는 외부 분석 도구의 입력·응답, 실제 사용자 요청·응답, 테스트 과정의 원문 입력·출력이 포함된다.

위 항목은 파일 내용뿐 아니라 커밋 메시지, PR 제목, PR 본문, PR 댓글, 터미널 출력, 스크린샷에도 포함하지 않는다.

## 3. 계약서 파일 처리 원칙

- 원본 계약서는 분석 중 임시 저장만 허용한다.
- 분석 완료 후 원본 파일은 삭제한다.
- DB에는 원본 계약서 전체 텍스트를 저장하지 않는다.
- 분석 API에는 마스킹된 조항 텍스트만 전달한다.
- 로그에는 계약서 원문이나 개인정보가 남지 않게 한다.
- 실제 사용자 요청/응답 원문은 로그에 남기지 않는다.
- 마스킹 전 텍스트는 로그, 오류 메시지, 터미널 출력에 남기지 않는다.
- 계약서 원문이나 마스킹 전 텍스트가 포함된 디버그 출력은 커밋하지 않는다.

## 4. 개인정보 마스킹 대상

MVP 단계의 주요 마스킹 대상은 다음과 같다.

| 유형 | 예시 | 마스킹 예시 |
|---|---|---|
| 이름 | 홍길동 | [PERSON_1] |
| 전화번호 | 010-0000-0000 | [PHONE_1] |
| 이메일 | sample@example.com | [EMAIL_1] |
| 주소 | 서울특별시 예시구 예시로 123 | [ADDRESS_1] |
| 주민등록번호 | 900101-1234567 | [RRN_1] |
| 계좌번호 | 000-0000-0000 | [ACCOUNT_1] |
| 사업자등록번호 | 000-00-00000 | [BIZ_NO_1] |

## 5. 로그 보안 규칙

다음 코드는 사용하지 않는다.

```python
print(contract_text)
print(original_text)
logger.info(contract_text)
logger.error(request_body)
```

로그에는 실제 사용자 요청/응답 원문, 계약서 원문, 마스킹 전 텍스트가 남지 않게 한다.

로그에는 다음 정보만 남긴다.

- document_id
- user_id
- job_id
- status
- error_code
- created_at
- completed_at

## 6. .gitignore 필수 항목

```gitignore
# env
.env
.env.*
!.env.example

# secrets
*.pem
*.key
*.p12
*.pfx
secrets/
credentials/
config/secrets.*

# logs
*.log
logs/

# dependencies
node_modules/
.venv/
venv/
__pycache__/

# build
dist/
build/
target/
out/

# database
*.db
*.sqlite
*.sqlite3
data/
mysql-data/

# raw contract/document files
*.pdf
*.doc
*.docx
*.hwp
*.hwpx
*.txt

# allow safe sample text files only
!docs/samples/*.sample.txt
!backend/tests/fixtures/*.sample.txt

# uploaded files
uploads/
storage/
tmp/
temp/
documents/
contracts/
originals/

# generated reports
reports/
exports/
downloads/

# private working notes
private-docs/
raw-notes/
temp-analysis/
local-contracts/
scratch/

# editor
.vscode/
.idea/
.DS_Store
Thumbs.db
```

## 7. 커밋 전 검색 명령어

커밋 전 다음 명령어로 민감정보 포함 여부를 확인한다.

### macOS/Linux/Git Bash

```bash
grep -R "API_KEY" .
grep -R "SECRET" .
grep -R "PRIVATE_KEY" .
grep -R "password" .
grep -R "sk-" .
grep -R "010-" .
grep -R "주민등록" .
grep -R "계좌" .
```

### Windows PowerShell

```powershell
Get-ChildItem -Path . -Recurse -File -Force -ErrorAction SilentlyContinue |
  Where-Object {
    $_.FullName -notmatch '\\.git\\|\\node_modules\\|\\.venv\\|\\venv\\|\\dist\\|\\build\\'
  } |
  Select-String -Pattern "API_KEY","SECRET","PRIVATE_KEY","password","sk-","010-","주민등록","계좌" -SimpleMatch
```

검색 결과에는 `docs/samples/`와 `backend/tests/fixtures/`에 있는 가상 샘플 데이터가 포함될 수 있다. 검색 결과는 실제 개인정보 또는 실제 Secret과 구분하여 확인한다.

## 8. 변경 파일 및 커밋 예정 파일 검증

작업 후 커밋 전에는 다음 순서로 변경 파일과 커밋 예정 파일을 확인한다.

```bash
git status
git diff
git diff --cached
git diff --cached --name-only
```

확인할 항목:

- 의도한 파일만 변경되었는가
- `.env`, 업로드 파일, 원본 계약서, 로그 파일, 임시 파일이 포함되지 않았는가
- API Key, Secret, Token, Password, DB 접속 정보가 포함되지 않았는가
- 실제 사용자 요청/응답 원문, 계약서 원문, 마스킹 전 텍스트가 포함되지 않았는가
- PR 제목, PR 본문, 커밋 메시지에 민감정보가 포함되지 않았는가
- 터미널 출력이나 스크린샷에 로컬 경로, 계정 정보, 인증 정보가 포함되지 않았는가
- 자동 삽입된 공동 작성자 문구가 포함되지 않았는가

커밋 후에는 다음 명령어로 커밋 메시지와 공동 작성자 문구를 확인한다.

```bash
git log -1 --pretty=full
```

## 9. 민감정보 노출 시 대응 원칙

민감정보가 로컬 커밋 또는 원격 저장소에 포함된 경우 단순 삭제만으로 해결된 것으로 보지 않는다.

- 로컬 변경에만 포함된 경우: 커밋하지 않고 즉시 제거한 뒤 `git diff`로 제거 여부를 확인한다.
- 로컬 커밋에 포함된 경우: 원격 push 전이라도 해당 커밋을 그대로 공유하지 않고, 이력 정리 또는 새 커밋 정리 방식을 선택한다.
- 원격 저장소에 push된 경우: 저장소 이력 정리, 영향 범위 확인, 필요한 접근 권한 점검을 진행한다.
- API Key, Secret, Token, Password가 노출된 경우: 문서나 코드에서 삭제하는 것만으로 끝내지 않고 즉시 폐기하고 재발급한다.
- 노출된 값이 사용된 서비스의 접근 로그와 권한 범위를 확인한다.
- 재발 방지를 위해 `.gitignore`, 환경변수 관리, 로그 출력, PR 검증 절차를 보완한다.

## 10. PR 전 보안 체크

- [ ] `.env` 파일이 포함되지 않았다.
- [ ] API Key, Secret, Token이 포함되지 않았다.
- [ ] 원본 계약서 파일이 포함되지 않았다.
- [ ] 업로드 파일, 임시 파일, 로그 파일이 포함되지 않았다.
- [ ] 검토 전 입력/출력 원문이 포함되지 않았다.
- [ ] 개인정보가 포함된 샘플 데이터가 포함되지 않았다.
- [ ] 계약서 원문이 로그에 출력되지 않는다.
- [ ] 실제 사용자 요청/응답 원문과 마스킹 전 텍스트가 로그에 출력되지 않는다.
- [ ] PR 제목, PR 본문, 커밋 메시지에 민감정보가 포함되지 않았다.
- [ ] 터미널 출력과 스크린샷에 민감정보가 포함되지 않았다.
- [ ] 자동 삽입된 공동 작성자 문구가 포함되지 않았다.

## 11. 샘플 데이터 규칙

샘플 계약서가 필요한 경우 반드시 가상의 데이터만 사용한다.

허용 위치:

```text
docs/samples/
backend/tests/fixtures/
```

파일명 규칙:

```text
employment-contract.sample.md
housing-lease.sample.md
employment-contract.sample.txt
housing-lease.sample.txt
```

사용 가능한 예시:

- 이름: 홍길동, 김민수 등 일반 가명
- 전화번호: 010-0000-0000
- 이메일: sample@example.com
- 주소: 서울특별시 예시구 예시로 123
- 계좌번호: 000-0000-0000

실제 인물, 실제 회사, 실제 주소, 실제 계약 내용은 사용하지 않는다.
