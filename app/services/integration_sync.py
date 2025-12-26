"""
시스템 간 통합을 위한 구글 시트 동기화
락카키 대여기 ↔ 운동복 대여기 간 통신 정보 공유
+ 헬스장 공통 설정 (gym_name, admin_password) 동기화
"""

import json
import socket
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

logger = logging.getLogger(__name__)


class IntegrationSync:
    """시스템 통합 정보 동기화"""
    
    # 기본 System_Integration 시트 ID (설정 파일에서 오버라이드 가능)
    DEFAULT_INTEGRATION_SHEET_ID = "15qpiY1r_SEK6b2dr00UDmKrYHSVuGMmiMeTZ898Lv8Q"
    
    def __init__(self, config_path: str = None):
        """초기화
        
        Args:
            config_path: 설정 파일 경로 (기본: config/google_sheets_config.json)
        """
        self.project_root = Path(__file__).parent.parent.parent
        self.credentials_path = self.project_root / "config" / "google_credentials.json"
        self.cache_file = self.project_root / "config" / "locker_api_cache.json"
        
        # 설정 로드
        if config_path is None:
            config_path = self.project_root / "config" / "google_sheets_config.json"
        self.config = self._load_config(config_path)
        
        # 통합 시트 ID (설정 파일에서 읽거나 기본값 사용)
        self.integration_sheet_id = self.config.get(
            'integration_sheet_id', 
            self.DEFAULT_INTEGRATION_SHEET_ID
        )
        
        # 시트 이름 매핑
        self.sheet_names = self.config.get('integration_sheet_names', {
            'gym_settings': '헬스장설정',
            'device_info': '시트1'
        })
        
        self.client = None
        self.spreadsheet = None
        self.connected = False
        
        logger.info(f"[IntegrationSync] 초기화 (시트 ID: {self.integration_sheet_id[:20]}...)")
    
    def _load_config(self, config_path) -> dict:
        """설정 파일 로드"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"[IntegrationSync] 설정 파일 로드 실패: {e}")
            return {}
    
    def connect(self) -> bool:
        """구글 시트 연결"""
        if not GSPREAD_AVAILABLE:
            logger.warning("[IntegrationSync] gspread 없음")
            return False
        
        try:
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            
            credentials = Credentials.from_service_account_file(
                str(self.credentials_path), scopes=scope
            )
            
            self.client = gspread.authorize(credentials)
            self.spreadsheet = self.client.open_by_key(self.integration_sheet_id)
            self.connected = True
            
            logger.info(f"[IntegrationSync] ✅ 연결 성공: {self.spreadsheet.title}")
            return True
            
        except Exception as e:
            logger.error(f"[IntegrationSync] ❌ 연결 실패: {e}")
            self.connected = False
            return False
    
    def get_local_ip(self) -> str:
        """내부망 IP 자동 감지"""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # 외부 서버에 연결 시도 (실제 연결은 안 함)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
        except Exception:
            ip = '127.0.0.1'
        finally:
            s.close()
        return ip
    
    # =============================
    # 헬스장 설정 동기화
    # =============================
    
    def download_gym_settings(self, db_manager=None) -> Dict[str, str]:
        """헬스장 설정 다운로드 (gym_name, admin_password 등)
        
        Args:
            db_manager: DatabaseManager 인스턴스 (DB에 저장할 경우)
            
        Returns:
            설정 딕셔너리 {'gym_name': '...', 'admin_password': '...'}
        """
        if not self.connected:
            if not self.connect():
                logger.warning("[IntegrationSync] 연결 실패, 캐시에서 로드")
                return self._load_gym_settings_cache()
        
        try:
            sheet_name = self.sheet_names.get('gym_settings', '헬스장설정')
            worksheet = self.spreadsheet.worksheet(sheet_name)
            
            records = worksheet.get_all_records()
            
            settings = {}
            for record in records:
                key = record.get('setting_key')
                value = record.get('setting_value')
                if key and value is not None:
                    settings[key] = str(value)
                    
                    # DB에 저장
                    if db_manager:
                        try:
                            db_manager.execute_query("""
                                INSERT OR REPLACE INTO system_settings 
                                (setting_key, setting_value, setting_type, description, updated_at)
                                VALUES (?, ?, ?, ?, ?)
                            """, (
                                key,
                                str(value),
                                record.get('setting_type', 'string'),
                                record.get('description', ''),
                                datetime.now().isoformat()
                            ))
                        except Exception as e:
                            logger.error(f"[IntegrationSync] DB 저장 실패: {key}, {e}")
            
            # 캐시 저장
            self._save_gym_settings_cache(settings)
            
            logger.info(f"[IntegrationSync] ✅ 헬스장 설정 다운로드 완료: {len(settings)}개")
            return settings
            
        except Exception as e:
            logger.error(f"[IntegrationSync] ❌ 헬스장 설정 다운로드 실패: {e}")
            return self._load_gym_settings_cache()
    
    def _save_gym_settings_cache(self, settings: dict):
        """헬스장 설정 캐시 저장"""
        cache_file = self.project_root / "config" / "gym_settings_cache.json"
        try:
            data = {
                'settings': settings,
                'cached_at': datetime.now().isoformat()
            }
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[IntegrationSync] 설정 캐시 저장 실패: {e}")
    
    def _load_gym_settings_cache(self) -> Dict[str, str]:
        """헬스장 설정 캐시 로드"""
        cache_file = self.project_root / "config" / "gym_settings_cache.json"
        try:
            if cache_file.exists():
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return data.get('settings', {})
        except Exception as e:
            logger.error(f"[IntegrationSync] 설정 캐시 로드 실패: {e}")
        
        # 기본값 반환
        return {
            'gym_name': '헬스장',
            'admin_password': '1234'
        }
    
    # =============================
    # 디바이스 정보 동기화 (기존 기능)
    # =============================
    
    def initialize_sheet_headers(self):
        """시트 헤더 초기화 (최초 1회)"""
        if not self.connected:
            if not self.connect():
                return False
        
        try:
            # 첫 번째 워크시트 가져오기
            worksheet = self.spreadsheet.sheet1
            
            # 헤더 작성
            headers = [
                'locker_api_host',
                'locker_api_port', 
                'last_updated',
                'status',
                'notes'
            ]
            
            # 첫 번째 행에 헤더 쓰기
            worksheet.update(range_name='A1:E1', values=[headers])
            
            # 헤더 행 서식 설정 (볼드, 배경색)
            worksheet.format('A1:E1', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
            })
            
            logger.info("[IntegrationSync] ✅ 헤더 초기화 완료")
            print("✅ System_Integration 시트 헤더 작성 완료!")
            return True
            
        except Exception as e:
            logger.error(f"[IntegrationSync] ❌ 헤더 초기화 실패: {e}")
            return False
    
    def upload_locker_api_info(self) -> bool:
        """락카키 대여기 IP를 시트에 업로드"""
        if not self.connected:
            if not self.connect():
                return False
        
        try:
            # 로컬 IP 감지
            ip = self.get_local_ip()
            port = 5000
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 데이터 준비
            data = [ip, port, timestamp, 'active', '락카키 대여기']
            
            # 워크시트 가져오기
            worksheet = self.spreadsheet.sheet1
            
            # 기존 데이터 확인 (2번째 행부터)
            existing_data = worksheet.get_all_values()
            
            if len(existing_data) <= 1:
                # 데이터 없음 → 2번째 행에 추가
                worksheet.update(range_name='A2:E2', values=[data])
                logger.info(f"[IntegrationSync] ✅ IP 추가: {ip}:{port}")
            else:
                # 데이터 있음 → 2번째 행 업데이트
                worksheet.update(range_name='A2:E2', values=[data])
                logger.info(f"[IntegrationSync] ✅ IP 업데이트: {ip}:{port}")
            
            print(f"✅ 락카키 대여기 IP 업로드 완료: {ip}:{port}")
            return True
            
        except Exception as e:
            logger.error(f"[IntegrationSync] ❌ IP 업로드 실패: {e}")
            print(f"❌ IP 업로드 실패: {e}")
            return False
    
    def download_locker_api_info(self) -> dict:
        """락카키 대여기 IP를 시트에서 다운로드 (운동복 대여기용)"""
        if not self.connected:
            if not self.connect():
                return self._load_cache()
        
        try:
            worksheet = self.spreadsheet.sheet1
            
            # 2번째 행 읽기 (데이터)
            values = worksheet.get('A2:E2')
            
            if not values or not values[0]:
                logger.warning("[IntegrationSync] ⚠️ 데이터 없음")
                return self._load_cache()
            
            row = values[0]
            
            if len(row) < 2:
                logger.warning("[IntegrationSync] ⚠️ 불완전한 데이터")
                return self._load_cache()
            
            locker_api = {
                'host': row[0],
                'port': int(row[1]) if len(row) > 1 else 5000,
                'url': f"http://{row[0]}:{row[1] if len(row) > 1 else 5000}",
                'last_updated': row[2] if len(row) > 2 else '',
                'status': row[3] if len(row) > 3 else 'unknown'
            }
            
            # 캐시 저장
            self._save_cache(locker_api)
            
            logger.info(f"[IntegrationSync] ✅ IP 다운로드: {locker_api['url']}")
            return locker_api
            
        except Exception as e:
            logger.error(f"[IntegrationSync] ❌ IP 다운로드 실패: {e}")
            return self._load_cache()
    
    def _save_cache(self, data: dict):
        """로컬 캐시 저장"""
        try:
            data['cached_at'] = datetime.now().isoformat()
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info("[IntegrationSync] 캐시 저장 완료")
        except Exception as e:
            logger.error(f"[IntegrationSync] 캐시 저장 실패: {e}")
    
    def _load_cache(self) -> dict:
        """로컬 캐시 읽기"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.info(f"[IntegrationSync] 📦 캐시 로드: {data.get('url', 'N/A')}")
                return data
        except Exception as e:
            logger.error(f"[IntegrationSync] 캐시 로드 실패: {e}")
        
        return {
            'host': '192.168.0.23',
            'port': 5000,
            'url': 'http://192.168.0.23:5000',
            'status': 'unknown'
        }


# 싱글톤 인스턴스
_integration_sync: Optional[IntegrationSync] = None


def get_integration_sync() -> IntegrationSync:
    """IntegrationSync 싱글톤 인스턴스 반환"""
    global _integration_sync
    if _integration_sync is None:
        _integration_sync = IntegrationSync()
    return _integration_sync
