"""
Google Drive 업로드 서비스 (OAuth 2.0)

사진 파일을 구글 드라이브에 업로드하고 공유 URL 반환
- OAuth 2.0 사용자 인증 방식 (개인 계정 저장 공간 사용)
- 인증 사진: rentals/{year}/{month}/ 폴더에 업로드
- 회원 사진: members/ 폴더에 업로드
"""

import logging
import pickle
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger(__name__)

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    DRIVE_AVAILABLE = True
except ImportError:
    DRIVE_AVAILABLE = False
    logger.warning("[DriveService] google-api-python-client 또는 google-auth-oauthlib 없음, 스텁 모드")


class DriveService:
    """Google Drive 업로드 서비스 (OAuth 2.0)"""
    
    # OAuth scopes
    SCOPES = ['https://www.googleapis.com/auth/drive']
    
    # 루트 폴더 ID (락카키대여기-사진)
    ROOT_FOLDER_ID = "1fTnW_MSrzMaWXpA5lPYJ9Ce9rUMu4wWL"
    
    def __init__(self, oauth_credentials_path: str = None, token_path: str = None):
        """
        Args:
            oauth_credentials_path: OAuth 클라이언트 인증 파일 경로
            token_path: 저장된 토큰 파일 경로 (자동 생성됨)
        """
        self.project_root = Path(__file__).parent.parent.parent
        
        if oauth_credentials_path is None:
            oauth_credentials_path = self.project_root / "client_secret_59516272673-h30ecghk38d912tkcal5k3mkgpqm11ad.apps.googleusercontent.com.json"
        
        if token_path is None:
            token_path = self.project_root / "instance" / "drive_token.pickle"
        
        self.oauth_credentials_path = Path(oauth_credentials_path)
        self.token_path = Path(token_path)
        self.service = None
        self.connected = False
        
        # 폴더 ID 캐시
        self._folder_cache: Dict[str, str] = {}
        self._root_folder_id: Optional[str] = self.ROOT_FOLDER_ID
        
        # 업로드 큐 (백그라운드 처리용)
        self._upload_queue = []
        self._upload_thread: Optional[threading.Thread] = None
        self._upload_lock = threading.Lock()
        
    def connect(self) -> bool:
        """Google Drive API 연결 (OAuth 2.0)
        
        토큰 만료 시 자동 갱신 처리:
        1. 저장된 토큰 로드
        2. 만료 시 refresh_token으로 자동 갱신
        3. 갱신 실패 시 토큰 삭제 (수동 재인증 필요)
        """
        if not DRIVE_AVAILABLE:
            logger.warning("[DriveService] google-api-python-client 없음")
            return False
        
        try:
            credentials = None
            
            # 저장된 토큰이 있으면 로드
            if self.token_path.exists():
                try:
                    with open(self.token_path, 'rb') as token:
                        credentials = pickle.load(token)
                        logger.info("[DriveService] 저장된 토큰 로드")
                except Exception as e:
                    logger.error(f"[DriveService] 토큰 로드 실패: {e}")
                    # 손상된 토큰 파일 삭제
                    self.token_path.unlink(missing_ok=True)
                    credentials = None
            
            # 토큰이 없거나 만료되었으면 갱신/재인증
            if not credentials or not credentials.valid:
                if credentials and credentials.expired and credentials.refresh_token:
                    try:
                        logger.info("[DriveService] 토큰 갱신 시도...")
                        credentials.refresh(Request())
                        logger.info("[DriveService] ✓ 토큰 갱신 성공")
                        
                        # 갱신된 토큰 저장
                        self.token_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(self.token_path, 'wb') as token:
                            pickle.dump(credentials, token)
                            logger.info(f"[DriveService] 갱신된 토큰 저장: {self.token_path}")
                            
                    except Exception as refresh_error:
                        logger.error(f"[DriveService] ✗ 토큰 갱신 실패: {refresh_error}")
                        # 갱신 실패 시 토큰 삭제 (재인증 필요)
                        self.token_path.unlink(missing_ok=True)
                        logger.warning("[DriveService] 토큰이 만료되었습니다. 수동 재인증이 필요합니다.")
                        logger.warning(f"[DriveService] 재인증 방법: python3 scripts/setup/oauth_setup.py 실행")
                        self.connected = False
                        return False
                else:
                    logger.warning("[DriveService] OAuth 토큰이 없습니다. 최초 인증이 필요합니다.")
                    logger.warning(f"[DriveService] 인증 방법: python3 scripts/setup/oauth_setup.py 실행")
                    self.connected = False
                    return False
            
            # Drive API 서비스 생성
            self.service = build('drive', 'v3', credentials=credentials)
            self.connected = True
            
            logger.info("[DriveService] ✓ 연결 성공 (OAuth)")
            
            # 루트 폴더 확인/생성
            self._ensure_root_folder()
            
            return True
            
        except Exception as e:
            logger.error(f"[DriveService] ✗ 연결 실패: {e}")
            self.connected = False
            return False
    
    def _ensure_root_folder(self):
        """루트 폴더 확인 (고정 폴더 ID 사용)"""
        try:
            # 폴더 접근 권한 확인
            folder = self.service.files().get(
                fileId=self.ROOT_FOLDER_ID, 
                fields='id, name'
            ).execute()
            
            logger.info(f"[DriveService] 루트 폴더 확인: {folder.get('name')} ({self.ROOT_FOLDER_ID})")
            self._root_folder_id = self.ROOT_FOLDER_ID
                
        except Exception as e:
            logger.error(f"[DriveService] 루트 폴더 접근 실패: {e}")
            logger.error("폴더 권한을 확인하세요")
    
    def _get_or_create_folder(self, folder_path: str) -> Optional[str]:
        """폴더 경로에 해당하는 폴더 ID 반환 (없으면 생성)
        
        Args:
            folder_path: 폴더 경로 (예: "rentals/2025/12")
            
        Returns:
            폴더 ID 또는 None
        """
        if folder_path in self._folder_cache:
            return self._folder_cache[folder_path]
        
        if not self._root_folder_id:
            return None
        
        try:
            parent_id = self._root_folder_id
            path_parts = folder_path.split('/')
            
            for part in path_parts:
                if not part:
                    continue
                    
                cache_key = '/'.join(path_parts[:path_parts.index(part) + 1])
                
                if cache_key in self._folder_cache:
                    parent_id = self._folder_cache[cache_key]
                    continue
                
                # 폴더 검색
                query = f"name='{part}' and '{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
                results = self.service.files().list(q=query, fields="files(id)").execute()
                files = results.get('files', [])
                
                if files:
                    parent_id = files[0]['id']
                else:
                    # 폴더 생성
                    folder_metadata = {
                        'name': part,
                        'mimeType': 'application/vnd.google-apps.folder',
                        'parents': [parent_id]
                    }
                    folder = self.service.files().create(body=folder_metadata, fields='id').execute()
                    parent_id = folder.get('id')
                
                self._folder_cache[cache_key] = parent_id
            
            return parent_id
            
        except Exception as e:
            logger.error(f"[DriveService] 폴더 생성 실패: {folder_path}, {e}")
            return None
    
    def upload_file(self, local_path: str, drive_folder: str = "", 
                    filename: str = None, max_retries: int = 3) -> Optional[str]:
        """파일 업로드 (동기, 재시도 지원)
        
        Args:
            local_path: 로컬 파일 경로
            drive_folder: 드라이브 폴더 경로 (예: "rentals/2025/12")
            filename: 드라이브에 저장할 파일명 (None이면 원본 이름)
            max_retries: 최대 재시도 횟수 (기본 3회)
            
        Returns:
            공유 URL 또는 None
        """
        if not self.connected:
            if not self.connect():
                logger.warning("[DriveService] 연결 실패. 로컬 저장만 수행됩니다.")
                return None
        
        local_path = Path(local_path)
        
        if not local_path.exists():
            logger.error(f"[DriveService] 파일 없음: {local_path}")
            return None
        
        # 재시도 로직
        for attempt in range(1, max_retries + 1):
            try:
                # 폴더 ID 가져오기
                if drive_folder:
                    folder_id = self._get_or_create_folder(drive_folder)
                else:
                    folder_id = self._root_folder_id
                
                if not folder_id:
                    logger.error(f"[DriveService] 폴더 ID 없음: {drive_folder}")
                    return None
                
                # 파일 메타데이터
                file_name = filename or local_path.name
                file_metadata = {
                    'name': file_name,
                    'parents': [folder_id]
                }
                
                # 파일 업로드
                media = MediaFileUpload(str(local_path), mimetype='image/jpeg')
                file = self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id, webViewLink'
                ).execute()
                
                file_id = file.get('id')
                
                # 공유 설정 (링크가 있는 사람은 누구나 볼 수 있음)
                self.service.permissions().create(
                    fileId=file_id,
                    body={'type': 'anyone', 'role': 'reader'}
                ).execute()
                
                # 공유 URL
                web_view_link = file.get('webViewLink')
                
                logger.info(f"[DriveService] ✓ 업로드 성공 ({attempt}/{max_retries}): {file_name}")
                return web_view_link
                
            except Exception as e:
                logger.error(f"[DriveService] ✗ 업로드 실패 ({attempt}/{max_retries}): {local_path}, {e}")
                
                # 토큰 만료 에러인 경우 재연결 시도
                if 'invalid_grant' in str(e) or 'Token has been expired' in str(e):
                    logger.warning("[DriveService] 토큰 만료 감지. 재연결 시도...")
                    self.connected = False
                    if not self.connect():
                        logger.error("[DriveService] 재연결 실패. 수동 재인증 필요.")
                        return None
                
                # 마지막 시도가 아니면 재시도
                if attempt < max_retries:
                    import time
                    wait_time = 2 ** attempt  # 지수 백오프 (2초, 4초, 8초)
                    logger.info(f"[DriveService] {wait_time}초 후 재시도...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"[DriveService] 최대 재시도 횟수 초과. 업로드 포기: {local_path}")
                    return None
        
        return None
    
    def upload_rental_photo(self, local_path: str, rental_id: str = None) -> Optional[str]:
        """인증 사진 업로드
        
        Args:
            local_path: 로컬 파일 경로
            rental_id: 대여 ID (파일명에 포함)
            
        Returns:
            공유 URL 또는 None
        """
        now = datetime.now()
        folder_path = f"rentals/{now.year}/{now.month:02d}"
        
        return self.upload_file(local_path, folder_path)
    
    def upload_member_photo(self, local_path: str, member_id: str) -> Optional[str]:
        """회원 확인용 사진 업로드
        
        Args:
            local_path: 로컬 파일 경로
            member_id: 회원 ID
            
        Returns:
            공유 URL 또는 None
        """
        return self.upload_file(local_path, "members", f"{member_id}.jpg")
    
    def upload_async(self, local_path: str, drive_folder: str, 
                     callback=None) -> None:
        """비동기 업로드 (백그라운드)
        
        Args:
            local_path: 로컬 파일 경로
            drive_folder: 드라이브 폴더 경로
            callback: 완료 시 호출할 함수 (url을 인자로 받음)
        """
        with self._upload_lock:
            self._upload_queue.append({
                'local_path': local_path,
                'drive_folder': drive_folder,
                'callback': callback
            })
        
        # 업로드 스레드가 없으면 시작
        if self._upload_thread is None or not self._upload_thread.is_alive():
            self._upload_thread = threading.Thread(
                target=self._process_upload_queue, 
                daemon=True
            )
            self._upload_thread.start()
    
    def _process_upload_queue(self):
        """업로드 큐 처리 (백그라운드)"""
        while True:
            with self._upload_lock:
                if not self._upload_queue:
                    break
                task = self._upload_queue.pop(0)
            
            try:
                url = self.upload_file(
                    task['local_path'], 
                    task['drive_folder']
                )
                
                if task['callback']:
                    task['callback'](url)
                    
            except Exception as e:
                logger.error(f"[DriveService] 비동기 업로드 실패: {e}")
    
    def get_status(self) -> Dict:
        """서비스 상태 반환"""
        return {
            'connected': self.connected,
            'available': DRIVE_AVAILABLE,
            'root_folder_id': self._root_folder_id,
            'folder_cache_count': len(self._folder_cache),
            'pending_uploads': len(self._upload_queue)
        }


# 싱글톤 인스턴스
_drive_service: Optional[DriveService] = None


def get_drive_service() -> DriveService:
    """DriveService 싱글톤 인스턴스 반환"""
    global _drive_service
    
    if _drive_service is None:
        _drive_service = DriveService()
        _drive_service.connect()  # 자동 연결
        
    return _drive_service
