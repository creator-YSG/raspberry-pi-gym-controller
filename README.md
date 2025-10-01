# 🏗️ 라즈베리파이 헬스장 락카키 대여기

> **최신 업데이트**: Phase 3 서비스 로직 통합 완료 - 완전한 대여/반납 플로우 구현 (2025.10.01)

## 📋 프로젝트 개요

라즈베리파이 기반 헬스장 락카키 자동 대여/반납 시스템으로, **트랜잭션 기반 안전한 처리**와 **실시간 센서 검증**을 제공합니다.

### 🎯 핵심 특징
- **🛡️ 트랜잭션 기반 안전성**: 동시성 제어 및 데이터 무결성 보장
- **⚡ 실시간 센서 연동**: ESP32를 통한 물리적 상태 동기화
- **☁️ Google Sheets 동기화**: 기존 관리 시스템과의 호환성 유지
- **📱 터치 최적화 UI**: 600x1024 세로 모드 키오스크

## 🏛️ 시스템 구성

- **중앙 제어**: 라즈베리파이 4B + SQLite 데이터베이스
- **하드웨어**: ESP32 통합 컨트롤러 (바코드/센서/모터)
- **데이터**: SQLite (로컬) + Google Sheets (동기화)
- **인터페이스**: Flask 웹 기반 터치스크린 키오스크

## 라즈베리파이 정보
- **IP 주소**: 192.168.0.23
- **사용자명**: pi
- **SSH 접속**: `ssh raspberry-pi` (키 기반 인증)
- **화면**: 1024x600 MPI7006 IPS 터치스크린 (세로모드)
- **터치IC**: GT911 (터치 보정 완료)

## 🚀 구현 현황

### ✅ 완료된 기능 (3단계/4단계)

**🔄 서비스 로직 통합 (3단계 완료)**
- MemberService SQLite 기반 완전 재작성
- LockerService 트랜잭션 기반 안전한 대여/반납
- ESP32 센서 이벤트 실시간 연동 (48개 센서)
- API 엔드포인트 비동기 처리 업데이트
- 완전한 대여 플로우: 회원검증 → 트랜잭션생성 → 하드웨어제어 → 센서검증 → 완료

**🗄️ 데이터베이스 시스템 (1단계 완료)**
- SQLite 데이터베이스 구조 설계 및 구현
- 5개 테이블 (members, rentals, locker_status, active_transactions, system_settings)
- 자동 인덱싱 및 트리거 시스템
- Google Sheets 양방향 동기화

**⚙️ 트랜잭션 시스템 (2단계 완료)**
- UUID 기반 트랜잭션 관리
- 동시성 제어 (1회원/1트랜잭션)
- 자동 타임아웃 처리 (30초)
- 센서 이벤트 기록 및 검증

**👤 확장된 모델 시스템**
- Member 모델 SQLite 연동 완료
- 대여 상태 추적 및 일일 제한
- 데이터베이스 변환 메서드

**🧪 완전한 테스트 커버리지**
- 24개 테스트 모두 통과 (100%)
- 데이터베이스, 모델, 트랜잭션 테스트

**🔧 기존 완성 기능**
- ESP32 자동 감지 및 통신 시스템
- Flask 웹 기반 터치스크린 UI
- 키오스크 모드 및 하드웨어 설정
- Google Sheets API 연동

### 🚀 키오스크 시스템
- **시작**: `./scripts/start_kiosk.sh`
- **종료**: `./scripts/stop_kiosk.sh`
- **재시작**: `./scripts/restart_kiosk.sh`
- **자동 시작**: 데스크톱 바로가기 생성 완료

### 📁 프로젝트 구조 (업데이트됨)

```
raspberry-pi-gym-controller/
├── 📊 database/                    # 🆕 데이터베이스 레이어
│   ├── schema.sql                 # SQLite 스키마 (5개 테이블)
│   ├── database_manager.py        # DB 연결 및 CRUD
│   ├── transaction_manager.py     # 트랜잭션 관리 시스템
│   └── sync_manager.py           # Google Sheets 동기화
├── 📱 app/                        # Flask 애플리케이션
│   ├── models/                   # 🔄 확장된 데이터 모델
│   │   ├── member.py            # SQLite 연동 Member 모델
│   │   ├── locker.py            # 락카 모델
│   │   └── rental.py            # 대여 기록 모델
│   ├── services/                 # 🔄 비즈니스 로직 (3단계 완료)
│   │   ├── member_service.py    # SQLite 기반 회원 관리
│   │   ├── locker_service.py    # 트랜잭션 기반 락카 관리
│   │   └── sensor_event_handler.py # 센서 이벤트 처리
│   ├── main/routes.py           # 메인 웹 라우트
│   ├── api/routes.py            # REST API 엔드포인트
│   └── events.py                # WebSocket 이벤트
├── 🔌 core/esp32_manager.py       # ESP32 자동감지/통신
├── 🔧 hardware/                   # 하드웨어 제어 모듈
├── 📊 data_sources/               # Google Sheets API
├── 🧪 tests/                      # 🆕 완전한 테스트 스위트
│   ├── database/                # 데이터베이스 레이어 테스트
│   │   ├── test_database_manager.py  # DB 매니저 테스트 (13개)
│   │   ├── test_member_model.py      # Member 모델 테스트 (8개)
│   │   └── test_transaction_manager.py # 트랜잭션 테스트 (9개)
│   └── services/                # 서비스 레이어 테스트
│       └── test_member_service.py    # MemberService 테스트 (13개)
├── 🛠️ scripts/                    # 시스템 스크립트
│   ├── init_database.py         # 🆕 DB 초기화
│   ├── add_test_members.py      # 테스트 회원 데이터 추가
│   ├── test_complete_flow.py    # 완전한 대여 플로우 테스트
│   ├── test_api_direct.py       # API 기능 직접 테스트
│   └── start_kiosk.sh           # 키오스크 시작
├── 📝 docs/                       # 🆕 완전한 문서화
│   ├── SYSTEM_OVERVIEW.md       # 전체 시스템 가이드
│   ├── DATABASE_DESIGN.md       # DB 설계 문서
│   ├── IMPLEMENTATION_PLAN.md   # 구현 계획서
│   ├── PHASE3_DETAILED_PLAN.md  # Phase 3 상세 계획
│   ├── PHASE3_COMPLETION_REPORT.md # Phase 3 완료 보고서
│   └── GETTING_STARTED.md       # 빠른 시작 가이드
├── 📋 locker.db                   # 🆕 SQLite 데이터베이스
└── ⚙️ config/                     # 설정 파일
```

### 🔧 기술 스택 (업데이트됨)

**백엔드**
- **Python 3**: 메인 언어
- **Flask + Flask-SocketIO**: 웹 프레임워크
- **SQLite**: 로컬 데이터베이스 (🆕)
- **asyncio**: 비동기 트랜잭션 처리 (🆕)

**데이터 관리**
- **SQLite**: 트랜잭션 기반 로컬 DB (🆕)
- **Google Sheets API**: 마스터 데이터 동기화
- **JSON**: ESP32 통신 프로토콜

**하드웨어 통신**
- **pyserial**: ESP32 USB 시리얼 통신
- **자동 감지**: VID:PID 기반 포트 스캔

**프론트엔드 & 시스템**
- **HTML5/CSS3/JavaScript**: 터치 최적화 UI
- **WebSocket**: 실시간 상태 업데이트
- **Chromium 키오스크**: 전체화면 모드

### 🎯 다음 단계 (3단계: 서비스 로직 통합)

- [ ] LockerService에 트랜잭션 시스템 통합
- [ ] ESP32 센서 이벤트와 검증 시스템 연결
- [ ] 완전한 대여/반납 플로우 구현
- [ ] 웹 UI에 실시간 트랜잭션 상태 표시
- [ ] 통합 테스트 및 성능 최적화

## 🚀 빠른 시작

### 📊 데이터베이스 초기화
```bash
# SQLite 데이터베이스 생성
python3 scripts/init_database.py

# 데이터베이스 상태 확인
sqlite3 locker.db "SELECT name FROM sqlite_master WHERE type='table';"
```

### 🧪 테스트 실행
```bash
# 전체 테스트 실행 (24개)
python3 tests/database/test_database_manager.py
python3 tests/database/test_member_model.py
python3 tests/database/test_transaction_manager.py

# 개별 기능 테스트
python3 -c "
from database import DatabaseManager
db = DatabaseManager('locker.db')
db.connect()
print('✅ 데이터베이스 연결 성공')
stats = db.get_database_stats()
print(f'📊 락카 수: {stats[\"locker_status_count\"]}개')
db.close()
"
```

### 🔧 개발 환경
```bash
# SSH 접속
./scripts/connect_pi.sh

# 코드 동기화
./scripts/sync_code.sh

# 로컬 개발 서버
python3 run.py

# 키오스크 모드 시작
./scripts/start_kiosk.sh
```

## 트러블슈팅 이력
- ✅ SSH 비밀번호 반복 입력 → SSH 키 인증으로 해결
- ✅ 디스플레이 가로 → KMS 드라이버로 세로 회전
- ✅ 터치 패널 misalign → xinput 매트릭스 보정
- ✅ 한글 폰트 깨짐 → Noto Sans KR + Droid Sans Fallback
- ✅ 이모티콘 네모 표시 → Google Fonts 이모티콘 웹폰트
- ✅ 화면 슬립 → DPMS 비활성화 + 마우스 움직임

## 📚 문서 가이드

### 🎯 시작하기
- **[SYSTEM_OVERVIEW.md](docs/SYSTEM_OVERVIEW.md)** - 전체 시스템 구조 및 사용법
- **[README.md](README.md)** - 이 문서 (프로젝트 개요)

### 🏗️ 설계 문서
- **[DATABASE_DESIGN.md](docs/DATABASE_DESIGN.md)** - SQLite 데이터베이스 상세 설계
- **[IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md)** - 4단계 구현 계획
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - ESP32 통합 아키텍처

### 📊 현재 상태
- **구현 진행률**: 2/4 단계 완료 (50%)
- **테스트 통과율**: 24/24 (100%)
- **데이터베이스**: 5개 테이블, 48개 락카 초기화 완료
- **다음 단계**: 서비스 로직 통합 (3단계)

---

**📝 최종 업데이트**: 2025년 10월 1일  
**🏗️ 버전**: v2.0 (SQLite 트랜잭션 시스템)  
**👨‍💻 상태**: 개발 진행 중 (2/4 단계 완료)