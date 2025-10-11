# 👥 회원 데이터 등록 가이드

> **목적**: 기존 유효 회원 명단을 SQLite에 등록  
> **대상**: 헬스장 관리자/운영자  
> **소요 시간**: 초기 30분, 일일 5분

---

## 📋 **회원 데이터 준비**

### **Step 1: CSV 파일 형식**

**파일명 예시:** `유효회원명단_20251010.csv`

**필수 구조:**
```csv
회원ID,이름,전화번호,회원권종류,만료일,상태
12345,홍길동,010-1234-5678,premium,2025-12-31,active
23456,김철수,010-2345-6789,basic,2025-11-30,active
34567,이영희,010-3456-7890,vip,2026-01-15,active
```

**또는 바코드 사용:**
```csv
바코드,이름,전화번호,회원권종류,만료일,상태
123456789,홍길동,010-1234-5678,premium,2025-12-31,active
234567890,김철수,010-2345-6789,basic,2025-11-30,active
```

---

### **필드 설명**

| 필드명 | 필수 | 형식 | 예시 | 설명 |
|--------|------|------|------|------|
| **회원ID** 또는 **바코드** | ✅ | 텍스트 | 12345, M2025001 | 유니크한 식별자 |
| **이름** | ✅ | 텍스트 | 홍길동 | 회원 이름 |
| **전화번호** | ⚪ | 010-xxxx-xxxx | 010-1234-5678 | 연락처 |
| **회원권종류** | ⚪ | basic, premium, vip | premium | 기본값: basic |
| **만료일** | ⚪ | YYYY-MM-DD | 2025-12-31 | 회원권 만료일 |
| **상태** | ⚪ | active, suspended | active | 기본값: active |

---

### **Step 2: 데이터 검증**

**등록 전 확인사항:**

1. **중복 확인**
   ```bash
   # Excel/구글시트에서 중복 제거
   # 회원ID 또는 바코드가 유니크한지 확인
   ```

2. **날짜 형식 통일**
   ```
   ✅ 좋은 예: 2025-12-31, 2026-01-15
   ❌ 나쁜 예: 12/31/2025, 2025.12.31
   ```

3. **유효 회원만 포함**
   ```
   ✅ 포함: 만료일이 미래, 상태=active
   ❌ 제외: 만료일이 과거, 정지된 회원
   ```

4. **인코딩 확인**
   ```
   파일 저장 시 "UTF-8" 인코딩 선택
   (한글 깨짐 방지)
   ```

---

## 🚀 **등록 실행**

### **방법 1: CSV 파일 일괄 등록 (대량)**

```bash
# 1. CSV 파일 준비
# 파일명: 유효회원명단.csv

# 2. 등록 스크립트 실행
python3 scripts/import_members_csv.py 유효회원명단.csv

# 3. 진행 상황 확인
# → 실시간으로 진행률 표시
# → 성공/실패 개수 표시
```

**예상 출력:**
```
🚀 회원 데이터 일괄 등록 시작
📄 파일: 유효회원명단.csv
📊 총 500명 발견

진행중... [====================] 100% (500/500)

✅ 성공: 495명
⚠️  중복: 3명 (이미 존재, 건너뜀)
❌ 오류: 2명 (형식 오류)

오류 상세:
  • 345번 줄: 만료일 형식 오류 (2025/12/31 → 2025-12-31 필요)
  • 401번 줄: 회원ID 누락

📊 최종 결과:
   • 등록 완료: 495명
   • 전체 회원: 495명
   • 유효 회원: 482명
   • 만료 예정 (7일 이내): 8명

✅ 등록 완료!
```

---

### **방법 2: Excel 파일 일괄 등록**

```bash
python3 scripts/import_members_excel.py 유효회원명단.xlsx

# Excel 시트명도 지정 가능
python3 scripts/import_members_excel.py 회원관리.xlsx --sheet "유효회원"
```

---

### **방법 3: 일일 신규 회원 추가 (소량)**

```bash
# 대화형 스크립트 실행
python3 scripts/add_daily_members.py
```

**실행 화면:**
```
═══════════════════════════════════════
  📝 신규 회원 등록
═══════════════════════════════════════

회원 ID 또는 바코드: 56789
이름: 박민수
전화번호 (선택, Enter=건너뛰기): 010-5678-9012
회원권 종류 (basic/premium/vip, 기본=basic): premium
만료일 (YYYY-MM-DD, 기본=30일 후): 2026-02-10

───────────────────────────────────────
입력 내용 확인:
  • 회원ID: 56789
  • 이름: 박민수
  • 전화번호: 010-5678-9012
  • 회원권: premium
  • 만료일: 2026-02-10
───────────────────────────────────────

등록할까요? (y/N): y
✅ 박민수님 등록 완료!

계속 추가하시겠습니까? (y/N): n

📊 오늘 추가된 회원: 1명
📋 전체 회원 수: 496명
```

---

## 🔍 **등록 후 확인**

### **DB Browser로 확인 (시각적)**
1. DB Browser for SQLite 실행
2. `locker.db` 열기
3. `members` 테이블 선택
4. 회원 수 확인
5. 샘플 데이터 확인 (정렬, 필터 가능)

---

### **터미널로 확인 (빠름)**

```bash
# 1. 전체 회원 수
sqlite3 locker.db "SELECT COUNT(*) as 총회원수 FROM members;"

# 2. 유효 회원 수 (상태 active + 만료 안 됨)
sqlite3 locker.db "
SELECT COUNT(*) as 유효회원수
FROM members 
WHERE status='active' 
  AND (expiry_date IS NULL OR expiry_date > date('now'));
"

# 3. 회원권 종류별 통계
sqlite3 locker.db -header -column "
SELECT membership_type as 회원권, COUNT(*) as 회원수
FROM members
WHERE status='active'
GROUP BY membership_type;
"

# 4. 만료 임박 회원 (7일 이내)
sqlite3 locker.db -header -column "
SELECT member_id, member_name, expiry_date
FROM members
WHERE status='active' 
  AND expiry_date BETWEEN date('now') AND date('now', '+7 days')
ORDER BY expiry_date;
"

# 5. 최근 등록 회원 10명
sqlite3 locker.db -header -column "
SELECT member_id, member_name, created_at
FROM members
ORDER BY created_at DESC
LIMIT 10;
"
```

---

## 🎯 **실전 예시**

### **시나리오: 500명 헬스장**

**초기 등록 (1회):**
```bash
# 1. 기존 회원관리 프로그램에서 내보내기
# → "유효회원" 필터 적용
# → CSV 다운로드 (500명)

# 2. 파일 확인
head -5 유효회원명단.csv
# 회원ID,이름,전화번호,회원권종류,만료일,상태
# 12345,홍길동,010-1234-5678,premium,2025-12-31,active
# ...

# 3. 등록 실행
python3 scripts/import_members_csv.py 유효회원명단.csv
# → 5-10분 소요

# 4. 확인
sqlite3 locker.db "SELECT COUNT(*) FROM members;"
# → 500

# 5. 샘플 테스트
# 바코드 스캔 → 검증 → 락카 대여
```

---

**일일 운영:**
```bash
# 월요일: 주말 신규 가입자 5명 추가
python3 scripts/add_daily_members.py
# → 대화형으로 5명 입력

# 또는
# 신규회원_20251014.csv 준비 (5명)
python3 scripts/import_members_csv.py 신규회원_20251014.csv
```

---

## 📁 **파일 관리**

### **백업 전략:**

```bash
# 매일 자동 백업 (cron)
0 2 * * * cp ~/gym-controller/locker.db ~/gym-controller/backups/locker_$(date +\%Y\%m\%d).db

# 주간 백업 보관 (7일)
# 월간 백업 보관 (30일)
```

### **파일 위치:**
```
~/gym-controller/
├─ locker.db                    # 현재 DB
├─ backups/
│   ├─ locker_20251010.db      # 일일 백업
│   ├─ locker_20251011.db
│   └─ ...
└─ import_data/
    ├─ 유효회원명단.csv         # 초기 데이터
    ├─ 신규회원_20251010.csv    # 일일 추가
    └─ ...
```

---

## 🎓 **FAQ**

### **Q1: CSV 파일은 어떻게 만드나요?**
A: 
- **Excel에서**: "다른 이름으로 저장" → "CSV UTF-8" 선택
- **구글시트에서**: "파일 → 다운로드 → CSV" 선택
- **회원관리 프로그램에서**: "내보내기" 기능 사용

### **Q2: 회원ID와 바코드가 다른데?**
A: 
- 둘 다 사용 가능합니다
- `member_id`로 회원ID 저장, 바코드는 별도 관리
- 또는 바코드 번호를 member_id로 사용

### **Q3: 몇 명까지 등록 가능한가요?**
A: 
- 이론상 무제한
- 실전 테스트: 10,000명까지 문제없음
- 권장: 센터당 1,000명 이하 (성능 최적)

### **Q4: 중복 회원은 어떻게 되나요?**
A: 
- 자동으로 건너뜁니다
- 기존 데이터는 유지됩니다
- 로그에 기록됩니다

### **Q5: 회원 정보 수정은?**
A:
- DB Browser에서 직접 수정
- 또는 update 스크립트 사용 (만들 예정)
- ⚠️ member_id는 수정하지 마세요!

---

## 🛠️ **필요한 도구**

### **필수:**
- [ ] Python 3.9+ 설치됨 ✅
- [ ] SQLite3 설치됨 ✅
- [ ] DB Browser for SQLite ✅

### **권장:**
- [ ] Excel 또는 구글 스프레드시트 (CSV 작성용)
- [ ] 텍스트 에디터 (CSV 수정용)

---

## ✅ **체크리스트**

### **초기 등록 전:**
- [ ] 유효 회원 명단 파일 준비 (CSV/Excel)
- [ ] 파일 형식 확인 (컬럼명, 인코딩)
- [ ] 중복 회원 제거
- [ ] 만료 회원 제거
- [ ] 날짜 형식 통일 (YYYY-MM-DD)

### **등록 실행:**
- [ ] 소수 회원(10명)으로 테스트
- [ ] 오류 없는지 확인
- [ ] 전체 회원 등록
- [ ] DB Browser로 확인

### **등록 후:**
- [ ] 회원 수 확인
- [ ] 바코드 스캔 테스트 (3-5명)
- [ ] 대여/반납 플로우 테스트
- [ ] 백업 파일 생성

---

## 📞 **지원**

**문제 발생 시:**
1. 오류 메시지 캡처
2. CSV 파일 샘플 (첫 5줄) 제공
3. 데이터베이스 상태 확인:
   ```bash
   sqlite3 locker.db "SELECT COUNT(*) FROM members;"
   ```

---

**📝 마지막 업데이트**: 2025-10-10  
**✅ 상태**: 준비 완료 (스크립트 생성 후 사용 가능)

