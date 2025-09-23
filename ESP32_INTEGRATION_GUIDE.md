# 🔌 ESP32 + 라즈베리파이 통합 가이드

## 📋 개요

ESP32 헬스장 컨트롤러와 라즈베리파이가 완전히 호환되도록 프로토콜을 통합했습니다.

### ✅ 구현 완료된 기능들

1. **바코드 스캔 자동 처리**
   - ESP32에서 바코드 스캔 → 330도 회전 → 5초 후 역회전
   - 라즈베리파이에서 실시간 이벤트 수신 및 회원 검증

2. **JSON 프로토콜 완전 호환**
   - ESP32 → 라즈베리파이: 이벤트 전송
   - 라즈베리파이 → ESP32: JSON 명령 전송

3. **IR 센서 데이터 전송**
   - MCP23017 센서 변화를 실시간 전송
   - 락카 상태 모니터링 가능

4. **통합 모터 제어**
   - ESP32 자동 회전과 라즈베리파이 수동 제어 조화
   - 충돌 방지 메커니즘

## 🔧 설정 방법

### 1. ESP32 펌웨어 업로드

```bash
# Arduino IDE에서 esp32_gym_controller_updated.ino 업로드
# 또는 PlatformIO 사용
```

**주요 설정 확인:**
- 보드 선택: ESP32 Dev Module
- 시리얼 속도: 115200
- USB 포트: /dev/ttyUSB0 (라즈베리파이에서)

### 2. 라즈베리파이 환경 설정

```bash
# 프로젝트 디렉토리로 이동
cd /path/to/raspberry-pi-gym-controller

# 필요한 패키지 설치
pip install pyserial asyncio

# 시리얼 권한 설정
sudo usermod -a -G dialout $USER
sudo chmod 666 /dev/ttyUSB0
```

### 3. 연결 테스트

```bash
# 통합 테스트 실행
python3 test_esp32_integration.py
```

**예상 출력:**
```
🔧 ESP32 통합 테스트 시작
✅ ESP32 연결 성공
📊 상태 요청 전송
✅ 상태 요청 전송 성공
📊 시스템 상태: READY
  - 업타임: 45623ms
  - 스캔 횟수: 0
  - 모터 이동: 2
🔄 자동 모드 토글 테스트
🔓 락카 열기 명령 전송: A01
✅ 락카 열기 명령 전송 성공
⚙️ 모터 이벤트: rotate - completed
  → 모터 회전 완료, 락카 열림!
```

## 📡 통신 프로토콜

### ESP32 → 라즈베리파이 이벤트

#### 1. 바코드 스캔 이벤트
```json
{
  "device_id": "esp32_gym",
  "message_type": "event",
  "event_type": "barcode_scanned",
  "timestamp": "2025-09-23T15:30:00Z",
  "data": {
    "barcode": "1234567890123",
    "scan_type": "barcode",
    "format": "EAN13",
    "quality": 95,
    "scan_count": 5
  }
}
```

#### 2. IR 센서 이벤트
```json
{
  "device_id": "esp32_gym",
  "message_type": "event", 
  "event_type": "sensor_triggered",
  "timestamp": "2025-09-23T15:30:01Z",
  "data": {
    "chip_idx": 0,
    "addr": "0x20",
    "pin": 3,
    "raw": "HIGH",
    "active": true
  }
}
```

#### 3. 모터 완료 이벤트
```json
{
  "device_id": "esp32_gym",
  "message_type": "event",
  "event_type": "motor_completed", 
  "timestamp": "2025-09-23T15:30:05Z",
  "data": {
    "action": "rotate",
    "status": "completed",
    "enabled": true,
    "direction": 1,
    "busy": false,
    "details": {
      "degrees": 330.0,
      "direction": "forward",
      "trigger": "barcode_scan"
    }
  }
}
```

### 라즈베리파이 → ESP32 명령

#### 1. 락카 열기 명령
```json
{
  "command": "open_locker",
  "locker_id": "A01", 
  "duration_ms": 3000
}
```

#### 2. 상태 요청
```json
{
  "command": "get_status"
}
```

#### 3. 자동 모드 설정
```json
{
  "command": "set_auto_mode",
  "enabled": true
}
```

#### 4. 수동 모터 제어
```json
{
  "command": "motor_move",
  "revs": 0.9167,
  "rpm": 60.0,
  "accel": true
}
```

## 🔄 실제 사용 시나리오

### 시나리오 1: 기본 락카 대여

1. **사용자가 바코드 스캔**
   ```
   ESP32: 바코드 읽기 → 자동 330도 회전 → 라즈베리파이에 이벤트 전송
   ```

2. **라즈베리파이에서 회원 검증**
   ```python
   async def handle_barcode_event(event_data):
       barcode = event_data["barcode"]
       member = await validate_member(barcode)
       if member.is_valid:
           show_locker_selection_ui()
   ```

3. **락카 선택 후 열기**
   ```python
   # 사용자가 A01 선택
   await esp32_manager.send_command(
       device_id="esp32_gym",
       command="OPEN_LOCKER", 
       locker_id="A01"
   )
   ```

4. **ESP32에서 락카 열기**
   ```
   ESP32: JSON 명령 수신 → 모터 330도 회전 → 완료 이벤트 전송
   ```

### 시나리오 2: IR 센서 활용

```python
async def handle_sensor_event(event_data):
    chip = event_data["chip_idx"]
    pin = event_data["pin"] 
    active = event_data["active"]
    
    # 특정 센서가 활성화되면 락카 상태 업데이트
    if chip == 0 and pin == 5 and active:
        update_locker_status("A01", "door_opened")
```

## 🛠️ 트러블슈팅

### 문제 1: ESP32 연결 안됨
```bash
# 시리얼 포트 확인
ls -la /dev/ttyUSB*

# 권한 확인
sudo chmod 666 /dev/ttyUSB0

# ESP32 재부팅
# Reset 버튼 누르기
```

### 문제 2: JSON 파싱 에러
```bash
# 시리얼 모니터에서 직접 확인
screen /dev/ttyUSB0 115200

# 수동으로 명령 전송해보기
{"command":"get_status"}
```

### 문제 3: 모터가 안 돌아감
```bash
# ESP32에서 테스트 명령 실행
{"command":"test_motor"}

# 수동 모터 제어
{"command":"motor_move","revs":1.0,"rpm":30}
```

## 🎯 성능 최적화 팁

### 1. 시리얼 통신 최적화
```python
# ESP32Manager에서 버퍼 크기 조정
device.serial_connection = serial.Serial(
    port=device.serial_port,
    baudrate=115200,
    timeout=0.05,  # 더 빠른 응답
    write_timeout=0.5,
    rtscts=False,  # 흐름 제어 비활성화
)
```

### 2. 이벤트 처리 최적화
```python
# 비동기 이벤트 핸들러
async def handle_barcode_event(event_data):
    # CPU 집약적 작업은 별도 스레드에서
    await asyncio.create_task(process_barcode_async(event_data))
```

### 3. 메모리 사용량 모니터링
```python
# ESP32 메모리 상태 주기적 체크
if event_data.get("free_heap", 0) < 10000:
    logger.warning("ESP32 메모리 부족!")
```

## 📊 모니터링 및 로깅

### 실시간 상태 확인
```python
# 상태 요청 주기적 전송
async def periodic_status_check():
    while True:
        await esp32_manager.send_command("esp32_gym", "GET_STATUS") 
        await asyncio.sleep(30)
```

### 로그 설정
```python
import logging

# 상세 로깅 활성화
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('esp32_integration.log'),
        logging.StreamHandler()
    ]
)
```

## ✅ 검증 체크리스트

- [ ] ESP32 펌웨어 업로드 완료
- [ ] 시리얼 연결 및 권한 설정
- [ ] 테스트 스크립트 실행 성공
- [ ] 바코드 스캔 → 이벤트 수신 확인
- [ ] 락카 열기 명령 → 모터 동작 확인
- [ ] IR 센서 → 이벤트 수신 확인
- [ ] 자동 모드 토글 동작 확인
- [ ] 에러 핸들링 정상 동작

## 🚀 다음 단계

1. **구글 시트 오프라인 기능 통합**
2. **웹 UI에서 실시간 ESP32 상태 표시**
3. **WebSocket을 통한 브라우저 실시간 업데이트**
4. **락카 상태 LED 표시 기능**
5. **사운드 알림 시스템 통합**

완료! 🎉
