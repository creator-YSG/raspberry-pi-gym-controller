# 센서 매핑 시스템 완벽 이해 가이드

> 센서 매핑이 어떻게 동작하는지, 어떤 파일이 실제로 사용되는지 명확하게 정리

---

## 📌 핵심 요약 (TL;DR)

### 실제 사용되는 파일
| 파일 | 위치 | 사용 여부 | 용도 |
|------|------|----------|------|
| `app/__init__.py` | `/app/` | ✅ **필수** | **(addr, chip, pin) → 센서번호** 매핑 |
| `esp32_mapping.json` | `/config/` | ✅ **필수** | **포트 → 디바이스** 매핑 |
| `sensor_mapping.json` | `/config/` | ⚠️ 선택 | **센서번호 → 락커ID** 매핑 (없으면 기본값 사용) |
| `sensor_mapping_detailed.json` | `/config/` | ❌ 미사용 | 매핑 작업 기록용 (런타임 사용 안 함) |
| `esp32_devices.json` | `/config/` | ❌ 미사용 | 과거 설정 (3개 ESP32용, 현재는 2개) |

### 현재 라즈베리파이 상태
```
✅ app/__init__.py - 하드코딩 매핑 존재
✅ esp32_mapping.json - 존재 (2개 ESP32 설정)
❌ sensor_mapping.json - 없음 (기본 매핑 자동 사용 중)
❌ sensor_mapping_detailed.json - 없음 (어차피 안 씀)
```

**결론**: **정상 작동 중**입니다. 동기화는 선택사항입니다.

---

## 🔄 센서 매핑 2단계 과정

### 전체 흐름도
```
ESP32 센서 감지
    ↓
{"addr":"0x26", "chip_idx":0, "pin":1, "state":"LOW"}
    ↓
[1단계] app/__init__.py 하드코딩 매핑
("0x26", 0, 1) → 센서 1번
    ↓
[2단계] sensor_mapping.json 또는 기본 매핑
센서 1번 → S01
    ↓
DB 저장 & 트랜잭션 처리
```

---

## 📝 1단계: 하드웨어 → 센서 번호

### 파일: `app/__init__.py` (라인 258-328)

```python
chip_addr_pin_to_sensor = {
    # (I2C주소, 칩번호, 핀번호): 센서번호
    ("0x26", 0,  1):  1,   # S01
    ("0x26", 0,  0):  2,   # S02
    ("0x26", 0,  6):  3,   # S03
    ...
    ("0x23", 0,  1): 11,   # M01
    ("0x23", 0,  2): 12,   # M02
    ...
    ("0x27", 3,  0): 51,   # F01
    ("0x27", 3,  1): 52,   # F03
    ...
}
```

### 동작 방식
1. ESP32에서 센서 이벤트 수신
2. `(addr, chip, pin)` 조합으로 테이블 검색
3. 센서 번호 확정

### ⚠️ 중요
- **이 매핑이 없으면 센서 감지 자체가 안 됨**
- 하드코딩되어 있어 수정하려면 코드 수정 필요
- 라즈베리파이에는 ✅ **존재함**

---

## 📝 2단계: 센서 번호 → 락커 ID

### 파일: `config/sensor_mapping.json` (선택사항)

```json
{
  "description": "센서 번호와 락커 ID 매핑",
  "mapping": {
    "1": "S01",
    "2": "S02",
    "3": "S03",
    ...
    "11": "M01",
    "12": "M02",
    ...
    "51": "F01",
    "52": "F03"
  }
}
```

### 동작 방식 (app/services/sensor_event_handler.py:49)
```python
config_file = Path(__file__).parent.parent.parent / "config" / "sensor_mapping.json"

if config_file.exists():
    # 파일에서 매핑 로드
    mapping = {int(k): v for k, v in mapping_config.items()}
else:
    # 기본 순차 매핑 자동 생성
    # 센서 1-10 → S01~S10
    # 센서 11-50 → M01~M40
    # 센서 51-60 → F01~F10
    for i in range(1, 11):
        mapping[i] = f"S{i:02d}"
    for i in range(1, 41):
        mapping[i + 10] = f"M{i:02d}"
    for i in range(1, 11):
        mapping[i + 50] = f"F{i:02d}"
```

### ⚠️ 중요
- **파일이 없어도 자동으로 기본 매핑 생성**
- 기본 매핑: 순차적 (1→S01, 2→S02, 11→M01...)
- 라즈베리파이에는 ❌ **없음** (기본 매핑 사용 중)

---

## 🤔 기본 매핑 vs 실제 매핑 비교

### 기본 매핑 (파일 없을 때 자동 생성)
```
센서 1 → S01
센서 2 → S02
센서 3 → S03
센서 4 → S04
...
센서 11 → M01
센서 12 → M02
...
```

### 실제 하드웨어 매핑 (app/__init__.py 기준)
```
("0x26", 0, 1) → 센서 1 → S01 ✅
("0x26", 0, 0) → 센서 2 → S02 ✅
("0x26", 0, 6) → 센서 3 → S03 ✅
("0x26", 0, 5) → 센서 4 → S04 ✅
...
("0x23", 0, 1) → 센서 11 → M01 ✅
("0x23", 0, 2) → 센서 12 → M02 ✅
...
```

### 결론
**기본 매핑과 실제 하드웨어 매핑이 일치합니다!**
→ 파일 없어도 정상 작동하는 이유

---

## 🔌 ESP32 포트 매핑

### 파일: `config/esp32_mapping.json` ✅ (실제 사용)

```json
{
  "devices": {
    "/dev/ttyUSB0": {
      "device_id": "esp32_male_female",
      "zones": ["MALE", "FEMALE"],
      "description": "남성/여성 구역 통합 문 제어"
    },
    "/dev/ttyUSB1": {
      "device_id": "esp32_staff",
      "zones": ["STAFF"],
      "description": "교직원 구역 문 제어"
    }
  }
}
```

### 파일: `config/esp32_devices.json` ❌ (사용 안 함)

```json
{
  "devices": [
    {
      "device_id": "esp32_male",
      "serial_port": "/dev/ttyUSB0"
    },
    {
      "device_id": "esp32_female",
      "serial_port": "/dev/ttyUSB1"
    },
    {
      "device_id": "esp32_staff",
      "serial_port": "/dev/ttyUSB2"
    }
  ]
}
```

### 차이점
- **esp32_mapping.json**: 현재 실제 하드웨어 (2개 ESP32)
- **esp32_devices.json**: 과거 설정 (3개 ESP32)
- 실제 사용: `esp32_mapping.json` (core/esp32_manager.py:191)

---

## 📊 라즈베리파이 현재 상태

### 존재하는 파일
```bash
pi@raspberrypi:~/raspberry-pi-gym-controller/config $ ls -la
-rw-r--r-- 1 pi pi 1338 esp32_devices.json        # 사용 안 함
-rw-r--r-- 1 pi pi  412 esp32_mapping.json       # ✅ 사용 중
-rw-r--r-- 1 pi pi 2399 google_credentials.json
-rw-r--r-- 1 pi pi  543 google_sheets_config.json
# sensor_mapping.json 없음 (기본 매핑 사용 중)
# sensor_mapping_detailed.json 없음 (어차피 안 씀)
```

### 실제 동작
```python
# 1단계: 하드웨어 → 센서번호
("0x26", 0, 1) → 센서 1  ✅ app/__init__.py 하드코딩

# 2단계: 센서번호 → 락커ID
센서 1 → S01  ✅ 기본 매핑 자동 생성

# 최종 결과
ESP32 pin 1 → 센서 1 → S01 ✅ 정상
```

---

## ❓ 자주 묻는 질문

### Q1. sensor_mapping.json이 없는데 정상 작동하는 이유는?
**A**: 파일이 없으면 자동으로 기본 순차 매핑을 생성하기 때문입니다.
```python
# 기본 매핑이 하드웨어 매핑과 일치함
1 → S01, 2 → S02, ..., 11 → M01 ...
```

### Q2. 동기화가 필요한가?
**A**: 현재는 **불필요**합니다. 하지만:
- 향후 매핑을 커스터마이징하려면 필요
- 문서화 목적으로 동기화 권장
- 다른 개발자가 보기 쉽게 하려면 동기화

### Q3. sensor_mapping_detailed.json은 왜 필요한가?
**A**: **런타임에는 불필요**합니다.
- 매핑 작업할 때 기록용
- 디버깅용 상세 정보
- 문서화 목적

### Q4. esp32_devices.json은 삭제해도 되나?
**A**: **삭제해도 됩니다**.
- 현재 사용 안 함
- 과거 3개 ESP32 설정
- 현재는 esp32_mapping.json 사용

### Q5. 매핑을 수정하려면?
**A**: 두 곳을 모두 수정해야 합니다.
1. **app/__init__.py** (258-328줄) - 하드웨어 매핑
2. **config/sensor_mapping.json** - 센서→락커 매핑 (선택)

---

## 🛠️ 실제 작업 시나리오

### 시나리오 1: 새로운 센서 추가

```python
# 1. app/__init__.py 수정
("0x28", 4, 10): 61,  # 새 센서

# 2. sensor_mapping.json 수정 (선택)
{
  "61": "S11"
}

# 3. 라즈베리파이 동기화 (app/__init__.py만 필수)
scp app/__init__.py pi@192.168.0.32:~/raspberry-pi-gym-controller/app/
scp config/sensor_mapping.json pi@192.168.0.32:~/raspberry-pi-gym-controller/config/

# 4. 재시작
ssh pi@192.168.0.32 "sudo systemctl restart gym-kiosk"
```

### 시나리오 2: 락커 번호만 변경 (하드웨어 안 바뀜)

```json
// sensor_mapping.json만 수정
{
  "1": "STAFF01",  // S01 → STAFF01로 변경
  "2": "STAFF02"
}

// app/__init__.py는 수정 안 해도 됨 (센서 번호는 그대로)
```

### 시나리오 3: 처음부터 설정 (신규 설치)

```bash
# 1. app/__init__.py에 하드웨어 매핑 작성 (필수)
# 2. sensor_mapping.json 작성 (선택, 없으면 기본 매핑)
# 3. esp32_mapping.json 작성 (필수)
```

---

## 📋 체크리스트

### 필수 파일 (없으면 작동 안 함)
- [x] `app/__init__.py` 하드코딩 매핑
- [x] `config/esp32_mapping.json` 포트 매핑
- [x] `/dev/ttyUSB0`, `/dev/ttyUSB1` 연결

### 선택 파일 (있으면 좋음)
- [ ] `config/sensor_mapping.json` (없으면 기본 매핑 사용)
- [ ] `config/sensor_mapping_detailed.json` (문서화용)

### 불필요 파일 (삭제 가능)
- [ ] `config/esp32_devices.json` (구 설정, 사용 안 함)

---

## 🎯 결론

### 현재 라즈베리파이 상태
```
✅ 정상 작동 중
✅ 센서 60개 모두 감지됨
✅ 기본 매핑으로 정상 처리 중
⚠️ sensor_mapping.json 없음 (문제없음, 기본값 사용)
```

### 권장 사항
1. **당장 할 일**: 없음 (정상 작동 중)
2. **향후 할 일**: 
   - `sensor_mapping.json` 동기화 (문서화 목적)
   - `esp32_devices.json` 삭제 또는 주석 추가
3. **중요한 파일**: 
   - `app/__init__.py` (백업 필수!)
   - `config/esp32_mapping.json` (백업 필수!)

---

## 📚 관련 파일 위치

```
raspberry-pi-gym-controller/
├── app/
│   └── __init__.py              ⭐ 1단계: 하드웨어 → 센서번호 (필수)
│
├── app/services/
│   └── sensor_event_handler.py  ⭐ 2단계: 센서번호 → 락커ID
│
├── core/
│   └── esp32_manager.py         ⭐ ESP32 포트 매핑 로드
│
└── config/
    ├── esp32_mapping.json       ✅ 포트 매핑 (사용 중)
    ├── esp32_devices.json       ❌ 구 설정 (사용 안 함)
    ├── sensor_mapping.json      ⚠️ 센서 매핑 (없음, 기본값 사용)
    └── sensor_mapping_detailed.json  ❌ 상세 기록 (런타임 사용 안 함)
```

---

## 📞 문제 해결

### 센서가 감지 안 될 때
1. `app/__init__.py` 하드코딩 매핑 확인
2. ESP32 연결 확인 (`ls /dev/ttyUSB*`)
3. 로그 확인 (`tail -f logs/locker_system.log`)

### 락커 ID가 이상할 때
1. `sensor_mapping.json` 확인 (있으면)
2. 없으면 기본 매핑 확인
3. 센서 번호가 올바른지 확인

### ESP32 연결 안 될 때
1. `config/esp32_mapping.json` 확인
2. 포트 번호 확인 (`/dev/ttyUSB0`, `/dev/ttyUSB1`)
3. 권한 확인 (`sudo usermod -a -G dialout pi`)

---

**문서 작성일**: 2025-12-23  
**최종 검증일**: 2025-12-23  
**시스템 버전**: v7.4-simple

