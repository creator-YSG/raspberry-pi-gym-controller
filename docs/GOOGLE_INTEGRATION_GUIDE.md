# Google 연동 완벽 가이드

라즈베리파이 락카키 대여기 시스템의 Google Sheets 및 Google Drive 연동 구현 가이드

---

## 📋 목차

1. [전체 아키텍처](#전체-아키텍처)
2. [사전 준비](#사전-준비)
3. [Google Cloud 프로젝트 설정](#google-cloud-프로젝트-설정)
4. [Google Sheets 연동 (서비스 계정)](#google-sheets-연동-서비스-계정)
5. [Google Drive 연동 (OAuth 2.0)](#google-drive-연동-oauth-20)
6. [코드 구조](#코드-구조)
7. [**시트 동기화 시점 (중요)**](#시트-동기화-시점-중요)
8. [센터별 배포 가이드](#센터별-배포-가이드)
9. [트러블슈팅](#트러블슈팅)

---

## 전체 아키텍처

### 두 가지 인증 방식 혼용

```
┌─────────────────────────────────────────┐
│     라즈베리파이 락카키 대여기          │
├─────────────────────────────────────────┤
│                                         │
│  ┌──────────────┐    ┌──────────────┐  │
│  │ Google       │    │ Google       │  │
│  │ Sheets 연동  │    │ Drive 연동   │  │
│  │              │    │              │  │
│  │ 서비스 계정  │    │ OAuth 2.0    │  │
│  │ (자동)       │    │ (개인 계정)  │  │
│  └──────────────┘    └──────────────┘  │
│         ↓                    ↓          │
└─────────│────────────────────│──────────┘
          │                    │
          ↓                    ↓
    ┌─────────────┐      ┌─────────────┐
    │   Google    │      │   Google    │
    │   Sheets    │      │   Drive     │
    │             │      │             │
    │ - 회원명단   │      │ - 인증사진   │
    │ - 대여기록   │      │ - 회원사진   │
    │ - 락카현황   │      │             │
    │ - 센서이벤트 │      │ 15GB 무료   │
    └─────────────┘      └─────────────┘
```

### 왜 두 가지 방식을 사용하나?

| 항목 | Google Sheets | Google Drive |
|------|--------------|--------------|
| **인증 방식** | 서비스 계정 | OAuth 2.0 |
| **저장 공간** | 필요 없음 | ✅ 필요 (15GB) |
| **토큰 만료** | ❌ 없음 | ⚠️ 있음 (자동 갱신) |
| **사용자 로그인** | ❌ 불필요 | ⚠️ 최초 1회 |
| **적합한 용도** | 구조화된 데이터 | 파일 저장 |

**결론:**
- **Sheets**: 서비스 계정 (완전 자동화, 저장 공간 불필요)
- **Drive**: OAuth 2.0 (개인 계정의 저장 공간 사용)

---

## 사전 준비

### 필요한 것

1. **Google 계정**
   - 개발용: 1개 (프로젝트 관리)
   - 센터별: 각 1개 (Drive 저장 공간)

2. **Google Cloud 프로젝트**
   - 무료 (결제 정보 불필요)

3. **Python 패키지**
   ```bash
   pip install google-api-python-client>=2.100.0
   pip install google-auth>=2.22.0
   pip install google-auth-oauthlib>=1.1.0
   pip install gspread>=5.10.0
   ```

---

## Google Cloud 프로젝트 설정

### 1단계: 프로젝트 생성

1. https://console.cloud.google.com 접속
2. "프로젝트 만들기" 클릭
3. 프로젝트 이름: `gym-locker-system` (예시)
4. "만들기" 클릭

### 2단계: API 활성화

필요한 API 3개:

```
https://console.cloud.google.com/apis/library
```

1. **Google Sheets API** 검색 → "사용" 클릭
2. **Google Drive API** 검색 → "사용" 클릭
3. **Google Cloud API** (자동 활성화)

---

## Google Sheets 연동 (서비스 계정)

### 왜 서비스 계정?

- ✅ 완전 자동화 (사용자 로그인 불필요)
- ✅ 토큰 만료 없음
- ✅ Sheets는 저장 공간 불필요
- ✅ 간단한 설정

### 1단계: 서비스 계정 생성

```
https://console.cloud.google.com/iam-admin/serviceaccounts
```

1. "서비스 계정 만들기" 클릭
2. **서비스 계정 이름**: `gym-sheets-service`
3. **서비스 계정 ID**: `gym-sheets-service@프로젝트ID.iam.gserviceaccount.com`
4. "만들기 및 계속하기" 클릭
5. 역할: **편집자** 선택 (또는 건너뛰기)
6. "완료" 클릭

### 2단계: 인증 키 생성

1. 생성된 서비스 계정 클릭
2. "키" 탭 → "키 추가" → "새 키 만들기"
3. **JSON** 선택 → "만들기"
4. 다운로드된 JSON 파일을 프로젝트에 복사:
   ```
   프로젝트_루트/config/google_credentials.json
   ```

### 3단계: Google Sheets 생성 및 공유

1. Google Sheets에서 새 스프레드시트 생성
2. 스프레드시트 ID 복사 (URL에서):
   ```
   https://docs.google.com/spreadsheets/d/[이_부분이_ID]/edit
   ```
3. **공유** 버튼 클릭
4. 서비스 계정 이메일 추가:
   ```
   gym-sheets-service@프로젝트ID.iam.gserviceaccount.com
   ```
5. 권한: **편집자** 선택
6. "공유" 클릭

### 4단계: 설정 파일 작성

`config/google_sheets_config.json`:

```json
{
  "spreadsheet_id": "스프레드시트_ID",
  "spreadsheet_name": "gym-locker-entry-system",
  "credentials_file": "google_credentials.json",
  "sheet_names": {
    "members": "회원명단",
    "rentals": "대여기록",
    "lockers": "락카현황",
    "sensor_events": "센서이벤트",
    "rental_photos": "인증사진"
  },
  "sync_settings": {
    "auto_sync": true,
    "download_interval_sec": 300,
    "upload_interval_sec": 300,
    "device_status_interval_sec": 60,
    "offline_mode": true
  }
}
```

### 5단계: 코드 구현

`app/services/sheets_sync.py`:

```python
from gspread import authorize
from google.oauth2.service_account import Credentials

class SheetsSync:
    def __init__(self):
        self.credentials_path = 'config/google_credentials.json'
        self.config_path = 'config/google_sheets_config.json'
        
    def connect(self):
        scope = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        credentials = Credentials.from_service_account_file(
            self.credentials_path, scopes=scope
        )
        self.gc = authorize(credentials)
        self.sheet = self.gc.open_by_key(self.spreadsheet_id)
        return True
```

---

## Google Drive 연동 (OAuth 2.0)

### 왜 OAuth 2.0?

- ✅ 개인 계정의 **저장 공간** 사용 (15GB 무료)
- ✅ 센터별 독립적 관리 가능
- ✅ 파일 소유권 명확
- ⚠️ 최초 1회 로그인 필요
- ⚠️ Refresh Token 관리 필요

### 1단계: OAuth 동의 화면 설정

```
https://console.cloud.google.com/apis/credentials/consent
```

1. **사용자 유형**: "외부" 선택
2. **앱 이름**: `락카키 대여기 시스템`
3. **사용자 지원 이메일**: 본인 이메일
4. **앱 도메인**: 건너뛰기
5. **범위 추가**:
   ```
   https://www.googleapis.com/auth/drive
   ```
6. **테스트 사용자 추가**:
   - 센터별 Gmail 계정 추가
   - 예: `gym-center-a@gmail.com`
7. **저장**

### ⚠️ 중요: 프로덕션 모드 전환

테스트 모드는 7일 후 토큰 만료!

```
OAuth 동의 화면 → "앱 게시" 버튼 클릭 → 프로덕션 모드
```

### 2단계: OAuth 클라이언트 ID 생성

```
https://console.cloud.google.com/apis/credentials
```

1. **"사용자 인증 정보 만들기"** 클릭
2. **"OAuth 클라이언트 ID"** 선택
3. **애플리케이션 유형**: `데스크톱 앱`
4. **이름**: `Gym Locker Desktop Client`
5. **만들기** 클릭
6. **JSON 다운로드** 클릭
7. 파일을 프로젝트 루트에 저장:
   ```
   client_secret_xxxxx.json
   ```

### 3단계: .gitignore 업데이트

민감 정보 보호:

```gitignore
# Google OAuth 인증 파일들 (민감 정보)
client_secret_*.json
*_credentials.json
instance/drive_token.pickle
```

### 4단계: Google Drive 폴더 준비

**중요:** 이 폴더를 센터별로 미리 만들어두세요.

1. Google Drive에서 폴더 생성: `락카키대여기-사진`
2. 폴더 URL에서 ID 복사:
   ```
   https://drive.google.com/drive/folders/[폴더_ID]
   ```
3. 코드에 폴더 ID 설정 (아래 참고)

### 5단계: DriveService 구현

`app/services/drive_service.py`:

```python
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import pickle
from pathlib import Path

class DriveService:
    """Google Drive 업로드 서비스 (OAuth 2.0)"""
    
    # OAuth scopes
    SCOPES = ['https://www.googleapis.com/auth/drive']
    
    # 루트 폴더 ID (센터별로 미리 생성한 폴더)
    ROOT_FOLDER_ID = "1fTnW_MSrzMaWXpA5lPYJ9Ce9rUMu4wWL"  # 예시
    
    def __init__(self, oauth_credentials_path: str = None, token_path: str = None):
        self.project_root = Path(__file__).parent.parent.parent
        
        if oauth_credentials_path is None:
            oauth_credentials_path = self.project_root / "client_secret_xxxxx.json"
        
        if token_path is None:
            token_path = self.project_root / "instance" / "drive_token.pickle"
        
        self.oauth_credentials_path = Path(oauth_credentials_path)
        self.token_path = Path(token_path)
        self.service = None
        self.connected = False
        self._root_folder_id = self.ROOT_FOLDER_ID
    
    def connect(self) -> bool:
        """Google Drive API 연결 (OAuth 2.0)"""
        try:
            credentials = None
            
            # 저장된 토큰이 있으면 로드
            if self.token_path.exists():
                with open(self.token_path, 'rb') as token:
                    credentials = pickle.load(token)
            
            # 토큰이 없거나 만료되었으면 새로 인증
            if not credentials or not credentials.valid:
                if credentials and credentials.expired and credentials.refresh_token:
                    # 자동 갱신
                    credentials.refresh(Request())
                else:
                    # 최초 인증 (브라우저 열림)
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.oauth_credentials_path), self.SCOPES
                    )
                    credentials = flow.run_local_server(port=0)
                
                # 토큰 저장
                self.token_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.token_path, 'wb') as token:
                    pickle.dump(credentials, token)
            
            # Drive API 서비스 생성
            self.service = build('drive', 'v3', credentials=credentials)
            self.connected = True
            return True
            
        except Exception as e:
            print(f"Drive 연결 실패: {e}")
            return False
    
    def upload_file(self, local_path: str, drive_folder: str = "", 
                    filename: str = None) -> str:
        """파일 업로드
        
        Args:
            local_path: 로컬 파일 경로
            drive_folder: 드라이브 하위 폴더 (예: "rentals/2025/12")
            filename: 저장할 파일명 (None이면 원본 이름)
        
        Returns:
            공유 URL 또는 None
        """
        if not self.connected:
            self.connect()
        
        local_path = Path(local_path)
        if not local_path.exists():
            return None
        
        try:
            # 폴더 ID 가져오기 (하위 폴더 생성 포함)
            folder_id = self._get_or_create_folder(drive_folder) if drive_folder else self._root_folder_id
            
            # 파일 메타데이터
            file_metadata = {
                'name': filename or local_path.name,
                'parents': [folder_id]
            }
            
            # 파일 업로드
            media = MediaFileUpload(str(local_path), mimetype='image/jpeg')
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            ).execute()
            
            # 공유 설정 (링크가 있는 사람은 누구나 볼 수 있음)
            self.service.permissions().create(
                fileId=file['id'],
                body={'type': 'anyone', 'role': 'reader'}
            ).execute()
            
            return file.get('webViewLink')
            
        except Exception as e:
            print(f"업로드 실패: {e}")
            return None
    
    def _get_or_create_folder(self, folder_path: str) -> str:
        """폴더 생성 (경로 기반)"""
        # 구현 생략 (코드 참고)
        pass
```

### 6단계: 최초 인증 스크립트

`scripts/setup/oauth_setup.py`:

```python
#!/usr/bin/env python3
"""
Google Drive OAuth 2.0 최초 인증 스크립트

사용법:
    python scripts/setup/oauth_setup.py
    
실행 후:
    - 브라우저가 자동으로 열림
    - Google 계정으로 로그인
    - 권한 승인
    - instance/drive_token.pickle 파일 자동 생성
"""

from app.services.drive_service import DriveService

def main():
    print("=" * 70)
    print("Google Drive OAuth 2.0 최초 인증")
    print("=" * 70)
    
    drive_service = DriveService()
    
    if drive_service.connect():
        print("\n✅ OAuth 인증 성공!")
        print(f"📁 토큰 저장 위치: {drive_service.token_path}")
        print(f"📂 루트 폴더 ID: {drive_service._root_folder_id}")
        return 0
    else:
        print("\n❌ OAuth 인증 실패")
        return 1

if __name__ == '__main__':
    import sys
    sys.exit(main())
```

### 7단계: 최초 인증 실행

```bash
python scripts/setup/oauth_setup.py
```

**과정:**
1. 스크립트 실행
2. 브라우저 자동 열림
3. Google 계정 로그인 (센터별 계정)
4. 권한 승인
5. `instance/drive_token.pickle` 생성 ✅

---

## 코드 구조

### 전체 파일 구조

```
프로젝트_루트/
├── config/
│   ├── google_credentials.json          # 서비스 계정 (Sheets)
│   └── google_sheets_config.json        # Sheets 설정
├── client_secret_xxxxx.json             # OAuth 클라이언트 ID (Drive)
├── instance/
│   ├── drive_token.pickle               # OAuth 토큰 (자동 생성)
│   └── photos/
│       ├── faces/                       # 회원 얼굴 사진
│       └── rentals/{year}/{month}/      # 인증 사진
├── app/
│   └── services/
│       ├── sheets_sync.py               # Sheets 동기화
│       └── drive_service.py             # Drive 업로드
└── scripts/
    └── setup/
        └── oauth_setup.py               # OAuth 최초 인증
```

### API 연동 예시

`app/api/routes.py`:

```python
from app.services.drive_service import get_drive_service
from datetime import datetime
from pathlib import Path

def _capture_auth_photo(member_id: str, auth_method: str):
    """인증 시 사진 촬영 및 Drive 업로드"""
    import threading
    
    def capture_async():
        try:
            from app.services.camera_service import get_camera_service
            from database.database_manager import DatabaseManager
            
            camera_service = get_camera_service()
            drive_service = get_drive_service()
            
            if not camera_service.is_running:
                return
            
            # 스냅샷 촬영
            now = datetime.now()
            photos_dir = Path('instance/photos/rentals') / str(now.year) / f"{now.month:02d}"
            photos_dir.mkdir(parents=True, exist_ok=True)
            
            filename = f"{member_id}_{now.strftime('%Y%m%d_%H%M%S')}.jpg"
            photo_path = str(photos_dir / filename)
            
            saved_path = camera_service.capture_snapshot(photo_path)
            
            rental_photo_url = None
            if saved_path:
                # Google Drive 업로드
                drive_url = drive_service.upload_file(
                    saved_path, 
                    f"rentals/{now.year}/{now.month:02d}",
                    filename
                )
                if drive_url:
                    rental_photo_url = drive_url
            
            # DB에 URL 저장
            db = DatabaseManager('instance/gym_system.db')
            db.connect()
            db.execute_query("""
                UPDATE rentals 
                SET rental_photo_path = ?, rental_photo_url = ?, auth_method = ?
                WHERE member_id = ? AND status IN ('active', 'pending')
                ORDER BY created_at DESC
                LIMIT 1
            """, (saved_path, rental_photo_url, auth_method, member_id))
            db.close()
            
        except Exception as e:
            logger.error(f'인증 사진 업로드 오류: {e}')
    
    # 비동기 실행
    thread = threading.Thread(target=capture_async, daemon=True)
    thread.start()

@bp.route('/auth/face', methods=['POST'])
def authenticate_face():
    result = face_service.process_face_auth(image)
    
    if result.get('success'):
        _capture_auth_photo(result['member_id'], 'face')  # 사진 촬영 + Drive 업로드
    
    return jsonify(result)
```

---

## 시트 동기화 시점 (중요)

### 대여/반납 프로세스별 동기화 흐름

대여 및 반납 과정에서 Google Sheets 동기화가 **여러 시점**에서 발생합니다. 각 시점을 이해하는 것이 중요합니다.

### 🔵 대여 프로세스

```
┌──────────────────────────────────────────────────────────────────┐
│ 1. member-check 페이지 진입 (바코드/얼굴 인증 완료)              │
├──────────────────────────────────────────────────────────────────┤
│ • DB: pending 레코드 생성 (locker_number = 'PENDING')           │
│ • 시트: ❌ 동기화 없음                                          │
│ • Drive: ❌ 업로드 없음                                         │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ 2. 인증 사진 촬영 → Drive 업로드 (비동기, 백그라운드)            │
├──────────────────────────────────────────────────────────────────┤
│ • DB: rental_photo_path, rental_photo_url 업데이트              │
│ • Drive: ✅ 사진 업로드                                         │
│ • 시트: ✅ 행이 없으면 새로 추가 (upload_rentals)               │
│        ✅ 사진 컬럼만 업데이트 (update_rental_photo)            │
│                                                                  │
│ ⚠️ 비동기 처리로 타이밍이 일정하지 않음 (2~10초 소요)           │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ 3. /api/rentals/process 호출 (센서 감지 또는 수동 확인)          │
├──────────────────────────────────────────────────────────────────┤
│ • DB (rentals): locker_number, status='active' 업데이트         │
│ • DB (locker_status): current_member 즉시 업데이트 ⚡           │
│ • DB (members): currently_renting 업데이트                      │
│ • DB commit() 실행 → 다른 기기에서 즉시 조회 가능               │
│                                                                  │
│ • 시트: ✅ 락커번호, 상태, 센서시간 업데이트                    │
│        - 컬럼 5: locker_number                                   │
│        - 컬럼 8: rental_sensor_time                              │
│        - 컬럼 10: status → 'active'                              │
│                                                                  │
│ 📍 코드 위치: app/api/routes.py (process_rental 함수)           │
│ 📍 locker_status 업데이트: 라인 831-838                         │
└──────────────────────────────────────────────────────────────────┘
```

### 🔴 반납 프로세스

```
┌──────────────────────────────────────────────────────────────────┐
│ 1. member-check 페이지 진입 (action=return)                     │
├──────────────────────────────────────────────────────────────────┤
│ • DB: return_barcode_time 기록                                  │
│ • 시트: ❌ 동기화 없음                                          │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ 2. /api/rentals/process 호출 (action=return)                    │
├──────────────────────────────────────────────────────────────────┤
│ • DB (rentals): status='returned', return_sensor_time 업데이트  │
│ • DB (locker_status): current_member = NULL 즉시 업데이트 ⚡    │
│ • DB (members): currently_renting = NULL 업데이트               │
│ • DB commit() 실행 → 다른 기기에서 즉시 조회 가능               │
│                                                                  │
│ • 시트: ✅ update_rental_return() 호출                          │
│        - 컬럼 9: return_sensor_time                              │
│        - 컬럼 10: status → 'returned'                            │
│                                                                  │
│ 📍 코드 위치: app/api/routes.py (process_rental 함수)           │
│ 📍 locker_status 업데이트: 라인 1002-1008                       │
└──────────────────────────────────────────────────────────────────┘
```

### 동기화 함수 정리

| 시점 | 함수 | 설명 | 파일 |
|------|------|------|------|
| 사진 업로드 시 | `upload_rentals()` | 행이 없으면 새 행 추가 | sheets_sync.py:242 |
| 사진 업로드 시 | `update_rental_photo()` | 사진 컬럼만 업데이트 | sheets_sync.py:319 |
| active 전환 시 | 개별 셀 업데이트 | 락커번호, 상태 업데이트 | routes.py:845-865 |
| 반납 시 | `update_rental_return()` | 반납시간, 상태 업데이트 | sheets_sync.py:377 |

### 시트 컬럼 매핑 (rentals 시트)

| 컬럼 | 인덱스 | 필드명 | 업데이트 시점 |
|------|--------|--------|---------------|
| A | 1 | rental_id | 최초 생성 시 |
| B | 2 | transaction_id | 최초 생성 시 |
| C | 3 | member_id | 최초 생성 시 |
| D | 4 | member_name | 최초 생성 시 |
| E | 5 | locker_number | active 전환 시 |
| F | 6 | zone | 최초 생성 시 |
| G | 7 | rental_barcode_time | 최초 생성 시 |
| H | 8 | rental_sensor_time | active 전환 시 |
| I | 9 | return_sensor_time | 반납 시 |
| J | 10 | status | active/returned 전환 시 |
| K | 11 | device_id | 최초 생성 시 |
| L | 12 | created_at | 최초 생성 시 |
| M | 13 | auth_method | 최초 생성 시 |
| N | 14 | rental_photo_path | 사진 업로드 시 |
| O | 15 | rental_photo_url | 사진 업로드 시 |

### ⚠️ 주의사항

1. **비동기 타이밍 문제**
   - 사진 업로드는 백그라운드에서 비동기로 진행됨
   - active 전환보다 늦게 완료될 수 있음
   - 시트에 행이 없는 상태에서 active 업데이트 시도 시 실패할 수 있음

2. **API 호출 제한**
   - Google Sheets API는 분당 호출 제한이 있음
   - `_rate_limit()` 함수로 1초 간격 유지
   - 대량 처리 시 주의 필요

3. **오프라인 모드**
   - 네트워크 연결이 끊기면 시트 동기화 실패
   - DB는 항상 로컬에 저장되므로 데이터 손실 없음
   - 연결 복구 후 `upload_rentals()`로 재동기화 가능

### 🟢 주기적 백그라운드 동기화 (SyncScheduler)

이벤트 기반 동기화 외에도, **백그라운드 스케줄러**가 주기적으로 동기화를 실행합니다.

#### 스케줄러 구성

| 동기화 유형 | 간격 | 방향 | 내용 |
|-------------|------|------|------|
| **다운로드** | 5분 (300초) | 시트 → DB | 회원 정보, 설정 |
| **업로드** | 5분 (300초) | DB → 시트 | 미동기화 대여 기록, 센서 이벤트 |
| **락카 상태** | 1분 (60초) | DB → 시트 | 60개 락카 현황 |

#### 코드 위치

```
app/services/sync_scheduler.py

주요 함수:
- _download_sync_loop(): 회원 정보 다운로드 (5분마다)
- _upload_sync_loop(): 대여/센서 이벤트 업로드 (5분마다)
- _locker_status_sync_loop(): 락카 상태 업데이트 (1분마다)
```

#### 시작 시점

- `app/__init__.py`에서 Flask 앱 시작 시 자동 시작
- `init_scheduler(db_manager, auto_start=True)` 호출

#### 동기화 대상

1. **다운로드 (`sync_all_downloads`)**
   - 회원명단 시트 → members 테이블
   - 설정 시트 → 로컬 설정

2. **업로드 (`upload_rentals`, `upload_sensor_events`)**
   - `sync_status = 0`인 레코드만 업로드
   - 업로드 후 `sync_status = 1`로 변경

3. **락카 상태 (`upload_locker_status`)**
   - locker_status 테이블 전체 → 락카현황 시트

#### 로그 확인

```bash
grep "SyncScheduler" logs/locker_system.log | tail -20
```

### 전체 동기화 흐름 요약

```
┌───────────────────────────────────────────────────────────────────────┐
│                     Google Sheets 동기화 전체 흐름                    │
├───────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  [이벤트 기반 동기화]                                                 │
│  ├── 사진 업로드 완료 시 → 시트에 행 추가 + 사진 URL                  │
│  ├── active 전환 시 → 시트에 락커번호/상태 업데이트                   │
│  └── 반납 완료 시 → 시트에 반납시간/상태 업데이트                     │
│                                                                       │
│  [주기적 백그라운드 동기화]                                           │
│  ├── 5분마다 → 회원 정보 다운로드 (시트 → DB)                        │
│  ├── 5분마다 → 미동기화 대여/센서 업로드 (DB → 시트)                 │
│  └── 1분마다 → 락카 상태 업데이트 (DB → 시트)                        │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

### 향후 개선 방향 (참고)

현재 구조는 여러 시점에서 개별적으로 업데이트하지만, 더 효율적인 방법:

```
[개선안] active 전환 시점에만 전체 동기화

1. pending 생성 → 시트 동기화 X
2. 사진 업로드 → DB만 업데이트 (시트 X)
3. active 전환 → 시트에 전체 정보 한 번에 추가/업데이트 ✅
4. 반납 → 시트에 반납 정보만 업데이트

장점:
- API 호출 횟수 감소
- 타이밍 문제 해결
- 로직 단순화
```

---

## 센터별 배포 가이드

### 시나리오

각 센터마다 독립적인 Google Drive 저장 공간 사용:

```
센터A → gym-center-a@gmail.com → Drive 15GB
센터B → gym-center-b@gmail.com → Drive 15GB
센터C → gym-center-c@gmail.com → Drive 15GB
```

### 배포 순서

#### 1️⃣ 사전 준비 (센터별 1회)

1. **Gmail 계정 생성**
   ```
   gym-center-a@gmail.com
   ```

2. **Google Drive 폴더 생성**
   - Google Drive 접속
   - 폴더 생성: `락카키대여기-사진`
   - 폴더 URL에서 ID 복사

3. **OAuth 테스트 사용자 추가**
   ```
   https://console.cloud.google.com/apis/credentials/consent
   → 테스트 사용자 → gym-center-a@gmail.com 추가
   ```

#### 2️⃣ 라즈베리파이 설정

**필요한 파일 복사:**

```bash
# 1. OAuth 클라이언트 ID (모든 센터 공통)
client_secret_xxxxx.json

# 2. Sheets 서비스 계정 (모든 센터 공통)
config/google_credentials.json
config/google_sheets_config.json
```

**폴더 ID 설정:**

`app/services/drive_service.py` 수정:

```python
class DriveService:
    # 센터별 폴더 ID로 변경
    ROOT_FOLDER_ID = "센터A_폴더_ID"
```

#### 3️⃣ 최초 인증

**라즈베리파이에서 실행:**

```bash
# SSH 또는 VNC로 접속
cd /home/pi/raspberry-pi-gym-controller
python scripts/setup/oauth_setup.py
```

**과정:**
1. 브라우저 열림 (라즈베리파이에서)
2. `gym-center-a@gmail.com` 로그인
3. 권한 승인
4. `instance/drive_token.pickle` 생성 ✅

#### 4️⃣ 테스트

```bash
python -c "
from app.services.drive_service import get_drive_service
drive = get_drive_service()
if drive.connect():
    print('✅ Drive 연결 성공')
    # 테스트 업로드
"
```

#### 5️⃣ 자동 시작 설정

```bash
# systemd 서비스 등록
sudo systemctl enable gym-locker.service
sudo systemctl start gym-locker.service
```

### 토큰 백업 (중요!)

**토큰 파일 백업:**

```bash
# 라즈베리파이에서 복사
cp instance/drive_token.pickle ~/backup/

# 로컬로 다운로드
scp pi@라즈베리파이IP:~/backup/drive_token.pickle ./
```

**재설치 시 복원:**

```bash
# 백업 토큰 복사
cp ~/backup/drive_token.pickle instance/
```

---

## OAuth 토큰 관리 및 모니터링

### 토큰 만료 문제

**문제:** OAuth 토큰이 만료되면 Google Drive 업로드가 실패합니다.

**해결 방안:**

1. **자동 갱신 (구현됨)**
   - `DriveService.connect()` 메서드가 토큰 만료 시 자동으로 `refresh_token`을 사용해 갱신
   - 갱신 성공 시 새 토큰을 `instance/drive_token.pickle`에 저장
   - 갱신 실패 시 토큰 파일 삭제 및 로그에 경고 메시지 출력

2. **재시도 로직 (구현됨)**
   - 업로드 실패 시 최대 3회 재시도 (지수 백오프: 2초, 4초, 8초)
   - 토큰 만료 감지 시 자동 재연결 시도
   - 모든 재시도 실패 시 로컬 저장만 유지

3. **헬스체크 스크립트**
   ```bash
   # 수동 실행
   python3 scripts/maintenance/check_drive_health.py
   
   # 크론탭 등록 (매일 오전 9시)
   crontab -e
   # 다음 줄 추가:
   0 9 * * * cd /home/pi/raspberry-pi-gym-controller && python3 scripts/maintenance/check_drive_health.py >> logs/drive_health.log 2>&1
   ```

4. **수동 재인증**
   - 자동 갱신이 실패한 경우 (refresh_token 만료)
   - 로컬 PC에서 실행:
     ```bash
     cd /path/to/raspberry-pi-gym-controller
     rm -f instance/drive_token.pickle
     python3 scripts/setup/oauth_setup.py
     ```
   - 생성된 토큰을 라즈베리파이로 복사:
     ```bash
     scp instance/drive_token.pickle pi@192.168.0.23:/home/pi/raspberry-pi-gym-controller/instance/
     ```

### 토큰 만료 징후

다음 로그 메시지가 보이면 토큰 문제입니다:

```
[DriveService] ✗ 토큰 갱신 실패: invalid_grant: Token has been expired or revoked.
[DriveService] 토큰이 만료되었습니다. 수동 재인증이 필요합니다.
[DriveService] 재인증 방법: python3 scripts/setup/oauth_setup.py 실행
```

### 예방 조치

1. **프로덕션 모드 유지**
   - OAuth 앱을 "프로덕션" 모드로 설정 (테스트 모드는 7일마다 만료)
   - Google Cloud Console → OAuth 동의 화면 → "앱 게시" 클릭

2. **정기 모니터링**
   - 헬스체크 스크립트를 크론탭에 등록
   - 로그 파일 주기적 확인: `logs/drive_health.log`

3. **백업 전략**
   - 로컬 사진 파일은 항상 보존 (`instance/photos/`)
   - Drive 업로드 실패 시에도 로컬 DB에 경로 기록
   - 나중에 수동으로 업로드 가능

## 트러블슈팅

### 1. Google Sheets 연동 오류

#### 증상: `Service Account not found`

**원인:** 서비스 계정이 Sheets에 공유되지 않음

**해결:**
```
1. Google Sheets 열기
2. "공유" 클릭
3. 서비스 계정 이메일 추가
   gym-sheets-service@프로젝트ID.iam.gserviceaccount.com
4. 권한: 편집자
```

#### 증상: `Insufficient Permission`

**원인:** 서비스 계정 권한 부족

**해결:**
```python
# scope에 drive 추가
scope = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'  # ← 추가
]
```

---

### 2. Google Drive 연동 오류

#### 증상: `Service Accounts do not have storage quota`

**원인:** 서비스 계정으로 Drive 업로드 시도

**해결:** OAuth 2.0으로 전환 (이 문서 참고)

#### 증상: `File not found: 폴더ID`

**원인:** OAuth Scope가 `drive.file`로 제한됨

**해결:**
```python
# Scope 변경
SCOPES = ['https://www.googleapis.com/auth/drive']  # ← 전체 권한
```

#### 증상: `invalid_grant` (토큰 만료)

**원인:** Refresh Token 무효화

**해결:**
```bash
# 토큰 삭제 후 재인증
rm instance/drive_token.pickle
python scripts/setup/oauth_setup.py
```

**근본 원인:**
- OAuth 앱이 테스트 모드 (7일 제한)
- → **프로덕션 모드로 전환 필수!**

---

### 3. OAuth 토큰 관리

#### 토큰 파일 경로

```
instance/drive_token.pickle
```

#### 토큰 수동 삭제 (재인증)

```bash
rm instance/drive_token.pickle
python scripts/setup/oauth_setup.py
```

#### 토큰 유효성 확인

```python
from app.services.drive_service import get_drive_service

drive = get_drive_service()
if drive.connect():
    print("✅ 토큰 유효")
else:
    print("❌ 재인증 필요")
```

#### Refresh Token 만료 조건

| 조건 | 해결책 |
|------|--------|
| **테스트 모드 7일** | 프로덕션 모드 전환 ✅ |
| **6개월 미사용** | 정기적으로 사용 |
| **사용자 권한 취소** | 재인증 |
| **보안 문제** | 재인증 |

---

### 4. 라즈베리파이 특수 상황

#### SSH 환경에서 OAuth 인증

**문제:** 브라우저가 없는 환경

**해결책 1: 로컬에서 인증 후 토큰 복사**

```bash
# 로컬 PC에서
python scripts/setup/oauth_setup.py
# → instance/drive_token.pickle 생성

# 라즈베리파이로 복사
scp instance/drive_token.pickle pi@라즈베리파이IP:~/프로젝트/instance/
```

**해결책 2: VNC로 접속**

```bash
# 라즈베리파이에 VNC 서버 실행
# VNC Viewer로 접속 후
python scripts/setup/oauth_setup.py
```

#### 재부팅 후 자동 연결

```python
# app/services/drive_service.py
def connect(self):
    # ... 기존 코드 ...
    
    # 토큰 갱신 실패 시 로깅
    if not credentials or not credentials.valid:
        if credentials and credentials.expired:
            if not credentials.refresh_token:
                logger.error("Refresh Token 없음 - 재인증 필요")
                # 알림 전송 로직 추가 가능
```

---

## 체크리스트

### Google Cloud 설정

- [ ] Google Cloud 프로젝트 생성
- [ ] Google Sheets API 활성화
- [ ] Google Drive API 활성화
- [ ] 서비스 계정 생성
- [ ] 서비스 계정 JSON 키 다운로드
- [ ] OAuth 동의 화면 설정
- [ ] OAuth 클라이언트 ID 생성
- [ ] **OAuth 프로덕션 모드 전환** ✅

### Google Sheets 설정

- [ ] 스프레드시트 생성
- [ ] 서비스 계정과 공유 (편집자)
- [ ] 스프레드시트 ID 복사
- [ ] `config/google_sheets_config.json` 작성

### Google Drive 설정

- [ ] 센터별 Gmail 계정 생성
- [ ] OAuth 테스트 사용자 추가
- [ ] Drive 폴더 생성
- [ ] 폴더 ID 복사
- [ ] `drive_service.py`에 폴더 ID 설정

### 코드 설정

- [ ] `google_credentials.json` 위치 확인
- [ ] `client_secret_xxxxx.json` 위치 확인
- [ ] `.gitignore` 업데이트
- [ ] 최초 OAuth 인증 실행
- [ ] `drive_token.pickle` 생성 확인

### 배포

- [ ] 라즈베리파이에 파일 복사
- [ ] 센터별 폴더 ID 설정
- [ ] OAuth 인증 실행
- [ ] 토큰 백업
- [ ] 테스트 업로드

---

## 참고 자료

### 공식 문서

- [Google Sheets API](https://developers.google.com/sheets/api)
- [Google Drive API](https://developers.google.com/drive/api)
- [OAuth 2.0](https://developers.google.com/identity/protocols/oauth2)
- [서비스 계정](https://cloud.google.com/iam/docs/service-accounts)

### 프로젝트 문서

- `docs/GOOGLE_SHEETS_SCHEMA.md` - Sheets 스키마
- `docs/DATABASE_SCHEMA.md` - SQLite 스키마
- `README.md` - 프로젝트 개요

---

## 버전 정보

- **작성일**: 2025-12-15
- **작성자**: AI Assistant
- **프로젝트**: 라즈베리파이 락카키 대여기 시스템
- **Google Cloud SDK**: 2.100.0+
- **Python**: 3.9+

---

## 라이선스

이 문서는 프로젝트와 동일한 라이선스를 따릅니다.

---

**다음 프로젝트에서 Google 연동 시 이 문서를 참고하세요!** 🎉

