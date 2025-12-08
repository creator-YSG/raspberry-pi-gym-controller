# 락카키 대여기 Google Sheets 스키마

## 개요

라즈베리파이 락카키 대여기 시스템의 Google Sheets 데이터베이스 구조입니다.
SQLite와 양방향 동기화를 통해 데이터를 관리합니다.

**스프레드시트 이름:** `락카키대여기-DB`

---

## 시트 구성

| 시트명 | 용도 | 동기화 방향 |
|--------|------|------------|
| 회원명단 | 회원 정보 | Sheets → DB |
| 대여기록 | 대여/반납 이력 | DB → Sheets |
| 락카현황 | 락카 실시간 상태 | 양방향 |
| 센서이벤트 | 센서 로그 | DB → Sheets |
| 시스템설정 | 설정값 | Sheets → DB |

---

## 시트 1: 회원명단 (members)

### 컬럼 구조

| 컬럼명 | 타입 | 필수 | 설명 | 예시 |
|--------|------|------|------|------|
| member_id | TEXT | O | 회원 고유 ID | M001, 202312345 |
| barcode | TEXT | O | 바코드 번호 (인증용) | 1234567890 |
| qr_code | TEXT | | QR 코드 (선택) | QR-001 |
| member_name | TEXT | O | 회원 이름 | 홍길동 |
| phone | TEXT | | 전화번호 | 010-1234-5678 |
| email | TEXT | | 이메일 | test@example.com |
| membership_type | TEXT | O | 회원권 종류 | basic, premium, vip |
| program_name | TEXT | | 가입 프로그램명 | 1.헬스1개월 |
| status | TEXT | O | 회원 상태 | active, suspended, expired |
| expiry_date | DATE | | 회원권 만료일 | 2025-12-31 |
| gender | TEXT | O | 성별 | male, female |
| member_category | TEXT | O | 회원 구분 | general, staff |
| customer_type | TEXT | | 고객 구분 | 학부, 대학교수, 대학직원, 기타 |
| created_at | DATETIME | | 가입일시 | 2024-12-01 09:00:00 |
| updated_at | DATETIME | | 최종 수정일시 | 2024-12-08 10:05:00 |

### 동기화 규칙
- **방향**: Sheets → DB (5분마다 다운로드)
- 회원 정보는 관리자가 구글 시트에서 직접 관리
- barcode가 인증의 기본 키

### 예시 데이터

```
| member_id | barcode    | member_name | phone         | membership_type | status | expiry_date | gender | member_category |
|-----------|------------|-------------|---------------|-----------------|--------|-------------|--------|-----------------|
| M001      | 1234567890 | 홍길동      | 010-1234-5678 | basic           | active | 2025-12-31  | male   | general         |
| M002      | 9876543210 | 김철수      | 010-2345-6789 | premium         | active | 2025-06-30  | male   | staff           |
```

---

## 시트 2: 대여기록 (rentals)

### 컬럼 구조

| 컬럼명 | 타입 | 필수 | 설명 | 예시 |
|--------|------|------|------|------|
| rental_id | NUMBER | O | 대여 ID (자동) | 1, 2, 3... |
| transaction_id | TEXT | O | 트랜잭션 UUID | uuid-xxxx-xxxx |
| member_id | TEXT | O | 회원 ID | M001 |
| member_name | TEXT | | 회원 이름 (조회용) | 홍길동 |
| locker_number | TEXT | O | 락카 번호 | M01, F05, S03 |
| zone | TEXT | O | 구역 | MALE, FEMALE, STAFF |
| rental_barcode_time | DATETIME | | 회원카드 인식 시각 | 2024-12-08 10:05:00 |
| rental_sensor_time | DATETIME | | 키 제거 감지 시각 | 2024-12-08 10:05:10 |
| return_sensor_time | DATETIME | | 키 삽입 감지 시각 | 2024-12-08 12:30:00 |
| status | TEXT | O | 상태 | active, returned, abnormal |
| device_id | TEXT | | 디바이스 ID | DEVICE_001 |
| created_at | DATETIME | O | 생성 시각 | 2024-12-08 10:05:00 |

### 동기화 규칙
- **방향**: DB → Sheets (5분마다 업로드)
- 새 대여 기록만 추가 (append)
- `sync_status = 0`인 레코드만 업로드

### 예시 데이터

```
| rental_id | transaction_id | member_id | member_name | locker_number | zone | status   | created_at          |
|-----------|----------------|-----------|-------------|---------------|------|----------|---------------------|
| 1         | uuid-001       | M001      | 홍길동      | M05           | MALE | returned | 2024-12-08 10:05:00 |
| 2         | uuid-002       | M002      | 김철수      | S03           | STAFF| active   | 2024-12-08 10:30:00 |
```

---

## 시트 3: 락카현황 (locker_status)

### 컬럼 구조

| 컬럼명 | 타입 | 필수 | 설명 | 예시 |
|--------|------|------|------|------|
| locker_number | TEXT | O | 락카 번호 | M01, F05, S03 |
| zone | TEXT | O | 구역 | MALE, FEMALE, STAFF |
| device_id | TEXT | | ESP32 디바이스 ID | esp32_male_female |
| sensor_status | NUMBER | O | 센서 상태 | 0=비어있음, 1=키있음 |
| door_status | NUMBER | O | 도어 상태 | 0=닫힘, 1=열림 |
| current_member | TEXT | | 현재 대여 회원 ID | M001 |
| nfc_uid | TEXT | | NFC 태그 UID | 04:AB:CD:EF |
| size | TEXT | | 락카 크기 | medium |
| maintenance_status | TEXT | O | 유지보수 상태 | normal, maintenance, broken |
| **sensor_number** | NUMBER | | 센서 번호 (1-60) | 11 |
| **serial_port** | TEXT | | 시리얼 포트 | /dev/ttyUSB0 |
| **chip_index** | NUMBER | | MCP23017 칩 인덱스 | 0, 1, 2, 3 |
| **chip_address** | TEXT | | MCP23017 I2C 주소 | 0x23, 0x25, 0x26, 0x27 |
| **pin_number** | NUMBER | | MCP23017 핀 번호 | 0-15 |
| **sensor_verified** | NUMBER | | 센서 검증 여부 | 0, 1 |
| sensor_verified_at | DATETIME | | 센서 검증 시각 | 2025-11-07 20:50:00 |
| created_at | DATETIME | | 생성 시각 | 2024-12-08 10:05:00 |
| updated_at | DATETIME | | 최종 업데이트 | 2024-12-08 10:05:00 |

### ⚠️ 센서 매핑 확인 필요 사항 (2025-12-08)

현재 기록된 센서 매핑에 이상한 점이 있어 **현장 확인 필요**:

1. **0x26 주소 중복**: Chip0(교직원 S01-S10)과 Chip2(남성 M21-M30 등)에서 동일 주소 사용
2. **M21-M40 비정상 분산**: 
   - 0x26 Chip2: M21-M30 + M34, M35, M38, M39, M40 (15핀)
   - 0x27 Chip3: M31, M32, M33, M36, M37 + F01-F10 (15핀)
3. **10개씩 안 나뉨**: 칩당 16핀 기준 10/10이 아닌 15/15 구성
4. 실제 물리적 배선과 일치하는지 현장 확인 필요

### 칩별 구성 (현재 기록 기준)

| addr | chip | 사용 핀 | 락카 | 포트 |
|------|------|---------|------|------|
| 0x23 | 0 | 10핀 (0-9) | M01-M10 | /dev/ttyUSB0 |
| 0x25 | 1 | 10핀 (0-9) | M11-M20 | /dev/ttyUSB0 |
| 0x26 | 0 | 10핀 (0-9) | S01-S10 | /dev/ttyUSB1 |
| 0x26 | 2 | 15핀 (0-14) | M21-30+일부 | /dev/ttyUSB0 |
| 0x27 | 3 | 15핀 (0-14) | F01-10+일부 | /dev/ttyUSB0 |

### 동기화 규칙
- **방향**: 양방향 (1분마다)
- DB에서 락카 상태 업데이트 → Sheets에 반영
- Sheets에서 유지보수 상태 변경 → DB에 반영

### 예시 데이터

```
| locker_number | zone   | sensor_status | door_status | current_member | maintenance_status | last_change_time    |
|---------------|--------|---------------|-------------|----------------|--------------------| --------------------|
| M01           | MALE   | 1             | 0           |                | normal             | 2024-12-08 10:05:00 |
| M02           | MALE   | 0             | 0           | M001           | normal             | 2024-12-08 10:30:00 |
| S01           | STAFF  | 1             | 0           |                | maintenance        | 2024-12-08 09:00:00 |
```

---

## 시트 4: 센서이벤트 (sensor_events)

### 컬럼 구조

| 컬럼명 | 타입 | 필수 | 설명 | 예시 |
|--------|------|------|------|------|
| event_id | NUMBER | O | 이벤트 ID | 1, 2, 3... |
| locker_number | TEXT | O | 락카 번호 | M05 |
| sensor_state | TEXT | O | 센서 상태 | HIGH, LOW |
| member_id | TEXT | | 관련 회원 ID | M001 |
| rental_id | NUMBER | | 관련 대여 ID | 1 |
| session_context | TEXT | | 세션 컨텍스트 | rental, return, unauthorized |
| description | TEXT | | 이벤트 설명 | 키 제거 감지 |
| event_timestamp | DATETIME | O | 이벤트 시각 | 2024-12-08 10:05:10 |

### 동기화 규칙
- **방향**: DB → Sheets (5분마다 업로드)
- 최근 7일 이벤트만 보관 (자동 정리)

---

## 시트 5: 시스템설정 (system_settings)

### 컬럼 구조

| 컬럼명 | 타입 | 필수 | 설명 | 예시 |
|--------|------|------|------|------|
| setting_key | TEXT | O | 설정 키 | transaction_timeout_seconds |
| setting_value | TEXT | O | 설정 값 | 30 |
| setting_type | TEXT | O | 값 타입 | string, integer, boolean, json |
| description | TEXT | | 설명 | 트랜잭션 타임아웃 시간 (초) |
| updated_at | DATETIME | | 최종 수정 | 2024-12-08 09:00:00 |

### 기본 설정값

| 키 | 값 | 타입 | 설명 |
|----|----|----|------|
| transaction_timeout_seconds | 30 | integer | 트랜잭션 타임아웃 (초) |
| max_daily_rentals | 3 | integer | 일일 최대 대여 횟수 |
| sensor_verification_timeout | 30 | integer | 센서 검증 타임아웃 (초) |
| sync_interval_minutes | 5 | integer | 구글시트 동기화 간격 (분) |
| system_version | 1.0.0 | string | 시스템 버전 |

### 동기화 규칙
- **방향**: Sheets → DB (10분마다 다운로드)
- 관리자가 구글 시트에서 설정 변경 가능

---

## 동기화 전략

### 라즈베리파이 → Google Sheets (업로드)

| 데이터 | 주기 | 방식 |
|--------|------|------|
| 대여기록 | 5분 | 미동기화 레코드 append |
| 센서이벤트 | 5분 | 미동기화 레코드 append |
| 락카현황 | 1분 | 전체 업데이트 |

### Google Sheets → 라즈베리파이 (다운로드)

| 데이터 | 주기 | 방식 |
|--------|------|------|
| 회원명단 | 5분 | 전체 동기화 |
| 시스템설정 | 10분 | 전체 동기화 |
| 락카현황 (유지보수) | 5분 | 변경 사항만 |

---

## API 호출 제한

### Google Sheets API 제한
- **무료**: 분당 60회 읽기/쓰기
- 최소 1초 간격으로 API 호출
- 배치 처리로 효율화

### Rate Limit 처리

```python
def _rate_limit(self):
    now = time.time()
    elapsed = now - self.last_api_call
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)
    self.last_api_call = time.time()
```

---

## 오프라인 모드

네트워크 연결이 끊어져도 로컬 SQLite DB로 정상 운영:
- 회원 인증: 로컬 DB 조회
- 대여/반납: 로컬 DB 기록
- 네트워크 복구 시 자동 동기화

---

## 구글 시트 생성 가이드

### 1. 새 스프레드시트 생성
1. Google Sheets에서 새 스프레드시트 생성
2. 이름: `락카키대여기-DB`

### 2. 시트(탭) 생성
아래 5개 시트 생성:
- 회원명단
- 대여기록
- 락카현황
- 센서이벤트
- 시스템설정

### 3. 서비스 계정 권한 부여
1. 스프레드시트 → 공유
2. 서비스 계정 이메일 추가 (편집자 권한)
   - 기존 서비스 계정: `config/google_credentials.json`에서 `client_email` 확인

### 4. 스프레드시트 ID 복사
URL에서 ID 추출:
```
https://docs.google.com/spreadsheets/d/[SPREADSHEET_ID]/edit
```

### 5. 설정 파일 업데이트
`config/google_sheets_config.json`:
```json
{
  "spreadsheet_id": "[새 스프레드시트 ID]",
  "credentials_file": "google_credentials.json",
  "sheet_names": {
    "members": "회원명단",
    "rentals": "대여기록",
    "lockers": "락카현황",
    "sensor_events": "센서이벤트",
    "settings": "시스템설정"
  }
}
```

