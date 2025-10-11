# 🚀 락카키 시스템 실제 도입 계획서

> **작성일**: 2025-10-10  
> **대상**: 헬스장 락카키 자동 대여 시스템  
> **방식**: 다운-탑 (Bottom-Up) - 로컬 완성 → 중앙 연동

---

## 📋 **전체 로드맵**

```
Phase 1: 로컬 시스템 완성 (1-2일)
  ├─ 데이터베이스 초기화 ✅ 완료
  ├─ 회원 명단 초기 등록 ← 작업 필요
  └─ 독립 운영 시작 테스트
      ↓
Phase 2: 안정화 및 운영 (1-2주)
  ├─ 실제 센터에서 운영
  ├─ 일일 신규 회원 추가
  └─ 오류 수집 및 개선
      ↓
Phase 3: 중앙 연동 (선택사항, 나중에)
  ├─ 구글 시트 구조 확정
  ├─ 자동 동기화 설정
  └─ 중앙 관리 시스템 구축
```

---

## 🎯 **Phase 1: 로컬 시스템 완성 (1-2일)**

### **Step 1.1: 시스템 확인** ✅ 완료

**시스템 담당자 작업:**
- ✅ 데이터베이스 초기화 완료 (140개 락카)
- ✅ 코드 검증 완료 (35개 테스트 통과)
- ✅ Git 커밋 및 푸시 완료

**확인 방법:**
```bash
cd /Users/yunseong-geun/Projects/raspberry-pi-gym-controller

# 데이터베이스 확인
sqlite3 locker.db "SELECT zone, COUNT(*) FROM locker_status GROUP BY zone;"
# 결과: MALE|70, FEMALE|50, STAFF|20

# 테스트 실행
python3 tests/database/test_database_manager.py
# 결과: OK (9 tests)
```

---

### **Step 1.2: 회원 명단 준비** 👤 귀하 작업 필요

**귀하가 준비할 것:**

**옵션 A: CSV 파일 (추천)**
```csv
# 파일명: 유효회원명단.csv
회원ID,이름,전화번호,회원권종류,만료일,바코드
M2025001,홍길동,010-1234-5678,premium,2025-12-31,123456789
M2025002,김철수,010-2345-6789,basic,2025-11-30,234567890
M2025003,이영희,010-3456-7890,vip,2026-01-15,345678901
... (500명)
```

**필수 컬럼:**
- `회원ID` 또는 `바코드`: 회원 식별자 (유니크해야 함)
- `이름`: 회원 이름
- `만료일`: YYYY-MM-DD 형식

**선택 컬럼:**
- `전화번호`: 010-xxxx-xxxx
- `회원권종류`: basic, premium, vip (기본값: basic)
- `상태`: active, suspended (기본값: active)

**옵션 B: 엑셀 파일 (.xlsx)**
```
# 파일명: 유효회원명단.xlsx
# 첫 번째 시트에 위와 동일한 구조
```

**옵션 C: 구글 시트에서 다운로드**
- 기존 관리 중인 구글 시트에서
- "유효회원" 필터링 적용
- "파일 → 다운로드 → CSV" 선택

---

### **Step 1.3: 대량 등록 스크립트 생성** 💻 시스템 담당자

**필요한 스크립트 (agent 모드에서 생성):**

1. **`scripts/import_members_csv.py`**
   - CSV 파일 읽기
   - 500명 일괄 등록
   - 중복 체크 및 건너뛰기
   - 진행 상황 표시

2. **`scripts/import_members_excel.py`**
   - Excel 파일 지원
   - 여러 시트 지원

---

### **Step 1.4: 회원 데이터 등록** 👤 귀하 작업

**실행:**
```bash
# CSV 파일로 등록
python3 scripts/import_members_csv.py 유효회원명단.csv

# 또는 Excel 파일로
python3 scripts/import_members_excel.py 유효회원명단.xlsx
```

**예상 결과:**
```
🚀 회원 데이터 일괄 등록 시작...
📄 파일: 유효회원명단.csv
📊 총 500명 발견

진행중... [====================] 100% (500/500)

✅ 성공: 495명
⚠️  중복: 3명 (이미 존재)
❌ 오류: 2명 (데이터 형식 오류)

📊 최종 결과:
   • 전체 회원: 495명
   • 유효 회원: 482명
   • 만료 회원: 13명
```

---

### **Step 1.5: 데이터 검증** 👤 귀하 작업

**DB Browser로 확인:**
1. DB Browser for SQLite 열기
2. `locker.db` 파일 열기
3. `members` 테이블 확인
   - 총 회원 수 확인
   - 샘플 몇 명 확인 (이름, 만료일 등)

**또는 터미널로:**
```bash
# 전체 회원 수
sqlite3 locker.db "SELECT COUNT(*) FROM members;"

# 유효 회원 수 (만료 안 됨, 활성화)
sqlite3 locker.db "
SELECT COUNT(*) 
FROM members 
WHERE status='active' AND (expiry_date IS NULL OR expiry_date > date('now'));
"

# 샘플 10명 확인
sqlite3 locker.db -header -column "
SELECT member_id, member_name, membership_type, expiry_date, status 
FROM members 
LIMIT 10;
"
```

---

### **Step 1.6: 시스템 테스트** 💻 시스템 담당자

**테스트 스크립트 실행:**
```bash
# 회원 검증 테스트
python3 -c "
from app.services.member_service import MemberService

ms = MemberService('locker.db')

# 실제 회원 ID로 테스트 (귀하가 알려주신 ID)
test_ids = ['12345', '23456', '만료된회원ID']

for member_id in test_ids:
    result = ms.validate_member(member_id)
    print(f'{member_id}: {result}')

ms.close()
"
```

---

## 🎯 **Phase 2: 일일 운영 (1-2주)**

### **Step 2.1: 센터 설치 및 가동** 👤 귀하 + 💻 시스템 담당자

**하드웨어 설치:**
- [ ] 라즈베리파이 설치 및 전원 연결
- [ ] 터치스크린 연결 및 세로 모드 확인
- [ ] ESP32 3개 USB 연결
  - /dev/ttyUSB0: 남성 락카 (esp32_male)
  - /dev/ttyUSB1: 여성 락카 (esp32_female)
  - /dev/ttyUSB2: 교직원 락카 (esp32_staff)
- [ ] 바코드 스캐너 연결
- [ ] 네트워크 연결 (WiFi 또는 이더넷)

**소프트웨어 설정:**
```bash
# 라즈베리파이에 SSH 접속
ssh raspberry-pi

# 코드 동기화
cd ~/gym-controller
git pull origin main

# 데이터베이스 복사 (회원 데이터 포함)
scp locker.db raspberry-pi:~/gym-controller/

# 키오스크 모드 시작
./scripts/start_kiosk.sh
```

---

### **Step 2.2: 일일 신규 회원 추가** 👤 귀하 작업

**매일 또는 주 1회:**

**방법 A: 간단 스크립트 (추천)**
```bash
# 라즈베리파이 또는 로컬에서
python3 scripts/add_daily_members.py

# 대화형으로 신규 회원 입력
# 완료 후 라즈베리파이에 동기화
```

**방법 B: CSV 파일**
```bash
# 1. 신규 회원 CSV 준비 (신규회원_20251010.csv)
# 2. 추가 실행
python3 scripts/import_members_csv.py 신규회원_20251010.csv

# 3. 라즈베리파이에 동기화
scp locker.db raspberry-pi:~/gym-controller/
```

**방법 C: DB Browser 직접 입력**
1. DB Browser로 `locker.db` 열기
2. `members` 테이블에서 "Insert Record"
3. 필드 입력 후 저장
4. 라즈베리파이에 파일 복사

---

### **Step 2.3: 일일 유지보수** 👤 귀하 작업

**매일 확인할 것:**
```bash
# 1. 시스템 작동 확인
# → 터치스크린 정상 작동?
# → 바코드 스캐너 인식?

# 2. 대여 기록 확인 (DB Browser)
sqlite3 locker.db "
SELECT COUNT(*) as 오늘대여건수
FROM rentals 
WHERE DATE(created_at) = DATE('now');
"

# 3. 에러 로그 확인
tail -50 logs/app.log
```

**자정에 자동 실행 (cron 설정):**
```bash
# 일일 대여 횟수 리셋 (자정)
0 0 * * * cd ~/gym-controller && python3 -c "from app.services.member_service import MemberService; ms = MemberService(); ms.reset_daily_rental_counts(); ms.close()"
```

---

## 🎯 **Phase 3: 중앙 연동 (선택사항, 나중에)**

### **Step 3.1: 구글 시트 구조 확정** 👤 귀하 작업

**결정할 것:**

1. **워크시트 이름**
   - [ ] 회원 명단 워크시트 이름: ________________
   - [ ] 락카 대여 기록 워크시트 이름: ________________

2. **컬럼명 (회원 명단)**
   | 항목 | 구글 시트 컬럼명 | 예시 |
   |------|-----------------|------|
   | 회원 ID | _______________ | 회원ID, member_id, 바코드 |
   | 이름 | _______________ | 이름, 회원명, name |
   | 전화번호 | _______________ | 전화번호, 연락처, phone |
   | 회원권 | _______________ | 회원권종류, 멤버십 |
   | 만료일 | _______________ | 만료일, 종료일 |
   | 활성화 | _______________ | 활성화, 상태, status |

3. **데이터 형식**
   - 만료일: YYYY-MM-DD 또는 MM/DD/YYYY?
   - 활성화: Y/N 또는 TRUE/FALSE?

---

### **Step 3.2: Google API 설정** 👤 귀하 작업

**Google Cloud Platform 설정:**

1. **프로젝트 생성**
   - https://console.cloud.google.com/ 접속
   - "새 프로젝트" 생성
   - 프로젝트 이름: 예) "헬스장-락카시스템"

2. **API 활성화**
   - "라이브러리" 메뉴
   - "Google Sheets API" 검색 후 활성화
   - "Google Drive API" 활성화

3. **서비스 계정 생성**
   - "IAM 및 관리자" → "서비스 계정"
   - "서비스 계정 만들기"
   - 이름: 예) "locker-system"
   - 역할: "편집자"
   - JSON 키 다운로드 → `service_account_key.json`

4. **구글 시트 공유**
   - 귀하의 헬스장 관리 구글 시트 열기
   - "공유" 버튼 클릭
   - 서비스 계정 이메일 추가 (예: locker-system@프로젝트ID.iam.gserviceaccount.com)
   - 권한: "편집자"

---

### **Step 3.3: 연동 설정** 💻 시스템 담당자

**1. 인증 파일 업로드:**
```bash
# 다운로드한 service_account_key.json을
# config/ 디렉토리에 복사
```

**2. 설정 파일 생성:**
```bash
python3 scripts/setup_google_sheets.py

# 대화형으로:
# - 구글 시트 ID 입력
# - 워크시트 이름 확인
# - 연결 테스트
```

**3. 컬럼명 매핑 (코드 수정):**
```python
# data_sources/google_sheets.py 수정
# 귀하가 정한 컬럼명으로 변경
```

---

### **Step 3.4: 동기화 테스트** 💻 시스템 담당자

```bash
# 수동 동기화 실행
python3 -c "
import asyncio
from database import DatabaseManager
from database.sync_manager import SyncManager
from data_sources.google_sheets import GoogleSheetsManager

async def test_sync():
    db = DatabaseManager('locker.db')
    db.connect()
    
    sheets = GoogleSheetsManager()
    await sheets.connect()
    
    sync = SyncManager(db, sheets)
    await sync.initialize()
    
    # 동기화 실행
    success = await sync.sync_all(force=True)
    print(f'동기화 결과: {success}')
    
    db.close()

asyncio.run(test_sync())
"
```

---

## 📅 **일일 작업 체크리스트**

### **매일 아침 (시스템 시작 전)**

**담당자: 귀하 또는 헬스장 직원**

- [ ] 라즈베리파이 전원 확인
- [ ] 터치스크린 정상 작동 확인
- [ ] ESP32 3개 연결 상태 확인 (LED 확인)
- [ ] 키오스크 모드 실행
  ```bash
  ./scripts/start_kiosk.sh
  ```

---

### **매일 또는 주 1회 (신규 회원 추가)**

**담당자: 귀하**

**방법 1: CSV 파일 사용**
```bash
# 1. 신규 회원 CSV 준비
# 파일명: 신규회원_20251010.csv

# 2. 등록 실행
python3 scripts/import_members_csv.py 신규회원_20251010.csv

# 3. 확인
sqlite3 locker.db "SELECT COUNT(*) FROM members;"
```

**방법 2: 대화형 입력**
```bash
python3 scripts/add_daily_members.py

# 실행 후 대화형으로 입력:
# 회원ID, 이름, 전화번호 등
```

**방법 3: DB Browser 직접 입력**
- `members` 테이블에서 수동 입력
- 5-10명 정도면 이게 가장 빠름

---

### **매일 밤 (자동 실행 - cron 설정 후)**

**자동으로 실행되는 것:**
```bash
# 자정: 일일 대여 횟수 리셋
0 0 * * * python3 ~/gym-controller/scripts/reset_daily_counts.py

# 새벽 2시: 데이터베이스 백업
0 2 * * * cp ~/gym-controller/locker.db ~/gym-controller/backups/locker_$(date +\%Y\%m\%d).db

# (Phase 3 이후) 새벽 3시: 구글시트 동기화
0 3 * * * python3 ~/gym-controller/scripts/sync_to_sheets.py
```

---

## 🛠️ **필요한 스크립트 목록**

### ✅ **이미 있는 것**
- `scripts/init_database.py` - DB 초기화
- `scripts/add_test_members.py` - 테스트 회원 5명 추가
- `scripts/start_kiosk.sh` - 키오스크 시작
- `scripts/stop_kiosk.sh` - 키오스크 종료

### 📝 **만들어야 할 것**

**우선순위 1 (Phase 1 필수):**
- [ ] `scripts/import_members_csv.py` - CSV 대량 등록
- [ ] `scripts/import_members_excel.py` - Excel 대량 등록
- [ ] `scripts/add_daily_members.py` - 일일 신규 회원 추가
- [ ] `scripts/export_members_csv.py` - 회원 백업 (CSV)

**우선순위 2 (Phase 2 권장):**
- [ ] `scripts/reset_daily_counts.py` - 일일 대여 횟수 리셋
- [ ] `scripts/backup_database.py` - DB 자동 백업
- [ ] `scripts/view_today_stats.py` - 오늘 통계 보기

**우선순위 3 (Phase 3 선택):**
- [ ] `scripts/sync_to_sheets.py` - 구글시트 동기화
- [ ] `scripts/sync_from_sheets.py` - 구글시트에서 가져오기

---

## 📊 **데이터 관리 전략**

### **회원 데이터 소스**

```
[현재 회원 관리 시스템/구글시트]
  ├─ 전체 회원: 10,000명
  ├─ 유효 회원: 500명 (활성화=Y, 만료일>오늘)
  └─ 신규 가입: 일 5-10명
      ↓ (초기 1회)
      ↓ CSV/Excel 다운로드
      ↓
[락카 시스템 SQLite]
  ├─ members: 500명
  ├─ 일일 추가: 5-10명
  └─ 매일 자정: 일일 횟수 리셋
```

---

### **회원 데이터 동기화 방식**

**Phase 1-2 (독립 운영):**
```
• 초기: 유효 회원 500명 일괄 등록
• 일일: 신규 회원 수동 추가 (CSV 또는 수동)
• 백업: 매일 자동 백업
```

**Phase 3 (구글시트 연동 후):**
```
• 새벽 3시: 구글시트 → SQLite 자동 동기화
• 실시간: 대여 기록 → 구글시트 자동 업로드
• 백업: 구글시트가 마스터 역할
```

---

## ⚠️ **주의사항**

### **회원 데이터 준비 시:**

1. **필수 검증:**
   - [ ] `member_id` 또는 `바코드`는 유니크한가?
   - [ ] 만료일 형식이 일관적인가? (YYYY-MM-DD 권장)
   - [ ] 중복 회원은 없는가?

2. **권장 사항:**
   - [ ] 만료일이 지난 회원은 제외
   - [ ] 정지된 회원은 status='suspended'로
   - [ ] 바코드 번호는 8-10자리 숫자

3. **테스트:**
   - [ ] 소수 회원(10명)으로 먼저 테스트
   - [ ] 바코드 스캔 검증 테스트
   - [ ] 대여/반납 플로우 테스트

---

## 🔧 **트러블슈팅**

### **문제: 회원이 검증 안 됨**

**확인:**
```bash
# 회원 데이터 확인
sqlite3 locker.db "SELECT * FROM members WHERE member_id='문제회원ID';"

# 검증 테스트
python3 -c "
from app.services.member_service import MemberService
ms = MemberService('locker.db')
result = ms.validate_member('문제회원ID')
print(result)
ms.close()
"
```

**가능한 원인:**
- status가 'active'가 아님
- expiry_date가 과거
- 이미 대여중 (currently_renting에 값 있음)
- daily_rental_count가 3 이상

---

### **문제: CSV 등록 실패**

**확인:**
- [ ] CSV 인코딩이 UTF-8인가?
- [ ] 첫 줄에 컬럼명이 있는가?
- [ ] 날짜 형식이 맞는가?
- [ ] 특수문자 문제는 없는가?

---

## 📈 **성공 기준**

### **Phase 1 완료 조건:**
- [ ] 500명 회원 등록 완료
- [ ] 10명 이상으로 대여/반납 테스트 성공
- [ ] 140개 락카 중 최소 10개 정상 작동
- [ ] 3개 zone (남성, 여성, 교직원) 모두 작동

### **Phase 2 완료 조건:**
- [ ] 1주일 이상 무중단 운영
- [ ] 일 30건 이상 대여 처리
- [ ] 오류율 < 1%
- [ ] 회원 만족도 양호

### **Phase 3 완료 조건:**
- [ ] 구글시트 자동 동기화 작동
- [ ] 실시간 대여 기록 업로드
- [ ] 중앙 관리 대시보드 작동

---

## 🎯 **즉시 작업 목록 (우선순위 순)**

### **지금 바로 (귀하):**
1. [ ] 유효 회원 명단 CSV/Excel 파일 준비 (500명)
2. [ ] 파일 형식 확인 (컬럼명, 날짜 형식)

### **오늘 중 (시스템 담당자):**
1. [ ] 대량 등록 스크립트 작성 (`import_members_csv.py`)
2. [ ] 일일 회원 추가 스크립트 작성 (`add_daily_members.py`)
3. [ ] 백업 스크립트 작성 (`backup_database.py`)

### **내일 (함께):**
1. [ ] 회원 데이터 일괄 등록
2. [ ] 검증 테스트 (10명)
3. [ ] 전체 플로우 테스트

### **이번 주 (센터 설치):**
1. [ ] 하드웨어 설치
2. [ ] 시스템 가동
3. [ ] 실제 운영 시작

---

## 📞 **의사소통 체크리스트**

### **귀하가 제공해야 할 정보:**
- [ ] 유효 회원 명단 파일 (CSV/Excel)
- [ ] 파일의 컬럼 구조 설명
- [ ] 일일 신규 회원 수 (평균)
- [ ] 선호하는 회원 추가 방식 (CSV vs 대화형 vs DB Browser)

### **시스템 담당자가 제공할 것:**
- [ ] 대량 등록 스크립트
- [ ] 사용 매뉴얼
- [ ] 트러블슈팅 가이드
- [ ] 설치 지원

---

## ✨ **결론**

**귀하의 계획:**
```
✅ 유효 회원 500명 일괄 등록
✅ 신규 회원 일일 추가 (5-10명)
✅ 회원관리 프로그램 연동 없이 독립 운영
```

**→ 완벽하게 가능합니다!**

**필요한 작업:**
1. 유효 회원 CSV 준비 (귀하)
2. 대량 등록 스크립트 작성 (시스템 담당자, 10-20분)
3. 등록 실행 및 테스트 (함께, 30분)

**예상 일정:**
- 오늘: 스크립트 작성
- 내일: 회원 데이터 등록 및 테스트
- 모레: 실제 센터 설치 및 운영 시작 가능! 🚀

---

**📝 작성일**: 2025-10-10  
**✅ 실행 가능**: 즉시  
**⏱️ 예상 소요**: 1-2일 (준비 완료 시)

