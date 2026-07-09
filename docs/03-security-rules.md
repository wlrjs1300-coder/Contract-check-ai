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
- 외부 도구 입력/출력 원문
- 로그 파일
- 임시 파일
- 로컬 DB 파일
- 개인 메모
- 작업 중간 산출물

## 3. 계약서 파일 처리 원칙

- 원본 계약서는 분석 중 임시 저장만 허용한다.
- 분석 완료 후 원본 파일은 삭제한다.
- DB에는 원본 계약서 전체 텍스트를 저장하지 않는다.
- 분석 API에는 마스킹된 조항 텍스트만 전달한다.
- 로그에는 계약서 원문이나 개인정보가 남지 않게 한다.

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
Select-String -Path .\* -Pattern "API_KEY","SECRET","PRIVATE_KEY","password","sk-","010-","주민등록","계좌" -Recurse
```

## 8. PR 전 보안 체크

- [ ] `.env` 파일이 포함되지 않았다.
- [ ] API Key, Secret, Token이 포함되지 않았다.
- [ ] 원본 계약서 파일이 포함되지 않았다.
- [ ] 업로드 파일, 임시 파일, 로그 파일이 포함되지 않았다.
- [ ] 외부 도구 입력/출력 원문이 포함되지 않았다.
- [ ] 개인정보가 포함된 샘플 데이터가 포함되지 않았다.
- [ ] 계약서 원문이 로그에 출력되지 않는다.
- [ ] 자동 삽입된 공동 작성자 문구가 포함되지 않았다.

## 9. 샘플 데이터 규칙

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
