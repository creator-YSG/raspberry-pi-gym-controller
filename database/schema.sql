-- 락카키 대여기 시스템 SQLite 스키마
-- 작성일: 2025-10-01
-- 버전: 1.0

-- =====================================================
-- 회원 마스터 테이블
-- =====================================================
CREATE TABLE IF NOT EXISTS members (
    member_id TEXT PRIMARY KEY,          -- 바코드 번호 (회원 ID)
    member_name TEXT NOT NULL,           -- 회원명
    phone TEXT DEFAULT '',               -- 전화번호
    membership_type TEXT DEFAULT 'basic', -- 회원권 종류 (basic, premium, vip)
    status TEXT DEFAULT 'active',        -- 상태 (active, suspended, expired)
    expiry_date DATE,                    -- 회원권 만료일
    currently_renting TEXT,              -- 현재 대여중인 락카 번호
    daily_rental_count INTEGER DEFAULT 0, -- 오늘 대여 횟수
    last_rental_time TIMESTAMP,          -- 마지막 대여 시각
    sync_date TIMESTAMP,                 -- 구글시트 동기화 시각
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 대여 기록 테이블
-- =====================================================
CREATE TABLE IF NOT EXISTS rentals (
    rental_id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id TEXT UNIQUE NOT NULL, -- 트랜잭션 ID (UUID)
    member_id TEXT NOT NULL,             -- 회원 바코드
    locker_number TEXT NOT NULL,         -- 락카 번호
    
    -- 대여 프로세스 타임스탬프
    rental_barcode_time TIMESTAMP,       -- 회원카드 인식 시각
    rental_sensor_time TIMESTAMP,        -- 센서 '키 제거' 감지 시각
    rental_verified BOOLEAN DEFAULT 0,   -- 정상 대여 확인 여부
    
    -- 반납 프로세스 타임스탬프
    return_barcode_time TIMESTAMP,       -- 락카키 바코드 인식 시각
    return_target_locker TEXT,           -- 반납하려는 락카 번호
    return_sensor_time TIMESTAMP,        -- 센서 '키 삽입' 감지 시각
    return_actual_locker TEXT,           -- 실제 감지된 락카 번호
    return_verified BOOLEAN DEFAULT 0,   -- 정상 반납 확인 여부
    
    -- 상태 관리
    status TEXT DEFAULT 'active',        -- 상태 (active, returned, abnormal, cancelled)
    error_code TEXT,                     -- 오류 코드
    error_details TEXT,                  -- 오류 상세 내용
    
    -- 메타 정보
    device_id TEXT DEFAULT 'DEVICE_001', -- 디바이스 식별자
    sync_status INTEGER DEFAULT 0,       -- 구글시트 동기화 상태 (0:미동기화, 1:동기화완료)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 외래키 제약조건
    FOREIGN KEY (member_id) REFERENCES members(member_id) ON DELETE CASCADE
);

-- =====================================================
-- 락카 실시간 상태 테이블
-- =====================================================
CREATE TABLE IF NOT EXISTS locker_status (
    locker_number TEXT PRIMARY KEY,      -- 락카 번호 (A01, B15 등)
    zone TEXT NOT NULL,                  -- 구역 (A, B, C 등)
    sensor_status INTEGER DEFAULT 0,     -- 센서 상태 (0:비어있음, 1:키있음)
    door_status INTEGER DEFAULT 0,       -- 도어 상태 (0:닫힘, 1:열림)
    current_member TEXT,                 -- 현재 대여 회원 ID
    current_transaction TEXT,            -- 진행중인 트랜잭션 ID
    locked_until TIMESTAMP,              -- 잠금 해제 예정 시각
    last_change_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- 마지막 상태 변경 시각
    
    -- 락카 메타 정보
    size TEXT DEFAULT 'medium',          -- 락카 크기 (small, medium, large)
    maintenance_status TEXT DEFAULT 'normal', -- 유지보수 상태 (normal, maintenance, broken)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 활성 트랜잭션 테이블 (동시성 제어)
-- =====================================================
CREATE TABLE IF NOT EXISTS active_transactions (
    transaction_id TEXT PRIMARY KEY,     -- 트랜잭션 ID (UUID)
    member_id TEXT NOT NULL,             -- 회원 ID
    transaction_type TEXT NOT NULL,      -- 트랜잭션 타입 (rental, return)
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- 시작 시각
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- 마지막 활동 시각
    timeout_at TIMESTAMP NOT NULL,       -- 타임아웃 예정 시각
    sensor_events TEXT,                  -- 센서 이벤트 기록 (JSON)
    status TEXT DEFAULT 'active',        -- 상태 (active, completed, timeout, failed)
    
    -- 트랜잭션 메타 정보
    locker_number TEXT,                  -- 대상 락카 번호
    step TEXT DEFAULT 'started',         -- 현재 단계 (started, hardware_sent, sensor_wait, completed)
    error_message TEXT,                  -- 오류 메시지
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 외래키 제약조건
    FOREIGN KEY (member_id) REFERENCES members(member_id) ON DELETE CASCADE
);

-- =====================================================
-- 시스템 설정 테이블
-- =====================================================
CREATE TABLE IF NOT EXISTS system_settings (
    setting_key TEXT PRIMARY KEY,        -- 설정 키
    setting_value TEXT NOT NULL,         -- 설정 값
    setting_type TEXT DEFAULT 'string',  -- 값 타입 (string, integer, boolean, json)
    description TEXT,                    -- 설정 설명
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 인덱스 생성
-- =====================================================

-- 회원 테이블 인덱스
CREATE INDEX IF NOT EXISTS idx_member_barcode ON members(member_id);
CREATE INDEX IF NOT EXISTS idx_member_status ON members(status);
CREATE INDEX IF NOT EXISTS idx_member_currently_renting ON members(currently_renting);

-- 대여 기록 테이블 인덱스
CREATE INDEX IF NOT EXISTS idx_rental_status ON rentals(status);
CREATE INDEX IF NOT EXISTS idx_rental_member ON rentals(member_id);
CREATE INDEX IF NOT EXISTS idx_rental_locker ON rentals(locker_number);
CREATE INDEX IF NOT EXISTS idx_rental_transaction ON rentals(transaction_id);
CREATE INDEX IF NOT EXISTS idx_rental_created_at ON rentals(created_at);
CREATE INDEX IF NOT EXISTS idx_rental_sync_status ON rentals(sync_status);

-- 락카 상태 테이블 인덱스
CREATE INDEX IF NOT EXISTS idx_locker_zone ON locker_status(zone);
CREATE INDEX IF NOT EXISTS idx_locker_current_member ON locker_status(current_member);
CREATE INDEX IF NOT EXISTS idx_locker_current_transaction ON locker_status(current_transaction);

-- 활성 트랜잭션 테이블 인덱스
CREATE INDEX IF NOT EXISTS idx_transaction_member ON active_transactions(member_id);
CREATE INDEX IF NOT EXISTS idx_transaction_status ON active_transactions(status);
CREATE INDEX IF NOT EXISTS idx_transaction_timeout ON active_transactions(timeout_at);
CREATE INDEX IF NOT EXISTS idx_transaction_type ON active_transactions(transaction_type);

-- =====================================================
-- 기본 데이터 삽입
-- =====================================================

-- 시스템 설정 기본값
INSERT OR IGNORE INTO system_settings (setting_key, setting_value, setting_type, description) VALUES
('transaction_timeout_seconds', '30', 'integer', '트랜잭션 타임아웃 시간 (초)'),
('max_daily_rentals', '3', 'integer', '일일 최대 대여 횟수'),
('sensor_verification_timeout', '30', 'integer', '센서 검증 타임아웃 시간 (초)'),
('sync_interval_minutes', '30', 'integer', '구글시트 동기화 간격 (분)'),
('system_version', '1.0.0', 'string', '시스템 버전'),
('last_sync_time', '', 'string', '마지막 동기화 시간'),
('maintenance_mode', 'false', 'boolean', '유지보수 모드 여부');

-- 락카 상태 기본 데이터 (A구역 24개, B구역 24개)
INSERT OR IGNORE INTO locker_status (locker_number, zone, size) VALUES
-- A구역 락카 (1-24)
('A01', 'A', 'medium'), ('A02', 'A', 'medium'), ('A03', 'A', 'medium'), ('A04', 'A', 'medium'),
('A05', 'A', 'medium'), ('A06', 'A', 'medium'), ('A07', 'A', 'medium'), ('A08', 'A', 'medium'),
('A09', 'A', 'medium'), ('A10', 'A', 'medium'), ('A11', 'A', 'medium'), ('A12', 'A', 'medium'),
('A13', 'A', 'large'), ('A14', 'A', 'large'), ('A15', 'A', 'large'), ('A16', 'A', 'large'),
('A17', 'A', 'medium'), ('A18', 'A', 'medium'), ('A19', 'A', 'medium'), ('A20', 'A', 'medium'),
('A21', 'A', 'small'), ('A22', 'A', 'small'), ('A23', 'A', 'small'), ('A24', 'A', 'small'),

-- B구역 락카 (1-24)
('B01', 'B', 'medium'), ('B02', 'B', 'medium'), ('B03', 'B', 'medium'), ('B04', 'B', 'medium'),
('B05', 'B', 'medium'), ('B06', 'B', 'medium'), ('B07', 'B', 'medium'), ('B08', 'B', 'medium'),
('B09', 'B', 'medium'), ('B10', 'B', 'medium'), ('B11', 'B', 'medium'), ('B12', 'B', 'medium'),
('B13', 'B', 'large'), ('B14', 'B', 'large'), ('B15', 'B', 'large'), ('B16', 'B', 'large'),
('B17', 'B', 'medium'), ('B18', 'B', 'medium'), ('B19', 'B', 'medium'), ('B20', 'B', 'medium'),
('B21', 'B', 'small'), ('B22', 'B', 'small'), ('B23', 'B', 'small'), ('B24', 'B', 'small');

-- =====================================================
-- 트리거 생성 (자동 업데이트)
-- =====================================================

-- members 테이블 updated_at 자동 업데이트
CREATE TRIGGER IF NOT EXISTS update_members_timestamp 
    AFTER UPDATE ON members
    FOR EACH ROW
BEGIN
    UPDATE members SET updated_at = CURRENT_TIMESTAMP WHERE member_id = NEW.member_id;
END;

-- rentals 테이블 updated_at 자동 업데이트
CREATE TRIGGER IF NOT EXISTS update_rentals_timestamp 
    AFTER UPDATE ON rentals
    FOR EACH ROW
BEGIN
    UPDATE rentals SET updated_at = CURRENT_TIMESTAMP WHERE rental_id = NEW.rental_id;
END;

-- locker_status 테이블 updated_at 자동 업데이트
CREATE TRIGGER IF NOT EXISTS update_locker_status_timestamp 
    AFTER UPDATE ON locker_status
    FOR EACH ROW
BEGIN
    UPDATE locker_status SET updated_at = CURRENT_TIMESTAMP WHERE locker_number = NEW.locker_number;
END;

-- active_transactions 테이블 updated_at 자동 업데이트
CREATE TRIGGER IF NOT EXISTS update_active_transactions_timestamp 
    AFTER UPDATE ON active_transactions
    FOR EACH ROW
BEGIN
    UPDATE active_transactions SET updated_at = CURRENT_TIMESTAMP WHERE transaction_id = NEW.transaction_id;
END;

-- system_settings 테이블 updated_at 자동 업데이트
CREATE TRIGGER IF NOT EXISTS update_system_settings_timestamp 
    AFTER UPDATE ON system_settings
    FOR EACH ROW
BEGIN
    UPDATE system_settings SET updated_at = CURRENT_TIMESTAMP WHERE setting_key = NEW.setting_key;
END;
