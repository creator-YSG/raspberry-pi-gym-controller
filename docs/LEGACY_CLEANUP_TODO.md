# 레거시 코드 정리 대상

> 작성일: 2024-12-26
> 상태: 정리 예정

## 개요

개발 과정에서 여러 차례 리팩토링하면서 사용되지 않거나 중복된 코드/설정이 남아있습니다.
이 문서는 정리 대상과 주의사항을 정리합니다.

---

## 1. 트랜잭션 시스템

### 정리 대상

| 파일 | 내용 | 우선순위 |
|------|------|----------|
| `database/transaction_manager.py` | TransactionManager 클래스 전체 | 높음 |
| `database/schema.sql` | `active_transactions` 테이블 | 높음 |
| `database/schema.sql` | `rentals.transaction_id` 컬럼 | 중간 |
| `app/services/locker_service.py` | `tx_manager` 호출부 | 높음 |
| `app/services/sensor_event_handler.py` | `tx_manager` 호출부 | 높음 |
| `app/main/routes.py` | `tx_manager.start_transaction()` 호출 | 높음 |

### 현재 상태

```
바코드 스캔
    ↓
tx_manager.start_transaction() ← 트랜잭션 시작
    ↓
active_transactions 테이블에 레코드 생성
    ↓
rentals.transaction_id 연결
    ↓
30초 타임아웃 관리, step 추적
    ↓
tx_manager.end_transaction()
```

### 문제점

1. **과도한 복잡성**: 키오스크 1대 환경에서 동시성 제어 불필요
2. **타임아웃 불일치**: 프론트엔드 20초 vs 백엔드 30초
3. **실제 미사용**: `rentals.rental_id`로 모든 처리 가능
4. **transaction_id 무의미**: UUID 생성만 하고 거의 조회 안 함

### 정리 후 구조

```
바코드 스캔
    ↓
rentals에 pending 레코드 생성 (rental_id)
    ↓
센서 이벤트 → rentals.status 업데이트
    ↓
프론트엔드 타임아웃 → 홈으로
```

### 주의사항

- [ ] `rentals.transaction_id` 컬럼은 기존 데이터 호환성 때문에 바로 삭제하면 안 됨
- [ ] 먼저 코드에서 transaction_id 참조를 모두 제거
- [ ] 이후 DB 마이그레이션으로 컬럼 삭제 (또는 그냥 두기)
- [ ] `active_transactions` 테이블은 데이터 백업 후 삭제
- [ ] 테스트 코드(`tests/`)도 함께 정리 필요

---

## 2. 동기화 시스템

### 정리 대상

| 파일 | 내용 | 우선순위 |
|------|------|----------|
| `database/sync_manager.py` | SyncManager 클래스 전체 | 높음 |
| `data_sources/google_sheets.py` | GoogleSheetsManager 클래스 | 높음 |
| `database/schema.sql` | `sync_interval_minutes` 설정 | 낮음 |

### 현재 상태

```
동기화 클래스 3개 존재:
├── SheetsSync (app/services/sheets_sync.py) ← 현재 사용
├── IntegrationSync (app/services/integration_sync.py) ← 현재 사용
├── SyncManager (database/sync_manager.py) ← 레거시, 미사용
└── GoogleSheetsManager (data_sources/google_sheets.py) ← 레거시, 미사용
```

### 문제점

1. **중복 클래스**: 같은 기능 3개 구현
2. **설정 파편화**: `sync_interval_minutes` (DB) vs `download_interval_sec` (config)
3. **혼란**: 어떤 클래스가 실제 동작하는지 파악 어려움

### 정리 후 구조

```
동기화:
├── SheetsSync ← 락카키 시트 동기화
├── IntegrationSync ← 통합 시트 동기화
└── SyncScheduler ← 스케줄링
```

### 주의사항

- [ ] `SyncManager` import하는 곳 확인 (있으면 제거)
- [ ] `GoogleSheetsManager` import하는 곳 확인 (있으면 제거)
- [ ] `sync_interval_minutes`는 DB에서 제거하거나, 실제 사용하도록 수정
- [ ] 구글시트 `시스템설정`에서도 `sync_interval_minutes` 제거

---

## 3. 설정 파편화

### 정리 대상

| 설정 | 현재 위치 | 권장 |
|------|----------|------|
| Google Sheet ID | 3곳 (config.json, .env, setup.py) | config.json만 |
| 동기화 간격 | 4곳 (DB, config.json, .env, 코드) | config.json만 |
| 관리자 비밀번호 | 2곳 (main.js, 통합시트) | 통합시트만 ✅ 완료 |
| 헬스장 이름 | 2곳 (.env, 통합시트) | 통합시트만 ✅ 완료 |

### 이미 완료된 것

- [x] `gym_name` → 통합시트 > 헬스장설정에서 관리
- [x] `admin_password` → 통합시트 > 헬스장설정에서 관리
- [x] `config.env.template`에서 레거시 설정 주석 처리

### 남은 작업

- [ ] `config/google_sheets_setup.py`의 하드코딩된 시트 ID 제거
- [ ] `database/sync_manager.py`의 레거시 시트 ID 참조 제거

---

## 4. 프론트엔드 하드코딩

### 정리 대상

| 파일 | 내용 | 현재 값 | 권장 |
|------|------|---------|------|
| `member_check.html` | 타임아웃 | 20초 하드코딩 | DB 설정 연동 |
| `face_auth.html` | 타임아웃 | 20초 하드코딩 | DB 설정 연동 |
| `app/static/js/main.js` | 관리자 비밀번호 | '1234' 하드코딩 | 제거 (이제 API 사용) |

### 주의사항

- [ ] 타임아웃 연동 시 서버에서 설정값 전달 필요 (템플릿 변수)
- [ ] 백엔드 `transaction_timeout_seconds`와 프론트엔드 타임아웃 통일

---

## 5. 정리 순서 권장

### Phase 1: 안전한 정리 (영향 적음)

1. `SyncManager`, `GoogleSheetsManager` 클래스 삭제
2. `config/google_sheets_setup.py` 레거시 ID 제거
3. `main.js`의 하드코딩된 비밀번호 제거

### Phase 2: 설정 통일 (테스트 필요)

1. `sync_interval_minutes` DB 설정 제거 또는 실제 연동
2. 프론트엔드 타임아웃 DB 연동

### Phase 3: 트랜잭션 시스템 제거 (큰 변경)

1. `TransactionManager` 호출부 모두 제거
2. `active_transactions` 테이블 삭제
3. `rentals.transaction_id` 참조 제거
4. 테스트 코드 정리

---

## 6. 테스트 체크리스트

정리 후 반드시 확인:

- [ ] 바코드 대여 정상 동작
- [ ] 바코드 반납 정상 동작
- [ ] 얼굴인식 대여 정상 동작
- [ ] NFC 반납 정상 동작
- [ ] 구글시트 동기화 정상 동작 (다운로드/업로드)
- [ ] 설정 화면 진입 (5회 터치 + 비밀번호)
- [ ] 센서 이벤트 처리 정상

---

## 관련 문서

- `docs/DATABASE.md` - 데이터베이스 구조
- `docs/GOOGLE_INTEGRATION_GUIDE.md` - 구글시트 연동 가이드
- `database/schema.sql` - DB 스키마 정의

