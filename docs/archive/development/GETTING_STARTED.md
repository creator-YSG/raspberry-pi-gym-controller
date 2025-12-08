# 🚀 개발 시작 가이드

> 헬스장 락커 시스템 개발 환경 설정 가이드

## 📋 사전 요구사항

- **Python 3.7+**
- **SQLite3** 
- **Git**

## 🏗️ 설치 및 설정

### 1. 프로젝트 클론
```bash
git clone [repository-url]
cd raspberry-pi-gym-controller
```

### 2. 의존성 설치
```bash
pip3 install -r requirements.txt
```

### 3. 데이터베이스 초기화
```bash
python3 scripts/setup/init_database.py
```

### 4. 회원 데이터 가져오기
```bash
python3 scripts/data/import_members_csv.py
```

### 5. 시스템 실행
```bash
python3 run.py
```

## 🧪 테스트 실행

### 서비스 플로우 테스트
```bash
python3 scripts/testing/test_service_flow.py
```

### 락커 권한 테스트
```bash
python3 scripts/testing/test_locker_permissions.py
```

### 구역 접근 테스트
```bash
python3 scripts/testing/test_zone_access.py
```

## 🔧 개발 도구

### 데이터베이스 확인
```bash
sqlite3 instance/gym_system.db ".tables"
```

### 회원 데이터 확인
```bash
sqlite3 instance/gym_system.db "SELECT COUNT(*) FROM members;"
```

### 락커 상태 확인
```bash
sqlite3 instance/gym_system.db "SELECT zone, COUNT(*) FROM locker_status GROUP BY zone;"
```

## 📚 주요 문서

- **시스템 가이드**: [`docs/SYSTEM_GUIDE.md`](../SYSTEM_GUIDE.md)
- **아키텍처**: [`docs/architecture/SYSTEM_ARCHITECTURE.md`](../architecture/SYSTEM_ARCHITECTURE.md)
- **배포 가이드**: [`docs/deployment/ESP32_INTEGRATION_GUIDE.md`](../deployment/ESP32_INTEGRATION_GUIDE.md)

## 🎯 개발 팁

### 프로젝트 구조 이해
```
app/
├── models/      # 데이터 모델 (Member, Locker, Rental)
├── services/    # 비즈니스 로직 (MemberService, LockerService)
├── api/         # REST API 엔드포인트
└── main/        # 웹 인터페이스

database/
├── schema.sql           # 데이터베이스 스키마
├── database_manager.py  # DB 연결 관리
└── transaction_manager.py # 트랜잭션 관리

scripts/
├── setup/       # 설치/설정 스크립트
├── data/        # 데이터 관리 스크립트
├── testing/     # 테스트 스크립트
└── deployment/  # 배포 스크립트
```

### 주요 서비스 클래스
- **MemberService**: 회원 관리 (검증, CRUD)
- **LockerService**: 락커 관리 (대여/반납, 권한 체크)
- **BarcodeService**: 바코드 처리 (회원/락커 구분)
- **TransactionManager**: 트랜잭션 관리 (동시성 제어)

### API 엔드포인트
- `GET /api/members/<member_id>`: 회원 정보 조회
- `GET /api/members/<member_id>/zones`: 접근 가능 구역 조회
- `GET /api/lockers/<zone>`: 구역별 사용 가능한 락커 조회
- `POST /api/rent`: 락커 대여 요청
- `POST /api/return`: 락커 반납 요청

## 🚀 다음 단계

1. **시스템 가이드 읽기**: 전체 시스템 이해
2. **아키텍처 문서 검토**: 설계 원리 파악
3. **테스트 실행**: 기능 검증
4. **코드 탐색**: 주요 서비스 클래스 분석
5. **API 테스트**: 엔드포인트 동작 확인

**🎯 개발 환경 설정이 완료되었습니다! 이제 시스템을 탐색하고 개발을 시작할 수 있습니다.**