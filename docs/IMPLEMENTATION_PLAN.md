# 🚀 SQLite 기반 락카키 대여기 시스템 구현 계획

## 📋 프로젝트 개요

기존 Google Sheets 기반 시스템을 SQLite 기반으로 점진적 업그레이드하여 안정성과 성능을 향상시키는 프로젝트입니다.

### 🎯 목표
- 기존 시스템 중단 없이 점진적 업그레이드
- 트랜잭션 기반 안전한 대여/반납 처리
- 물리적 센서와 DB 상태 동기화
- Google Sheets와의 양방향 동기화 유지

### 📊 현재 상태 분석
- ✅ ESP32 통신 시스템 완성 (100% 활용)
- ✅ Flask 웹 인터페이스 구축 (90% 활용)
- ✅ 기본 모델 구조 완성 (70% 활용, 확장 필요)
- ❌ SQLite 데이터베이스 미구현 (신규 구축)
- ❌ 트랜잭션 관리 시스템 미구현 (신규 구축)

---

## 🏗️ 1단계: 데이터베이스 기반 구조 구축 (1-2일)

### 📁 새로 생성할 파일들

```
raspberry-pi-gym-controller/
├── database/
│   ├── __init__.py
│   ├── schema.sql                  # SQLite 스키마 정의
│   ├── database_manager.py         # SQLite 연결 및 기본 CRUD
│   ├── migration_manager.py        # 스키마 마이그레이션
│   └── sync_manager.py            # Google Sheets 동기화
├── tests/
│   ├── test_database.py           # 데이터베이스 테스트
│   └── test_sync.py               # 동기화 테스트
└── scripts/
    ├── init_database.py           # DB 초기화 스크립트
    └── migrate_from_sheets.py     # 기존 데이터 마이그레이션
```

### 🔧 구현 작업

#### 1.1 SQLite 스키마 생성 (`database/schema.sql`)
```sql
-- members 테이블 (회원 마스터)
CREATE TABLE members (
    member_id TEXT PRIMARY KEY,
    member_name TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    expiry_date DATE,
    currently_renting TEXT,
    daily_rental_count INTEGER DEFAULT 0,
    last_rental_time TIMESTAMP,
    sync_date TIMESTAMP
);

-- rentals 테이블 (대여 기록)
CREATE TABLE rentals (
    rental_id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id TEXT UNIQUE,
    member_id TEXT NOT NULL,
    locker_number TEXT NOT NULL,
    -- 대여 프로세스
    rental_barcode_time TIMESTAMP,
    rental_sensor_time TIMESTAMP,
    rental_verified BOOLEAN DEFAULT 0,
    -- 반납 프로세스
    return_barcode_time TIMESTAMP,
    return_target_locker TEXT,
    return_sensor_time TIMESTAMP,
    return_actual_locker TEXT,
    return_verified BOOLEAN DEFAULT 0,
    -- 상태 관리
    status TEXT DEFAULT 'active',
    error_code TEXT,
    error_details TEXT,
    -- 메타 정보
    device_id TEXT DEFAULT 'DEVICE_001',
    sync_status INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (member_id) REFERENCES members(member_id)
);

-- locker_status 테이블 (실시간 상태)
CREATE TABLE locker_status (
    locker_number TEXT PRIMARY KEY,
    sensor_status INTEGER DEFAULT 0,
    door_status INTEGER DEFAULT 0,
    current_member TEXT,
    current_transaction TEXT,
    locked_until TIMESTAMP,
    last_change_time TIMESTAMP
);

-- active_transactions 테이블 (동시성 제어)
CREATE TABLE active_transactions (
    transaction_id TEXT PRIMARY KEY,
    member_id TEXT NOT NULL,
    transaction_type TEXT,
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    timeout_at TIMESTAMP,
    sensor_events TEXT,
    status TEXT DEFAULT 'active'
);

-- 인덱스 생성
CREATE INDEX idx_member_barcode ON members(member_id);
CREATE INDEX idx_rental_status ON rentals(status);
CREATE INDEX idx_rental_member ON rentals(member_id);
```

#### 1.2 데이터베이스 매니저 구현 (`database/database_manager.py`)
```python
import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

class DatabaseManager:
    """SQLite 데이터베이스 연결 및 기본 CRUD 관리"""
    
    def __init__(self, db_path: str = 'locker.db'):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self.logger = logging.getLogger(__name__)
        
    def connect(self) -> bool:
        """데이터베이스 연결"""
        try:
            self.conn = sqlite3.connect(
                self.db_path, 
                check_same_thread=False,
                timeout=30.0
            )
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys = ON")
            self.logger.info(f"데이터베이스 연결 성공: {self.db_path}")
            return True
        except Exception as e:
            self.logger.error(f"데이터베이스 연결 실패: {e}")
            return False
    
    def initialize_schema(self) -> bool:
        """스키마 초기화"""
        try:
            schema_path = Path(__file__).parent / "schema.sql"
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            
            self.conn.executescript(schema_sql)
            self.conn.commit()
            self.logger.info("데이터베이스 스키마 초기화 완료")
            return True
        except Exception as e:
            self.logger.error(f"스키마 초기화 실패: {e}")
            return False
    
    def execute_query(self, query: str, params: tuple = ()) -> Optional[sqlite3.Cursor]:
        """쿼리 실행"""
        try:
            cursor = self.conn.execute(query, params)
            return cursor
        except Exception as e:
            self.logger.error(f"쿼리 실행 실패: {query}, {e}")
            return None
    
    def commit(self):
        """트랜잭션 커밋"""
        if self.conn:
            self.conn.commit()
    
    def rollback(self):
        """트랜잭션 롤백"""
        if self.conn:
            self.conn.rollback()
    
    def close(self):
        """연결 종료"""
        if self.conn:
            self.conn.close()
            self.logger.info("데이터베이스 연결 종료")
```

#### 1.3 Google Sheets 동기화 매니저 (`database/sync_manager.py`)
```python
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from .database_manager import DatabaseManager
from data_sources.google_sheets import GoogleSheetsManager

class SyncManager:
    """Google Sheets와 SQLite 간 양방향 동기화"""
    
    def __init__(self, db_manager: DatabaseManager, sheets_manager: GoogleSheetsManager):
        self.db = db_manager
        self.sheets = sheets_manager
        self.logger = logging.getLogger(__name__)
        
    async def sync_members_from_sheets(self) -> bool:
        """Google Sheets에서 회원 정보 동기화"""
        try:
            # Google Sheets에서 회원 데이터 가져오기
            await self.sheets.refresh_cache()
            
            # SQLite에 업데이트
            for member_id, member_info in self.sheets._members_cache.items():
                self.db.execute_query("""
                    INSERT OR REPLACE INTO members 
                    (member_id, member_name, status, expiry_date, sync_date)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    member_info.member_id,
                    member_info.name,
                    'active' if member_info.is_active else 'inactive',
                    member_info.expiry_date,
                    datetime.now(timezone.utc)
                ))
            
            self.db.commit()
            self.logger.info("회원 정보 동기화 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"회원 동기화 실패: {e}")
            self.db.rollback()
            return False
    
    async def sync_rentals_to_sheets(self) -> bool:
        """대여 기록을 Google Sheets로 업로드"""
        try:
            # 미동기화 대여 기록 조회
            cursor = self.db.execute_query("""
                SELECT * FROM rentals 
                WHERE sync_status = 0 
                AND status IN ('returned', 'active')
            """)
            
            if not cursor:
                return False
                
            records = cursor.fetchall()
            
            # Google Sheets에 업로드
            for record in records:
                success = await self.sheets.record_rental(
                    record['member_id'],
                    record['locker_number'],
                    f"KEY_{record['locker_number']}"  # 임시 키 바코드
                )
                
                if success:
                    # 동기화 완료 표시
                    self.db.execute_query("""
                        UPDATE rentals 
                        SET sync_status = 1 
                        WHERE rental_id = ?
                    """, (record['rental_id'],))
            
            self.db.commit()
            self.logger.info(f"대여 기록 동기화 완료: {len(records)}건")
            return True
            
        except Exception as e:
            self.logger.error(f"대여 기록 동기화 실패: {e}")
            self.db.rollback()
            return False
```

### 📋 1단계 체크리스트

- [ ] `database/` 폴더 생성
- [ ] `schema.sql` 파일 작성
- [ ] `database_manager.py` 구현
- [ ] `sync_manager.py` 구현
- [ ] `init_database.py` 스크립트 작성
- [ ] 기본 데이터베이스 연결 테스트
- [ ] Google Sheets 동기화 테스트

---

## 🔧 2단계: 모델 확장 및 트랜잭션 시스템 (2-3일)

### 📝 수정할 기존 파일들

#### 2.1 Member 모델 확장 (`app/models/member.py`)
```python
# 기존 필드에 추가
class Member:
    def __init__(self, id: str, name: str, phone: str = '',
                 membership_type: str = 'basic', 
                 membership_expires: Optional[datetime] = None,
                 status: str = 'active',
                 # 🆕 새로 추가되는 필드들
                 currently_renting: Optional[str] = None,
                 daily_rental_count: int = 0,
                 last_rental_time: Optional[datetime] = None):
        # 기존 코드 유지
        self.currently_renting = currently_renting
        self.daily_rental_count = daily_rental_count
        self.last_rental_time = last_rental_time
    
    @classmethod
    def from_db_row(cls, row: sqlite3.Row) -> 'Member':
        """데이터베이스 행에서 Member 객체 생성"""
        return cls(
            id=row['member_id'],
            name=row['member_name'],
            status=row['status'],
            membership_expires=datetime.fromisoformat(row['expiry_date']) if row['expiry_date'] else None,
            currently_renting=row['currently_renting'],
            daily_rental_count=row['daily_rental_count'],
            last_rental_time=datetime.fromisoformat(row['last_rental_time']) if row['last_rental_time'] else None
        )
```

#### 2.2 트랜잭션 매니저 구현 (`database/transaction_manager.py`)
```python
import uuid
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from .database_manager import DatabaseManager

class TransactionManager:
    """대여/반납 트랜잭션 관리"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.logger = logging.getLogger(__name__)
        
    async def start_transaction(self, member_id: str, trans_type: str = 'rental') -> Dict[str, Any]:
        """새 트랜잭션 시작"""
        try:
            # 1. 활성 트랜잭션 체크
            cursor = self.db.execute_query("""
                SELECT * FROM active_transactions 
                WHERE status = 'active' 
                AND datetime('now') < timeout_at
            """)
            
            if cursor and cursor.fetchone():
                return {'success': False, 'message': '다른 회원이 이용 중입니다'}
            
            # 2. 타임아웃된 트랜잭션 정리
            self.db.execute_query("""
                UPDATE active_transactions 
                SET status = 'timeout' 
                WHERE status = 'active' 
                AND datetime('now') >= timeout_at
            """)
            
            # 3. 새 트랜잭션 생성
            tx_id = str(uuid.uuid4())
            timeout = datetime.now() + timedelta(seconds=30)
            
            self.db.execute_query("""
                INSERT INTO active_transactions 
                (transaction_id, member_id, transaction_type, timeout_at)
                VALUES (?, ?, ?, ?)
            """, (tx_id, member_id, trans_type, timeout))
            
            # 4. 모든 락카 잠금
            self.db.execute_query("""
                UPDATE locker_status 
                SET current_transaction = ?, 
                    locked_until = ?
            """, (tx_id, timeout))
            
            self.db.commit()
            
            return {'success': True, 'transaction_id': tx_id}
            
        except Exception as e:
            self.logger.error(f"트랜잭션 시작 실패: {e}")
            self.db.rollback()
            return {'success': False, 'error': str(e)}
    
    async def end_transaction(self, tx_id: str, status: str = 'completed'):
        """트랜잭션 종료"""
        try:
            # 트랜잭션 상태 업데이트
            self.db.execute_query("""
                UPDATE active_transactions 
                SET status = ?, last_activity = datetime('now')
                WHERE transaction_id = ?
            """, (status, tx_id))
            
            # 락카 잠금 해제
            self.db.execute_query("""
                UPDATE locker_status 
                SET current_transaction = NULL, 
                    locked_until = NULL
                WHERE current_transaction = ?
            """, (tx_id,))
            
            self.db.commit()
            self.logger.info(f"트랜잭션 종료: {tx_id} ({status})")
            
        except Exception as e:
            self.logger.error(f"트랜잭션 종료 실패: {e}")
            self.db.rollback()
```

### 📋 2단계 체크리스트

- [ ] Member 모델 확장
- [ ] Locker 모델 확장  
- [ ] Rental 모델 확장
- [ ] TransactionManager 구현
- [ ] 모델 단위 테스트 작성
- [ ] 트랜잭션 시스템 테스트

---

## ⚙️ 3단계: 서비스 로직 통합 (3-4일)

### 🔄 수정할 서비스 파일들

#### 3.1 LockerService 개선 (`app/services/locker_service.py`)
```python
from database.database_manager import DatabaseManager
from database.transaction_manager import TransactionManager

class LockerService:
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.transaction_manager = TransactionManager(self.db_manager)
        self.esp32_manager = None  # 기존 ESP32Manager 유지
        
    async def rent_locker_with_transaction(self, member_id: str, locker_id: str) -> Dict:
        """트랜잭션 기반 락카 대여"""
        # 1. 트랜잭션 시작
        tx_result = await self.transaction_manager.start_transaction(member_id)
        if not tx_result['success']:
            return tx_result
            
        tx_id = tx_result['transaction_id']
        
        try:
            # 2. 회원 검증
            member_valid = await self.validate_member_for_rental(member_id)
            if not member_valid['valid']:
                await self.transaction_manager.end_transaction(tx_id, 'failed')
                return member_valid
            
            # 3. 락카 상태 확인
            locker_available = await self.check_locker_availability(locker_id)
            if not locker_available:
                await self.transaction_manager.end_transaction(tx_id, 'failed')
                return {'success': False, 'error': '락카를 사용할 수 없습니다'}
            
            # 4. ESP32 명령 전송 (기존 코드 활용)
            hardware_success = await self.open_locker_hardware(locker_id)
            if not hardware_success:
                await self.transaction_manager.end_transaction(tx_id, 'failed')
                return {'success': False, 'error': '락카 열기 실패'}
            
            # 5. 센서 검증 대기
            sensor_verified = await self.wait_for_sensor_verification(locker_id, tx_id)
            if not sensor_verified:
                await self.transaction_manager.end_transaction(tx_id, 'failed')
                return {'success': False, 'error': '센서 검증 실패'}
            
            # 6. 대여 기록 생성
            rental_success = await self.create_rental_record(member_id, locker_id, tx_id)
            if not rental_success:
                await self.transaction_manager.end_transaction(tx_id, 'failed')
                return {'success': False, 'error': '대여 기록 생성 실패'}
            
            # 7. 트랜잭션 완료
            await self.transaction_manager.end_transaction(tx_id, 'completed')
            
            return {
                'success': True,
                'message': f'{locker_id}번 락카 대여 완료',
                'transaction_id': tx_id
            }
            
        except Exception as e:
            await self.transaction_manager.end_transaction(tx_id, 'error')
            return {'success': False, 'error': f'시스템 오류: {str(e)}'}
```

#### 3.2 센서 검증 시스템 (`app/services/sensor_service.py`)
```python
import asyncio
from typing import Dict, Optional
from core.esp32_manager import ESP32Manager

class SensorService:
    """센서 이벤트 처리 및 검증"""
    
    def __init__(self, esp32_manager: ESP32Manager, db_manager: DatabaseManager):
        self.esp32_manager = esp32_manager
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
        
        # 센서 이벤트 핸들러 등록
        self.esp32_manager.register_event_handler("sensor_triggered", self.handle_sensor_event)
        
    async def handle_sensor_event(self, event_data: Dict):
        """센서 이벤트 처리"""
        try:
            locker_number = self.extract_locker_from_sensor(event_data)
            sensor_status = event_data.get('active', False)
            
            # 현재 진행중인 트랜잭션 확인
            cursor = self.db_manager.execute_query("""
                SELECT * FROM active_transactions 
                WHERE status = 'active'
                ORDER BY start_time DESC 
                LIMIT 1
            """)
            
            if cursor:
                transaction = cursor.fetchone()
                if transaction:
                    # 센서 이벤트를 트랜잭션에 기록
                    await self.record_sensor_event(
                        transaction['transaction_id'], 
                        locker_number, 
                        sensor_status
                    )
            
        except Exception as e:
            self.logger.error(f"센서 이벤트 처리 오류: {e}")
    
    async def wait_for_sensor_verification(self, locker_id: str, tx_id: str, timeout: int = 30) -> bool:
        """센서 검증 대기"""
        start_time = asyncio.get_event_loop().time()
        
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            # 센서 이벤트 확인
            cursor = self.db_manager.execute_query("""
                SELECT sensor_events FROM active_transactions 
                WHERE transaction_id = ?
            """, (tx_id,))
            
            if cursor:
                row = cursor.fetchone()
                if row and row['sensor_events']:
                    events = json.loads(row['sensor_events'])
                    # 적절한 센서 이벤트가 있는지 확인
                    if self.verify_sensor_events(events, locker_id):
                        return True
            
            await asyncio.sleep(0.5)  # 500ms 간격으로 체크
        
        return False
```

### 📋 3단계 체크리스트

- [ ] LockerService 트랜잭션 로직 적용
- [ ] MemberService DB 연동 추가
- [ ] SensorService 구현
- [ ] 기존 ESP32Manager와 통합
- [ ] 웹 API 엔드포인트 업데이트
- [ ] 통합 테스트 작성

---

## 🧪 4단계: 테스트 및 최적화 (2-3일)

### 🔍 테스트 시나리오

#### 4.1 단위 테스트
- [ ] 데이터베이스 CRUD 테스트
- [ ] 트랜잭션 관리 테스트
- [ ] 모델 변환 테스트
- [ ] 동기화 로직 테스트

#### 4.2 통합 테스트
- [ ] 전체 대여 프로세스 테스트
- [ ] 전체 반납 프로세스 테스트
- [ ] 동시성 제어 테스트
- [ ] 센서 검증 테스트
- [ ] 오류 복구 테스트

#### 4.3 성능 테스트
- [ ] 대량 트랜잭션 처리 테스트
- [ ] 동기화 성능 테스트
- [ ] 메모리 사용량 모니터링

### 🚀 최적화 작업

#### 4.4 성능 최적화
- [ ] 데이터베이스 인덱스 최적화
- [ ] 쿼리 성능 튜닝
- [ ] 캐시 시스템 구현
- [ ] 비동기 처리 최적화

#### 4.5 안정성 강화
- [ ] 예외 처리 강화
- [ ] 로깅 시스템 개선
- [ ] 자동 복구 메커니즘
- [ ] 모니터링 대시보드

---

## 📅 전체 일정 계획

| 단계 | 기간 | 주요 작업 | 완료 기준 |
|------|------|-----------|-----------|
| **1단계** | 1-2일 | 데이터베이스 기반 구조 구축 | SQLite 연결 및 기본 동기화 완료 |
| **2단계** | 2-3일 | 모델 확장 및 트랜잭션 시스템 | 트랜잭션 기반 처리 가능 |
| **3단계** | 3-4일 | 서비스 로직 통합 | 전체 대여/반납 프로세스 완성 |
| **4단계** | 2-3일 | 테스트 및 최적화 | 프로덕션 배포 준비 완료 |
| **총 기간** | **8-12일** | | **완전한 시스템 구축** |

---

## 🎯 성공 지표

### 기능적 지표
- [ ] 트랜잭션 기반 안전한 대여/반납 처리
- [ ] 물리적 센서와 DB 상태 100% 동기화
- [ ] Google Sheets 양방향 동기화 유지
- [ ] 동시성 제어로 충돌 방지

### 성능 지표
- [ ] 대여 프로세스 완료 시간 < 5초
- [ ] 센서 검증 응답 시간 < 2초
- [ ] 동기화 처리 시간 < 10초
- [ ] 시스템 가용성 > 99.9%

### 안정성 지표
- [ ] 트랜잭션 실패율 < 0.1%
- [ ] 자동 복구 성공률 > 95%
- [ ] 데이터 무결성 100% 보장
- [ ] 오류 로깅 및 알림 시스템 완성

---

## 📝 참고 문서

- [DATABASE_DESIGN.md](./DATABASE_DESIGN.md) - 데이터베이스 설계 상세
- [ARCHITECTURE.md](../ARCHITECTURE.md) - 전체 시스템 아키텍처
- [ESP32_INTEGRATION_GUIDE.md](../ESP32_INTEGRATION_GUIDE.md) - ESP32 통합 가이드

---

**📋 작성일**: 2025년 10월 1일  
**🎯 목표 완료일**: 2025년 10월 13일  
**👨‍💻 담당자**: 개발팀  
**📊 진행 상황**: 계획 수립 완료, 구현 대기 중
