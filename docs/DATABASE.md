# 데이터베이스 가이드

> SQLite 기반 락카키 대여 시스템 데이터베이스

## 개요

- **DB 파일**: `instance/gym_system.db`
- **테이블 수**: 6개
- **락커 수**: 60개 (교직원 10, 남성 40, 여성 10)

---

## 테이블 구조

### 1. members (회원)

```sql
CREATE TABLE members (
    member_id           TEXT PRIMARY KEY,     -- 회원 ID (바코드)
    barcode             TEXT UNIQUE,          -- 바코드 번호
    member_name         TEXT NOT NULL,        -- 회원명
    status              TEXT DEFAULT 'active',-- active/expired/suspended
    expiry_date         DATE,                 -- 만료일
    currently_renting   TEXT,                 -- 현재 대여 중인 락커 (M01 등)
    gender              TEXT DEFAULT 'male',  -- male/female
    member_category     TEXT DEFAULT 'general', -- general/staff
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 2. rentals (대여 기록)

```sql
CREATE TABLE rentals (
    rental_id               INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id          TEXT NOT NULL,      -- UUID
    member_id               TEXT NOT NULL,      -- 회원 ID
    locker_number           TEXT NOT NULL,      -- 락커 번호 (PENDING 가능)
    
    -- 대여 정보
    rental_barcode_time     TIMESTAMP,          -- 바코드 스캔 시각
    rental_sensor_time      TIMESTAMP,          -- 센서 감지 시각
    rental_verified         BOOLEAN DEFAULT 0,  -- 대여 검증 완료
    
    -- 반납 정보
    return_barcode_time     TIMESTAMP,
    return_target_locker    TEXT,               -- 반납 목표 락커
    return_sensor_time      TIMESTAMP,
    return_actual_locker    TEXT,               -- 실제 반납 락커
    return_verified         BOOLEAN DEFAULT 0,
    
    -- 상태
    status                  TEXT DEFAULT 'active', -- pending/active/returned/timeout
    error_code              TEXT,               -- WRONG_LOCKER/TIMEOUT
    error_details           TEXT,               -- 에러 상세 (누적)
    
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**상태 전이:**
```
pending → active → returned
              ↘ timeout
```

### 3. locker_status (락커 상태)

```sql
CREATE TABLE locker_status (
    locker_number       TEXT PRIMARY KEY,     -- M01, F01, S01 등
    zone                TEXT NOT NULL,        -- MALE/FEMALE/STAFF
    sensor_status       INTEGER DEFAULT 0,    -- 0=키있음, 1=키없음
    current_member      TEXT,                 -- 현재 사용 회원
    serial_port         TEXT,                 -- /dev/ttyUSB0 등
    i2c_address         TEXT,                 -- 0x23 등
    chip_index          INTEGER,              -- 0-3
    pin_number          INTEGER,              -- 0-15
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 4. sensor_events (센서 이벤트 로그)

```sql
CREATE TABLE sensor_events (
    event_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    locker_number       TEXT NOT NULL,
    sensor_state        TEXT NOT NULL,        -- HIGH/LOW
    member_id           TEXT,                 -- 연결된 회원
    rental_id           INTEGER,              -- 연결된 대여 ID
    session_context     TEXT,                 -- rental/return/unauthorized
    event_timestamp     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description         TEXT
);
```

### 5. active_transactions (활성 트랜잭션)

```sql
CREATE TABLE active_transactions (
    transaction_id      TEXT PRIMARY KEY,
    member_id           TEXT NOT NULL,
    transaction_type    TEXT NOT NULL,        -- rental/return
    status              TEXT DEFAULT 'active',-- active/completed/timeout
    locker_number       TEXT,
    timeout_at          TIMESTAMP NOT NULL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

> **참고**: `active_transactions` 테이블은 타임아웃 추적용입니다. 
> 실제 대여/반납 처리는 `rentals` 테이블만 사용합니다.

### 6. system_settings (시스템 설정)

```sql
CREATE TABLE system_settings (
    setting_key         TEXT PRIMARY KEY,
    setting_value       TEXT NOT NULL,
    setting_type        TEXT DEFAULT 'string',
    description         TEXT
);
```

| 키 | 값 | 설명 |
|----|-----|------|
| `transaction_timeout_seconds` | 30 | 트랜잭션 타임아웃 |
| `max_daily_rentals` | 3 | 일일 최대 대여 |

---

## 센서 상태

| 값 | 의미 |
|----|------|
| `HIGH` | 키 없음 (뽑힘) |
| `LOW` | 키 있음 (꽂힘) |

---

## 주요 쿼리

### 회원 조회
```sql
SELECT * FROM members WHERE member_id = '20240673';
```

### 활성 대여 조회
```sql
SELECT * FROM rentals 
WHERE member_id = '20240673' AND status = 'active';
```

### 락커 현황
```sql
SELECT zone, COUNT(*) FROM locker_status GROUP BY zone;
```

### 대여 통계
```sql
SELECT DATE(created_at), COUNT(*) 
FROM rentals 
WHERE status = 'returned'
GROUP BY DATE(created_at);
```

---

## 백업

### WAL 모드 주의

SQLite WAL 모드 사용 중. 단순 파일 복사 시 데이터 손실 가능!

```
instance/
├── gym_system.db       # 메인 DB
├── gym_system.db-wal   # WAL 파일 (최신 데이터!)
└── gym_system.db-shm   # 공유 메모리
```

### 올바른 백업 방법

```bash
# 방법 1: 스크립트 사용 (권장)
python3 scripts/maintenance/backup_database.py --skip-checkpoint

# 방법 2: 모든 파일 복사
cp instance/gym_system.db* backup/

# 방법 3: 체크포인트 후 복사
sqlite3 instance/gym_system.db "PRAGMA wal_checkpoint(TRUNCATE);"
cp instance/gym_system.db backup/
```

### 라즈베리파이에서 동기화

```bash
# 안전한 방법 (쿼리 기반)
python3 scripts/maintenance/sync_db_from_pi.py --method query

# 빠른 방법 (파일 복사)
scp 'raspberry-pi:/home/pi/gym-controller/instance/gym_system.db*' instance/
```

---

## 데이터 흐름

```
[바코드 스캔]
     ↓
 members (회원 검증)
     ↓
 rentals (pending 레코드 생성)
     ↓
 [센서 이벤트 대기]
     ↓
 sensor_events (로그 기록)
     ↓
 rentals (active/returned 업데이트)
     ↓
 locker_status (락커 상태 업데이트)
     ↓
 members (currently_renting 업데이트)
```

---

## 관련 파일

- `database/schema.sql` - DB 스키마 정의
- `database/database_manager.py` - DB 연결 관리
- `scripts/setup/init_database.py` - DB 초기화 스크립트
- `scripts/maintenance/backup_database.py` - 백업 스크립트

