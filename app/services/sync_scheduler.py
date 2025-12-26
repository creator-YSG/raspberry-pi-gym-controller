"""
동기화 스케줄러

백그라운드에서 주기적으로 Google Sheets 동기화 실행
- 회원 정보 다운로드: 5분마다 (설정에서 읽음)
- 대여/센서 업로드: 5분마다 (설정에서 읽음)
- 락카 상태 업데이트: 1분마다 (설정에서 읽음)
- 헬스장 설정 동기화: 다운로드 시 함께 수행
"""

import json
import threading
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.services.sheets_sync import SheetsSync
from app.services.integration_sync import IntegrationSync

logger = logging.getLogger(__name__)


def _load_sync_config() -> dict:
    """동기화 설정 로드 (config/google_sheets_config.json에서)"""
    config_path = Path(__file__).parent.parent.parent / "config" / "google_sheets_config.json"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config.get('sync_settings', {})
    except Exception as e:
        logger.warning(f"[SyncScheduler] 설정 로드 실패, 기본값 사용: {e}")
        return {}


class SyncScheduler:
    """동기화 스케줄러"""
    
    def __init__(self, sheets_sync: SheetsSync, db_manager,
                 integration_sync: IntegrationSync = None,
                 download_interval: int = None,
                 upload_interval: int = None,
                 locker_status_interval: int = None):
        """
        초기화
        
        Args:
            sheets_sync: SheetsSync 인스턴스
            db_manager: DatabaseManager 인스턴스
            integration_sync: IntegrationSync 인스턴스 (헬스장 설정 동기화)
            download_interval: 다운로드 동기화 간격 (초, None이면 설정에서 읽음)
            upload_interval: 업로드 동기화 간격 (초, None이면 설정에서 읽음)
            locker_status_interval: 락카 상태 동기화 간격 (초, None이면 설정에서 읽음)
        """
        self.sheets_sync = sheets_sync
        self.db_manager = db_manager
        self.integration_sync = integration_sync or IntegrationSync()
        
        # 설정에서 interval 읽기
        sync_config = _load_sync_config()
        self.download_interval = download_interval or sync_config.get('download_interval_sec', 300)
        self.upload_interval = upload_interval or sync_config.get('upload_interval_sec', 300)
        self.locker_status_interval = locker_status_interval or sync_config.get('device_status_interval_sec', 60)
        
        self._running = False
        self._threads = []
        
        # 동기화 통계
        self.stats = {
            'last_download': None,
            'last_upload': None,
            'last_locker_update': None,
            'last_gym_settings': None,
            'last_photo_upload': None,
            'download_count': 0,
            'upload_count': 0,
            'photo_upload_count': 0,
            'error_count': 0,
        }
        
        # DriveService (lazy init)
        self._drive_service = None
        
        logger.info(f"[SyncScheduler] 초기화 완료")
        logger.info(f"  - 다운로드 간격: {self.download_interval}초")
        logger.info(f"  - 업로드 간격: {self.upload_interval}초")
        logger.info(f"  - 락카 상태 간격: {self.locker_status_interval}초")
    
    def start(self):
        """스케줄러 시작"""
        if self._running:
            logger.warning("[SyncScheduler] 이미 실행 중")
            return
        
        self._running = True
        
        # 다운로드 동기화 스레드
        t1 = threading.Thread(target=self._download_sync_loop, daemon=True, name="SyncDownload")
        t1.start()
        self._threads.append(t1)
        
        # 업로드 동기화 스레드
        t2 = threading.Thread(target=self._upload_sync_loop, daemon=True, name="SyncUpload")
        t2.start()
        self._threads.append(t2)
        
        # 락카 상태 동기화 스레드
        t3 = threading.Thread(target=self._locker_status_sync_loop, daemon=True, name="SyncLockerStatus")
        t3.start()
        self._threads.append(t3)
        
        logger.info("[SyncScheduler] ✓ 시작됨")
    
    def stop(self):
        """스케줄러 중지"""
        self._running = False
        logger.info("[SyncScheduler] 중지됨")
    
    def _download_sync_loop(self):
        """다운로드 동기화 루프 (회원 정보, 설정)"""
        # 시작 시 초기 동기화
        time.sleep(5)  # 앱 시작 후 5초 대기
        
        while self._running:
            try:
                self._sync_downloads()
            except Exception as e:
                logger.error(f"[SyncScheduler] 다운로드 동기화 오류: {e}")
                self.stats['error_count'] += 1
            
            time.sleep(self.download_interval)
    
    def _upload_sync_loop(self):
        """업로드 동기화 루프 (대여 기록, 센서 이벤트)"""
        # 시작 시 10초 대기
        time.sleep(10)
        
        while self._running:
            try:
                self._sync_uploads()
            except Exception as e:
                logger.error(f"[SyncScheduler] 업로드 동기화 오류: {e}")
                self.stats['error_count'] += 1
            
            time.sleep(self.upload_interval)
    
    def _locker_status_sync_loop(self):
        """락카 상태 동기화 루프"""
        # 시작 시 15초 대기
        time.sleep(15)
        
        while self._running:
            try:
                self._sync_locker_status()
            except Exception as e:
                logger.error(f"[SyncScheduler] 락카 상태 동기화 오류: {e}")
                self.stats['error_count'] += 1
            
            time.sleep(self.locker_status_interval)
    
    def _sync_downloads(self):
        """다운로드 동기화 실행"""
        if not self.sheets_sync:
            return
        
        # 1. 락카키 시트에서 회원/설정 다운로드
        result = self.sheets_sync.sync_all_downloads(self.db_manager)
        
        if result:
            self.stats['last_download'] = datetime.now().isoformat()
            self.stats['download_count'] += 1
            
            total = sum(result.values())
            if total > 0:
                logger.info(f"[SyncScheduler] 다운로드 완료: 회원 {result.get('members', 0)}명, 설정 {result.get('settings', 0)}개")
        
        # 2. 통합 시트에서 헬스장 설정 다운로드
        try:
            if self.integration_sync:
                gym_settings = self.integration_sync.download_gym_settings(self.db_manager)
                if gym_settings:
                    self.stats['last_gym_settings'] = datetime.now().isoformat()
                    logger.info(f"[SyncScheduler] 헬스장 설정 동기화: {len(gym_settings)}개")
        except Exception as e:
            logger.error(f"[SyncScheduler] 헬스장 설정 동기화 실패: {e}")
    
    def _sync_uploads(self):
        """업로드 동기화 실행"""
        if not self.sheets_sync:
            return
        
        # 대여 기록 + 센서 이벤트 + 시스템 로그 업로드
        rentals = self.sheets_sync.upload_rentals(self.db_manager)
        sensor_events = self.sheets_sync.upload_sensor_events(self.db_manager)
        system_logs = self.sheets_sync.upload_system_logs(self.db_manager)
        
        if rentals > 0 or sensor_events > 0 or system_logs > 0:
            self.stats['last_upload'] = datetime.now().isoformat()
            self.stats['upload_count'] += 1
            logger.info(f"[SyncScheduler] 업로드 완료: 대여 {rentals}건, 센서 {sensor_events}건, 로그 {system_logs}건")
        
        # Pending 사진 드라이브 업로드 (photo_path 있지만 photo_url 없는 레코드)
        try:
            photo_count = self._upload_pending_photos()
            if photo_count > 0:
                self.stats['last_photo_upload'] = datetime.now().isoformat()
                self.stats['photo_upload_count'] += photo_count
        except Exception as e:
            logger.error(f"[SyncScheduler] 사진 업로드 오류: {e}")
    
    def _upload_pending_photos(self) -> int:
        """
        Pending 사진 업로드 (photo_path 있지만 photo_url 없는 레코드)
        드라이브 업로드 후 DB와 구글시트 업데이트
        
        Returns:
            업로드 성공 건수
        """
        from pathlib import Path
        
        # DriveService lazy init
        if self._drive_service is None:
            try:
                from app.services.drive_service import DriveService
                self._drive_service = DriveService()
            except Exception as e:
                logger.warning(f"[SyncScheduler] DriveService 초기화 실패: {e}")
                return 0
        
        # 드라이브 연결 확인
        if not self._drive_service.connect():
            logger.debug("[SyncScheduler] 드라이브 연결 실패, 사진 업로드 스킵")
            return 0
        
        # Pending 레코드 조회 (photo_path 있고 photo_url 없는 것)
        try:
            cursor = self.db_manager.execute_query("""
                SELECT rental_id, rental_photo_path 
                FROM rentals 
                WHERE rental_photo_path IS NOT NULL 
                  AND rental_photo_path != ''
                  AND (rental_photo_url IS NULL OR rental_photo_url = '')
                ORDER BY rental_id
                LIMIT 10
            """)
            
            if not cursor:
                return 0
            
            pending_records = cursor.fetchall()
            if not pending_records:
                return 0
            
            logger.info(f"[SyncScheduler] 📸 Pending 사진 {len(pending_records)}건 발견")
            
        except Exception as e:
            logger.error(f"[SyncScheduler] Pending 사진 조회 실패: {e}")
            return 0
        
        uploaded_count = 0
        
        for record in pending_records:
            rental_id = record[0]
            photo_path = record[1]
            
            # 파일 존재 확인
            full_path = Path(photo_path)
            if not full_path.exists():
                # 프로젝트 루트 기준 경로 시도
                project_root = Path(__file__).parent.parent.parent
                full_path = project_root / photo_path
            
            if not full_path.exists():
                logger.warning(f"[SyncScheduler] 사진 파일 없음: {photo_path}")
                continue
            
            try:
                # 드라이브 업로드
                # 폴더 경로 추출 (예: instance/photos/rentals/2025/12/xxx.jpg → rentals/2025/12)
                path_parts = Path(photo_path).parts
                if 'rentals' in path_parts:
                    idx = path_parts.index('rentals')
                    drive_folder = '/'.join(path_parts[idx:-1])  # rentals/2025/12
                else:
                    drive_folder = 'rentals'
                
                drive_url = self._drive_service.upload_file(
                    str(full_path),
                    drive_folder=drive_folder,
                    max_retries=2
                )
                
                if drive_url:
                    # DB 업데이트
                    self.db_manager.execute_query("""
                        UPDATE rentals 
                        SET rental_photo_url = ?
                        WHERE rental_id = ?
                    """, (drive_url, rental_id))
                    self.db_manager.conn.commit()
                    
                    # 구글시트 업데이트
                    try:
                        self.sheets_sync.update_rental_photo(rental_id, photo_path, drive_url)
                    except Exception as sheet_err:
                        logger.warning(f"[SyncScheduler] 시트 업데이트 실패 (rental_id={rental_id}): {sheet_err}")
                    
                    uploaded_count += 1
                    logger.info(f"[SyncScheduler] ✅ 사진 업로드 완료: rental_id={rental_id}")
                else:
                    logger.warning(f"[SyncScheduler] 사진 업로드 실패: rental_id={rental_id}")
                    
            except Exception as e:
                logger.error(f"[SyncScheduler] 사진 업로드 오류 (rental_id={rental_id}): {e}")
        
        if uploaded_count > 0:
            logger.info(f"[SyncScheduler] 📸 총 {uploaded_count}건 사진 업로드 완료")
        
        return uploaded_count
    
    def _sync_locker_status(self):
        """락카 상태 동기화 실행"""
        if not self.sheets_sync:
            return
        
        count = self.sheets_sync.upload_locker_status(self.db_manager)
        
        if count > 0:
            self.stats['last_locker_update'] = datetime.now().isoformat()
    
    def sync_now(self):
        """즉시 전체 동기화 실행"""
        logger.info("[SyncScheduler] 즉시 동기화 시작...")
        
        try:
            self._sync_downloads()
            self._sync_uploads()
            self._sync_locker_status()
            logger.info("[SyncScheduler] 즉시 동기화 완료")
            return {'success': True, 'message': '동기화 완료'}
        except Exception as e:
            logger.error(f"[SyncScheduler] 즉시 동기화 오류: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_status(self) -> dict:
        """스케줄러 상태 정보"""
        return {
            'running': self._running,
            'threads_alive': sum(1 for t in self._threads if t.is_alive()),
            'intervals': {
                'download': self.download_interval,
                'upload': self.upload_interval,
                'locker_status': self.locker_status_interval,
            },
            'stats': self.stats.copy(),
            'sheets_status': self.sheets_sync.get_status() if self.sheets_sync else None,
        }


# 전역 스케줄러 인스턴스
_scheduler: Optional[SyncScheduler] = None


def get_scheduler() -> Optional[SyncScheduler]:
    """전역 스케줄러 인스턴스 반환"""
    return _scheduler


def init_scheduler(db_manager, auto_start: bool = True) -> Optional[SyncScheduler]:
    """
    스케줄러 초기화 및 시작
    
    Args:
        db_manager: DatabaseManager 인스턴스
        auto_start: 자동 시작 여부
    
    Returns:
        SyncScheduler 인스턴스 또는 None (실패 시)
    """
    global _scheduler
    
    try:
        # SheetsSync 초기화 (락카키 시트)
        sheets_sync = SheetsSync()
        
        # 연결 테스트
        if not sheets_sync.connect():
            logger.warning("[SyncScheduler] Google Sheets 연결 실패, 오프라인 모드로 실행")
            # 연결 실패해도 스케줄러는 생성 (나중에 재연결 시도)
        
        # IntegrationSync 초기화 (통합 시트)
        integration_sync = IntegrationSync()
        # 연결은 필요 시 자동으로 수행됨
        
        # 스케줄러 생성 (interval은 config에서 자동으로 읽음)
        _scheduler = SyncScheduler(
            sheets_sync=sheets_sync,
            db_manager=db_manager,
            integration_sync=integration_sync
        )
        
        if auto_start:
            _scheduler.start()
        
        return _scheduler
        
    except Exception as e:
        logger.error(f"[SyncScheduler] 초기화 실패: {e}")
        return None


def stop_scheduler():
    """스케줄러 중지"""
    global _scheduler
    if _scheduler:
        _scheduler.stop()
        _scheduler = None

