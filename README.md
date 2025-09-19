# 라즈베리파이 헬스장 락카키 대여기

## 프로젝트 개요
라즈베리파이를 중심으로 한 헬스장 락카키 자동 대여 시스템입니다. ESP32 마이크로컨트롤러와 USB 시리얼 통신으로 연결되어 바코드 스캐닝, 모터 제어, 센서 데이터를 처리하며, 터치스크린 키오스크로 운영됩니다.

## 시스템 구성
- **중앙 제어**: 라즈베리파이 4B (1024x600 터치스크린 - 세로모드)
- **하드웨어 제어**: ESP32 (3대) - USB 시리얼 통신
- **데이터베이스**: Google Sheets API
- **사용자 인터페이스**: Flask 웹 기반 터치스크린 키오스크

## 라즈베리파이 정보
- **IP 주소**: 192.168.0.23
- **사용자명**: pi
- **SSH 접속**: `ssh raspberry-pi` (키 기반 인증)
- **화면**: 1024x600 MPI7006 IPS 터치스크린 (세로모드)
- **터치IC**: GT911 (터치 보정 완료)

## 현재 구현 상태

### ✅ 완료된 기능
- **원격 개발 환경**: SSH 키 인증, 코드 동기화 스크립트
- **하드웨어 설정**: 
  - 디스플레이 세로 회전 (portrait mode)
  - 터치 패널 보정 (Coordinate Transformation Matrix)
  - 오디오 출력 확인 및 설정
  - 화면 슬립 방지 설정
- **웹 기반 GUI**: Flask + HTML/CSS/JS 구조
- **키오스크 모드**: 전체화면 브라우저 자동 실행
- **Google Sheets 연동**: 기존 credentials 통합 완료
- **한글 및 이모티콘 폰트**: 정상 표시 확인
- **프로젝트 구조**: Flask 블루프린트 기반 모듈화

### 🚀 키오스크 시스템
- **시작**: `./scripts/start_kiosk.sh`
- **종료**: `./scripts/stop_kiosk.sh`
- **재시작**: `./scripts/restart_kiosk.sh`
- **자동 시작**: 데스크톱 바로가기 생성 완료

### 📁 폴더 구조
```
raspberry-pi-gym-controller/
├── app/                    # Flask 애플리케이션
│   ├── __init__.py        # 앱 팩토리
│   ├── main/              # 메인 블루프린트 (홈화면)
│   ├── api/               # API 블루프린트 (REST API)
│   ├── events.py          # WebSocket 이벤트
│   ├── models/            # 데이터 모델
│   ├── services/          # 비즈니스 로직
│   ├── static/            # CSS, JS, 이미지
│   └── templates/         # HTML 템플릿
├── core/                  # 핵심 시스템 로직
├── data_sources/          # 외부 데이터 연동
├── hardware/              # 하드웨어 통신
├── config/                # 설정 파일
├── scripts/               # 시스템 스크립트
├── logs/                  # 로그 파일
└── run.py                 # Flask 앱 실행
```

### 🔧 주요 기술 스택
- **Backend**: Python 3, Flask, Flask-SocketIO
- **Frontend**: HTML5, CSS3, JavaScript (바닐라)
- **통신**: WebSocket (실시간), REST API
- **데이터**: Google Sheets API, JSON
- **하드웨어**: pyserial (ESP32 통신)
- **시스템**: systemd, X11, Chromium 키오스크

### ⏭️ 다음 구현 예정
- [ ] 락카 선택 및 대여 프로세스 UI
- [ ] 바코드 스캔 인터페이스
- [ ] ESP32 시리얼 통신 활성화
- [ ] 대여 기록 관리 시스템
- [ ] 관리자 모드 구현

## 개발 환경 사용법
```bash
# SSH 접속
./scripts/connect_pi.sh

# 코드 동기화
./scripts/sync_code.sh

# 로컬 테스트
python3 run.py

# 원격 키오스크 제어
ssh raspberry-pi "cd /home/pi/gym-controller && ./scripts/start_kiosk.sh"
```

## 트러블슈팅 이력
- ✅ SSH 비밀번호 반복 입력 → SSH 키 인증으로 해결
- ✅ 디스플레이 가로 → KMS 드라이버로 세로 회전
- ✅ 터치 패널 misalign → xinput 매트릭스 보정
- ✅ 한글 폰트 깨짐 → Noto Sans KR + Droid Sans Fallback
- ✅ 이모티콘 네모 표시 → Google Fonts 이모티콘 웹폰트
- ✅ 화면 슬립 → DPMS 비활성화 + 마우스 움직임

## Git 버전 관리
- **저장소**: [GitHub Repository URL]
- **현재 브랜치**: main
- **최근 커밋**: 이모티콘 폰트 지원 및 키오스크 시스템 완성