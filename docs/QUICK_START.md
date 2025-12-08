# 빠른 시작 가이드

> 락카키 대여기 시스템 설치 및 운영 가이드

## 시스템 개요

라즈베리파이 + ESP32 기반 헬스장 락카키 자동 대여/반납 시스템입니다.

- **60개 락커**: 교직원 10개(S01-S10), 남성 40개(M01-M40), 여성 10개(F01-F10)
- **구역별 접근 제어**: 성별/직급에 따른 락커 권한
- **센서 기반 자동화**: IR 센서로 키 삽입/제거 감지

---

## 1. 설치

```bash
# 프로젝트 클론
git clone [repository-url]
cd raspberry-pi-gym-controller

# 의존성 설치
pip3 install -r requirements.txt

# 데이터베이스 초기화
python3 scripts/setup/init_database.py
```

---

## 2. 실행

```bash
# 웹 서버 시작
python3 run.py

# 키오스크 모드 (라즈베리파이)
./scripts/start_kiosk.sh
```

- **URL**: http://localhost:5000
- **키오스크**: 600x1024 세로 모드 터치스크린

---

## 3. 데이터 관리

```bash
# 회원 데이터 가져오기
python3 scripts/data/import_members_csv.py

# DB 확인
sqlite3 instance/gym_system.db ".tables"
sqlite3 instance/gym_system.db "SELECT COUNT(*) FROM members;"
```

---

## 4. 테스트

```bash
# 서비스 플로우 테스트
python3 scripts/testing/test_service_flow.py

# 락커 권한 테스트
python3 scripts/testing/test_locker_permissions.py
```

---

## 5. 프로젝트 구조

```
app/
├── models/      # 데이터 모델 (Member, Locker, Rental)
├── services/    # 비즈니스 로직 (MemberService, LockerService)
├── api/         # REST API 엔드포인트
└── templates/   # 웹 UI 템플릿

database/
├── schema.sql           # DB 스키마
└── database_manager.py  # DB 연결 관리

config/
├── sensor_mapping.json  # 센서 → 락커 매핑
└── esp32_mapping.json   # ESP32 장치 설정

scripts/
├── setup/       # 설치/설정 스크립트
├── data/        # 데이터 관리
└── testing/     # 테스트 스크립트
```

---

## 6. 주요 API

| 엔드포인트 | 설명 |
|-----------|------|
| `GET /api/members/<id>` | 회원 정보 조회 |
| `GET /api/members/<id>/zones` | 접근 가능 구역 |
| `POST /api/rentals/process` | 대여/반납 처리 |
| `POST /api/test/inject-sensor` | 센서 시뮬레이션 |

---

## 7. 문제 해결

**ModuleNotFoundError**
```bash
export PYTHONPATH=.
```

**database is locked**
```bash
lsof instance/gym_system.db  # 사용 중인 프로세스 확인
```

---

## 관련 문서

- [DATABASE.md](DATABASE.md) - 데이터베이스 스키마
- [SENSOR_GUIDE.md](SENSOR_GUIDE.md) - 센서 매핑 및 테스트
- [HARDWARE.md](HARDWARE.md) - ESP32 하드웨어 설정
- [GOOGLE_SHEETS.md](GOOGLE_SHEETS_SCHEMA.md) - Google Sheets 동기화

