# 🎉 다중 Zone 락카 시스템 업데이트 완료

> **업데이트 일시**: 2025년 10월 10일  
> **버전**: v2.1.0  
> **상태**: ✅ 완료 및 테스트 통과

---

## 📊 변경 사항 요약

### **이전 시스템**
- 락카 개수: **48개** (A구역 24개 + B구역 24개)
- ESP32: **1개**
- Zone: A, B

### **새로운 시스템**
- 락카 개수: **140개** (남성 70개 + 여성 50개 + 교직원 20개)
- ESP32: **3개** (zone별 독립 제어)
- Zone: MALE, FEMALE, STAFF

---

## 🏗️ 락카 구성

| Zone | 락카 번호 | 개수 | ESP32 디바이스 | Serial Port |
|------|-----------|------|----------------|-------------|
| **남성 (MALE)** | M01 ~ M70 | 70개 | `esp32_male` | /dev/ttyUSB0 |
| **여성 (FEMALE)** | F01 ~ F50 | 50개 | `esp32_female` | /dev/ttyUSB1 |
| **교직원 (STAFF)** | S01 ~ S20 | 20개 | `esp32_staff` | /dev/ttyUSB2 |
| **총합** | - | **140개** | 3개 | - |

### 락카 크기 분포

**남성 구역 (70개)**
- M01~M50: medium 크기 (50개)
- M51~M70: large 크기 (20개)

**여성 구역 (50개)**
- F01~F30: medium 크기 (30개)
- F31~F50: large 크기 (20개)

**교직원 구역 (20개)**
- S01~S20: large 크기 (20개)

---

## 🔧 수정된 파일들

### 1. 데이터베이스 스키마
**파일**: `database/schema.sql`
- `locker_status` 테이블에 `device_id` 컬럼 추가
- zone 값 변경: A, B → MALE, FEMALE, STAFF
- 140개 락카 초기 데이터 추가

### 2. 모델 클래스
**파일**: `app/models/locker.py`
- `device_id` 필드 추가
- `to_dict()` 메서드 업데이트

### 3. 서비스 로직
**파일**: `app/services/locker_service.py`
- zone별 락카 조회 로직 강화
- device_id 기반 ESP32 매핑
- SQLite Row 객체 안전 처리

### 4. 설정 파일 (신규)
**파일**: `config/esp32_devices.json`
- 3개 ESP32 디바이스 설정
- zone별 매핑 정보
- serial_port, baudrate 설정

### 5. 문서 업데이트
- `README.md`: 프로젝트 개요 및 현황
- `docs/DATABASE_DESIGN.md`: 데이터베이스 설계
- `CHANGELOG.md`: 변경 이력 (신규)

---

## ✅ 테스트 결과

### Zone별 락카 개수
```
✅ MALE      :  70개 (예상: 70개)
✅ FEMALE    :  50개 (예상: 50개)
✅ STAFF     :  20개 (예상: 20개)
```

### device_id 매핑
```
✅ MALE      → esp32_male      (70개)
✅ FEMALE    → esp32_female    (50개)
✅ STAFF     → esp32_staff     (20개)
```

### 락카 번호 범위
```
✅ MALE      : M01 ~ M70 (70개)
✅ FEMALE    : F01 ~ F50 (50개)
✅ STAFF     : S01 ~ S20 (20개)
```

### 통합 테스트
```
✅ Zone별 락카 조회: 정상
✅ device_id 매핑: 정상
✅ 락카 속성 검증: 정상
✅ LockerService 기능: 정상
```

---

## 🚀 사용 방법

### Python 코드에서 사용

```python
from app.services.locker_service import LockerService

# LockerService 초기화
locker_service = LockerService('locker.db')

# 남성 락카 조회
male_lockers = locker_service.get_available_lockers('MALE')
print(f"사용 가능한 남성 락카: {len(male_lockers)}개")

# 여성 락카 조회
female_lockers = locker_service.get_available_lockers('FEMALE')
print(f"사용 가능한 여성 락카: {len(female_lockers)}개")

# 교직원 락카 조회
staff_lockers = locker_service.get_available_lockers('STAFF')
print(f"사용 가능한 교직원 락카: {len(staff_lockers)}개")

# 특정 락카 정보 확인
for locker in male_lockers[:3]:
    print(f"  {locker.id}: zone={locker.zone}, device={locker.device_id}, size={locker.size}")
```

### SQL 쿼리로 확인

```bash
# zone별 개수 확인
sqlite3 locker.db "SELECT zone, COUNT(*) FROM locker_status GROUP BY zone;"

# device_id별 개수 확인
sqlite3 locker.db "SELECT device_id, COUNT(*) FROM locker_status GROUP BY device_id;"

# 특정 zone 락카 목록
sqlite3 locker.db "SELECT locker_number, zone, device_id, size FROM locker_status WHERE zone='MALE' LIMIT 10;"
```

---

## 📁 백업 파일

기존 데이터베이스는 자동으로 백업되었습니다:
```
locker_backup_20251010_165325.db  (132KB)
```

혹시 이전 버전으로 돌아가야 한다면:
```bash
cp locker_backup_20251010_165325.db locker.db
```

---

## 🔄 다음 개선 사항 (선택사항)

1. **ESP32 자동 감지 개선**
   - 3개 ESP32를 자동으로 감지하고 zone에 매핑
   - `config/esp32_devices.json` 기반 동적 연결

2. **Zone별 권한 관리**
   - 회원 타입에 따라 접근 가능한 zone 제한
   - 교직원은 STAFF zone만, 일반 회원은 MALE/FEMALE만

3. **관리자 대시보드**
   - Zone별 락카 사용 현황 실시간 표시
   - 통계 및 리포트 기능

4. **동적 락카 설정**
   - 웹 UI에서 락카 추가/제거/이동
   - 센터별 맞춤 설정

---

## ❓ 문제 해결

### Q: 기존 대여 기록은 어떻게 되나요?
A: 기존 대여 기록은 백업 DB에 보존되어 있습니다. 필요시 migration 스크립트로 이전 가능합니다.

### Q: 락카 개수를 변경하려면?
A: `database/schema.sql` 파일의 INSERT 문을 수정한 후 `python3 scripts/init_database.py`로 재생성하면 됩니다.

### Q: ESP32가 3개보다 많으면?
A: `config/esp32_devices.json`에 추가하고, schema.sql에 해당 zone 락카들을 추가하면 됩니다.

### Q: zone 이름을 바꾸고 싶어요
A: schema.sql의 zone 값과 esp32_devices.json의 zone 값을 일치시켜 수정하면 됩니다.

---

## 📞 지원

문제가 발생하거나 추가 지원이 필요하시면:
1. `CHANGELOG.md` 참조
2. `docs/DATABASE_DESIGN.md` 참조
3. GitHub Issues 등록

---

**✅ 시스템이 정상 작동하며 즉시 사용 가능한 상태입니다!**

📝 **작성일**: 2025년 10월 10일  
🔖 **버전**: v2.1.0

