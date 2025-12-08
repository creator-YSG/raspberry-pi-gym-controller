# 락카키 대여기 시스템 아키텍처 (SQLite 기반)

## 전체 구조도
```
[구글 시트 - 마스터]
    ↓ (1일 2회 동기화)
[라즈베리파이]
    ├─ SQLite DB (locker.db)
    ├─ Python 제어 프로그램
    └─ USB Serial ← → ESP32 (센서/모터)
```

## 1. SQLite 데이터베이스 설계

### members 테이블 (회원 마스터)
```sql
CREATE TABLE members (
    member_id TEXT PRIMARY KEY,          -- 바코드 번호
    member_name TEXT NOT NULL,           -- 회원명
    status TEXT DEFAULT 'active',        -- active/suspended/expired
    expiry_date DATE,                    -- 회원권 만료일
    currently_renting TEXT,              -- 현재 대여중인 락카 번호
    daily_rental_count INTEGER DEFAULT 0, -- 오늘 대여 횟수
    last_rental_time TIMESTAMP,          -- 마지막 대여 시각
    sync_date TIMESTAMP                  -- 구글시트 동기화 시각
);
CREATE INDEX idx_member_barcode ON members(member_id);
```

### rentals 테이블 (대여 기록)
```sql
CREATE TABLE rentals (
    rental_id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id TEXT UNIQUE,          -- 트랜잭션 ID (UUID)
    member_id TEXT NOT NULL,             -- 회원 바코드
    locker_number TEXT NOT NULL,         -- 락카 번호
    
    -- 대여 프로세스
    rental_barcode_time TIMESTAMP,       -- 회원카드 인식 시각
    rental_sensor_time TIMESTAMP,        -- 센서 '키 제거' 감지
    rental_verified BOOLEAN DEFAULT 0,   -- 정상 대여 확인
    
    -- 반납 프로세스  
    return_barcode_time TIMESTAMP,       -- 락카키 바코드 인식
    return_target_locker TEXT,           -- 반납하려는 락카 번호
    return_sensor_time TIMESTAMP,        -- 센서 '키 삽입' 감지
    return_actual_locker TEXT,           -- 실제 감지된 락카 번호
    return_verified BOOLEAN DEFAULT 0,   -- 정상 반납 확인
    
    -- 상태 관리
    status TEXT DEFAULT 'active',        -- active/returned/abnormal
    error_code TEXT,                     -- 오류 코드
    error_details TEXT,                  -- 오류 상세
    
    -- 메타 정보
    device_id TEXT DEFAULT 'DEVICE_001',
    sync_status INTEGER DEFAULT 0,       -- 0:미동기화 1:동기화완료
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (member_id) REFERENCES members(member_id)
);
CREATE INDEX idx_rental_status ON rentals(status);
CREATE INDEX idx_rental_member ON rentals(member_id);
```

### locker_status 테이블 (실시간 상태)
```sql
CREATE TABLE locker_status (
    locker_number TEXT PRIMARY KEY,      -- 락카 번호
    sensor_status INTEGER DEFAULT 0,     -- 0:비어있음 1:키있음
    door_status INTEGER DEFAULT 0,       -- 0:닫힘 1:열림
    current_member TEXT,                 -- 현재 대여 회원
    current_transaction TEXT,            -- 진행중인 트랜잭션
    locked_until TIMESTAMP,              -- 잠금 해제 시각
    last_change_time TIMESTAMP          -- 마지막 변경 시각
);
```

### active_transactions 테이블 (동시성 제어)
```sql
CREATE TABLE active_transactions (
    transaction_id TEXT PRIMARY KEY,
    member_id TEXT NOT NULL,
    transaction_type TEXT,               -- rental/return
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    timeout_at TIMESTAMP,                -- 타임아웃 예정 시각
    sensor_events TEXT,                  -- JSON: 센서 이벤트 기록
    status TEXT DEFAULT 'active'         -- active/completed/timeout/failed
);
```

## 2. Python 핵심 클래스 설계

```python
# locker_system.py
import sqlite3
import json
import uuid
from datetime import datetime, timedelta
import serial

class LockerSystem:
    def __init__(self, db_path='locker.db', serial_port='/dev/ttyUSB0'):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.serial = serial.Serial(serial_port, 115200)
        self.init_database()
        
    def init_database(self):
        """데이터베이스 초기화"""
        with open('schema.sql', 'r') as f:
            self.conn.executescript(f.read())
    
    # ===== 회원 검증 =====
    def validate_member(self, barcode):
        """회원 유효성 검증"""
        cursor = self.conn.execute("""
            SELECT * FROM members 
            WHERE member_id = ? 
            AND status = 'active'
            AND (expiry_date IS NULL OR date(expiry_date) >= date('now'))
        """, (barcode,))
        
        member = cursor.fetchone()
        if not member:
            return {'valid': False, 'reason': '미등록 또는 만료'}
            
        # 이미 대여중인지 체크
        if member['currently_renting']:
            return {'valid': False, 'reason': '이미 대여중', 
                   'locker': member['currently_renting']}
        
        return {'valid': True, 'member': dict(member)}
    
    # ===== 트랜잭션 관리 =====
    def start_transaction(self, member_id, trans_type='rental'):
        """새 트랜잭션 시작 (동시성 제어)"""
        
        # 1. 활성 트랜잭션 체크
        cursor = self.conn.execute("""
            SELECT * FROM active_transactions 
            WHERE status = 'active' 
            AND datetime('now') < timeout_at
        """)
        
        if cursor.fetchone():
            return {'success': False, 'message': '다른 회원이 이용 중입니다'}
        
        # 2. 타임아웃된 트랜잭션 정리
        self.conn.execute("""
            UPDATE active_transactions 
            SET status = 'timeout' 
            WHERE status = 'active' 
            AND datetime('now') >= timeout_at
        """)
        
        # 3. 새 트랜잭션 생성
        tx_id = str(uuid.uuid4())
        timeout = datetime.now() + timedelta(seconds=30)
        
        self.conn.execute("""
            INSERT INTO active_transactions 
            (transaction_id, member_id, transaction_type, timeout_at)
            VALUES (?, ?, ?, ?)
        """, (tx_id, member_id, trans_type, timeout))
        
        # 4. 모든 락카 잠금
        self.conn.execute("""
            UPDATE locker_status 
            SET current_transaction = ?, 
                locked_until = ?
        """, (tx_id, timeout))
        
        self.conn.commit()
        
        return {'success': True, 'transaction_id': tx_id}
    
    # ===== 대여 프로세스 =====
    def process_rental(self, member_id, locker_number, tx_id):
        """대여 처리"""
        try:
            self.conn.execute("BEGIN TRANSACTION")
            
            # 1. 대여 기록 생성
            self.conn.execute("""
                INSERT INTO rentals 
                (transaction_id, member_id, locker_number, rental_barcode_time)
                VALUES (?, ?, ?, datetime('now'))
            """, (tx_id, member_id, locker_number))
            
            # 2. ESP32에 명령 전송
            self.send_command({'cmd': 'open_locker', 'locker': locker_number})
            
            # 3. 센서 이벤트 대기 (최대 30초)
            sensor_events = self.wait_for_sensor_change(locker_number, timeout=30)
            
            # 4. 검증
            if self.verify_rental(sensor_events, locker_number):
                # 성공: 회원 상태 업데이트
                self.conn.execute("""
                    UPDATE members 
                    SET currently_renting = ?, 
                        last_rental_time = datetime('now')
                    WHERE member_id = ?
                """, (locker_number, member_id))
                
                # 대여 기록 업데이트
                self.conn.execute("""
                    UPDATE rentals 
                    SET rental_sensor_time = datetime('now'),
                        rental_verified = 1,
                        status = 'active'
                    WHERE transaction_id = ?
                """, (tx_id,))
                
                self.conn.commit()
                return {'success': True}
            else:
                # 실패: 롤백
                self.conn.rollback()
                return {'success': False, 'reason': '비정상 센서 감지'}
                
        except Exception as e:
            self.conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            self.end_transaction(tx_id)
    
    # ===== ESP32 통신 =====
    def send_command(self, cmd_dict):
        """ESP32로 JSON 명령 전송"""
        cmd_json = json.dumps(cmd_dict) + '\n'
        self.serial.write(cmd_json.encode())
        
    def read_sensor_data(self):
        """ESP32에서 센서 데이터 수신"""
        if self.serial.in_waiting:
            line = self.serial.readline().decode().strip()
            return json.loads(line)
        return None
    
    # ===== 동기화 =====
    def sync_with_google_sheets(self):
        """구글 시트와 동기화"""
        try:
            # 1. 회원 정보 다운로드
            import gspread
            gc = gspread.service_account(filename='credentials.json')
            sheet = gc.open('락카키_회원관리').sheet1
            
            # 2. 회원 테이블 업데이트
            members_data = sheet.get_all_records()
            for member in members_data:
                self.conn.execute("""
                    INSERT OR REPLACE INTO members 
                    (member_id, member_name, status, expiry_date)
                    VALUES (?, ?, ?, ?)
                """, (member['barcode'], member['name'], 
                     member['status'], member['expiry_date']))
            
            # 3. 대여 기록 업로드
            cursor = self.conn.execute("""
                SELECT * FROM rentals 
                WHERE sync_status = 0
            """)
            
            rental_records = cursor.fetchall()
            if rental_records:
                rental_sheet = gc.open('락카키_대여기록').sheet1
                for record in rental_records:
                    rental_sheet.append_row([...])  # 기록 추가
                    
                # 동기화 완료 표시
                self.conn.execute("""
                    UPDATE rentals 
                    SET sync_status = 1 
                    WHERE sync_status = 0
                """)
            
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"동기화 실패: {e}")
            return False
```

## 3. 메인 실행 파일

```python
# main.py
from locker_system import LockerSystem
import schedule
import threading

system = LockerSystem()

def barcode_reader_loop():
    """바코드 리더 메인 루프"""
    while True:
        barcode = input_from_barcode_reader()
        
        # 1. 트랜잭션 시작 시도
        tx_result = system.start_transaction(barcode)
        if not tx_result['success']:
            display_message(tx_result['message'])
            continue
            
        # 2. 회원 검증
        member_result = system.validate_member(barcode)
        if not member_result['valid']:
            display_message(member_result['reason'])
            system.end_transaction(tx_result['transaction_id'])
            continue
        
        # 3. 대여 프로세스
        display_message("락카를 선택하세요")
        locker_num = wait_for_locker_selection()
        
        rental_result = system.process_rental(
            barcode, locker_num, tx_result['transaction_id']
        )
        
        if rental_result['success']:
            display_message(f"{locker_num}번 락카 대여 완료")
        else:
            display_message("대여 실패: " + rental_result['reason'])

# 동기화 스케줄
schedule.every(6).hours.do(system.sync_with_google_sheets)

# 멀티스레드 실행
if __name__ == "__main__":
    sync_thread = threading.Thread(target=lambda: 
        schedule.run_pending(), daemon=True)
    sync_thread.start()
    
    barcode_reader_loop()
```

## 4. 폴더 구조
```
/home/pi/locker/
├── locker.db              # SQLite DB
├── schema.sql             # DB 스키마
├── locker_system.py       # 핵심 클래스
├── main.py               # 메인 실행
├── sync.py               # 동기화 스크립트
├── credentials.json      # 구글 API 인증
├── logs/                 # 로그 파일
└── backup/              # DB 백업
```

## 5. 주요 특징

### 동시성 제어
- `active_transactions` 테이블을 통한 트랜잭션 관리
- 30초 타임아웃으로 데드락 방지
- 한 번에 하나의 회원만 시스템 이용 가능

### 데이터 무결성
- 외래키 제약조건으로 참조 무결성 보장
- 트랜잭션을 통한 원자성 보장
- 센서 검증을 통한 물리적 상태와 DB 상태 동기화

### 확장성
- 모듈화된 클래스 설계
- 플러그인 방식의 센서/액추에이터 지원
- 구글 시트와의 양방향 동기화

### 안정성
- 예외 처리 및 롤백 메커니즘
- 로그 기록 및 오류 추적
- 정기적인 DB 백업

이 구조로 안정적이고 확장 가능한 락카키 대여 시스템을 구축할 수 있습니다.
