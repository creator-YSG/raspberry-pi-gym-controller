# ESP32 펌웨어 관리

이 디렉토리에는 헬스장 락커 시스템용 ESP32 펌웨어가 포함되어 있습니다.

## 📁 펌웨어 버전

### 현재 사용 중 (권장)
- **`esp32_gym_controller_v7.4_simple.ino`** ⭐ **현재 업로드됨**
  - WiFi/OTA 제거로 안정성 향상
  - 시리얼 통신만 사용 (USB 케이블)
  - 플러그앤플레이 방식
  - 라즈베리파이와 100% 호환

### 이전 버전 (참고용)
- **`esp32_gym_controller_updated.ino`**
  - WiFi/OTA 지원 버전 (v7.1)
  - 무선 업데이트 가능
  - 네트워크 설정 필요

## 🔧 하드웨어 연결

### 핀 배치
```
ESP32 핀 배치:
├── 바코드 스캐너 (UART2)
│   ├── RX2: GPIO 16
│   └── TX2: GPIO 17
├── I2C (MCP23017)
│   ├── SDA: GPIO 21
│   └── SCL: GPIO 22
├── 스테퍼 모터 (TB6600)
│   ├── STEP: GPIO 25
│   ├── DIR:  GPIO 26
│   └── EN:   GPIO 27
└── 표시등
    ├── LED:    GPIO 2
    └── BUZZER: GPIO 4
```

### MCP23017 IR 센서
- **I2C 주소**: 0x20 ~ 0x27 (최대 8개)
- **센서 수**: 최대 128개 (16핀 × 8칩)
- **디바운싱**: 15ms

## 📡 통신 프로토콜

### 라즈베리파이 → ESP32 (명령)
```json
// 상태 요청
{"command": "get_status"}

// 락커 열기 (330도 회전)
{"command": "open_locker", "locker_id": "M01"}

// 모터 직접 제어
{"command": "motor_move", "revs": 0.5, "rpm": 60}

// 테스트
{"command": "test"}
```

### ESP32 → 라즈베리파이 (이벤트)
```json
// 바코드 스캔
{
  "device_id": "esp32_gym",
  "message_type": "event",
  "event_type": "barcode_scanned",
  "data": {"barcode": "1234567890", "scan_count": 5}
}

// 상태 응답
{
  "device_id": "esp32_gym", 
  "message_type": "response",
  "data": {
    "status": "ready",
    "uptime": 60000,
    "motor_busy": false,
    "mcp_count": 2,
    "total_scans": 10,
    "microstep": 2,
    "steps_per_rev": 400
  }
}

// 락커 열기 완료
{
  "device_id": "esp32_gym",
  "message_type": "response", 
  "event_type": "locker_opened",
  "data": {"status": "opened"}
}
```

## ⚙️ 모터 설정

### 스테퍼 모터 사양
- **기본 스텝**: 200 스텝/회전 (1.8도/스텝)
- **마이크로스텝**: 1/2 (2배 세분화)
- **실제 스텝**: 400 스텝/회전
- **락커 열기**: 0.917회전 (330도 = 367스텝)

### 타이밍
- **펄스 간격**: 1000μs (HIGH) + 1000μs (LOW)
- **방향 설정 지연**: 10ms
- **RPM**: 기본 30RPM

## 🚀 업로드 방법

### Arduino IDE
1. ESP32 보드 패키지 설치
2. 라이브러리 설치:
   - `Adafruit MCP23017`
   - `ArduinoJson`
3. 보드 선택: ESP32 Dev Module
4. 포트 선택 후 업로드

### PlatformIO
```ini
[env:esp32dev]
platform = espressif32
board = esp32dev
framework = arduino
lib_deps = 
    adafruit/Adafruit MCP23017 Arduino Library
    bblanchon/ArduinoJson
```

## 🔍 디버깅

### 시리얼 모니터
- **Baud Rate**: 115200
- **바코드 스캐너**: 9600 (UART2)

### 상태 확인
```
// 시리얼 모니터에서 입력
status        // 현재 상태 조회
test          // LED/부저 테스트
```

## 📊 호환성

### 라즈베리파이 시스템
- ✅ **메시지 파싱**: 100% 호환
- ✅ **명령어 처리**: 100% 호환  
- ✅ **바코드 스캔**: 완벽 연동
- ✅ **락커 제어**: 완벽 연동
- ✅ **센서 감지**: 완벽 연동

### 버전별 특징
| 기능 | v7.1 (WiFi) | v7.4-simple | 권장 |
|------|-------------|-------------|------|
| 안정성 | ⚠️ WiFi 의존 | ✅ 독립적 | **v7.4** |
| 설정 | ⚠️ WiFi 필요 | ✅ 플러그앤플레이 | **v7.4** |
| 업데이트 | ✅ 무선 OTA | ⚠️ USB 케이블 | v7.1 |

---

**현재 사용 중**: ESP32 v7.4-simple (안정성 우선)  
**업데이트 날짜**: 2025년 10월 13일  
**상태**: 라즈베리파이 시스템과 100% 호환 확인
