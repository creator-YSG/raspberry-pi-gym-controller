# 🚀 빠른 시작 가이드

> 락카키 대여기 시스템을 처음 사용하는 개발자를 위한 가이드

---

## 📋 사전 요구사항

- **Python 3.7+** 설치
- **SQLite3** 설치 (대부분 Python과 함께 설치됨)
- **Git** (코드 클론용)

---

## 🏗️ 1단계: 프로젝트 설정

### 코드 클론 및 이동
```bash
git clone [repository-url]
cd raspberry-pi-gym-controller
```

### 의존성 설치
```bash
pip3 install -r requirements.txt
```

---

## 🗄️ 2단계: 데이터베이스 초기화

### SQLite 데이터베이스 생성
```bash
python3 scripts/init_database.py
```

**예상 출력:**
```
🚀 락카키 대여기 시스템 데이터베이스 초기화
==================================================
🔧 데이터베이스 매니저 생성 중...
📊 데이터베이스 초기화 완료!
   • 회원 테이블: 0명
   • 락카 상태: 48개
   • 대여 기록: 0건
   • 활성 트랜잭션: 0개
   • 사용 가능한 락카: 48개
   • 데이터베이스 크기: 0.0MB
✅ 데이터베이스 초기화가 성공적으로 완료되었습니다!
```

### 데이터베이스 확인
```bash
sqlite3 locker.db "SELECT name FROM sqlite_master WHERE type='table';"
```

**예상 출력:**
```
members
rentals
sqlite_sequence
locker_status
active_transactions
system_settings
```

---

## 🧪 3단계: 테스트 실행

### 전체 테스트 실행
```bash
# 데이터베이스 매니저 테스트 (9개)
python3 tests/database/test_database_manager.py

# Member 모델 테스트 (7개)
python3 tests/database/test_member_model.py

# 트랜잭션 매니저 테스트 (8개)
python3 tests/database/test_transaction_manager.py
```

**성공 시 출력:**
```
----------------------------------------------------------------------
Ran 9 tests in 0.086s

OK
```

---

## 💡 4단계: 기본 사용법 익히기

### 데이터베이스 매니저 사용
```python
from database import DatabaseManager

# 연결
db = DatabaseManager('locker.db')
db.connect()

# 통계 확인
stats = db.get_database_stats()
print(f"사용 가능한 락카: {stats['available_lockers']}개")

# 연결 종료
db.close()
```

### 트랜잭션 시스템 사용
```python
import asyncio
from database import DatabaseManager, TransactionManager
from database.transaction_manager import TransactionType

async def example():
    db = DatabaseManager('locker.db')
    db.connect()
    
    # 테스트 회원 추가
    db.execute_query("""
        INSERT INTO members (member_id, member_name, status)
        VALUES (?, ?, ?)
    """, ('TEST001', '테스트 회원', 'active'))
    
    # 트랜잭션 매니저
    tx_manager = TransactionManager(db)
    
    # 트랜잭션 시작
    result = await tx_manager.start_transaction('TEST001', TransactionType.RENTAL)
    if result['success']:
        print(f"✅ 트랜잭션 시작: {result['transaction_id']}")
        
        # 트랜잭션 종료
        await tx_manager.end_transaction(result['transaction_id'])
        print("✅ 트랜잭션 완료")
    
    db.close()

# 실행
asyncio.run(example())
```

---

## 🔍 5단계: 시스템 상태 확인

### 데이터베이스 내용 확인
```bash
# 락카 상태 확인
sqlite3 locker.db "SELECT locker_number, zone, size FROM locker_status LIMIT 5;"

# 시스템 설정 확인
sqlite3 locker.db "SELECT * FROM system_settings;"

# 테이블별 레코드 수
sqlite3 locker.db "
SELECT 
    'members' as table_name, COUNT(*) as count FROM members
UNION ALL
SELECT 'lockers', COUNT(*) FROM locker_status
UNION ALL  
SELECT 'rentals', COUNT(*) FROM rentals;
"
```

---

## 🚀 6단계: 웹 서버 실행 (선택사항)

### Flask 개발 서버 시작
```bash
python3 run.py
```

### 브라우저에서 확인
- **URL**: http://localhost:5000
- **터치 모드**: 600x1024 세로 모드로 최적화됨

---

## 📚 다음 단계

### 문서 읽기
1. **[SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md)** - 전체 시스템 이해
2. **[DATABASE_DESIGN.md](DATABASE_DESIGN.md)** - 데이터베이스 구조 상세
3. **[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)** - 구현 계획

### 개발 참여
1. **3단계**: 서비스 로직 통합 (현재 진행 예정)
2. **4단계**: 테스트 및 최적화
3. **ESP32 연동**: 하드웨어 통합 테스트

---

## 🆘 문제 해결

### 자주 발생하는 문제

**Q: `ModuleNotFoundError: No module named 'database'`**
```bash
# 프로젝트 루트에서 실행하는지 확인
pwd  # raspberry-pi-gym-controller 디렉토리여야 함
export PYTHONPATH=.
```

**Q: `sqlite3.OperationalError: database is locked`**
```bash
# 다른 프로세스가 DB를 사용 중인지 확인
lsof locker.db
# 또는 DB 파일 재생성
rm locker.db
python3 scripts/init_database.py
```

**Q: 테스트 실패**
```bash
# 상세 로그 확인
python3 tests/database/test_database_manager.py -v
```

### 도움 요청
- **로그 확인**: `logs/` 폴더
- **테스트 코드**: `tests/database/` 폴더 참조
- **예시 코드**: 각 테스트 파일의 사용 예시 참조

---

## ✅ 체크리스트

완료되면 체크하세요:

- [ ] Python 3.7+ 설치 확인
- [ ] 프로젝트 클론 완료
- [ ] 의존성 설치 완료
- [ ] 데이터베이스 초기화 성공
- [ ] 전체 테스트 통과 (24개)
- [ ] 기본 사용법 실습 완료
- [ ] 웹 서버 실행 확인 (선택)

**🎉 모든 단계를 완료했다면, 이제 락카키 대여기 시스템을 사용할 준비가 되었습니다!**

---

**📝 작성일**: 2025년 10월 1일  
**🔄 업데이트**: 시스템 변경 시 함께 업데이트됩니다
