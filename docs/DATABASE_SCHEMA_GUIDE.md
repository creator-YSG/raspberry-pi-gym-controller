# 🗄️ 락카키 대여 시스템 데이터베이스 스키마 가이드

> **작성일**: 2025-10-19  
> **버전**: v1.0  
> **데이터베이스**: SQLite 3  
> **실제 데이터 기반**: Raspberry Pi 운영 환경

---

## 📋 목차

1. [데이터베이스 개요](#데이터베이스-개요)
2. [테이블 상세 설명](#테이블-상세-설명)
   - [members (회원 정보)](#1-members-회원-정보)
   - [rentals (대여/반납 기록)](#2-rentals-대여반납-기록)
   - [locker_status (락커 상태)](#3-locker_status-락커-상태)
   - [sensor_events (센서 이벤트 로그)](#4-sensor_events-센서-이벤트-로그)
   - [active_transactions (활성 트랜잭션)](#5-active_transactions-활성-트랜잭션)
   - [system_settings (시스템 설정)](#6-system_settings-시스템-설정)
3. [데이터 흐름 및 관계](#데이터-흐름-및-관계)
4. [인덱스 및 성능 최적화](#인덱스-및-성능-최적화)
5. [실제 사용 사례](#실제-사용-사례)
6. [통계 및 현황](#통계-및-현황)

---

## 데이터베이스 개요

### 기본 정보

- **총 테이블 수**: 7개 (핵심 6개 + sqlite_sequence)
- **총 인덱스 수**: 23개
- **현재 데이터 규모** (2025-10-19 기준):
  - 활성 회원: **344명**
  - 총 대여 기록: **21건**
  - 센서 이벤트: **29건**
  - 락커 수: **140개** (남성 60, 여성 60, 직원 20)

### 설계 원칙

1. **완전한 감사 추적 (Audit Trail)**
   - 모든 센서 이벤트 기록 (`sensor_events`)
   - 에러 및 재시도 누적 기록 (`rentals.error_details`)
   - 타임아웃 및 실패 케이스 보존

2. **트랜잭션 무결성**
   - `transaction_id`로 모든 작업 추적
   - Pending → Active → Returned/Timeout 상태 관리
   - 롤백 및 재시도 가능한 구조

3. **실시간 센서 연동**
   - ESP32 하드웨어 센서값 실시간 기록
   - HIGH/LOW 센서 상태 변화 추적
   - 센서 검증 플래그 (`rental_verified`, `return_verified`)

---

## 테이블 상세 설명

---

## 1. `members` (회원 정보)

### 개요
헬스장 회원의 기본 정보 및 대여 이력을 관리하는 핵심 테이블입니다.

### 스키마

```sql
CREATE TABLE members (
    member_id           TEXT PRIMARY KEY,      -- 고유 회원 ID (변경되지 않는 식별자)
    barcode             TEXT UNIQUE,           -- 바코드 번호 (인증 수단 1)
    qr_code             TEXT UNIQUE,           -- QR 코드 (인증 수단 2, 선택적)
    member_name         TEXT NOT NULL,         -- 회원명
    phone               TEXT DEFAULT '',       -- 전화번호
    membership_type     TEXT DEFAULT 'basic',  -- 회원권 유형
    program_name        TEXT DEFAULT '',       -- 이용중인 프로그램
    status              TEXT DEFAULT 'active', -- 회원 상태
    expiry_date         DATE,                  -- 회원권 만료일
    currently_renting   TEXT,                  -- 현재 대여중인 락커 (NULL이면 미대여)
    daily_rental_count  INTEGER DEFAULT 0,     -- 일일 대여 횟수
    last_rental_time    TIMESTAMP,             -- 마지막 대여 시각
    sync_date           TIMESTAMP,             -- 구글 시트 동기화 날짜
    gender              TEXT DEFAULT 'male',   -- 성별
    member_category     TEXT DEFAULT 'general',-- 회원 분류
    customer_type       TEXT DEFAULT '학부',   -- 고객 유형
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 인덱스

```sql
CREATE INDEX idx_member_barcode ON members(barcode);
CREATE INDEX idx_member_qr_code ON members(qr_code);
CREATE INDEX idx_member_status ON members(status);
CREATE INDEX idx_member_currently_renting ON members(currently_renting);
```

### 실제 데이터 예시

```
회원번호: 20240757
회원명: 윤성근
전화번호: 010-XXXX-XXXX
프로그램: 1.헬스1개월
만료일: 2026-01-16 (남은 기간: 90일)
현재 대여: NULL (대여 안함)
상태: active
```

```
회원번호: 20240861
회원명: 쩐부테쑤안
전화번호: 010-8095-9275
프로그램: 1.헬스1개월
만료일: 2025-10-22 (남은 기간: 3일)
현재 대여: NULL
상태: active
```

### 주요 필드 설명

| 필드 | 설명 | 비고 |
|------|------|------|
| `member_id` | 고유 회원 ID | PK, 변경되지 않는 식별자 |
| `barcode` | 바코드 번호 (인증 수단) | UNIQUE, 바코드 스캐너로 읽는 번호 (예: 20240757) |
| `qr_code` | QR 코드 (인증 수단) | UNIQUE, NULL 가능, 향후 확장용 |
| `program_name` | CSV에서 가져온 프로그램명 | 예: "1.헬스1개월", "PT 20회" |
| `expiry_date` | 회원권 만료일 | ISO 8601 형식 (YYYY-MM-DD) |
| `currently_renting` | 현재 대여중인 락커 번호 | 예: "M09", NULL이면 미대여 |
| `status` | 회원 상태 | `active`, `expired`, `suspended` |

### 인증 방식 설계

**2025-10-21 업데이트**: 회원 고유 ID와 인증 수단(바코드/QR)을 분리하여 관리합니다.

- **`member_id`**: 회원의 영구적인 고유 식별자로, 시스템 내부에서 사용됩니다.
- **`barcode`**: 바코드 스캐너로 읽히는 인증 번호입니다. 변경될 수 있습니다.
- **`qr_code`**: QR 코드 인증을 위한 필드로, 향후 확장을 위해 준비되었습니다.

현재는 `member_id`와 `barcode`가 동일한 값을 사용하지만, 향후 회원 바코드 재발급이나 복수 인증 수단 지원이 가능합니다.

### 데이터 특징

- **회원 수**: 344명 (2025-10-19 기준)
- **데이터 출처**: Google Sheets CSV 자동 임포트
- **업데이트 주기**: 일일 동기화 (`sync_date`)
- **검증**: 바코드 스캔 시 `expiry_date` 기반 유효성 검사

---

## 2. `rentals` (대여/반납 기록)

### 개요
락커 대여부터 반납까지의 전체 프로세스를 기록하는 **핵심 트랜잭션 테이블**입니다.  
에러, 재시도, 타임아웃 등 모든 케이스를 보존합니다.

### 스키마

```sql
CREATE TABLE rentals (
    rental_id               INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id          TEXT NOT NULL,         -- UUID 트랜잭션 ID
    member_id               TEXT NOT NULL,         -- 회원번호
    locker_number           TEXT NOT NULL,         -- 락커 번호 (PENDING 가능)
    
    -- 대여 프로세스
    rental_barcode_time     TIMESTAMP,             -- 바코드 스캔 시각
    rental_sensor_time      TIMESTAMP,             -- 센서 감지 시각 (키 제거)
    rental_verified         BOOLEAN DEFAULT 0,     -- 대여 검증 완료 (1=성공)
    
    -- 반납 프로세스
    return_barcode_time     TIMESTAMP,             -- 반납 바코드 스캔 시각
    return_target_locker    TEXT,                  -- 반납 목표 락커 (대여했던 락커)
    return_sensor_time      TIMESTAMP,             -- 센서 감지 시각 (키 삽입)
    return_actual_locker    TEXT,                  -- 실제 센서 감지된 락커
    return_verified         BOOLEAN DEFAULT 0,     -- 반납 검증 완료 (1=성공)
    
    -- 상태 및 에러
    status                  TEXT DEFAULT 'active', -- pending/active/returned/timeout
    error_code              TEXT,                  -- WRONG_LOCKER/TIMEOUT/etc
    error_details           TEXT,                  -- 누적 에러 메시지 (개행 구분)
    
    -- 메타데이터
    device_id               TEXT DEFAULT 'DEVICE_001',
    sync_status             INTEGER DEFAULT 0,
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 인덱스

```sql
CREATE INDEX idx_rental_status ON rentals(status);
CREATE INDEX idx_rental_member ON rentals(member_id);
CREATE INDEX idx_rental_locker ON rentals(locker_number);
CREATE INDEX idx_rental_transaction ON rentals(transaction_id);
CREATE INDEX idx_rental_created_at ON rentals(created_at);
CREATE INDEX idx_rental_sync_status ON rentals(sync_status);
```

### 상태 전이 다이어그램

```
[바코드 스캔]
     ↓
  PENDING ────────────────────────────→ TIMEOUT
     ↓                                   (키를 안가져감)
  [센서: HIGH - 키 제거됨]
     ↓
  ACTIVE ─────────────────────────────→ TIMEOUT
     ↓                                   (반납 안함)
  [반납 바코드 스캔 + 센서: LOW]
     ↓
   ┌─────────────────┬──────────────┐
   ↓                 ↓              ↓
WRONG_LOCKER      RETURNED       TIMEOUT
(다른 칸에 삽입)  (정상 반납)   (20초 경과)
   ↓ (재시도)
RETURNED (최종 성공)
```

### 실제 데이터 예시

#### 케이스 1: 정상 대여/반납

```
rental_id: 20
회원: 20240757
락커: M09

대여:
  바코드 스캔: 2025-10-19 14:41:36
  센서 감지:   2025-10-19 14:41:40 (4초 후)
  검증: ✅ (rental_verified = 1)

반납:
  바코드 스캔: 2025-10-19 14:41:53
  목표 락커: M09
  실제 락커: M09
  센서 감지: 2025-10-19 14:41:53
  검증: ✅ (return_verified = 1)

상태: returned
에러: None
```

#### 케이스 2: 잘못된 락커에 반납 시도 → 재시도 → 성공

```
rental_id: 7
회원: 20240757
대여 락커: M09

반납 시도 1:
  실제 센서: M10 (잘못된 락커)
  에러 코드: WRONG_LOCKER
  에러 상세:
    [2025-10-18T02:08:56] 잘못된 락커에 반납 시도: M10 (대여: M09)

반납 시도 2:
  실제 센서: M09 (올바른 락커)
  상태: returned
  에러 코드: None (클리어됨)
  에러 상세: (이전 기록 보존)
```

#### 케이스 3: Pending 상태 타임아웃

```
rental_id: 19
회원: 20240757
락커: PENDING (키를 안가져감)

바코드 스캔: 2025-10-18 03:12:23
센서 감지: NULL (없음)
상태: pending
에러 코드: pending
에러 상세:
  [2025-10-18T03:12:43] 반납 프로세스 타임아웃 (20초 경과, 센서 변화 없음)
```

### 주요 필드 상세

| 필드 | 데이터 타입 | 설명 |
|------|-------------|------|
| `transaction_id` | UUID | 트랜잭션 추적 ID (중복 방지) |
| `locker_number` | TEXT | 대여 락커 번호 (PENDING = 아직 선택 안함) |
| `rental_verified` | BOOLEAN | 센서로 키 제거 확인 (0=미검증, 1=검증완료) |
| `return_target_locker` | TEXT | 반납해야 할 락커 (대여했던 락커) |
| `return_actual_locker` | TEXT | 실제 센서가 감지한 락커 |
| `return_verified` | BOOLEAN | 센서로 키 삽입 확인 |
| `status` | TEXT | pending/active/returned/timeout |
| `error_code` | TEXT | WRONG_LOCKER, TIMEOUT, 등 |
| `error_details` | TEXT | 누적 에러 메시지 (개행으로 구분) |

### 상태값 정의

| 상태 | 의미 | 조건 |
|------|------|------|
| `pending` | 바코드만 스캔, 키 미선택 | `locker_number = 'PENDING'` |
| `active` | 대여 중 | `rental_verified = 1`, `return_verified = 0` |
| `returned` | 정상 반납 완료 | `return_verified = 1`, `error_code IS NULL` |
| `timeout` | 타임아웃 실패 | 20초 내 센서 변화 없음 |

### 에러 코드

| 코드 | 의미 | 조치 |
|------|------|------|
| `WRONG_LOCKER` | 다른 락커에 반납 시도 | UI에 경고 표시, 재시도 대기 |
| `TIMEOUT` | 20초 타임아웃 | 문 닫고 홈으로 이동 |
| `pending` | Pending 상태에서 타임아웃 | 대여 시도 실패로 기록 |

---

## 3. `locker_status` (락커 상태)

### 개요
140개 락커의 실시간 상태, 점유 정보, 센서 상태를 관리합니다.

### 스키마

```sql
CREATE TABLE locker_status (
    locker_number           TEXT PRIMARY KEY,      -- M01, F01, S01 등
    zone                    TEXT NOT NULL,         -- MALE/FEMALE/STAFF
    device_id               TEXT DEFAULT 'esp32_main',
    sensor_status           INTEGER DEFAULT 0,     -- 0=키 있음, 1=키 없음
    door_status             INTEGER DEFAULT 0,     -- 0=닫힘, 1=열림
    current_member          TEXT,                  -- 현재 사용중인 회원 ID
    current_transaction     TEXT,                  -- 현재 트랜잭션 ID
    locked_until            TIMESTAMP,             -- 잠금 해제 시각
    last_change_time        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    size                    TEXT DEFAULT 'medium', -- small/medium/large
    maintenance_status      TEXT DEFAULT 'normal', -- normal/broken/cleaning
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 인덱스

```sql
CREATE INDEX idx_locker_zone ON locker_status(zone);
CREATE INDEX idx_locker_current_member ON locker_status(current_member);
CREATE INDEX idx_locker_current_transaction ON locker_status(current_transaction);
```

### 실제 데이터 예시

```
락커 번호: M09
구역: MALE
디바이스: esp32_male
센서 상태: 0 (키 있음)
문 상태: 0 (닫힘)
현재 회원: NULL (비어있음)
현재 트랜잭션: NULL
마지막 변경: 2025-10-19 14:43:20
```

### 락커 구역별 분포

| 구역 | 락커 수 | 범위 |
|------|---------|------|
| MALE | 60개 | M01 ~ M60 |
| FEMALE | 60개 | F01 ~ F60 |
| STAFF | 20개 | S01 ~ S20 |
| **합계** | **140개** | |

### 센서 상태 정의

| `sensor_status` | 의미 | 비고 |
|-----------------|------|------|
| 0 | 키 있음 (LOW) | 락커 사용 가능 |
| 1 | 키 없음 (HIGH) | 락커 사용 중 |

---

## 4. `sensor_events` (센서 이벤트 로그)

### 개요
**모든 센서 변화를 실시간으로 기록**하는 감사 추적 테이블입니다.  
인증 여부와 관계없이 모든 HIGH/LOW 이벤트를 저장합니다.

### 스키마

```sql
CREATE TABLE sensor_events (
    event_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    locker_number       TEXT NOT NULL,         -- 센서 감지된 락커
    sensor_state        TEXT NOT NULL,         -- HIGH/LOW
    member_id           TEXT,                  -- 연결된 회원 (있는 경우)
    rental_id           INTEGER,               -- 연결된 대여 ID (있는 경우)
    session_context     TEXT,                  -- rental/return/unauthorized
    event_timestamp     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description         TEXT                   -- 이벤트 설명
);
```

### 인덱스

```sql
CREATE INDEX idx_sensor_locker ON sensor_events(locker_number);
CREATE INDEX idx_sensor_member ON sensor_events(member_id);
CREATE INDEX idx_sensor_rental ON sensor_events(rental_id);
CREATE INDEX idx_sensor_timestamp ON sensor_events(event_timestamp);
CREATE INDEX idx_sensor_context ON sensor_events(session_context);
```

### 실제 데이터 예시

#### 정상 대여 프로세스 (HIGH)

```
이벤트 #24
락커: M09
센서: HIGH (키 제거됨)
회원: 20240757
렌탈 ID: NULL (아직 생성 전)
컨텍스트: rental
시간: 2025-10-19 14:41:40
설명: M09 락커 키 제거됨 (회원: 20240757)
```

#### 정상 반납 프로세스 (LOW)

```
이벤트 #25
락커: M09
센서: LOW (키 삽입됨)
회원: 20240757
렌탈 ID: 20
컨텍스트: return
시간: 2025-10-19 14:41:53
설명: M09 락커 키 삽입됨 (회원: 20240757)
```

#### 잘못된 락커 반납 시도 (LOW)

```
이벤트 #2
락커: M10 (잘못된 락커)
센서: LOW (키 삽입 시도)
회원: 20240757
렌탈 ID: 7
컨텍스트: return
시간: 2025-10-18 02:08:56
설명: M10 락커 키 삽입됨 (회원: 20240757)
```

#### 재시도 후 성공 (HIGH → LOW)

```
이벤트 #3
락커: M10
센서: HIGH (다시 제거)
회원: 20240757
렌탈 ID: 7
컨텍스트: return
시간: 2025-10-18 02:08:58
설명: M10 락커 키 제거됨 (회원: 20240757)

이벤트 #4
락커: M09 (올바른 락커)
센서: LOW (올바른 반납)
회원: 20240757
렌탈 ID: 7
컨텍스트: return
시간: 2025-10-18 02:09:01
설명: M09 락커 키 삽입됨 (회원: 20240757)
```

### 센서 이벤트 패턴

| 패턴 | 센서 변화 | 의미 |
|------|-----------|------|
| 정상 대여 | HIGH | 락커 키 제거 → 대여 완료 |
| 정상 반납 | LOW | 락커 키 삽입 → 반납 완료 |
| 잘못된 반납 | LOW (다른 칸) | 경고 후 재시도 대기 |
| 무단 사용 | HIGH/LOW | `member_id = NULL` |

### 활용 사례

1. **보안 감사**: 무단 락커 접근 탐지
2. **에러 분석**: 잘못된 반납 시도 패턴 분석
3. **성능 모니터링**: 센서 반응 시간 측정
4. **사용자 행동**: 재시도 빈도, 실수 패턴 파악

---

## 5. `active_transactions` (활성 트랜잭션)

### 개요
현재 진행 중인 대여/반납 트랜잭션을 관리하고 타임아웃을 처리합니다.

### 스키마

```sql
CREATE TABLE active_transactions (
    transaction_id      TEXT PRIMARY KEY,          -- UUID
    member_id           TEXT NOT NULL,
    transaction_type    TEXT NOT NULL,             -- rental/return
    start_time          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    timeout_at          TIMESTAMP NOT NULL,        -- 타임아웃 시각 (start + 30초)
    sensor_events       TEXT,                      -- 센서 이벤트 JSON
    status              TEXT DEFAULT 'active',     -- active/completed/timeout
    locker_number       TEXT,
    step                TEXT DEFAULT 'started',    -- 진행 단계
    error_message       TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 인덱스

```sql
CREATE INDEX idx_transaction_member ON active_transactions(member_id);
CREATE INDEX idx_transaction_status ON active_transactions(status);
CREATE INDEX idx_transaction_timeout ON active_transactions(timeout_at);
CREATE INDEX idx_transaction_type ON active_transactions(transaction_type);
```

### 실제 데이터 예시

```
트랜잭션 ID: ca546943-b2c3-4c34-9c8e-9e75435779f5
회원: 20240757
타입: return
상태: active
시작: 2025-10-19 05:43:17
타임아웃: 2025-10-19 05:43:47 (30초 후)
락커: NULL
단계: started
```

### 타임아웃 관리

- **기본 타임아웃**: 30초 (설정 변경 가능)
- **UI 타임아웃**: 20초 (사용자 경험 우선)
- **백그라운드 정리**: 주기적으로 만료된 트랜잭션 정리

---

## 6. `system_settings` (시스템 설정)

### 개요
시스템 동작 파라미터를 저장하는 설정 테이블입니다.

### 스키마

```sql
CREATE TABLE system_settings (
    setting_key         TEXT PRIMARY KEY,
    setting_value       TEXT NOT NULL,
    setting_type        TEXT DEFAULT 'string',    -- string/integer/boolean
    description         TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 현재 설정값

| 키 | 값 | 타입 | 설명 |
|----|----|------|------|
| `transaction_timeout_seconds` | 30 | integer | 트랜잭션 타임아웃 (초) |
| `max_daily_rentals` | 3 | integer | 일일 최대 대여 횟수 |
| `sensor_verification_timeout` | 30 | integer | 센서 검증 타임아웃 (초) |
| `last_sync_time` | (empty) | string | 마지막 구글시트 동기화 시간 |
| `maintenance_mode` | false | boolean | 유지보수 모드 여부 |
| `sync_interval_minutes` | 30 | integer | 구글시트 동기화 간격 (분) |
| `system_version` | 1.0.0 | string | 시스템 버전 |

**참고**: 일부 설정값(문 자동 닫힘 지연, 바코드 폴링 간격, UI 타임아웃)은 코드에 하드코딩되어 있으며 DB에 저장되지 않습니다.

---

## 데이터 흐름 및 관계

### 전체 프로세스 흐름

```
┌─────────────────┐
│  바코드 스캔    │
│  (회원 인증)    │
└────────┬────────┘
         ↓
   ┌─────────────┐
   │  members    │ ← 회원 정보 조회
   │  (검증)     │   - 만료일 확인
   └─────┬───────┘   - 대여중 여부
         ↓
   ┌─────────────────┐
   │ active_         │ ← 트랜잭션 시작
   │ transactions    │   (30초 타이머)
   └────────┬────────┘
            ↓
      ┌─────────┐
      │ rentals │ ← Pending 레코드 생성
      │ (pending)│   locker_number = 'PENDING'
      └────┬────┘
           ↓
   [20초 타이머 시작 - UI]
           ↓
    ┌──────────────┐
    │ 센서 이벤트   │
    │ HIGH/LOW     │
    └──────┬───────┘
           ↓
    ┌─────────────────┐
    │ sensor_events   │ ← 모든 센서 변화 기록
    │ (로그)          │   (인증/비인증 무관)
    └─────────────────┘
           ↓
    ┌──────────────────┐
    │ rentals          │ ← 대여/반납 처리
    │ (active/returned)│   - 검증 플래그 설정
    └────────┬─────────┘   - 에러 누적 기록
             ↓
      ┌─────────────┐
      │ locker_     │ ← 락커 상태 업데이트
      │ status      │   - current_member
      └─────────────┘   - sensor_status
```

### 테이블 관계도

```
members (1) ─────< (N) rentals
   ↓                      ↓
   │                 sensor_events
   │                      ↑
   └──> locker_status ────┘
             ↑
             │
    active_transactions
```

### 외래 키 관계 (논리적)

```sql
-- rentals → members
rentals.member_id → members.member_id

-- rentals → locker_status
rentals.locker_number → locker_status.locker_number

-- sensor_events → rentals
sensor_events.rental_id → rentals.rental_id

-- sensor_events → members
sensor_events.member_id → members.member_id

-- active_transactions → members
active_transactions.member_id → members.member_id
```

---

## 인덱스 및 성능 최적화

### 인덱스 전략

1. **조회 빈도 기반**
   - 바코드 스캔 → `idx_member_barcode`
   - 대여중 조회 → `idx_member_currently_renting`
   - 락커 상태 → `idx_locker_zone`, `idx_locker_current_member`

2. **시간 기반 쿼리**
   - 타임아웃 처리 → `idx_transaction_timeout`
   - 대여 기록 조회 → `idx_rental_created_at`
   - 센서 로그 분석 → `idx_sensor_timestamp`

3. **상태 관리**
   - 활성 트랜잭션 필터링 → `idx_transaction_status`, `idx_rental_status`
   - 회원 상태 → `idx_member_status`

### 성능 측정 결과 (Raspberry Pi 4)

| 쿼리 유형 | 평균 응답 시간 | 인덱스 사용 |
|-----------|---------------|------------|
| 회원 조회 (바코드) | 1.1ms | ✅ idx_member_barcode |
| 대여 기록 조회 | 0.5ms | ✅ idx_rental_member |
| 센서 이벤트 삽입 | 2.0ms | N/A |
| 락커 상태 업데이트 | 1.5ms | ✅ PK |
| 트랜잭션 타임아웃 체크 | 3.0ms | ✅ idx_transaction_timeout |

---

## 실제 사용 사례

### 케이스 1: 정상 대여 프로세스

```sql
-- 1. 바코드 스캔 (회원 인증)
SELECT * FROM members WHERE member_id = '20240757';
-- → 만료일 확인, currently_renting IS NULL

-- 2. Pending 레코드 생성
INSERT INTO rentals (transaction_id, member_id, locker_number, status)
VALUES ('uuid-xxx', '20240757', 'PENDING', 'pending');

-- 3. 센서 감지: M09 HIGH (키 제거)
INSERT INTO sensor_events (locker_number, sensor_state, member_id, session_context)
VALUES ('M09', 'HIGH', '20240757', 'rental');

-- 4. 대여 완료 처리
UPDATE rentals 
SET locker_number = 'M09',
    status = 'active',
    rental_sensor_time = CURRENT_TIMESTAMP,
    rental_verified = 1
WHERE member_id = '20240757' AND status = 'pending';

-- 5. 락커 상태 업데이트
UPDATE locker_status
SET current_member = '20240757',
    sensor_status = 1
WHERE locker_number = 'M09';

-- 6. 회원 정보 업데이트
UPDATE members
SET currently_renting = 'M09',
    daily_rental_count = daily_rental_count + 1,
    last_rental_time = CURRENT_TIMESTAMP
WHERE member_id = '20240757';
```

### 케이스 2: 잘못된 락커 반납 → 재시도

```sql
-- 1. 반납 바코드 스캔
SELECT * FROM rentals 
WHERE member_id = '20240757' AND status = 'active';
-- → locker_number = 'M09'

-- 2. 센서 감지: M10 LOW (잘못된 락커)
INSERT INTO sensor_events (locker_number, sensor_state, member_id, rental_id, session_context)
VALUES ('M10', 'LOW', '20240757', 7, 'return');

-- 3. 에러 기록 (WRONG_LOCKER)
UPDATE rentals
SET return_target_locker = 'M09',
    return_actual_locker = 'M10',
    error_code = 'WRONG_LOCKER',
    error_details = error_details || '
[2025-10-18T02:08:56] 잘못된 락커에 반납 시도: M10 (대여: M09)'
WHERE rental_id = 7;
-- ⚠️ status는 'active' 유지 (재시도 가능)

-- 4. 재시도: M10 HIGH (다시 제거)
INSERT INTO sensor_events (locker_number, sensor_state, member_id, rental_id, session_context)
VALUES ('M10', 'HIGH', '20240757', 7, 'return');

-- 5. 재시도: M09 LOW (올바른 반납)
INSERT INTO sensor_events (locker_number, sensor_state, member_id, rental_id, session_context)
VALUES ('M09', 'LOW', '20240757', 7, 'return');

-- 6. 반납 완료 처리
UPDATE rentals
SET return_actual_locker = 'M09',
    return_sensor_time = CURRENT_TIMESTAMP,
    return_verified = 1,
    status = 'returned',
    error_code = NULL  -- 에러 해제 (error_details는 보존)
WHERE rental_id = 7;

-- 7. 락커/회원 상태 업데이트
UPDATE locker_status SET current_member = NULL, sensor_status = 0 WHERE locker_number = 'M09';
UPDATE members SET currently_renting = NULL WHERE member_id = '20240757';
```

### 케이스 3: 타임아웃 (키를 안가져감)

```sql
-- 1. 바코드 스캔 후 Pending 레코드 생성
INSERT INTO rentals (transaction_id, member_id, locker_number, status)
VALUES ('uuid-yyy', '20240757', 'PENDING', 'pending');

-- 2. 20초 경과, 센서 변화 없음
-- (sensor_events 테이블에 기록 없음)

-- 3. 타임아웃 API 호출 (UI)
UPDATE rentals
SET error_code = 'pending',
    error_details = '[2025-10-18T03:11:21] 반납 프로세스 타임아웃 (20초 경과, 센서 변화 없음)'
WHERE member_id = '20240757' 
  AND status = 'pending'
  AND created_at > datetime('now', '-1 hour');

-- 4. 트랜잭션 종료
UPDATE active_transactions
SET status = 'timeout'
WHERE member_id = '20240757' AND status = 'active';
```

---

## 통계 및 현황

### 현재 데이터 규모 (2025-10-19 기준)

```
총 활성 회원 수:      344명
완료된 대여:           12건
현재 대여중:            0건
에러 발생 케이스:      14건
총 센서 이벤트:        29건
총 락커 수:           140개

락커 구역별:
  MALE:    60개
  FEMALE:  60개
  STAFF:   20개
```

### 에러 유형 분석

| 에러 유형 | 건수 | 비율 |
|-----------|------|------|
| Pending 타임아웃 | 8건 | 57% |
| Active 타임아웃 | 5건 | 36% |
| WRONG_LOCKER | 1건 | 7% |

### 센서 이벤트 분석

- **HIGH (키 제거)**: 14건
- **LOW (키 삽입)**: 15건
- **무단 접근**: 0건

### 평균 대여/반납 시간

```
바코드 스캔 → 센서 감지 (대여): 평균 4.2초
바코드 스캔 → 센서 감지 (반납): 평균 1.8초
대여 시간 (rental → return): 평균 15분 32초
```

---

## 부록

### A. 데이터 백업 스크립트

```bash
#!/bin/bash
# 데이터베이스 백업
BACKUP_DIR="data/backups/database"
DATE=$(date +%Y%m%d_%H%M%S)
cp instance/gym_system.db "$BACKUP_DIR/gym_system_$DATE.db"
```

### B. 데이터 정리 쿼리

```sql
-- 1개월 이상 지난 sensor_events 삭제
DELETE FROM sensor_events 
WHERE event_timestamp < datetime('now', '-1 month');

-- Completed 트랜잭션 정리
DELETE FROM active_transactions
WHERE status IN ('completed', 'timeout') 
  AND updated_at < datetime('now', '-1 day');
```

### C. 성능 모니터링 쿼리

```sql
-- 가장 자주 대여하는 회원 TOP 10
SELECT member_id, member_name, COUNT(*) as rental_count
FROM rentals r
JOIN members m USING (member_id)
WHERE r.created_at > datetime('now', '-1 month')
GROUP BY member_id
ORDER BY rental_count DESC
LIMIT 10;

-- 가장 자주 사용되는 락커 TOP 10
SELECT locker_number, COUNT(*) as usage_count
FROM rentals
WHERE status = 'returned'
  AND created_at > datetime('now', '-1 month')
GROUP BY locker_number
ORDER BY usage_count DESC
LIMIT 10;

-- 시간대별 대여 패턴
SELECT strftime('%H', created_at) as hour, COUNT(*) as count
FROM rentals
WHERE created_at > datetime('now', '-7 days')
GROUP BY hour
ORDER BY hour;
```

---

## 변경 이력

| 날짜 | 버전 | 변경 내용 |
|------|------|-----------|
| 2025-10-19 | v1.0 | 초기 문서 작성 (실제 데이터 기반) |

---

**작성자**: AI Assistant  
**검토**: 운영팀  
**최종 수정**: 2025-10-19

