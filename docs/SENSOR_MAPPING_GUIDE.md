# 센서 매핑 설정 가이드

> **⚠️ 주의**: 이 문서는 참고용입니다. 현재 센서 매핑은 `app/__init__.py`에 **하드코딩**되어 있으며,
> `config/sensor_mapping.json`은 UI 표시용으로만 사용됩니다.
> 
> **최종 검증일**: 2025-11-07 (전체 60개 센서)

## 📋 개요

센서 신호선이 물리적으로 규칙성 없이 연결되어 있어서, **addr(칩 주소) + chip_idx + pin 조합을 물리적으로 테스트하여 하드코딩**했습니다.

**예시**: S01번 락커는 addr=0x26, Chip0, Pin1에 연결됨

---

## 🎯 센서 매핑 작업 프로세스

### 준비물
- 라즈베리파이 SSH 접속
- 락커 키 (또는 센서를 건드릴 도구)
- 메모장 (센서 순서 기록용)

---

## 📝 작업 순서

### 1단계: 로그 모니터링 시작

**로컬 컴퓨터에서 실행:**

```bash
ssh raspberry-pi "tail -f ~/gym-controller/logs/locker_system.log | grep -E 'pin.*state.*LOW'"
```

이 명령어는 **센서가 감지될 때마다 실시간으로 로그를 표시**합니다.

**출력 예시:**
```
2025-11-05 18:53:55 ... "pin":1,"state":"LOW" ...
2025-11-05 18:53:56 ... "pin":0,"state":"LOW" ...
2025-11-05 18:53:57 ... "pin":6,"state":"LOW" ...
```

---

### 2단계: 순서대로 센서 건드리기

**중요**: 반드시 **순서대로** 진행하세요!

**교직원 구역 (10개):**
```
1. S01번 락커 키 빼기
2. S02번 락커 키 빼기
3. S03번 락커 키 빼기
...
10. S10번 락커 키 빼기
```

**남성 구역 (40개):**
```
11. M01번 락커 키 빼기
12. M02번 락커 키 빼기
...
50. M40번 락커 키 빼기
```

**여성 구역 (10개):**
```
51. F01번 락커 키 빼기
52. F02번 락커 키 빼기
...
60. F10번 락커 키 빼기
```

---

### 3단계: 로그에서 센서 정보 추출

로그에서 `"addr"`, `"chip_idx"`, `"pin"` 부분을 찾아서 기록합니다.

**❌ 공식을 사용하지 않음:**
```
센서 번호 = (chip_idx × 16) + pin + 1  # 작동하지 않음!
```

**✅ 하드코딩된 매핑 사용:**
```python
# app/__init__.py에 하드코딩됨
chip_addr_pin_to_sensor = {
    ("0x26", 0, 1): 1,   # S01 (addr로 구분)
    ("0x23", 0, 1): 11,  # M01 (같은 Chip0, Pin1이지만 addr가 다름!)
    # ... 전체 60개
}
```

---

### 4단계: 매핑 결과 확인

하드코딩된 매핑은 실제 물리적 테스트를 통해 검증되었습니다.

**실제 매핑 (교직원 구역 예시):**

| 순서 | 락커 ID | addr  | Chip | Pin | 센서 번호 |
|------|---------|-------|------|-----|-----------|
| 1    | S01     | 0x26  | 0    | 1   | 1         |
| 2    | S02     | 0x26  | 0    | 0   | 2         |
| 3    | S03     | 0x26  | 0    | 6   | 3         |
| 4    | S04     | 0x26  | 0    | 5   | 4         |
| 5    | S05     | 0x26  | 0    | 4   | 5         |
| 6    | S06     | 0x26  | 0    | 3   | 6         |
| 7    | S07     | 0x26  | 0    | 2   | 7         |
| 8    | S08     | 0x26  | 0    | 9   | 8         |
| 9    | S09     | 0x26  | 0    | 8   | 9         |
| 10   | S10     | 0x26  | 0    | 7   | 10        |

**중요**: 남성 M01-M10은 **같은 Chip0**를 사용하지만 **addr=0x23**으로 구분됩니다!

**매핑 결과 (config/sensor_mapping.json):**
```json
{
  "1": "S01",  // 센서 1번 → S01 락커 (addr=0x26, Chip0, Pin1)
  "2": "S02",  // 센서 2번 → S02 락커 (addr=0x26, Chip0, Pin0)
  "3": "S03",
  "4": "S04",
  "5": "S05",
  "6": "S06",
  "7": "S07",
  "8": "S08",
  "9": "S09",
  "10": "S10",
  "11": "M01", // 센서 11번 → M01 락커 (addr=0x23, Chip0, Pin1)
  "12": "M02",
  // ... (전체 60개)
}
```

---

### 5단계: 매핑 파일 수정

**파일 위치:**
```
config/sensor_mapping.json
```

**수정 방법:**

```bash
# 로컬에서 수정
nano config/sensor_mapping.json

# 또는
code config/sensor_mapping.json
```

**파일 형식:**
```json
{
  "description": "센서 번호와 락커 ID 매핑 (실제 물리적 연결 기준)",
  "note": "2025-11-05 실제 테스트 완료",
  "last_updated": "2025-11-05T18:54:00",
  "total_sensors": 60,
  "mapping": {
    "1": "S02",
    "2": "S01",
    "3": "S07",
    ...
    "60": "F10"
  }
}
```

---

### 6단계: 라즈베리파이에 동기화

```bash
# 매핑 파일 동기화
rsync -av config/sensor_mapping.json raspberry-pi:~/gym-controller/config/

# 키오스크 재시작
ssh raspberry-pi "cd ~/gym-controller && bash scripts/deployment/stop_kiosk.sh"
ssh raspberry-pi "cd ~/gym-controller && bash scripts/deployment/start_kiosk.sh > /dev/null 2>&1 &"
```

---

### 7단계: 테스트

각 락커에서 키를 빼고 **올바른 락커 번호가 시스템에 표시되는지** 확인합니다.

---

## 🔧 빠른 참조 명령어

### 로그 실시간 모니터링
```bash
ssh raspberry-pi "tail -f ~/gym-controller/logs/locker_system.log | grep -E 'pin.*state.*LOW'"
```

### 최근 센서 이벤트 확인 (타임스탬프 포함)
```bash
ssh raspberry-pi "tail -100 ~/gym-controller/logs/locker_system.log | grep -E 'pin.*state.*LOW' | tail -20"
```

### 특정 시간대 로그 확인
```bash
ssh raspberry-pi "grep '18:53:' ~/gym-controller/logs/locker_system.log | grep -E 'pin.*state.*LOW'"
```

---

## 📊 로그 형식 이해하기

**전체 로그 예시:**
```
2025-11-05 18:53:55,127 INFO: 🔥 [DEBUG] 센서 이벤트 핸들러 호출됨! event_data: {
  'device_id': 'esp32_gym',
  'timestamp': 1762336435.127697,
  'raw_message': '{"device_id":"esp32_gym","message_type":"event","timestamp":15784899,"version":"v7.4-simple","event_type":"sensor_triggered","data":{"chip_idx":0,"addr":"0x26","pin":1,"state":"LOW","active":true}}',
  'sensor_type': 'ir_sensor',
  'chip_idx': 0,
  'addr': '0x26',
  'pin': 1,           ← 이 숫자가 중요!
  'state': 'LOW',     ← LOW = 키 뺌
  'active': True
}
```

**핵심 정보:**
- `"pin": 1` → Pin 번호
- `"state": "LOW"` → 키를 뺀 상태
- `"chip_idx": 0` → 칩 번호 (대부분 0)

---

## 🛠️ 문제 해결

### 센서가 감지 안 됨
1. ESP32 연결 확인: `ssh raspberry-pi "ls /dev/ttyUSB*"`
2. 서버 실행 확인: `ssh raspberry-pi "ps aux | grep run.py"`
3. 로그 확인: `ssh raspberry-pi "tail -50 ~/gym-controller/logs/locker_system.log"`

### 중복된 센서 번호가 나옴
- 키를 빼고 다시 넣으면 같은 센서에서 LOW/HIGH 이벤트가 발생합니다
- **LOW 상태만** 기록하세요

### 순서가 꼬였을 때
- 처음부터 다시 시작하는 게 가장 안전합니다
- 매핑 파일 백업: `cp config/sensor_mapping.json config/sensor_mapping.json.backup`

---

## 📝 체크리스트

### 작업 전
- [ ] 라즈베리파이 SSH 접속 확인
- [ ] 서버 실행 중 확인
- [ ] 락커 키 준비
- [ ] 메모장 준비 (센서 번호 기록용)

### 작업 중
- [ ] 로그 모니터링 시작
- [ ] 순서대로 락커 키 빼기 (S01→S10, M01→M40, F01→F10)
- [ ] Pin 번호 기록
- [ ] 매핑 테이블 작성

### 작업 후
- [ ] `sensor_mapping.json` 파일 수정
- [ ] 라즈베리파이에 동기화
- [ ] 키오스크 재시작
- [ ] 각 락커 테스트
- [ ] 매핑 파일 백업

---

## 💡 팁

### 효율적인 작업 방법
1. **두 사람이 함께**: 한 명은 락커 키를 순서대로 빼고, 다른 한 명은 로그를 보면서 Pin 번호를 기록
2. **녹화**: 락커 건드리는 과정을 녹화해서 나중에 다시 확인
3. **구간별 작업**: 10개씩 끊어서 작업 (교직원 10개 → 확인 → 남성 40개 → 확인 → 여성 10개)

### 백업
```bash
# 작업 전 백업
cp config/sensor_mapping.json config/sensor_mapping.json.$(date +%Y%m%d_%H%M%S)

# 라즈베리파이 백업
ssh raspberry-pi "cp ~/gym-controller/config/sensor_mapping.json ~/gym-controller/config/sensor_mapping.json.backup"
```

---

## 📞 참고

- 센서 매핑은 **하드웨어 연결이 바뀌지 않는 한 한 번만** 하면 됩니다
- 매핑 파일은 **백업 필수**입니다
- 문제가 생기면 백업 파일로 복원: `mv config/sensor_mapping.json.backup config/sensor_mapping.json`

---

## 📂 관련 파일

```
config/
└── sensor_mapping.json          # 센서 매핑 설정 파일

app/services/
└── sensor_event_handler.py      # 센서 매핑을 읽어서 사용하는 코드

logs/
└── locker_system.log            # 센서 이벤트 로그
```

---

## 🔍 예제: 전체 작업 흐름

```bash
# 1. 로그 모니터링 시작 (터미널 1)
ssh raspberry-pi "tail -f ~/gym-controller/logs/locker_system.log | grep -E 'pin.*state.*LOW'"

# 2. 락커 순서대로 키 빼기
# (물리적으로 S01, S02, ... S10 순서대로)

# 3. 로그에서 Pin 번호 확인
# Pin 1, Pin 0, Pin 6, Pin 5, ... 기록

# 4. 매핑 파일 수정 (터미널 2)
nano config/sensor_mapping.json

# 5. 동기화
rsync -av config/sensor_mapping.json raspberry-pi:~/gym-controller/config/

# 6. 재시작
ssh raspberry-pi "cd ~/gym-controller && bash scripts/deployment/stop_kiosk.sh"
ssh raspberry-pi "cd ~/gym-controller && bash scripts/deployment/start_kiosk.sh > /dev/null 2>&1 &"

# 7. 테스트
# S01 락커 키 빼기 → 화면에 "S01" 표시되는지 확인
```

---

**작성일**: 2025-11-05  
**최종 수정**: 2025-11-05  
**작성자**: 락커 시스템 관리자

