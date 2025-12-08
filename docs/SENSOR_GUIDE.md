# 센서 가이드

> 센서 매핑, 이벤트 처리, 테스트 시뮬레이션

## 개요

- **총 센서**: 60개
- **구역**: 교직원(S01-S10), 남성(M01-M40), 여성(F01-F10)
- **매핑 방식**: `app/__init__.py`에 하드코딩 (addr + chip + pin 조합)

---

## 센서 상태

| 상태 | 의미 | 설명 |
|------|------|------|
| `HIGH` | 키 없음 | 키를 뽑음 → 대여 |
| `LOW` | 키 있음 | 키를 꽂음 → 반납 |

---

## 센서 매핑

### 센서 번호 할당

| 센서 번호 | 락커 | 구역 |
|-----------|------|------|
| 1-10 | S01-S10 | 교직원 |
| 11-50 | M01-M40 | 남성 |
| 51-60 | F01-F10 | 여성 |

### 하드코딩 매핑 (app/__init__.py)

```python
chip_addr_pin_to_sensor = {
    # addr=0x26, Chip0 → 교직원 (S01-S10)
    ("0x26", 0, 1): 1,   # S01
    ("0x26", 0, 0): 2,   # S02
    # ...
    
    # addr=0x23, Chip0 → 남성 (M01-M10)
    ("0x23", 0, 1): 11,  # M01
    ("0x23", 0, 2): 12,  # M02
    # ...
    
    # addr=0x25, Chip1 → 남성 (M11-M20)
    ("0x25", 1, 0): 21,  # M11
    # ...
}
```

> **중요**: 같은 Chip0, Pin1이어도 addr가 다르면 다른 센서!
> - addr=0x26 + Chip0 + Pin1 → S01
> - addr=0x23 + Chip0 + Pin1 → M01

### 설정 파일

- `config/sensor_mapping.json`: 센서 번호 → 락커 ID 매핑 (UI 표시용)
- `app/__init__.py`: addr+chip+pin → 센서 번호 (실제 처리용)

---

## 센서 시뮬레이션 (테스트용)

### API: `/api/test/inject-sensor`

실제 하드웨어 없이 센서 이벤트를 테스트할 때 사용합니다.

```bash
curl -X POST http://localhost:5000/api/test/inject-sensor \
  -H 'Content-Type: application/json' \
  -d '{"sensor_num": 11, "state": "HIGH"}'
```

| 파라미터 | 설명 |
|---------|------|
| `sensor_num` | 센서 번호 (1-60) |
| `state` | `"HIGH"` (키 뽑음) / `"LOW"` (키 꽂음) |

### 대여 테스트

```bash
# 1. 바코드 주입
export DISPLAY=:0
xdotool type '20240673' && xdotool key Return

# 2. 4초 대기
sleep 4

# 3. 센서 주입 (HIGH = 대여)
curl -X POST http://localhost:5000/api/test/inject-sensor \
  -H 'Content-Type: application/json' \
  -d '{"sensor_num": 11, "state": "HIGH"}'
```

### 반납 테스트

```bash
# 1. 바코드 주입
xdotool type '20240673' && xdotool key Return

# 2. 4초 대기
sleep 4

# 3. 센서 주입 (LOW = 반납)
curl -X POST http://localhost:5000/api/test/inject-sensor \
  -H 'Content-Type: application/json' \
  -d '{"sensor_num": 11, "state": "LOW"}'
```

---

## 이벤트 처리 흐름

```
ESP32 센서 감지
    ↓
ESP32Manager (비동기)
    ↓
handle_sensor_triggered()
    ↓
addr+chip+pin → 센서 번호 매핑
    ↓
with app.app_context():
    add_sensor_event()
    ↓
recent_sensor_events (API용)
sensor_queue (폴링용)
```

### 핵심 코드 (app/__init__.py)

```python
async def handle_sensor_triggered(event_data):
    # 센서 번호 매핑
    sensor_num = chip_addr_pin_to_sensor.get((addr, chip_idx, pin))
    
    if sensor_num:
        # 반드시 Flask 컨텍스트 내에서 실행!
        with app.app_context():
            add_sensor_event(sensor_num, raw_state)
        
        # 센서 큐에도 저장 (폴링용)
        sensor_queue.put_nowait(sensor_data)
```

> **주의**: `with app.app_context()` 없이 호출하면 이벤트가 저장되지 않습니다!

---

## DB 관련 참고사항

### active_transactions 테이블

`active_transactions` 테이블은 **타임아웃 추적용**입니다.

실제 대여/반납 처리는 **`rentals` 테이블만 사용**합니다:
- 대여: `rentals`에서 `status='pending'` 레코드 → `status='active'` 업데이트
- 반납: `rentals`에서 `status='active'` 레코드 → `status='returned'` 업데이트

---

## 로그 모니터링

### 실시간 센서 로그

```bash
ssh raspberry-pi "tail -f ~/gym-controller/logs/locker_system.log | grep -E 'pin.*state.*LOW'"
```

### 예상 로그 출력

```
2025-11-07 17:15:30 INFO: 🔥 [DEBUG] 센서 이벤트 핸들러 호출됨!
2025-11-07 17:15:30 INFO: 📡 센서: Chip0 Pin1 = LOW (ACTIVE)
2025-11-07 17:15:30 INFO: 🔥 [DEBUG] 핀 1 -> 센서 2 매핑
2025-11-07 17:15:30 INFO: 📦 센서 큐에 저장: 센서2, 상태LOW
```

---

## 트러블슈팅

### 센서 감지가 안 됨

1. ESP32 연결 확인: `ls /dev/ttyUSB*`
2. 서버 실행 확인: `ps aux | grep run.py`
3. 로그 확인: `tail -50 ~/gym-controller/logs/locker_system.log`

### API가 이벤트 0개 반환

`app/__init__.py`에서 `with app.app_context():` 확인:

```python
# 올바른 방식
with app.app_context():
    add_sensor_event(sensor_num, raw_state)
```

### 락커 ID가 null

`config/sensor_mapping.json` 파일 확인:

```bash
cat ~/gym-controller/config/sensor_mapping.json
```

---

## 관련 파일

| 파일 | 설명 |
|------|------|
| `app/__init__.py` | 센서 이벤트 핸들러, 하드코딩 매핑 |
| `app/api/routes.py` | add_sensor_event 함수, API 엔드포인트 |
| `config/sensor_mapping.json` | 센서 번호 → 락커 ID 매핑 |

---

## 센서 매핑 재작업 시

### 작업 순서

1. 로그 모니터링 시작
2. S01 → S10 순서로 키 빼기
3. M01 → M40 순서로 키 빼기
4. F01 → F10 순서로 키 빼기
5. 로그에서 addr/chip/pin 기록
6. `app/__init__.py` 매핑 테이블 수정
7. `config/sensor_mapping.json` 수정
8. 테스트

### 로그 모니터링 명령

```bash
ssh raspberry-pi "tail -f ~/gym-controller/logs/locker_system.log | grep -E 'pin.*state.*LOW'"
```

