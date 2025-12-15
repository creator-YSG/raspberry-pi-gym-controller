# 락카키 대여기 ↔ 운동복 대여기 통합 구현 가이드

**작성일**: 2025-12-09  
**버전**: 1.0

---

## 📋 목차

1. [전체 아키텍처](#전체-아키텍처)
2. [락카키 대여기 작업 완료 내역](#락카키-대여기-작업-완료-내역)
3. [운동복 대여기 작업 가이드](#운동복-대여기-작업-가이드)
4. [구글 시트 구조](#구글-시트-구조)
5. [API 명세](#api-명세)
6. [테스트 방법](#테스트-방법)
7. [트러블슈팅](#트러블슈팅)

---

## 🏗️ 전체 아키텍처

### 설계 원칙

**핵심 아이디어**: 헬스장별 독립된 구글 드라이브 폴더 + 서비스 계정

- ✅ 헬스장마다 독립된 구글 드라이브 폴더
- ✅ 기기별 독립된 서비스 계정 (락카키 대여기용, 운동복 대여기용)
- ✅ `gym_id` 불필요 (서비스 계정 = 헬스장 식별)
- ✅ 기존 시스템 변경 최소화
- ✅ 통신 정보만 별도 시트로 공유

### 시스템 흐름

```
┌─────────────────────────────────────────────────────────────┐
│  구글 드라이브: 서울본점_헬스장                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  📊 System_Integration.xlsx  ← 통합 정보 공유 시트          │
│     locker_api_host: 192.168.0.23                          │
│     locker_api_port: 5000                                  │
│                                                             │
│  🔑 service_account_locker.json  (락카키 대여기)            │
│  🔑 service_account_rental.json  (운동복 대여기)            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
         ↑                                    ↓
         │                                    │
    [락카키 대여기]                     [운동복 대여기]
    192.168.0.23                        192.168.0.24
         │                                    │
         │ 1. 부팅 시 IP 업로드                │
         │    → System_Integration            │
         │                                    │
         │                                    │ 2. 부팅 시 IP 다운로드
         │                                    │    ← System_Integration
         │                                    │
         │                                    │ 3. NFC 태그 인식
         │                                    │    (5A41B914524189)
         │                                    │
         │ 4. API 호출                        │
         │    GET /api/member/by-nfc/xxx  ←───┤
         │                                    │
         │ 5. 회원 정보 응답                   │
         ├───→ {member_id, name, ...}        │
         │                                    │
         │                                    │ 6. 운동복 대여 처리
```

---

## ✅ 락카키 대여기 작업 완료 내역

### 1. API 엔드포인트 구현

**파일**: `app/api/routes.py`

#### 주요 API: NFC UID로 회원 조회

```python
@bp.route('/member/by-nfc/<nfc_uid>')
def get_member_by_nfc(nfc_uid):
    """
    NFC UID로 회원 정보 조회
    
    Args:
        nfc_uid: NFC 태그 UID (예: "5A41B914524189")
    
    Returns:
        200 OK: {status: "ok", locker_number, member_id, name, assigned_at}
        404 Not Found: {status: "error", message}
    """
```

**엔드포인트**: `GET /api/member/by-nfc/{nfc_uid}`

**처리 과정**:
1. NFC UID → 락카 번호 매핑 (`locker_status.nfc_uid`)
2. 락카 번호 → 대여 정보 조회 (`rentals` + `members` JOIN)
3. 회원 정보 반환

**테스트 완료**:
```bash
# 성공 케이스
curl http://localhost:5000/api/member/by-nfc/5A41B914524189
# → {"status":"ok", "member_id":"20240861", "name":"쩐부테쑤안", ...}

# 실패 케이스 (빈 락카)
curl http://localhost:5000/api/member/by-nfc/5AE17DD3514189
# → {"status":"error", "message":"해당 락카가 배정되어 있지 않습니다"}
```

### 2. 구글 시트 통합 동기화

**파일**: `app/services/integration_sync.py`

#### IntegrationSync 클래스

```python
class IntegrationSync:
    """시스템 통합 정보 동기화"""
    
    INTEGRATION_SHEET_ID = "15qpiY1r_SEK6b2dr00UDmKrYHSVuGMmiMeTZ898Lv8Q"
    
    def upload_locker_api_info(self):
        """락카키 대여기 IP를 시트에 업로드"""
        # 로컬 IP 자동 감지
        # System_Integration 시트에 업로드
        
    def download_locker_api_info(self):
        """락카키 대여기 IP를 시트에서 다운로드 (운동복 대여기용)"""
        # System_Integration 시트 읽기
        # 로컬 캐시 저장
```

**기능**:
- ✅ 로컬 IP 자동 감지 (`get_local_ip()`)
- ✅ 시트 헤더 초기화 (`initialize_sheet_headers()`)
- ✅ IP 업로드 (`upload_locker_api_info()`)
- ✅ IP 다운로드 (`download_locker_api_info()`)
- ✅ 로컬 캐시 (오프라인 백업)

### 3. 부팅 시 자동 업로드

**파일**: `run.py`

```python
# 시스템 통합 정보 업로드 (운동복 대여기와 통신용)
try:
    from app.services.integration_sync import IntegrationSync
    sync = IntegrationSync()
    if sync.upload_locker_api_info():
        print(f"🔗 통합 시트 업로드 완료: {sync.get_local_ip()}:5000")
except Exception as e:
    print(f"⚠️  통합 시트 업로드 오류: {e} (계속 진행)")
```

**동작**:
- 락카키 대여기 부팅 시 자동으로 자신의 IP를 시트에 업로드
- 10분마다 갱신 (향후 스케줄러 추가 가능)

### 4. 문서 작성

**파일**: `docs/LOCKER_INTEGRATION_API.md`

- API 명세서
- NFC UID 예시
- Python/JavaScript 구현 예시
- 테스트 방법
- 트러블슈팅 가이드

### 5. 테스트 스크립트

**파일**: `scripts/test_integration_sync.py`

```bash
python3 scripts/test_integration_sync.py
# → 시트 연결, 헤더 초기화, IP 업로드/다운로드 테스트
```

---

## 🚀 운동복 대여기 작업 가이드

### 필요한 작업

#### 1. 서비스 계정 파일 설치

**파일**: `config/google_credentials.json`

- 헬스장 폴더에 접근 가능한 서비스 계정 JSON 파일
- 락카키 대여기와 **같은 폴더**를 공유하는 다른 서비스 계정

#### 2. IntegrationSync 모듈 추가

**파일**: `app/services/integration_sync.py` (복사)

락카키 대여기의 `integration_sync.py` 파일을 그대로 복사하거나, 다음 코드를 작성:

```python
from app.services.integration_sync import IntegrationSync

# 부팅 시 한 번 실행
sync = IntegrationSync()
LOCKER_API_URL = sync.download_locker_api_info()['url']

# 또는 캐시 우선 (빠름)
LOCKER_API_URL = sync._load_cache().get('url', 'http://192.168.0.23:5000')
```

#### 3. NFC 스캔 처리 구현

**예시**: `app/api/nfc_handler.py`

```python
import requests
from app.services.integration_sync import IntegrationSync

class NFCHandler:
    def __init__(self):
        # 부팅 시 락카키 대여기 주소 로드
        sync = IntegrationSync()
        info = sync.download_locker_api_info()
        self.locker_api_url = info['url']
        
    def handle_nfc_scan(self, nfc_uid: str):
        """
        NFC 스캔 처리
        
        Args:
            nfc_uid: NFC 리더에서 읽은 UID (예: "5A41B914524189")
        
        Returns:
            dict: 회원 정보 또는 None
        """
        try:
            # 1. 락카키 대여기 API 호출
            response = requests.get(
                f"{self.locker_api_url}/api/member/by-nfc/{nfc_uid}",
                timeout=2.0
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data['status'] == 'ok':
                    # 2. 회원 정보 추출
                    member_id = data['member_id']
                    name = data['name']
                    locker_number = data['locker_number']
                    
                    print(f"✅ 회원 확인: {name} ({member_id})")
                    print(f"   락카: {locker_number}")
                    
                    # 3. 로컬 DB에서 금액권/구독권 조회
                    subscription = self.get_subscription(member_id)
                    
                    if subscription:
                        # 4. 운동복 대여 처리
                        return self.process_rental(member_id, name, subscription)
                    else:
                        return {
                            'success': False,
                            'error': '유효한 금액권/구독권이 없습니다'
                        }
            
            elif response.status_code == 404:
                # 락카 미배정 또는 NFC 미등록
                error = response.json()
                print(f"❌ {error['message']}")
                return None
                
            else:
                print(f"❌ API 오류: {response.status_code}")
                return None
                
        except requests.Timeout:
            print("❌ 타임아웃: 락카키 대여기 응답 없음")
            return None
            
        except requests.ConnectionError:
            print("❌ 연결 실패: 락카키 대여기 서버 다운")
            return None
            
        except Exception as e:
            print(f"❌ 예외 발생: {e}")
            return None
    
    def get_subscription(self, member_id: str):
        """로컬 DB에서 금액권/구독권 조회"""
        # TODO: 운동복 대여기 로컬 DB 조회 로직
        pass
    
    def process_rental(self, member_id: str, name: str, subscription):
        """운동복 대여 처리"""
        # TODO: 운동복 대여 로직
        pass
```

#### 4. 주기적 갱신 (선택사항)

**추천**: 5분마다 락카키 대여기 주소 갱신

```python
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

@scheduler.scheduled_job('interval', minutes=5)
def refresh_locker_api_url():
    """락카키 대여기 주소 주기적 갱신"""
    global LOCKER_API_URL
    sync = IntegrationSync()
    info = sync.download_locker_api_info()
    if info:
        LOCKER_API_URL = info['url']
        print(f"🔄 락카키 대여기 주소 갱신: {LOCKER_API_URL}")

scheduler.start()
```

---

## 📊 구글 시트 구조

### System_Integration 시트

**시트 ID**: `15qpiY1r_SEK6b2dr00UDmKrYHSVuGMmiMeTZ898Lv8Q`

**URL**: https://docs.google.com/spreadsheets/d/15qpiY1r_SEK6b2dr00UDmKrYHSVuGMmiMeTZ898Lv8Q/edit

**구조**:

| locker_api_host | locker_api_port | last_updated        | status | notes          |
|-----------------|-----------------|---------------------|--------|----------------|
| 192.168.0.23    | 5000            | 2025-12-09 21:13:55 | active | 락카키 대여기  |

**필드 설명**:
- `locker_api_host`: 락카키 대여기 IP (자동 감지 후 업로드)
- `locker_api_port`: 락카키 대여기 포트 (5000)
- `last_updated`: 마지막 업데이트 시각
- `status`: 상태 (active/inactive)
- `notes`: 메모 (선택)

**권한 설정**:
- 락카키 대여기 서비스 계정: 읽기/쓰기
- 운동복 대여기 서비스 계정: 읽기

---

## 🔌 API 명세

### 엔드포인트

```
GET http://192.168.0.23:5000/api/member/by-nfc/{nfc_uid}
```

### 요청 예시

```bash
GET http://192.168.0.23:5000/api/member/by-nfc/5A41B914524189
```

### 응답 예시

#### ✅ 성공 (200 OK)

```json
{
  "status": "ok",
  "locker_number": "M01",
  "member_id": "20240861",
  "name": "쩐부테쑤안",
  "assigned_at": "2025-12-09 10:33:52"
}
```

#### ❌ 실패 (404 Not Found)

**락카 미배정**:
```json
{
  "status": "error",
  "locker_number": "S01",
  "nfc_uid": "5AE17DD3514189",
  "message": "해당 락카가 배정되어 있지 않습니다"
}
```

**등록되지 않은 NFC**:
```json
{
  "status": "error",
  "nfc_uid": "UNKNOWN_UID",
  "message": "해당 락카가 배정되어 있지 않습니다"
}
```

**회원 정보 없음**:
```json
{
  "status": "error",
  "locker_number": "M01",
  "member_id": "20240861",
  "message": "회원 정보를 찾을 수 없습니다"
}
```

#### ❌ 서버 오류 (500)

```json
{
  "status": "error",
  "message": "서버 오류"
}
```

### 헬스 체크

```
GET http://192.168.0.23:5000/api/health
```

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2025-12-09T21:00:00",
  "kiosk_mode": true
}
```

---

## 🧪 테스트 방법

### 1. 락카키 대여기 연결 테스트

```bash
# 헬스 체크
curl http://192.168.0.23:5000/api/health

# 성공 응답 예상
# {"status":"healthy", ...}
```

### 2. NFC UID 테스트

**테스트 데이터**:

| NFC UID | 락카 번호 | 상태 | 회원 |
|---------|----------|------|------|
| `5A41B914524189` | M01 | 대여 중 | 쩐부테쑤안 (20240861) |
| `5AE17DD3514189` | S01 | 비어있음 | - |

```bash
# 성공 케이스 (대여 중)
curl http://192.168.0.23:5000/api/member/by-nfc/5A41B914524189

# 실패 케이스 (빈 락카)
curl http://192.168.0.23:5000/api/member/by-nfc/5AE17DD3514189
```

### 3. Python 테스트 스크립트

```python
import requests

LOCKER_API_URL = "http://192.168.0.23:5000"

def test_nfc_integration():
    """NFC 통합 테스트"""
    test_cases = [
        ("5A41B914524189", "M01 대여중 - 성공 예상"),
        ("5AE17DD3514189", "S01 비어있음 - 404 예상"),
        ("INVALID_UID", "잘못된 UID - 404 예상")
    ]
    
    for nfc_uid, description in test_cases:
        print(f"\n테스트: {description}")
        print(f"NFC UID: {nfc_uid}")
        
        try:
            response = requests.get(
                f"{LOCKER_API_URL}/api/member/by-nfc/{nfc_uid}",
                timeout=2.0
            )
            
            print(f"응답 코드: {response.status_code}")
            print(f"응답 데이터: {response.json()}")
            
        except Exception as e:
            print(f"오류: {e}")

if __name__ == '__main__':
    test_nfc_integration()
```

---

## 🔧 트러블슈팅

### 문제 1: 락카키 대여기 연결 실패

**증상**: `Connection Refused` 또는 타임아웃

**원인**:
- 락카키 대여기 서버 미실행
- 잘못된 IP 주소
- 방화벽 차단

**해결**:
```bash
# 1. 서버 실행 확인
curl http://192.168.0.23:5000/api/health

# 2. 구글 시트에서 최신 IP 확인
# System_Integration 시트 확인

# 3. 캐시 삭제 후 재시도
rm config/locker_api_cache.json
```

### 문제 2: 404 Not Found

**증상**: 모든 NFC UID가 404 반환

**원인**:
- NFC UID가 DB에 등록되지 않음
- 락카가 비어있음

**해결**:
- 락카키 대여기 관리자에게 NFC UID 등록 요청
- 테스트용 NFC UID 사용: `5A41B914524189`

### 문제 3: 구글 시트 읽기 실패

**증상**: `gspread` 오류 또는 권한 오류

**원인**:
- 서비스 계정 파일 누락
- 시트 권한 없음

**해결**:
```bash
# 1. 서비스 계정 파일 확인
ls config/google_credentials.json

# 2. 시트 권한 확인
# System_Integration 시트에 서비스 계정 이메일 추가
# (example@project.iam.gserviceaccount.com)

# 3. 캐시 사용 (임시)
# 캐시가 있으면 시트 접근 실패해도 동작
```

---

## 📝 체크리스트

### 운동복 대여기 설치 시

- [ ] **1. 서비스 계정 파일 설치**
  - `config/google_credentials.json` 배치
  - 헬스장 폴더 권한 확인

- [ ] **2. IntegrationSync 모듈 추가**
  - `app/services/integration_sync.py` 복사
  - 의존성 설치: `pip install gspread google-auth`

- [ ] **3. 부팅 시 IP 다운로드**
  - `run.py` 또는 초기화 코드에 추가
  - 캐시 파일 생성 확인: `config/locker_api_cache.json`

- [ ] **4. NFC 스캔 핸들러 구현**
  - NFC 리더 → UID 읽기
  - 락카키 대여기 API 호출
  - 회원 정보 → 운동복 대여 처리

- [ ] **5. 에러 처리**
  - 타임아웃 (2초)
  - 연결 실패 (서버 다운)
  - 404 (락카 미배정)

- [ ] **6. 테스트**
  - 헬스 체크: `curl http://192.168.0.23:5000/api/health`
  - NFC 테스트: `curl http://192.168.0.23:5000/api/member/by-nfc/5A41B914524189`

---

## 📞 문의 및 지원

- **락카키 대여기 코드**: `/Users/yunseong-geun/Projects/raspberry-pi-gym-controller`
- **운동복 대여기 코드**: `/Users/yunseong-geun/Projects/gym-rental-system`
- **통합 시트**: https://docs.google.com/spreadsheets/d/15qpiY1r_SEK6b2dr00UDmKrYHSVuGMmiMeTZ898Lv8Q/edit
- **API 문서**: `docs/LOCKER_INTEGRATION_API.md`

---

## 📅 버전 이력

- **v1.0.0** (2025-12-09)
  - NFC UID 기반 회원 조회 API 구현
  - 구글 시트 통합 동기화 (IntegrationSync)
  - 부팅 시 자동 IP 업로드/다운로드
  - 문서 작성 및 테스트 완료

