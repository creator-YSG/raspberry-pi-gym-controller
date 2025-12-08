# 헬스장 락커 시스템

> 라즈베리파이 + ESP32 기반 완전 무인 헬스장 락커 시스템

## 핵심 특징

- **완전 자동화**: 바코드 스캔만으로 대여/반납 자동 처리
- **센서 기반 감지**: IR 센서로 락카키 제거/삽입 실시간 감지
- **구역별 접근 제어**: 교직원/일반회원, 성별에 따른 락커 권한
- **Google Sheets 동기화**: 클라우드 기반 데이터 백업 및 관리

## 시스템 구성

- **중앙 제어**: 라즈베리파이 4B + SQLite
- **하드웨어**: 2개 ESP32 컨트롤러 (총 60개 락커)
  - 교직원: S01-S10 (10개)
  - 남성: M01-M40 (40개)
  - 여성: F01-F10 (10개)
- **인터페이스**: Flask 웹 키오스크 (600x1024)

---

## 빠른 시작

```bash
# 의존성 설치
pip3 install -r requirements.txt

# 데이터베이스 초기화
python3 scripts/setup/init_database.py

# 시스템 실행
python3 run.py
```

### 키오스크 모드 (라즈베리파이)

```bash
./scripts/start_kiosk.sh
```

---

## 서비스 플로우

```
[바코드 스캔] → [회원 검증] → [대여/반납 판단] → [문 열림] → [센서 감지] → [완료]
```

### 대여 프로세스
1. 회원 바코드 스캔
2. 문 자동 열림
3. 원하는 락카키 선택 (센서 감지)
4. 대여 완료

### 반납 프로세스
1. 회원 바코드 스캔
2. 문 자동 열림
3. 락카키 제자리에 삽입 (센서 감지)
4. 반납 완료

---

## 문서

| 문서 | 설명 |
|------|------|
| [QUICK_START.md](docs/QUICK_START.md) | 빠른 시작 가이드 |
| [DATABASE.md](docs/DATABASE.md) | 데이터베이스 스키마 |
| [SENSOR_GUIDE.md](docs/SENSOR_GUIDE.md) | 센서 매핑 및 테스트 |
| [HARDWARE.md](docs/HARDWARE.md) | ESP32 하드웨어 설정 |
| [GOOGLE_SHEETS_SCHEMA.md](docs/GOOGLE_SHEETS_SCHEMA.md) | Google Sheets 동기화 |
| [UI_UX_GUIDE.md](docs/UI_UX_GUIDE.md) | UI/UX 가이드 |

---

## 프로젝트 구조

```
raspberry-pi-gym-controller/
├── app/                    # Flask 웹 애플리케이션
│   ├── api/               # REST API 엔드포인트
│   ├── services/          # 비즈니스 로직
│   └── templates/         # HTML 템플릿
├── core/                   # ESP32 통신 관리
├── database/               # DB 스키마 및 관리
├── config/                 # 설정 파일
├── hardware/               # ESP32 펌웨어
├── scripts/                # 관리 스크립트
└── docs/                   # 문서
    ├── QUICK_START.md
    ├── DATABASE.md
    ├── SENSOR_GUIDE.md
    ├── HARDWARE.md
    ├── GOOGLE_SHEETS_SCHEMA.md
    ├── UI_UX_GUIDE.md
    ├── screenshots/
    └── archive/           # 이전 문서
```

---

## 라즈베리파이 접속

```bash
ssh raspberry-pi
# 또는
ssh pi@192.168.0.27
```

---

## 테스트

```bash
# 서비스 플로우 테스트
python3 scripts/testing/test_service_flow.py

# 센서 시뮬레이션 (개발용)
curl -X POST http://localhost:5000/api/test/inject-sensor \
  -H 'Content-Type: application/json' \
  -d '{"sensor_num": 11, "state": "HIGH"}'
```
