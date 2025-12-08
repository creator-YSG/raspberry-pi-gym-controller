"""
동기화 스케줄러

백그라운드에서 주기적으로 Google Sheets 동기화 실행
- 회원 정보 다운로드: 5분마다
- 대여/센서 업로드: 5분마다
- 락카 상태 업데이트: 1분마다
"""

import threading
import time
import logging
from datetime import datetime
from typing import Optional

from app.services.sheets_sync import SheetsSync

logger = logging.getLogger(__name__)


class SyncScheduler:
    """동기화 스케줄러"""
    
    def __init__(self, sheets_sync: SheetsSync, db_manager,
                 download_interval: int = 300,
                 upload_interval: int = 300,
                 locker_status_interval: int = 60):
        """
        초기화
        
        Args:
            sheets_sync: SheetsSync 인스턴스
            db_manager: DatabaseManager 인스턴스
            download_interval: 다운로드 동기화 간격 (초, 기본 5분)
            upload_interval: 업로드 동기화 간격 (초, 기본 5분)
            locker_status_interval: 락카 상태 동기화 간격 (초, 기본 1분)
        """
        self.sheets_sync = sheets_sync
        self.db_manager = db_manager
        
        self.download_interval = download_interval
        self.upload_interval = upload_interval
        self.locker_status_interval = locker_status_interval
        
        self._running = False
        self._threads = []
        
        # 동기화 통계
        self.stats = {
            'last_download': None,
            'last_upload': None,
            'last_locker_update': None,
            'download_count': 0,
            'upload_count': 0,
            'error_count': 0,
        }
        
        logger.info(f"[SyncScheduler] 초기화 완료")
        logger.info(f"  - 다운로드 간격: {download_interval}초")
        logger.info(f"  - 업로드 간격: {upload_interval}초")
        logger.info(f"  - 락카 상태 간격: {locker_status_interval}초")
    
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
        
        result = self.sheets_sync.sync_all_downloads(self.db_manager)
        
        if result:
            self.stats['last_download'] = datetime.now().isoformat()
            self.stats['download_count'] += 1
            
            total = sum(result.values())
            if total > 0:
                logger.info(f"[SyncScheduler] 다운로드 완료: 회원 {result.get('members', 0)}명, 설정 {result.get('settings', 0)}개")
    
    def _sync_uploads(self):
        """업로드 동기화 실행"""
        if not self.sheets_sync:
            return
        
        # 대여 기록 + 센서 이벤트 업로드
        rentals = self.sheets_sync.upload_rentals(self.db_manager)
        sensor_events = self.sheets_sync.upload_sensor_events(self.db_manager)
        
        if rentals > 0 or sensor_events > 0:
            self.stats['last_upload'] = datetime.now().isoformat()
            self.stats['upload_count'] += 1
            logger.info(f"[SyncScheduler] 업로드 완료: 대여 {rentals}건, 센서 {sensor_events}건")
    
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
        # SheetsSync 초기화
        sheets_sync = SheetsSync()
        
        # 연결 테스트
        if not sheets_sync.connect():
            logger.warning("[SyncScheduler] Google Sheets 연결 실패, 오프라인 모드로 실행")
            # 연결 실패해도 스케줄러는 생성 (나중에 재연결 시도)
        
        # 스케줄러 생성
        _scheduler = SyncScheduler(sheets_sync, db_manager)
        
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

