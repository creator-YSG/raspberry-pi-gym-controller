# 🔐 회원 인증 정보 분리 마이그레이션

> **작성일**: 2025-10-21  
> **버전**: v1.1  
> **마이그레이션 ID**: `AUTH_CREDENTIALS_SEPARATION`

---

## 📋 목차

1. [마이그레이션 개요](#마이그레이션-개요)
2. [변경 사항](#변경-사항)
3. [실행 결과](#실행-결과)
4. [영향 받는 코드](#영향-받는-코드)
5. [롤백 방법](#롤백-방법)

---

## 마이그레이션 개요

### 목적
회원 고유 ID(`member_id`)와 인증 수단(바코드/QR 코드)을 분리하여:
- 회원 바코드 재발급 가능
- 복수 인증 수단 지원 (바코드 + QR 코드)
- 인증 방식 확장 용이 (NFC, 지문 등)

### 변경 전 구조
```sql
members (
    member_id TEXT PRIMARY KEY  -- 바코드 번호 = 회원 ID (동일)
)
```

### 변경 후 구조
```sql
members (
    member_id TEXT PRIMARY KEY,  -- 고유 회원 ID
    barcode   TEXT UNIQUE,       -- 바코드 번호 (인증 수단 1)
    qr_code   TEXT UNIQUE        -- QR 코드 (인증 수단 2, 선택적)
)
```

---

## 변경 사항

### 1. 데이터베이스 스키마

#### `members` 테이블
- ✅ **추가**: `barcode TEXT UNIQUE` 컬럼
- ✅ **추가**: `qr_code TEXT UNIQUE` 컬럼
- ✅ **변경**: `member_id` 주석 수정 (바코드 번호 → 고유 회원 ID)

#### 인덱스
- ✅ **변경**: `idx_member_barcode` → `members(barcode)` 참조로 변경
- ✅ **추가**: `idx_member_qr_code` → `members(qr_code)` 인덱스

### 2. 애플리케이션 코드

#### `app/models/member.py`
```python
class Member:
    def __init__(self, id: str, barcode: str = None, qr_code: str = None, ...):
        self.id = id          # 고유 회원 ID
        self.barcode = barcode  # 바코드 번호
        self.qr_code = qr_code  # QR 코드
```

#### `app/services/member_service.py`
```python
# 🆕 신규 메서드
def authenticate_by_barcode(self, barcode: str) -> Optional[Member]:
    """바코드로 회원 조회"""
    
def authenticate_by_qr(self, qr_code: str) -> Optional[Member]:
    """QR 코드로 회원 조회"""
```

#### `app/services/barcode_service.py`
```python
def _process_member_barcode(self, barcode: str) -> Dict:
    # 변경 전: validate_member(barcode)
    # 변경 후: authenticate_by_barcode(barcode) → validate_member(member.id)
    member = self.member_service.authenticate_by_barcode(barcode)
    validation = self.member_service.validate_member(member.id)
```

#### `scripts/data/import_members_csv.py`
```python
member_data = {
    'member_id': customer_number,
    'barcode': customer_number,  # 동일한 값으로 초기화
    'qr_code': None,             # QR은 없음
    ...
}
```

---

## 실행 결과

### 맥미니 (개발 환경)

```
📂 데이터베이스: instance/gym_system.db
📌 기존 회원 수: 344명
✅ 344명 데이터 복사 완료
✅ 마이그레이션 검증 성공!

💾 백업 파일: data/backups/database/pre_auth_migration_20251021_181956.db
```

### 라즈베리파이 (운영 환경)

```
📂 데이터베이스: /home/pi/gym-controller/instance/gym_system.db
📌 기존 회원 수: 344명
✅ 344명 데이터 복사 완료
✅ 마이그레이션 검증 성공!

💾 백업 파일: /home/pi/gym-controller/data/backups/database/pre_auth_migration_20251021_182036.db
```

### 샘플 데이터 확인

```
회원ID: 20240757 | 바코드: 20240757 | QR: (없음) | 이름: 윤성근 | 상태: active
회원ID: 20240861 | 바코드: 20240861 | QR: (없음) | 이름: 쩐부테쑤안 | 상태: active
```

---

## 영향 받는 코드

### ✅ 수정 완료

| 파일 | 변경 내용 | 상태 |
|------|----------|------|
| `database/schema.sql` | `barcode`, `qr_code` 컬럼 추가 | ✅ |
| `app/models/member.py` | `barcode`, `qr_code` 필드 추가 | ✅ |
| `app/services/member_service.py` | 인증 메서드 추가 (`authenticate_by_barcode`, `authenticate_by_qr`) | ✅ |
| `app/services/barcode_service.py` | `authenticate_by_barcode` 사용으로 변경 | ✅ |
| `scripts/data/import_members_csv.py` | `barcode` 필드 처리 추가 | ✅ |
| `docs/DATABASE_SCHEMA_GUIDE.md` | 스키마 문서 업데이트 | ✅ |

### ✅ 호환성 유지

| 항목 | 설명 |
|------|------|
| 기존 API | `get_member(member_id)` 메서드 그대로 유지 |
| 대여/반납 로직 | `member.id` 기반 조회 유지 (변경 없음) |
| DB 조회 성능 | `barcode`, `qr_code` 인덱스로 성능 보장 |

---

## 롤백 방법

### 자동 백업 복구

마이그레이션 실행 시 자동으로 백업이 생성됩니다:

```bash
# 맥미니
cp data/backups/database/pre_auth_migration_20251021_181956.db instance/gym_system.db

# 라즈베리파이
ssh raspberry-pi "cd /home/pi/gym-controller && \
  cp data/backups/database/pre_auth_migration_20251021_182036.db instance/gym_system.db"
```

### 애플리케이션 재시작

```bash
# 맥미니 (개발)
pkill -f "python.*run.py"
python3 run.py

# 라즈베리파이 (운영)
ssh raspberry-pi "cd /home/pi/gym-controller && \
  ./scripts/deployment/stop_kiosk.sh && \
  ./scripts/deployment/start_kiosk.sh"
```

---

## 향후 확장 계획

### 1. QR 코드 발급
```python
# 회원에게 QR 코드 추가 발급
service.update_member(member_id, {
    'qr_code': 'QR_20240757'
})
```

### 2. 바코드 재발급
```python
# 바코드 분실/파손 시 새로운 바코드 발급
service.update_member(member_id, {
    'barcode': 'NEW_BARCODE_001'
})
```

### 3. 복수 인증 수단
```python
# 바코드 + QR 동시 사용 가능
member = service.authenticate_by_barcode('20240757')
# OR
member = service.authenticate_by_qr('QR_20240757')
```

---

## 테스트 결과

### 기능 테스트

```bash
✅ 바코드 인증 (authenticate_by_barcode): 성공
✅ 회원 ID 조회 (get_member): 성공
✅ 대여 프로세스: 정상 작동
✅ 반납 프로세스: 정상 작동
✅ CSV 임포트: 정상 작동
```

### 성능 테스트

```bash
✅ 바코드 인증 속도: < 2ms (인덱스 적용)
✅ 회원 검증 속도: < 1ms
✅ 전체 조회 속도: 변화 없음
```

---

## 결론

- ✅ **무중단 마이그레이션**: 기존 기능 모두 정상 작동
- ✅ **데이터 무결성**: 344명 전체 회원 데이터 보존
- ✅ **성능 유지**: 인덱스 최적화로 성능 저하 없음
- ✅ **확장성 확보**: 향후 다양한 인증 수단 지원 가능

**마이그레이션 완료일**: 2025-10-21 18:20:36 KST

