# 🏋️ 헬스장 락커 시스템

> **현재 상태**: 실제 운영 100% 준비 완료 (345명 회원 데이터 통합)

라즈베리파이 기반 헬스장 락커 자동 대여/반납 시스템으로, **구역별 접근 제어**와 **트랜잭션 기반 안전성**을 제공합니다.

## 🎯 핵심 특징
- **🔐 구역별 접근 제어**: 교직원/일반회원, 성별에 따른 락커 접근 권한
- **🛡️ 트랜잭션 기반 안전성**: 동시성 제어 및 데이터 무결성 보장
- **⚡ 실시간 센서 연동**: 3개 ESP32를 통한 물리적 상태 동기화
- **👥 실제 회원 데이터**: 345명 실제 헬스장 회원 데이터 통합 운영
- **🔄 스마트 반납 시스템**: 회원 바코드 스캔으로 대여/반납 모드 자동 판별

## 🏛️ 시스템 구성
- **중앙 제어**: 라즈베리파이 4B + SQLite 데이터베이스
- **하드웨어**: 3개 ESP32 컨트롤러 (총 140개 락커)
  - 남성 락커 70개 (M01~M70) + 여성 락커 50개 (F01~F50) + 교직원 락커 20개 (S01~S20)
- **인터페이스**: Flask 웹 기반 터치스크린 키오스크 (1024x600)

## 🚀 시스템 운영

### ✅ 완료된 기능 (100% 운영 준비)
- **345명 실제 회원 데이터**: CSV 기반 일괄 등록 및 검증 완료
- **구역별 접근 제어**: 교직원/일반회원, 성별에 따른 락커 권한 완벽 구현
- **스마트 반납 메커니즘**: 회원 바코드 스캔으로 대여/반납 모드 자동 판별
- **트랜잭션 기반 안전성**: 동시성 제어 및 데이터 무결성 보장
- **실시간 센서 연동**: 물리적 상태와 DB 동기화
- **실전 테스트 완료**: 모든 시나리오 100% 통과

### 🚀 키오스크 시스템
```bash
# 키오스크 시작
./scripts/deployment/start_kiosk.sh

# 키오스크 종료
./scripts/deployment/stop_kiosk.sh

# 키오스크 재시작
./scripts/deployment/restart_kiosk.sh
```

### 💾 데이터 관리
```bash
# 회원 데이터 가져오기
python3 scripts/data/import_members_csv.py

# 회원 권한 업데이트
python3 scripts/data/update_member_permissions.py
```

### 🧪 시스템 테스트
```bash
# 서비스 플로우 테스트
python3 scripts/testing/test_service_flow.py

# 락커 권한 테스트
python3 scripts/testing/test_locker_permissions.py
```

## 📁 프로젝트 구조

```
raspberry-pi-gym-controller/
├── 📱 app/                        # Flask 웹 애플리케이션
│   ├── api/                      # REST API 엔드포인트
│   ├── main/                     # 메인 웹 라우트
│   ├── models/                   # 데이터 모델 (Member, Locker, Rental)
│   ├── services/                 # 비즈니스 로직 서비스
│   ├── static/                   # CSS, JS, 이미지 파일
│   └── templates/                # HTML 템플릿
├── 🔌 core/                       # 핵심 시스템
│   └── esp32_manager.py          # ESP32 통신 관리자
├── 📊 database/                   # 데이터베이스 레이어
│   ├── schema.sql                # SQLite 스키마 (5개 테이블, 140개 락커)
│   ├── database_manager.py       # DB 연결 및 CRUD
│   ├── transaction_manager.py    # 트랜잭션 관리 시스템
│   └── sync_manager.py          # Google Sheets 동기화
├── 🔧 hardware/                   # 하드웨어 추상화
│   ├── barcode_utils.py         # 바코드 처리
│   ├── protocol_handler.py      # ESP32 통신 프로토콜
│   └── serial_scanner.py        # 시리얼 포트 스캐너
├── 📊 data_sources/               # 외부 데이터 소스
│   └── google_sheets.py         # Google Sheets API
├── ⚙️ config/                     # 설정 파일들
├── 💾 data/                       # 데이터 파일들 (체계적 관리)
│   ├── members/                 # 회원 데이터 (CSV 등)
│   └── backups/                 # 백업 파일들
├── 🧪 tests/                      # 테스트 파일들 (통합 정리)
│   ├── unit/                    # 단위 테스트
│   ├── integration/             # 통합 테스트
│   └── fixtures/                # 테스트 데이터
├── 🛠️ scripts/                    # 관리 스크립트들 (용도별 분류)
│   ├── setup/                   # 설치/설정 스크립트
│   ├── data/                    # 데이터 관리 스크립트
│   ├── deployment/              # 배포 관련 스크립트
│   ├── maintenance/             # 유지보수 스크립트
│   └── testing/                 # 테스트 스크립트
└── 📚 docs/                       # 프로젝트 문서 (주제별 분류)
    ├── architecture/            # 시스템 아키텍처
    ├── development/             # 개발 가이드
    ├── deployment/              # 배포 가이드
    ├── features/                # 기능 문서
    └── maintenance/             # 유지보수 문서
```

## 🔄 서비스 플로우

### 📱 바코드 스캔 → 락커 열기 전체 과정
1. **바코드 스캔**: 회원번호 입력
2. **회원 검증**: 데이터베이스에서 등록된 회원인지 확인
3. **유효성 검사**: 만료일자 체크
4. **대여/반납 판단**: 현재 대여 상태 확인
5. **회원 구분별 접근 구역 확인**: 성별 + 직급에 따른 권한
6. **선택 락커 구역 권한 체크**: 해당 구역 접근 가능한지 확인
7. **락커 열기 또는 접근 거부**

### 🎯 권한 제어 예시
```python
# 김현 교수 (남자 교직원) - 바코드: 20156111
✅ M01~M70 (남자구역) 접근 가능
❌ F01~F50 (여자구역) 접근 차단
✅ S01~S20 (교직원구역) 접근 가능

# 손준표 학생 (남자 일반회원) - 바코드: 20240838  
✅ M01~M70 (남자구역) 접근 가능
❌ F01~F50 (여자구역) 접근 차단
❌ S01~S20 (교직원구역) 접근 차단
```

## 📚 문서

- **📖 완전 가이드**: [`docs/SYSTEM_GUIDE.md`](docs/SYSTEM_GUIDE.md) - 시스템 전체 가이드
- **🏗️ 아키텍처**: [`docs/architecture/`](docs/architecture/) - 시스템 설계 문서
- **🚀 개발 가이드**: [`docs/development/`](docs/development/) - 개발 시작 가이드
- **🚀 배포 가이드**: [`docs/deployment/`](docs/deployment/) - ESP32 통합 가이드
- **🔧 유지보수**: [`docs/maintenance/`](docs/maintenance/) - 문제 해결 가이드

## 🎉 운영 현황

**🎯 실제 헬스장 운영을 위한 모든 준비가 완료된 완벽한 시스템입니다!**

- **140개 락커**: 남성 70개, 여성 50개, 교직원 20개
- **3개 ESP32**: zone별 독립 제어
- **345명 회원**: 실제 헬스장 회원 데이터 통합
- **트랜잭션 기반**: 동시성 제어 및 안전성 보장
- **실시간 센서**: 물리적 상태와 DB 동기화
- **터치 최적화**: 1024x600 키오스크 인터페이스

---

## 🛠️ 개발 환경 설정

### 사전 요구사항
- Python 3.7+
- SQLite3
- Git

### 설치 및 실행
```bash
# 1. 의존성 설치
pip3 install -r requirements.txt

# 2. 데이터베이스 초기화
python3 scripts/setup/init_database.py

# 3. 회원 데이터 가져오기
python3 scripts/data/import_members_csv.py

# 4. 시스템 실행
python3 run.py
```

### 라즈베리파이 정보
- **IP 주소**: 192.168.0.23
- **사용자명**: pi
- **SSH 접속**: `ssh raspberry-pi`
- **화면**: 1024x600 터치스크린 (세로모드)