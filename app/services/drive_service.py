"""
Google Drive 업로드 서비스

사진 파일을 구글 드라이브에 업로드하고 공유 URL 반환
- 인증 사진: rentals/{year}/{month}/ 폴더에 업로드
- 회원 사진: members/ 폴더에 업로드
"""

import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger(__name__)

try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    DRIVE_AVAILABLE = True
except ImportError:
    DRIVE_AVAILABLE = False
    logger.warning("[DriveService] google-api-python-client 없음, 스텁 모드")


class DriveService:
    """Google Drive 업로드 서비스"""
    
    # 드라이브 폴더 ID (초기화 시 설정 또는 자동 생성)
    ROOT_FOLDER_NAME = "락카키대여기-사진"
    
    def __init__(self, credentials_path: str = None):
        """
        Args:
            credentials_path: 서비스 계정 인증 파일 경로
        """
        self.project_root = Path(__file__).parent.parent.parent
        
        if credentials_path is None:
            credentials_path = self.project_root / "config" / "google_credentials.json"
        
        self.credentials_path = Path(credentials_path)
        self.service = None
        self.connected = False
        
        # 폴더 ID 캐시
        self._folder_cache: Dict[str, str] = {}
        self._root_folder_id: Optional[str] = None
        
        # 업로드 큐 (백그라운드 처리용)
        self._upload_queue = []
        self._upload_thread: Optional[threading.Thread] = None
        self._upload_lock = threading.Lock()
        
    def connect(self) -> bool:
        """Google Drive API 연결"""
        if not DRIVE_AVAILABLE:
            logger.warning("[DriveService] google-api-python-client 없음")
            return False
        
        try:
            scope = ['https://www.googleapis.com/auth/drive.file']
            
            credentials = Credentials.from_service_account_file(
                str(self.credentials_path), scopes=scope
            )
            
            self.service = build('drive', 'v3', credentials=credentials)
            self.connected = True
            
            logger.info("[DriveService] ✓ 연결 성공")
            
            # 루트 폴더 확인/생성
            self._ensure_root_folder()
            
            return True
            
        except Exception as e:
            logger.error(f"[DriveService] ✗ 연결 실패: {e}")
            self.connected = False
            return False
    
    def _ensure_root_folder(self):
        """루트 폴더 확인/생성"""
        try:
            # 기존 폴더 검색
            query = f"name='{self.ROOT_FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = self.service.files().list(q=query, fields="files(id, name)").execute()
            files = results.get('files', [])
            
            if files:
                self._root_folder_id = files[0]['id']
                logger.info(f"[DriveService] 루트 폴더 발견: {self._root_folder_id}")
            else:
                # 폴더 생성
                folder_metadata = {
                    'name': self.ROOT_FOLDER_NAME,
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                folder = self.service.files().create(body=folder_metadata, fields='id').execute()
                self._root_folder_id = folder.get('id')
                logger.info(f"[DriveService] 루트 폴더 생성: {self._root_folder_id}")
                
        except Exception as e:
            logger.error(f"[DriveService] 루트 폴더 확인/생성 실패: {e}")
    
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
                    filename: str = None) -> Optional[str]:
        """파일 업로드 (동기)
        
        Args:
            local_path: 로컬 파일 경로
            drive_folder: 드라이브 폴더 경로 (예: "rentals/2025/12")
            filename: 드라이브에 저장할 파일명 (None이면 원본 이름)
            
        Returns:
            공유 URL 또는 None
        """
        if not self.connected:
            if not self.connect():
                return None
        
        local_path = Path(local_path)
        
        if not local_path.exists():
            logger.error(f"[DriveService] 파일 없음: {local_path}")
            return None
        
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
            
            logger.info(f"[DriveService] 업로드 완료: {file_name} → {web_view_link}")
            return web_view_link
            
        except Exception as e:
            logger.error(f"[DriveService] 업로드 실패: {local_path}, {e}")
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
        
    return _drive_service

