# 🏗️ 라즈베리파이 락카키 대여기 시스템 아키텍처

## 📋 시스템 개요

라즈베리파이가 중앙 제어 허브 역할을 하여 3개의 ESP32와 JSON 통신하며, 터치스크린 GUI와 외부 데이터 소스를 관리하는 통합 락카키 대여 시스템

## 🔧 하드웨어 구성

```
┌─────────────────────────────────────────────────────────────┐
│                    락카키 대여기 박스                          │
│  ┌─────────────────┐    ┌─────────────────────────────────┐  │
│  │ 라즈베리파이 4B │────│       터치스크린 모니터         │  │
│  │   (중앙제어)    │HDMI│        (사용자 인터페이스)       │  │
│  └─────────────────┘    └─────────────────────────────────┘  │
│           │ WiFi (구글시트 접근)                              │
│           │                                                  │
│           │ USB 시리얼 통신                                   │
│           ├─────────────────────────────────────────────────┐  │
│           │                                                 │  │
│  ┌────────▼─────┐  ┌────────────────┐  ┌────────────────┐  │  │
│  │   ESP32 #1   │  │   ESP32 #2     │  │   ESP32 #3     │  │  │
│  │ 바코드스캐너 │  │  모터제어#1    │  │  모터제어#2    │  │  │
│  │    릴레이    │  │     센서       │  │     센서       │  │  │
│  │  /dev/ttyUSB0│  │  /dev/ttyUSB1  │  │  /dev/ttyUSB2  │  │  │
│  └──────────────┘  └────────────────┘  └────────────────┘  │  │
└─────────────────────────────────────────────────────────────┘
```

## 🏛️ 소프트웨어 아키텍처

### 📦 모듈 구조

```
raspberry-pi-gym-controller/
├── core/                     # 핵심 시스템 모듈
│   └── esp32_manager.py     # ESP32 시리얼 통신 관리자
├── hardware/                 # 하드웨어 제어 모듈 (기존 ESP32 프로토콜)
│   ├── protocol_handler.py  # ESP32 메시지 파싱
│   ├── serial_scanner.py    # 시리얼 바코드 스캐너
│   └── barcode_utils.py     # 바코드 유틸리티
├── data_sources/             # 데이터 소스 모듈
│   └── google_sheets.py     # 구글시트 API (WiFi)
├── gui/                      # 터치스크린 GUI
│   ├── main_controller.py   # GUI 메인 컨트롤러
│   ├── screens/             # 화면별 컴포넌트
│   └── widgets/             # 재사용 위젯
├── services/                 # 비즈니스 로직 서비스
│   ├── locker_service.py    # 락카 대여/반납 로직
│   └── member_service.py    # 회원 관리 로직
├── config/                   # 설정 파일
├── scripts/                  # 유틸리티 스크립트
├── tests/                    # 테스트
└── main.py                   # 메인 애플리케이션
```

## 🔄 통신 프로토콜

### ESP32 ↔ 라즈베리파이 USB 시리얼 통신

**시리얼 포트 구성:**
- `/dev/ttyUSB0` : ESP32 #1 (바코드 스캐너)
- `/dev/ttyUSB1` : ESP32 #2 (모터 제어 #1) 
- `/dev/ttyUSB2` : ESP32 #3 (모터 제어 #2)

**JSON 메시지 형식:**
```json
{
  "device_id": "esp32_barcode",
  "message_type": "command|response|event|status", 
  "timestamp": "2025-09-18T21:30:00Z",
  "data": {
    // 메시지별 데이터 구조
  }
}
```

**시리얼 통신 설정:**
- Baudrate: 115200
- Data bits: 8
- Stop bits: 1
- Parity: None
- Flow control: None

#### 1. 바코드 스캔 이벤트 (ESP32 → 라즈베리파이)
```json
{
  "device_id": "esp32_barcode",
  "message_type": "event",
  "event_type": "barcode_scanned",
  "timestamp": "2025-09-18T21:30:00Z",
  "data": {
    "barcode": "1234567890123",
    "scan_type": "barcode|qr_code",
    "quality": 95
  }
}
```

#### 2. 모터 제어 명령 (라즈베리파이 → ESP32)
```json
{
  "device_id": "esp32_motor_01",
  "message_type": "command",
  "command": "open_locker",
  "timestamp": "2025-09-18T21:30:00Z",
  "data": {
    "locker_id": "A001",
    "duration_ms": 3000,
    "confirm_required": true
  }
}
```

#### 3. 상태 응답 (ESP32 → 라즈베리파이)
```json
{
  "device_id": "esp32_motor_01",
  "message_type": "response",
  "timestamp": "2025-09-18T21:30:00Z",
  "data": {
    "status": "success|error|busy",
    "locker_id": "A001",
    "action_completed": true,
    "error_message": null
  }
}
```

## 🎯 데이터 플로우

### 1. 락카키 대여 프로세스
```
1. 사용자 바코드 스캔 
   ├─► ESP32(바코드) → JSON → 라즈베리파이
   └─► 라즈베리파이: 회원 유효성 검증 (구글시트/로컬DB)

2. 유효 회원 확인 시
   ├─► GUI: 락카 선택 화면 표시
   ├─► 사용자: 터치스크린으로 락카 선택
   └─► 라즈베리파이 → JSON → ESP32(모터): 락카 열기

3. 대여 완료
   ├─► 데이터 기록 (구글시트/로컬DB)
   ├─► GUI: 완료 메시지 표시
   └─► 감사 로그 저장
```

### 2. 락카키 반납 프로세스
```
1. 락카키 바코드 스캔
   ├─► ESP32(바코드) → JSON → 라즈베리파이
   └─► 라즈베리파이: 대여 기록 확인

2. 유효한 락카키 확인 시
   ├─► 라즈베리파이 → JSON → ESP32(모터): 해당 락카 열기
   └─► 대여 기록 업데이트 (반납 처리)

3. 반납 완료
   ├─► GUI: 반납 완료 메시지
   └─► 감사 로그 저장
```

## 🔧 핵심 컴포넌트 설계

### 1. ESP32Manager (core/esp32_manager.py)
```python
class ESP32Manager:
    """ESP32 디바이스들과의 통신을 총괄 관리"""
    
    def __init__(self):
        self.devices = {
            "barcode_scanner": ESP32Device("esp32_barcode", "192.168.0.101"),
            "motor_controller_1": ESP32Device("esp32_motor_01", "192.168.0.102"), 
            "motor_controller_2": ESP32Device("esp32_motor_02", "192.168.0.103")
        }
    
    async def send_command(self, device_id: str, command: dict) -> dict
    async def broadcast_status_request(self) -> dict
    def register_event_handler(self, event_type: str, handler: callable)
```

### 2. DataManager (core/data_manager.py)
```python
class DataManager:
    """구글시트, 로컬DB 등 모든 데이터 소스 관리"""
    
    async def validate_member(self, barcode: str) -> MemberInfo
    async def get_available_lockers(self) -> List[LockerInfo]
    async def record_rental(self, member_id: str, locker_id: str) -> bool
    async def process_return(self, locker_key_barcode: str) -> bool
```

### 3. GUIController (gui/main_controller.py) 
```python
class GUIController:
    """터치스크린 GUI 메인 컨트롤러"""
    
    def __init__(self, esp32_manager: ESP32Manager, data_manager: DataManager):
        self.screens = {
            "home": HomeScreen(),
            "scan": ScanScreen(), 
            "locker_select": LockerSelectScreen(),
            "admin": AdminScreen()
        }
    
    def show_screen(self, screen_name: str, **kwargs)
    def handle_barcode_event(self, barcode_data: dict)
    def handle_locker_selection(self, locker_id: str)
```

## 🛡️ 오류 처리 및 복구

### 1. ESP32 연결 실패
- 자동 재연결 시도 (최대 3회)
- 대체 디바이스로 fallback
- 사용자에게 상태 알림

### 2. 네트워크 연결 실패  
- 로컬 캐시된 회원 데이터 사용
- 연결 복구 시 동기화
- 오프라인 모드 전환

### 3. 모터 제어 실패
- 수동 개입 알림
- 관리자 화면에서 수동 제어
- 물리적 백업 키 사용 안내

## 📊 모니터링 및 로깅

### 1. 실시간 상태 모니터링
- ESP32 디바이스 상태
- 네트워크 연결 상태  
- 시스템 리소스 사용량
- 락카 사용 현황

### 2. 감사 로그
- 모든 대여/반납 기록
- 시스템 오류 로그
- 사용자 액션 로그
- 관리자 접근 로그

## 🔧 설정 관리

### device_config.json
```json
{
  "esp32_devices": {
    "barcode_scanner": {
      "device_id": "esp32_barcode",
      "serial_port": "/dev/ttyUSB0",
      "baudrate": 115200,
      "type": "barcode_scanner"
    },
    "motor_controller_1": {
      "device_id": "esp32_motor_01", 
      "serial_port": "/dev/ttyUSB1",
      "baudrate": 115200,
      "type": "motor_controller",
      "managed_lockers": ["A001", "A002", "A003"]
    },
    "motor_controller_2": {
      "device_id": "esp32_motor_02", 
      "serial_port": "/dev/ttyUSB2",
      "baudrate": 115200,
      "type": "motor_controller",
      "managed_lockers": ["A004", "A005", "A006"]
    }
  },
  "data_sources": {
    "google_sheets": {
      "enabled": true,
      "sheet_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
      "credentials_file": "credentials.json"
    },
    "local_database": {
      "enabled": true,
      "db_path": "data/locker_system.db"
    }
  }
}
```

이 아키텍처는 확장 가능하고 유지보수가 용이하며, ESP32들과의 JSON 통신을 통해 안정적인 락카키 대여 시스템을 구현할 수 있습니다.
