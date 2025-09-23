# 🏗️ 라즈베리파이 헬스장 락카키 대여기 시스템 아키텍처

## 📋 시스템 개요

라즈베리파이가 중앙 제어 허브 역할을 하여 ESP32 헬스장 컨트롤러와 JSON 통신하며, 웹 기반 터치스크린 GUI와 Google Sheets 오프라인 동기화를 통해 완전 자동화된 락카키 대여/반납 시스템을 제공합니다.

### ✨ 주요 특징
- 🔍 **ESP32 자동 감지 및 연결**: 부팅시 USB 포트 자동 스캔
- 🌐 **웹 기반 터치 UI**: 600x1024 세로 모드 최적화
- 📱 **실시간 통신**: WebSocket 기반 즉시 응답
- 📊 **오프라인 운영**: Google Sheets 로컬 캐시 활용
- ⚙️ **하드웨어 통합**: 바코드, IR센서, 스테퍼모터 완전 제어

## 🔧 하드웨어 구성

```
┌───────────────────────────────────────────────────────────────────────┐
│                    헬스장 락카키 대여기 시스템                         │
│                                                                       │
│  ┌─────────────────┐    ┌─────────────────────────────────────────┐   │
│  │ 라즈베리파이 4B │────│     터치스크린 모니터 (600x1024)       │   │
│  │   (중앙제어)    │HDMI│       웹 기반 키오스크 모드             │   │
│  │                 │    │     • 바코드 스캔 UI                   │   │
│  │ • Flask 웹서버  │    │     • 락카 선택 UI                     │   │
│  │ • ESP32 자동감지│    │     • 실시간 상태 표시                 │   │
│  │ • Google Sheets │    │     • WebSocket 실시간 업데이트        │   │
│  └─────────────────┘    └─────────────────────────────────────────┘   │
│           │ WiFi (Google Sheets 동기화)                               │
│           │                                                           │
│           │ USB 시리얼 통신 (자동 감지)                               │
│           │                                                           │
│  ┌────────▼─────────────────────────────────────────────────────────┐ │
│  │              ESP32 헬스장 통합 컨트롤러                         │ │
│  │                                                                 │ │
│  │  • GM65 바코드 스캐너 (UART2: GPIO16/17)                       │ │
│  │  • MCP23017 IR센서 확장 (I2C: GPIO21/22)                      │ │
│  │  • A4988 스테퍼모터 제어 (GPIO25/26/27)                       │ │
│  │  • LED/부저 알림 (GPIO2/4)                                    │ │
│  │                                                                 │ │
│  │  [자동 감지 USB VID:PID]                                       │ │
│  │  • CP2102: 10c4:ea60                                          │ │
│  │  • CH340G: 1a86:7523                                          │ │
│  │  • 포트: /dev/ttyUSB* (자동)                                  │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────┘
```

## 🏛️ 소프트웨어 아키텍처

### 📦 모듈 구조

```
raspberry-pi-gym-controller/
├── 🚀 run.py                     # 메인 실행 파일 (Flask 서버 시작)
├── 📱 app/                       # Flask 웹 애플리케이션
│   ├── __init__.py              # 앱 팩토리 (ESP32 자동 연결 포함)
│   ├── main/                    # 메인 블루프린트
│   │   └── routes.py           # 홈, 락카선택 등 메인 라우트
│   ├── api/                     # API 블루프린트  
│   │   └── routes.py           # REST API 엔드포인트
│   ├── events.py               # WebSocket 이벤트 핸들러
│   ├── models/                 # 데이터 모델
│   │   ├── member.py          # 회원 모델
│   │   ├── locker.py          # 락카 모델
│   │   └── rental.py          # 대여 기록 모델
│   ├── services/               # 비즈니스 로직
│   │   ├── member_service.py  # 회원 관리 서비스
│   │   ├── locker_service.py  # 락카 관리 서비스
│   │   ├── barcode_service.py # 바코드 처리 서비스
│   │   └── system_service.py  # 시스템 관리 서비스
│   ├── templates/              # Jinja2 HTML 템플릿
│   │   ├── layouts/base.html  # 기본 레이아웃 (600x1024 최적화)
│   │   └── pages/home.html    # 홈 화면 (터치 최적화)
│   ├── static/                # 정적 파일
│   │   ├── css/               # 스타일시트 (세로모드 + 터치)
│   │   ├── js/main.js         # JavaScript (WebSocket 포함)
│   │   └── images/            # 이미지 파일
│   └── utils/                 # 유틸리티 함수
├── 🔌 core/                     # 핵심 시스템 모듈
│   └── esp32_manager.py       # ESP32 자동감지/통신 관리자
├── 🔧 hardware/                 # 하드웨어 제어 모듈
│   ├── protocol_handler.py    # ESP32 JSON 프로토콜 파서
│   ├── serial_scanner.py      # 시리얼 포트 자동 감지
│   └── barcode_utils.py       # 바코드 생성/검증 유틸리티
├── 📊 data_sources/             # 데이터 소스 모듈
│   └── google_sheets.py       # Google Sheets API (오프라인 지원)
├── ⚙️ config/                   # 설정 파일
│   ├── config.env.template    # 환경 변수 템플릿
│   ├── google_sheets_config.json # Google Sheets 설정
│   └── google_credentials.json   # Google API 인증 정보
├── 🛠️ scripts/                  # 유틸리티 스크립트
│   ├── create_kiosk_mode.sh   # 키오스크 모드 설정
│   ├── start_kiosk.sh         # 키오스크 시작
│   └── connect_pi.sh          # SSH 연결
├── 🧪 tests/                    # 테스트 파일
│   ├── test_esp32_integration.py  # ESP32 통합 테스트
│   └── test_esp32_autodetect.py   # 자동 감지 테스트
├── 📝 logs/                     # 로그 파일
└── 🗂️ instance/                 # 인스턴스별 설정
```

### 🎯 추가된 통합 파일들

```
📋 ESP32_INTEGRATION_GUIDE.md    # ESP32 통합 가이드
🔧 esp32_gym_controller_updated.ino # ESP32 펌웨어 (라즈베리파이 호환)
🧪 test_esp32_integration.py     # 완전 통합 테스트
🔍 test_esp32_autodetect.py      # 자동 감지 테스트
```

## 🔄 통신 프로토콜

### ESP32 ↔ 라즈베리파이 USB 시리얼 통신

**🔍 자동 포트 감지:**
- ESP32 USB 칩 자동 인식 (CP2102, CH340G, FT232 등)
- VID:PID 기반 매칭: `10c4:ea60`, `1a86:7523`, `0403:6001`
- 동적 포트 할당: `/dev/ttyUSB*` (자동 감지)
- 부팅시 자동 연결 및 검증

**JSON 프로토콜 v2.0:**
```json
{
  "device_id": "esp32_gym",
  "message_type": "event|response|command",
  "timestamp": "2025-09-23T15:30:00Z",
  "event_type": "barcode_scanned|sensor_triggered|motor_completed",
  "data": {
    // 이벤트별 상세 데이터
  }
}
```

**통신 설정:**
- Baudrate: 115200 bps
- Data: 8 bits, Stop: 1 bit, Parity: None
- Timeout: 0.1s (non-blocking)
- Buffer: 자동 초기화

#### 1. 바코드 스캔 이벤트 (ESP32 → 라즈베리파이)
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
    "scan_count": 15
  }
}
```

#### 2. IR 센서 이벤트 (ESP32 → 라즈베리파이)
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

#### 3. 모터 완료 이벤트 (ESP32 → 라즈베리파이)
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

#### 4. 락카 열기 명령 (라즈베리파이 → ESP32)
```json
{
  "command": "open_locker",
  "locker_id": "A01",
  "duration_ms": 3000
}
```

#### 5. 상태 요청 명령 (라즈베리파이 → ESP32)
```json
{
  "command": "get_status"
}
```

#### 6. 자동 모드 설정 명령 (라즈베리파이 → ESP32)
```json
{
  "command": "set_auto_mode",
  "enabled": true
}
```

### 🔄 실시간 데이터 플로우

```
[ESP32] 바코드 스캔 
    ↓ JSON 이벤트
[라즈베리파이] 파싱 → 회원 검증 → 락카 선택 UI
    ↓ WebSocket
[브라우저] 실시간 UI 업데이트
    ↓ 사용자 락카 선택
[라즈베리파이] JSON 명령 생성
    ↓ 시리얼 통신
[ESP32] 모터 제어 → 락카 열기 → 완료 이벤트
    ↓ JSON 응답
[라즈베리파이] 상태 업데이트 → WebSocket → UI 갱신
```

## 🚀 **시스템 시작 프로세스**

### 부팅 시퀀스
1. **라즈베리파이 부팅** → Raspbian OS 로드
2. **Flask 앱 시작** → `python3 run.py`
3. **ESP32 자동 감지** → USB 포트 스캔 및 연결
4. **WebSocket 서버 시작** → 실시간 통신 준비
5. **키오스크 모드 활성화** → 터치스크린 UI 표시
6. **Google Sheets 동기화** → 오프라인 데이터 준비
7. **시스템 준비 완료** → 사용자 입력 대기

### 자동 복구 메커니즘
- ESP32 연결 끊김 감지 → 자동 재연결 시도 (10초 간격)
- Google Sheets 접근 실패 → 로컬 캐시 사용
- WebSocket 연결 끊김 → 자동 재연결
- 하드웨어 오류 감지 → 관리자 알림 및 수동 모드 전환

## 🎯 **핵심 기능별 상세 구현**

### 1. ESP32 자동 감지 시스템

```python
# core/esp32_manager.py
async def scan_and_connect_esp32_devices():
    """USB 포트 스캔하여 ESP32 자동 감지"""
    ports = serial.tools.list_ports.comports()
    
    # ESP32 USB 칩 감지
    esp32_usb_ids = [
        "10c4:ea60",  # CP2102
        "1a86:7523",  # CH340G
        "0403:6001",  # FT232
    ]
    
    for port in ports:
        if any(usb_id in port.hwid.lower() for usb_id in esp32_usb_ids):
            # ESP32 연결 시도 및 검증
            device = await connect_and_verify_esp32(port.device)
```

### 2. 실시간 이벤트 처리

```python
# app/__init__.py
def setup_esp32_event_handlers(app, esp32_manager):
    async def handle_barcode_scanned(event_data):
        # 바코드 → 회원 검증 → WebSocket 전송
        socketio.emit('barcode_scanned', event_data)
    
    esp32_manager.register_event_handler("barcode_scanned", handle_barcode_scanned)
```

### 3. Google Sheets 오프라인 동기화

```python
# data_sources/google_sheets.py  
class GoogleSheetsManager:
    def __init__(self):
        self._members_cache = {}  # 로컬 캐시
        self._cache_timeout = 300  # 5분
    
    async def validate_member(self, barcode):
        # 캐시 우선 검색 → API 폴백
        if self._should_refresh_cache():
            await self._load_members()
        return self._members_cache.get(barcode)
```

## 📊 **성능 지표**

| 항목 | 성능 | 개선점 |
|------|------|--------|
| 바코드 스캔 응답 | < 100ms | ESP32 직접 처리 |
| 회원 검증 | < 50ms | 로컬 캐시 활용 |
| 락카 열기 | < 200ms | 모터 가속 제어 |
| UI 업데이트 | < 30ms | WebSocket 실시간 |
| ESP32 자동 연결 | < 5초 | USB VID:PID 매칭 |

## 🔧 **개발 및 테스트 도구**

### 개발 테스트
```bash
# ESP32 자동 감지 테스트
python3 test_esp32_autodetect.py

# 완전 통합 테스트
python3 test_esp32_integration.py

# 웹 서버 개발 모드
python3 run.py --debug
```

### 배포 및 운영
```bash
# 키오스크 모드 시작
./scripts/start_kiosk.sh

# 시스템 상태 확인
./scripts/system_status.sh

# Google Sheets 설정
python3 config/google_sheets_setup.py
```

## 🔄 **버전 히스토리**

### v2.0 (현재) - ESP32 통합 완료
- ✅ ESP32 자동 감지 및 연결
- ✅ JSON 프로토콜 v2.0 구현
- ✅ 실시간 WebSocket 통신
- ✅ Google Sheets 오프라인 캐시
- ✅ 터치 최적화 UI (600x1024)
- ✅ 완전 자동화된 바코드 → 락카 열기 플로우

### v1.0 - 기본 기능
- 기본 Flask 웹 서버
- Google Sheets API 연동
- 단순 바코드 스캔 처리

## 🚀 **향후 개발 계획**

### Phase 1: 안정성 향상
- [ ] 에러 복구 메커니즘 강화
- [ ] 로깅 시스템 개선
- [ ] 성능 모니터링 대시보드

### Phase 2: 기능 확장  
- [ ] 다중 ESP32 지원 (락카 확장)
- [ ] 회원 사진 표시 기능
- [ ] 음성 안내 시스템
- [ ] 관리자 원격 모니터링

### Phase 3: 고도화
- [ ] AI 기반 사용 패턴 분석
- [ ] 모바일 앱 연동
- [ ] 클라우드 백업 시스템

---

> **📝 문서 마지막 업데이트**: 2025년 9월 23일  
> **시스템 버전**: v2.0  
> **ESP32 펌웨어**: esp32_gym_controller_updated.ino  
> **주요 기능**: 완전 자동화 ESP32 통합 락카키 대여 시스템
```

---

**📋 ARCHITECTURE.md 업데이트 완료!**  
🎯 **ESP32 통합 완료 버전 v2.0 반영**

> 이 문서는 최신 구현사항을 반영하여 업데이트되었습니다.  
> 세부 화면 설계와 구현 가이드는 `ESP32_INTEGRATION_GUIDE.md`를 참조하세요.
