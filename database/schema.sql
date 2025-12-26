-- 락카키 대여기 시스템 SQLite 스키마
-- 작성일: 2025-10-01
-- 버전: 1.0

-- =====================================================
-- 회원 마스터 테이블
-- =====================================================
CREATE TABLE IF NOT EXISTS members (
    member_id TEXT PRIMARY KEY,          -- 고유 회원 ID (변경되지 않는 고유 식별자)
    barcode TEXT UNIQUE,                 -- 바코드 번호 (인증 수단 1)
    qr_code TEXT UNIQUE,                 -- QR 코드 (인증 수단 2, 선택적)
    member_name TEXT NOT NULL,           -- 회원명
    email TEXT DEFAULT '',               -- 이메일 주소
    phone TEXT DEFAULT '',               -- 전화번호
    membership_type TEXT DEFAULT 'basic', -- 회원권 종류 (basic, premium, vip)
    program_name TEXT DEFAULT '',        -- 가입 프로그램명 (예: 1.헬스1개월, 1.헬스3+1)
    status TEXT DEFAULT 'active',        -- 상태 (active, suspended, expired)
    expiry_date DATE,                    -- 회원권 만료일
    currently_renting TEXT,              -- 현재 대여중인 락카 번호
    daily_rental_count INTEGER DEFAULT 0, -- 오늘 대여 횟수
    last_rental_time TIMESTAMP,          -- 마지막 대여 시각
    sync_date TIMESTAMP,                 -- 구글시트 동기화 시각
    -- 🆕 락커 권한 관련 필드들
    gender TEXT DEFAULT 'male',          -- 성별 (male, female)
    member_category TEXT DEFAULT 'general', -- 회원 구분 (general, staff)
    customer_type TEXT DEFAULT '학부',    -- 고객구분 (학부, 대학교수, 대학직원, 기타 등)
    -- 🆕 얼굴인식 관련 필드들
    face_embedding BLOB,                  -- 얼굴 임베딩 벡터 (pickle 직렬화)
    face_photo_path TEXT,                 -- 등록된 얼굴 사진 로컬 경로
    face_photo_url TEXT,                  -- 구글 드라이브 공유 URL (회원 확인용)
    face_registered_at TIMESTAMP,         -- 얼굴 등록 시각
    face_enabled INTEGER DEFAULT 0,       -- 얼굴인식 활성화 여부 (0:비활성, 1:활성)
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
    -- 🆕 얼굴인식/사진 관련 필드들
    auth_method TEXT DEFAULT 'barcode',  -- 인증 방법 (barcode, qr, nfc, face)
    rental_photo_path TEXT,              -- 인증 시 촬영된 사진 로컬 경로
    rental_photo_url TEXT,               -- 구글 드라이브 공유 URL
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 외래키 제약조건
    FOREIGN KEY (member_id) REFERENCES members(member_id) ON DELETE CASCADE
);

-- =====================================================
-- 락카 실시간 상태 테이블
-- =====================================================
CREATE TABLE IF NOT EXISTS locker_status (
    locker_number TEXT PRIMARY KEY,      -- 락카 번호 (M01, F01, S01 등)
    zone TEXT NOT NULL,                  -- 구역 (MALE, FEMALE, STAFF 등)
    device_id TEXT DEFAULT 'esp32_main', -- 제어 ESP32 디바이스 ID
    sensor_status INTEGER DEFAULT 0,     -- 센서 상태 (0:비어있음, 1:키있음)
    door_status INTEGER DEFAULT 0,       -- 도어 상태 (0:닫힘, 1:열림)
    current_member TEXT,                 -- 현재 대여 회원 ID
    current_transaction TEXT,            -- 진행중인 트랜잭션 ID
    locked_until TIMESTAMP,              -- 잠금 해제 예정 시각
    last_change_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- 마지막 상태 변경 시각
    
    -- 락카 메타 정보
    size TEXT DEFAULT 'medium',          -- 락카 크기 (small, medium, large)
    maintenance_status TEXT DEFAULT 'normal', -- 유지보수 상태 (normal, maintenance, broken)
    nfc_uid TEXT UNIQUE,                 -- NFC 태그 UID (락커키 식별용)
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
-- 센서 이벤트 로그 테이블 (모든 센서 변화 기록)
-- =====================================================
CREATE TABLE IF NOT EXISTS sensor_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    locker_number TEXT NOT NULL,         -- 락커 번호 (예: M09)
    sensor_state TEXT NOT NULL,          -- 센서 상태 (HIGH/LOW)
    member_id TEXT,                      -- 연관된 회원 ID (있는 경우)
    rental_id INTEGER,                   -- 연관된 대여 ID (있는 경우)
    session_context TEXT,                -- 세션 컨텍스트 (rental/return/unauthorized)
    event_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT,                    -- 이벤트 설명
    FOREIGN KEY (member_id) REFERENCES members(member_id),
    FOREIGN KEY (rental_id) REFERENCES rentals(rental_id)
);

-- =====================================================
-- 센서 매핑 테이블 (ESP32 센서 → 락커 매핑)
-- =====================================================
CREATE TABLE IF NOT EXISTS sensor_mapping (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    addr TEXT NOT NULL,                  -- ESP32 MCP23017 I2C 주소 ("0x26", "0x23" 등)
    chip_idx INTEGER NOT NULL,           -- ESP32 내 MCP 칩 인덱스 (0, 1, 2, 3)
    pin INTEGER NOT NULL,                -- MCP23017 핀 번호 (0-15)
    sensor_num INTEGER NOT NULL,         -- 논리적 센서 번호 (1-60)
    locker_id TEXT,                      -- 락커 ID ("M01", "S01" 등)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(addr, chip_idx, pin)
);

-- =====================================================
-- 인덱스 생성
-- =====================================================

-- 회원 테이블 인덱스
CREATE INDEX IF NOT EXISTS idx_member_barcode ON members(barcode);
CREATE INDEX IF NOT EXISTS idx_member_qr_code ON members(qr_code);
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

-- 센서 이벤트 테이블 인덱스
CREATE INDEX IF NOT EXISTS idx_sensor_locker ON sensor_events(locker_number);
CREATE INDEX IF NOT EXISTS idx_sensor_member ON sensor_events(member_id);
CREATE INDEX IF NOT EXISTS idx_sensor_rental ON sensor_events(rental_id);
CREATE INDEX IF NOT EXISTS idx_sensor_timestamp ON sensor_events(event_timestamp);
CREATE INDEX IF NOT EXISTS idx_sensor_context ON sensor_events(session_context);

-- 센서 매핑 테이블 인덱스
CREATE INDEX IF NOT EXISTS idx_sensor_mapping_addr_chip_pin ON sensor_mapping(addr, chip_idx, pin);
CREATE INDEX IF NOT EXISTS idx_sensor_mapping_sensor_num ON sensor_mapping(sensor_num);
CREATE INDEX IF NOT EXISTS idx_sensor_mapping_locker_id ON sensor_mapping(locker_id);

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

-- 락카 상태 기본 데이터 (교직원 10개, 남성 40개, 여성 10개 = 총 60개)
-- 10개 x 6줄 락커 시스템
INSERT OR IGNORE INTO locker_status (locker_number, zone, device_id, size) VALUES
-- 교직원 구역 10개 (S01-S10) - ESP32 #1 (esp32_staff)
('S01', 'STAFF', 'esp32_staff', 'medium'), ('S02', 'STAFF', 'esp32_staff', 'medium'), ('S03', 'STAFF', 'esp32_staff', 'medium'), ('S04', 'STAFF', 'esp32_staff', 'medium'),
('S05', 'STAFF', 'esp32_staff', 'medium'), ('S06', 'STAFF', 'esp32_staff', 'medium'), ('S07', 'STAFF', 'esp32_staff', 'medium'), ('S08', 'STAFF', 'esp32_staff', 'medium'),
('S09', 'STAFF', 'esp32_staff', 'medium'), ('S10', 'STAFF', 'esp32_staff', 'medium'),

-- 남성 구역 40개 (M01-M40) - ESP32 #2 (esp32_male_female)
('M01', 'MALE', 'esp32_male_female', 'medium'), ('M02', 'MALE', 'esp32_male_female', 'medium'), ('M03', 'MALE', 'esp32_male_female', 'medium'), ('M04', 'MALE', 'esp32_male_female', 'medium'),
('M05', 'MALE', 'esp32_male_female', 'medium'), ('M06', 'MALE', 'esp32_male_female', 'medium'), ('M07', 'MALE', 'esp32_male_female', 'medium'), ('M08', 'MALE', 'esp32_male_female', 'medium'),
('M09', 'MALE', 'esp32_male_female', 'medium'), ('M10', 'MALE', 'esp32_male_female', 'medium'), ('M11', 'MALE', 'esp32_male_female', 'medium'), ('M12', 'MALE', 'esp32_male_female', 'medium'),
('M13', 'MALE', 'esp32_male_female', 'medium'), ('M14', 'MALE', 'esp32_male_female', 'medium'), ('M15', 'MALE', 'esp32_male_female', 'medium'), ('M16', 'MALE', 'esp32_male_female', 'medium'),
('M17', 'MALE', 'esp32_male_female', 'medium'), ('M18', 'MALE', 'esp32_male_female', 'medium'), ('M19', 'MALE', 'esp32_male_female', 'medium'), ('M20', 'MALE', 'esp32_male_female', 'medium'),
('M21', 'MALE', 'esp32_male_female', 'medium'), ('M22', 'MALE', 'esp32_male_female', 'medium'), ('M23', 'MALE', 'esp32_male_female', 'medium'), ('M24', 'MALE', 'esp32_male_female', 'medium'),
('M25', 'MALE', 'esp32_male_female', 'medium'), ('M26', 'MALE', 'esp32_male_female', 'medium'), ('M27', 'MALE', 'esp32_male_female', 'medium'), ('M28', 'MALE', 'esp32_male_female', 'medium'),
('M29', 'MALE', 'esp32_male_female', 'medium'), ('M30', 'MALE', 'esp32_male_female', 'medium'), ('M31', 'MALE', 'esp32_male_female', 'medium'), ('M32', 'MALE', 'esp32_male_female', 'medium'),
('M33', 'MALE', 'esp32_male_female', 'medium'), ('M34', 'MALE', 'esp32_male_female', 'medium'), ('M35', 'MALE', 'esp32_male_female', 'medium'), ('M36', 'MALE', 'esp32_male_female', 'medium'),
('M37', 'MALE', 'esp32_male_female', 'medium'), ('M38', 'MALE', 'esp32_male_female', 'medium'), ('M39', 'MALE', 'esp32_male_female', 'medium'), ('M40', 'MALE', 'esp32_male_female', 'medium'),

-- 여성 구역 10개 (F01-F10) - ESP32 #2 (esp32_male_female)
('F01', 'FEMALE', 'esp32_male_female', 'medium'), ('F02', 'FEMALE', 'esp32_male_female', 'medium'), ('F03', 'FEMALE', 'esp32_male_female', 'medium'), ('F04', 'FEMALE', 'esp32_male_female', 'medium'),
('F05', 'FEMALE', 'esp32_male_female', 'medium'), ('F06', 'FEMALE', 'esp32_male_female', 'medium'), ('F07', 'FEMALE', 'esp32_male_female', 'medium'), ('F08', 'FEMALE', 'esp32_male_female', 'medium'),
('F09', 'FEMALE', 'esp32_male_female', 'medium'), ('F10', 'FEMALE', 'esp32_male_female', 'medium');

-- =====================================================
-- 센서 매핑 기본 데이터 (ESP32 센서 → 락커 매핑)
-- =====================================================

-- 기존 하드코딩 데이터를 DB로 마이그레이션 (app/__init__.py 기준)
INSERT OR IGNORE INTO sensor_mapping (addr, chip_idx, pin, sensor_num, locker_id) VALUES
-- addr=0x26, Chip0 → 교직원 (S01-S10)
('0x26', 0, 1, 1, 'S01'), ('0x26', 0, 0, 2, 'S02'), ('0x26', 0, 6, 3, 'S03'), ('0x26', 0, 5, 4, 'S04'),
('0x26', 0, 4, 5, 'S05'), ('0x26', 0, 3, 6, 'S06'), ('0x26', 0, 2, 7, 'S07'), ('0x26', 0, 9, 8, 'S08'),
('0x26', 0, 8, 9, 'S09'), ('0x26', 0, 7, 10, 'S10'),

-- addr=0x23, Chip0 → 남성 (M01-M10)
('0x23', 0, 1, 11, 'M01'), ('0x23', 0, 2, 12, 'M02'), ('0x23', 0, 0, 13, 'M03'), ('0x23', 0, 6, 14, 'M04'),
('0x23', 0, 5, 15, 'M05'), ('0x23', 0, 3, 16, 'M06'), ('0x23', 0, 4, 17, 'M07'), ('0x23', 0, 9, 18, 'M08'),
('0x23', 0, 7, 19, 'M09'), ('0x23', 0, 8, 20, 'M10'),

-- addr=0x25, Chip1 → 남성 (M11-M20)
('0x25', 1, 0, 21, 'M11'), ('0x25', 1, 3, 22, 'M12'), ('0x25', 1, 1, 23, 'M13'), ('0x25', 1, 2, 24, 'M14'),
('0x25', 1, 5, 25, 'M15'), ('0x25', 1, 7, 26, 'M16'), ('0x25', 1, 4, 27, 'M17'), ('0x25', 1, 6, 28, 'M18'),
('0x25', 1, 8, 29, 'M19'), ('0x25', 1, 9, 30, 'M20'),

-- addr=0x26, Chip2 → 남성 (M21-M30, M34-M35, M38-M40)
('0x26', 2, 5, 31, 'M21'), ('0x26', 2, 6, 32, 'M22'), ('0x26', 2, 7, 33, 'M23'), ('0x26', 2, 10, 34, 'M24'),
('0x26', 2, 11, 35, 'M25'), ('0x26', 2, 9, 36, 'M26'), ('0x26', 2, 8, 37, 'M27'), ('0x26', 2, 14, 38, 'M28'),
('0x26', 2, 13, 39, 'M29'), ('0x26', 2, 12, 40, 'M30'), ('0x26', 2, 0, 44, 'M34'), ('0x26', 2, 1, 45, 'M35'),
('0x26', 2, 3, 48, 'M38'), ('0x26', 2, 2, 49, 'M39'), ('0x26', 2, 4, 50, 'M40'),

-- addr=0x27, Chip3 → 남성 (M31-M33, M36-M37) + 여성 (F01-F10)
('0x27', 3, 10, 41, 'M31'), ('0x27', 3, 14, 42, 'M32'), ('0x27', 3, 11, 43, 'M33'), ('0x27', 3, 12, 46, 'M36'),
('0x27', 3, 13, 47, 'M37'), ('0x27', 3, 0, 51, 'F01'), ('0x27', 3, 1, 52, 'F03'), ('0x27', 3, 2, 53, 'F02'),
('0x27', 3, 3, 54, 'F07'), ('0x27', 3, 4, 55, 'F06'), ('0x27', 3, 5, 56, 'F04'), ('0x27', 3, 6, 57, 'F05'),
('0x27', 3, 7, 58, 'F10'), ('0x27', 3, 8, 59, 'F09'), ('0x27', 3, 9, 60, 'F08');

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

-- sensor_mapping 테이블 updated_at 자동 업데이트
CREATE TRIGGER IF NOT EXISTS update_sensor_mapping_timestamp
    AFTER UPDATE ON sensor_mapping
    FOR EACH ROW
BEGIN
    UPDATE sensor_mapping SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
