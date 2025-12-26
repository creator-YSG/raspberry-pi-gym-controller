"""
DB 로그 핸들러

로그를 SQLite DB에 저장하여 나중에 구글시트로 동기화
"""

import logging
import threading
import json
from datetime import datetime
from typing import Optional
from queue import Queue
import re


class DBLogHandler(logging.Handler):
    """로그를 SQLite DB에 저장하는 핸들러"""
    
    def __init__(self, db_path: str = 'instance/gym_system.db', 
                 min_level: int = logging.DEBUG,
                 batch_size: int = 50,
                 flush_interval: float = 10.0):
        """
        초기화
        
        Args:
            db_path: SQLite DB 경로
            min_level: 최소 로그 레벨 (INFO 이상만 저장)
            batch_size: 배치 저장 크기
            flush_interval: 자동 flush 간격 (초)
        """
        super().__init__(level=min_level)
        self.db_path = db_path
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        
        self._queue = Queue()
        self._lock = threading.Lock()
        self._running = True
        
        # 백그라운드 스레드로 DB 저장
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()
        
        # 회원/락커/대여 ID 추출 패턴
        self._member_pattern = re.compile(r'member[_\s]*(?:id)?[=:\s]*([A-Za-z0-9]+)', re.IGNORECASE)
        self._locker_pattern = re.compile(r'(?:locker|락카|락커)[_\s]*(?:number|id)?[=:\s]*([A-Za-z0-9]+)', re.IGNORECASE)
        self._rental_pattern = re.compile(r'rental[_\s]*(?:id)?[=:\s]*(\d+)', re.IGNORECASE)
    
    def emit(self, record: logging.LogRecord):
        """로그 레코드 처리"""
        try:
            # 메시지 포맷팅
            message = self.format(record)
            
            # 관련 ID 추출
            member_id = self._extract_member_id(message)
            locker_number = self._extract_locker_number(message)
            rental_id = self._extract_rental_id(message)
            
            # 추가 데이터
            extra_data = None
            if hasattr(record, 'extra'):
                extra_data = json.dumps(record.extra, ensure_ascii=False)
            
            log_entry = {
                'log_level': record.levelname,
                'logger_name': record.name,
                'message': message[:2000],  # 최대 2000자
                'member_id': member_id,
                'rental_id': rental_id,
                'locker_number': locker_number,
                'extra_data': extra_data,
                'created_at': datetime.now().isoformat()
            }
            
            self._queue.put(log_entry)
            
        except Exception:
            self.handleError(record)
    
    def _extract_member_id(self, message: str) -> Optional[str]:
        """메시지에서 회원 ID 추출"""
        match = self._member_pattern.search(message)
        return match.group(1) if match else None
    
    def _extract_locker_number(self, message: str) -> Optional[str]:
        """메시지에서 락커 번호 추출"""
        match = self._locker_pattern.search(message)
        return match.group(1) if match else None
    
    def _extract_rental_id(self, message: str) -> Optional[int]:
        """메시지에서 대여 ID 추출"""
        match = self._rental_pattern.search(message)
        return int(match.group(1)) if match else None
    
    def _worker_loop(self):
        """백그라운드 DB 저장 루프"""
        import sqlite3
        import time
        
        last_flush = time.time()
        batch = []
        
        while self._running:
            try:
                # 큐에서 로그 가져오기 (타임아웃 1초)
                try:
                    from queue import Empty
                    entry = self._queue.get(timeout=1.0)
                    batch.append(entry)
                except:
                    pass
                
                # 배치 저장 조건 확인
                should_flush = (
                    len(batch) >= self.batch_size or
                    (len(batch) > 0 and time.time() - last_flush >= self.flush_interval)
                )
                
                if should_flush and batch:
                    self._save_batch(batch)
                    batch = []
                    last_flush = time.time()
                    
            except Exception as e:
                print(f"[DBLogHandler] Worker error: {e}")
    
    def _save_batch(self, batch: list):
        """배치로 DB에 저장"""
        import sqlite3
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for entry in batch:
                cursor.execute("""
                    INSERT INTO system_logs 
                    (log_level, logger_name, message, member_id, rental_id, locker_number, extra_data, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry['log_level'],
                    entry['logger_name'],
                    entry['message'],
                    entry['member_id'],
                    entry['rental_id'],
                    entry['locker_number'],
                    entry['extra_data'],
                    entry['created_at']
                ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"[DBLogHandler] Save batch error: {e}")
    
    def flush(self):
        """즉시 저장"""
        batch = []
        while not self._queue.empty():
            try:
                batch.append(self._queue.get_nowait())
            except:
                break
        
        if batch:
            self._save_batch(batch)
    
    def close(self):
        """핸들러 종료"""
        self._running = False
        self.flush()
        super().close()


# 전역 핸들러 인스턴스
_db_handler: Optional[DBLogHandler] = None


def setup_db_logging(db_path: str = 'instance/gym_system.db', 
                     min_level: int = logging.DEBUG) -> DBLogHandler:
    """DB 로깅 설정"""
    global _db_handler
    
    if _db_handler is None:
        _db_handler = DBLogHandler(db_path=db_path, min_level=min_level)
        
        # 루트 로거에 핸들러 추가
        root_logger = logging.getLogger()
        root_logger.addHandler(_db_handler)
        
        print(f"[DBLogHandler] ✅ DB 로깅 활성화: {db_path}")
    
    return _db_handler


def get_db_handler() -> Optional[DBLogHandler]:
    """현재 DB 핸들러 반환"""
    return _db_handler

