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
├── web/                      # 웹 기반 GUI (Flask + HTML/CSS/JS)
│   ├── app.py               # Flask 웹 서버
│   ├── routes/              # 웹 API 라우트
│   │   ├── main.py          # 메인 페이지 라우트
│   │   ├── api.py           # REST API 엔드포인트
│   │   └── websocket.py     # WebSocket 실시간 통신
│   ├── templates/           # HTML 템플릿 (Jinja2)
│   │   ├── base.html        # 기본 레이아웃
│   │   ├── home.html        # 홈 화면
│   │   ├── member_check.html # 회원 확인 화면
│   │   ├── locker_select.html # 락카 선택 화면
│   │   ├── rental_complete.html # 대여 완료 화면
│   │   └── admin.html       # 관리자 화면
│   ├── static/              # 정적 파일
│   │   ├── css/             # 스타일시트
│   │   │   ├── main.css     # 메인 스타일
│   │   │   └── touch.css    # 터치 최적화 스타일
│   │   ├── js/              # JavaScript
│   │   │   ├── main.js      # 메인 로직
│   │   │   ├── websocket.js # WebSocket 클라이언트
│   │   │   └── touch.js     # 터치 이벤트 처리
│   │   └── images/          # 이미지 파일
│   └── services/            # 웹 서비스 로직
│       ├── locker_service.py # 락카 대여/반납 로직
│       └── member_service.py # 회원 관리 로직
├── config/                   # 설정 파일
├── scripts/                  # 유틸리티 스크립트
├── tests/                    # 테스트
└── main.py                   # 메인 애플리케이션 (Flask 서버 실행)
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

## 🌐 **웹 기반 UI 아키텍처**

## 📱 **화면 구성 및 사용자 시나리오**

### 🎭 **사용자 시나리오 상세 분석**

#### 시나리오 1: 락카키 대여 (신규 사용자)
```
1️⃣ 헬스장 도착
   사용자: "락카키를 빌려야지"
   
2️⃣ 홈 화면 확인  
   화면: "회원 바코드를 스캔해주세요"
   사용자: 회원카드 바코드 스캔
   
3️⃣ 회원 확인
   시스템: 구글시트에서 회원 정보 조회
   화면: "안녕하세요, 홍길동님!"
   
4️⃣ 락카 선택
   화면: 사용 가능한 락카들 그리드 표시
   사용자: 원하는 락카 터치 선택
   
5️⃣ 대여 완료
   시스템: 해당 락카 자동으로 열림
   화면: "A-05번 락카가 열렸습니다"
   사용자: 물건 넣고 락카 닫음
```

#### 시나리오 2: 락카키 반납
```
1️⃣ 운동 완료 후
   사용자: "락카키를 반납해야지"
   
2️⃣ 홈 화면에서 락카키 바코드 스캔
   사용자: 락카키에 붙은 바코드 스캔
   
3️⃣ 반납 처리
   시스템: 대여 기록 확인 후 해당 락카 열기
   화면: "A-05번 락카가 열렸습니다. 물건을 가져가세요"
   
4️⃣ 반납 완료
   사용자: 물건 가져간 후 락카키 반납함에 넣음
   화면: "반납이 완료되었습니다"
```

#### 시나리오 3: 오류 상황들
```
❌ 회원 정보 없음
   → "등록되지 않은 회원입니다. 프론트에 문의하세요"
   
❌ 사용 가능한 락카 없음  
   → "현재 사용 가능한 락카가 없습니다"
   
❌ 락카키 대여 기록 없음
   → "대여 기록이 없는 락카키입니다"
   
❌ ESP32 연결 실패
   → "시스템 오류입니다. 관리자에게 문의하세요"
```

### 🖥️ **상세 화면 설계 (1024×600)**

#### 🏠 홈 화면 - 대기 상태
```
┌─────────────────────────────────────────────────────────────┐
│                     🏋️ 헬스장 락카키 대여기                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                  📱 회원 바코드를 스캔해주세요                    │
│                                                             │
│                     [바코드 스캔 대기 애니메이션]                   │
│                                                             │
│              💡 락카키 반납시에도 바코드를 스캔해주세요              │
│                                                             │
│                                                             │
│                                              [관리자] 버튼    │
└─────────────────────────────────────────────────────────────┘
```

#### 👤 회원 확인 화면
```
┌─────────────────────────────────────────────────────────────┐
│                        회원 정보 확인                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                     👤 홍길동 님                            │
│                   회원번호: 2024-001                         │
│                 회원권: 프리미엄 (2024.12.31까지)              │
│                                                             │
│                 🗃️ 사용 가능한 락카: 15개                     │
│                                                             │
│                                                             │
│   [취소하기]                              [락카 선택하기]      │
└─────────────────────────────────────────────────────────────┘
```

#### 🗃️ 락카 선택 화면 - A구역
```
┌─────────────────────────────────────────────────────────────┐
│  🗃️ 락카 선택  │  [A구역]  [B구역]  │           [← 뒤로가기]  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [A01] [A02] [A03] [A04] [A05] [A06] [A07] [A08]           │
│   ✅    ✅    ❌    ✅    ✅    ❌    ✅    ✅             │
│                                                             │
│  [A09] [A10] [A11] [A12] [A13] [A14] [A15] [A16]           │
│   ✅    ❌    ✅    ✅    ❌    ✅    ✅    ✅             │
│                                                             │
│  [A17] [A18] [A19] [A20] [A21] [A22] [A23] [A24]           │
│   ✅    ✅    ❌    ✅    ✅    ✅    ❌    ✅             │
│                                                             │
│                     ✅ 사용가능  ❌ 사용중                    │
└─────────────────────────────────────────────────────────────┘
```

#### ✅ 대여 완료 화면
```
┌─────────────────────────────────────────────────────────────┐
│                       🎉 대여 완료!                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                    🗃️ A-05번 락카                           │
│                     락카가 열렸습니다                          │
│                                                             │
│                   💡 주의사항                               │
│                 • 락카를 완전히 닫아주세요                      │
│                 • 락카키를 꼭 보관해주세요                      │
│                 • 분실 시 5,000원이 청구됩니다                 │
│                                                             │
│              5초 후 자동으로 처음 화면으로 이동합니다              │
│                          ⏰ 5                               │
└─────────────────────────────────────────────────────────────┘
```

#### 🔑 반납 완료 화면  
```
┌─────────────────────────────────────────────────────────────┐
│                      ✨ 반납 완료!                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                    🗃️ A-05번 락카                           │
│                     락카가 열렸습니다                          │
│                                                             │
│                  물건을 가져가신 후                           │
│               락카키를 반납함에 넣어주세요                       │
│                                                             │
│                      🙏 감사합니다!                          │
│                                                             │
│              3초 후 자동으로 처음 화면으로 이동합니다              │
│                          ⏰ 3                               │
└─────────────────────────────────────────────────────────────┘
```

#### ⚙️ 관리자 화면
```
┌─────────────────────────────────────────────────────────────┐
│  ⚙️ 관리자 화면 (비밀번호: 1234)  │         [홈으로] [로그아웃] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ 📊 시스템 상태                    📡 ESP32 연결 상태           │
│ • 시스템 정상 ✅                  • 바코드스캐너: 연결됨 ✅      │
│ • 메모리: 45% 사용중               • 모터1: 연결됨 ✅          │
│ • CPU: 12% 사용중                 • 모터2: 연결안됨 ❌        │
│                                                             │
│ 🌐 구글시트 연동                  🗃️ 락카 현황                │
│ • 마지막 동기화: 5분전 ✅          • 전체: 48개                │
│ • 회원 데이터: 최신 ✅            • 사용중: 23개              │
│ • 대여 기록: 정상 ✅              • 사용가능: 25개            │
│                                                             │
│ [ESP32 재연결] [구글시트 동기화] [시스템 재시작] [로그 보기]       │
└─────────────────────────────────────────────────────────────┘
```

### 🔄 **실시간 통신 흐름**
```
ESP32 바코드 스캔
    ↓
Python 백엔드 수신
    ↓
WebSocket으로 프론트엔드에 전송
    ↓
JavaScript가 화면 전환 처리
    ↓
사용자 액션 (락카 선택)
    ↓
AJAX로 백엔드에 요청
    ↓
ESP32로 모터 제어 명령
    ↓
WebSocket으로 완료 알림
```

### 🎨 **UI/UX 설계 원칙**
```
터치 최적화:
✅ 버튼 최소 크기: 60px × 60px
✅ 간격: 최소 10px
✅ 폰트 크기: 최소 16px

사용성:
✅ 한번에 하나의 액션만
✅ 명확한 피드백 (로딩, 성공, 오류)
✅ 자동 타임아웃 (30초 무반응 시 홈으로)
✅ 큰 텍스트 및 아이콘

접근성:
✅ 고대비 색상 조합
✅ 한글 폰트 최적화
✅ 음성 피드백 (선택사항)
```

## 🔧 핵심 컴포넌트 설계

### 1. ESP32Manager (core/esp32_manager.py)
```python
class ESP32Manager:
    """ESP32 디바이스들과의 통신을 총괄 관리"""
    
    def __init__(self):
        self.devices = {
            "barcode_scanner": ESP32Device("esp32_barcode", "/dev/ttyUSB0"),
            "motor_controller_1": ESP32Device("esp32_motor_01", "/dev/ttyUSB1"), 
            "motor_controller_2": ESP32Device("esp32_motor_02", "/dev/ttyUSB2")
        }
    
    async def send_command(self, device_id: str, command: dict) -> dict
    async def broadcast_status_request(self) -> dict
    def register_event_handler(self, event_type: str, handler: callable)
```

### 2. GoogleSheetsManager (data_sources/google_sheets.py)
```python
class GoogleSheetsManager:
    """구글시트 API를 통한 데이터 관리"""
    
    async def validate_member(self, barcode: str) -> MemberInfo
    async def get_available_lockers(self) -> List[LockerInfo]
    async def record_rental(self, member_id: str, locker_id: str) -> bool
    async def process_return(self, locker_key_barcode: str) -> bool
```

### 3. Flask 웹 애플리케이션 (web/app.py)
```python
class LockerWebApp:
    """웹 기반 터치스크린 인터페이스"""
    
    def __init__(self, esp32_manager: ESP32Manager, google_sheets: GoogleSheetsManager):
        self.app = Flask(__name__)
        self.socketio = SocketIO(self.app)
        self.esp32_manager = esp32_manager
        self.google_sheets = google_sheets
    
    # REST API 엔드포인트
    @app.route('/api/member/validate', methods=['POST'])
    @app.route('/api/locker/open', methods=['POST'])
    @app.route('/api/rental/complete', methods=['POST'])
    
    # WebSocket 이벤트
    @socketio.on('barcode_scan')
    @socketio.on('locker_select')
```

### 4. 웹 프론트엔드 구조
```javascript
// static/js/main.js - 메인 애플리케이션 로직
class LockerApp {
    constructor() {
        this.socket = io();
        this.currentScreen = 'home';
        this.setupEventHandlers();
    }
    
    // 화면 전환
    showScreen(screenName) { }
    
    // 바코드 스캔 처리
    handleBarcodeScan(barcode) { }
    
    // 락카 선택 처리
    handleLockerSelect(lockerId) { }
}

// static/js/websocket.js - 실시간 통신
socket.on('barcode_scanned', function(data) {
    app.handleBarcodeScan(data.barcode);
});

socket.on('locker_opened', function(data) {
    app.showSuccessMessage(data.locker_id);
});
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

## 🚀 **웹 서버 및 브라우저 설정**

### 키오스크 모드 설정
```bash
# Chromium 브라우저 키오스크 모드
chromium-browser --kiosk --disable-infobars --disable-session-crashed-bubble \
  --disable-restore-session-state --autoplay-policy=no-user-gesture-required \
  http://localhost:5000

# 또는 Firefox 키오스크 모드  
firefox --kiosk http://localhost:5000
```

### Flask 서버 설정
```python
# 라즈베리파이 최적화 설정
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # 캐시 비활성화
socketio.run(app, host='0.0.0.0', port=5000, debug=False)
```

### 터치스크린 최적화
```css
/* static/css/touch.css */
* {
    -webkit-touch-callout: none;  /* iOS 길게 누르기 비활성화 */
    -webkit-user-select: none;    /* 텍스트 선택 비활성화 */
    user-select: none;
}

button {
    min-height: 60px;  /* 터치 최소 크기 */
    min-width: 60px;
    font-size: 18px;
}
```

## 📊 모니터링 및 로깅

### 1. 실시간 상태 모니터링
- ESP32 디바이스 상태 (WebSocket)
- 네트워크 연결 상태  
- 시스템 리소스 사용량
- 락카 사용 현황 (대시보드)

### 2. 웹 기반 관리 도구
- 실시간 로그 뷰어 (/admin/logs)
- ESP32 상태 대시보드 (/admin/devices)
- 구글시트 동기화 상태 (/admin/sync)
- 시스템 성능 모니터링 (/admin/performance)

### 3. 감사 로그
- 모든 대여/반납 기록
- 웹 요청 로그 (Flask)
- WebSocket 연결 로그
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
  },
  "web_server": {
    "host": "0.0.0.0",
    "port": 5000,
    "debug": false,
    "kiosk_mode": true,
    "browser": "chromium"
  },
  "ui_settings": {
    "screen_timeout": 30,
    "auto_home_timeout": 5,
    "touch_feedback": true,
    "sound_enabled": false
  }
}
```

## 🎯 **개발 및 배포 프로세스**

### 개발 환경
```bash
# 로컬 개발 (macOS/Windows)
1. Flask 서버 실행: python main.py --debug
2. 브라우저에서 테스트: http://localhost:5000
3. 코드 수정 후 자동 리로드

# 라즈베리파이 배포
1. ./scripts/sync_code.sh
2. ssh raspberry-pi "cd /home/pi/gym-controller && python3 main.py"
3. 브라우저 키오스크 모드 자동 실행
```

### 실제 운영 시
```bash
# 부팅 시 자동 실행 설정
1. Flask 서버 자동 시작 (systemd 서비스)
2. Chromium 키오스크 모드 자동 실행
3. 터치스크린 보정 자동 적용
```

이 **웹 기반 아키텍처**는 실무에서 검증된 방식으로, 확장 가능하고 유지보수가 용이하며, ESP32들과의 시리얼 통신과 구글시트 연동을 통해 안정적인 락카키 대여 시스템을 구현할 수 있습니다.
