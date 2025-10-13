"""
SQLite 데이터베이스 연결 및 기본 CRUD 관리

락카키 대여기 시스템의 데이터베이스 레이어 핵심 클래스
"""

import sqlite3
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import threading


class DatabaseManager:
    """SQLite 데이터베이스 연결 및 기본 CRUD 관리"""
    
    def __init__(self, db_path: str = 'instance/gym_system.db'):
        """
        Args:
            db_path: SQLite 데이터베이스 파일 경로
        """
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self.logger = logging.getLogger(__name__)
        self._lock = threading.RLock()  # 스레드 안전성을 위한 락
        
    def connect(self) -> bool:
        """데이터베이스 연결
        
        Returns:
            연결 성공 여부
        """
        try:
            with self._lock:
                if self.conn:
                    self.conn.close()
                
                self.conn = sqlite3.connect(
                    self.db_path, 
                    check_same_thread=False,
                    timeout=30.0,
                    isolation_level=None  # autocommit 모드
                )
                
                # Row 팩토리 설정 (딕셔너리 형태로 결과 반환)
                self.conn.row_factory = sqlite3.Row
                
                # 외래키 제약조건 활성화
                self.conn.execute("PRAGMA foreign_keys = ON")
                
                # WAL 모드 활성화 (동시성 향상)
                self.conn.execute("PRAGMA journal_mode = WAL")
                
                # 동기화 모드 설정 (성능 향상)
                self.conn.execute("PRAGMA synchronous = NORMAL")
                
                self.logger.info(f"데이터베이스 연결 성공: {self.db_path}")
                return True
                
        except Exception as e:
            self.logger.error(f"데이터베이스 연결 실패: {e}")
            return False
    
    def initialize_schema(self) -> bool:
        """스키마 초기화
        
        Returns:
            초기화 성공 여부
        """
        try:
            with self._lock:
                if not self.conn:
                    self.logger.error("데이터베이스 연결이 필요합니다")
                    return False
                
                # 스키마 파일 경로
                schema_path = Path(__file__).parent / "schema.sql"
                
                if not schema_path.exists():
                    self.logger.error(f"스키마 파일을 찾을 수 없습니다: {schema_path}")
                    return False
                
                # 스키마 파일 읽기 및 실행
                with open(schema_path, 'r', encoding='utf-8') as f:
                    schema_sql = f.read()
                
                self.conn.executescript(schema_sql)
                self.logger.info("데이터베이스 스키마 초기화 완료")
                return True
                
        except Exception as e:
            self.logger.error(f"스키마 초기화 실패: {e}")
            return False
    
    def execute_query(self, query: str, params: Union[tuple, dict] = ()) -> Optional[sqlite3.Cursor]:
        """쿼리 실행
        
        Args:
            query: SQL 쿼리
            params: 쿼리 파라미터
            
        Returns:
            커서 객체 또는 None
        """
        try:
            with self._lock:
                if not self.conn:
                    self.logger.error("데이터베이스 연결이 필요합니다")
                    return None
                
                cursor = self.conn.execute(query, params)
                self.logger.debug(f"쿼리 실행: {query[:100]}...")
                return cursor
                
        except Exception as e:
            self.logger.error(f"쿼리 실행 실패: {query[:100]}..., 오류: {e}")
            return None
    
    def execute_many(self, query: str, params_list: List[Union[tuple, dict]]) -> bool:
        """다중 쿼리 실행
        
        Args:
            query: SQL 쿼리
            params_list: 파라미터 리스트
            
        Returns:
            실행 성공 여부
        """
        try:
            with self._lock:
                if not self.conn:
                    self.logger.error("데이터베이스 연결이 필요합니다")
                    return False
                
                self.conn.executemany(query, params_list)
                self.logger.debug(f"다중 쿼리 실행 완료: {len(params_list)}건")
                return True
                
        except Exception as e:
            self.logger.error(f"다중 쿼리 실행 실패: {e}")
            return False
    
    def begin_transaction(self):
        """트랜잭션 시작"""
        try:
            with self._lock:
                if self.conn:
                    self.conn.execute("BEGIN IMMEDIATE")
                    self.logger.debug("트랜잭션 시작")
        except Exception as e:
            self.logger.error(f"트랜잭션 시작 실패: {e}")
    
    def commit(self):
        """트랜잭션 커밋"""
        try:
            with self._lock:
                if self.conn:
                    self.conn.commit()
                    self.logger.debug("트랜잭션 커밋")
        except Exception as e:
            self.logger.error(f"트랜잭션 커밋 실패: {e}")
    
    def rollback(self):
        """트랜잭션 롤백"""
        try:
            with self._lock:
                if self.conn:
                    self.conn.rollback()
                    self.logger.debug("트랜잭션 롤백")
        except Exception as e:
            self.logger.error(f"트랜잭션 롤백 실패: {e}")
    
    def close(self):
        """연결 종료"""
        try:
            with self._lock:
                if self.conn:
                    self.conn.close()
                    self.conn = None
                    self.logger.info("데이터베이스 연결 종료")
        except Exception as e:
            self.logger.error(f"연결 종료 실패: {e}")
    
    # =====================================================
    # 편의 메서드들
    # =====================================================
    
    def get_member(self, member_id: str) -> Optional[Dict[str, Any]]:
        """회원 정보 조회
        
        Args:
            member_id: 회원 ID
            
        Returns:
            회원 정보 딕셔너리 또는 None
        """
        cursor = self.execute_query(
            "SELECT * FROM members WHERE member_id = ?", 
            (member_id,)
        )
        
        if cursor:
            row = cursor.fetchone()
            return dict(row) if row else None
        return None
    
    def get_locker_status(self, locker_number: str) -> Optional[Dict[str, Any]]:
        """락카 상태 조회
        
        Args:
            locker_number: 락카 번호
            
        Returns:
            락카 상태 딕셔너리 또는 None
        """
        cursor = self.execute_query(
            "SELECT * FROM locker_status WHERE locker_number = ?", 
            (locker_number,)
        )
        
        if cursor:
            row = cursor.fetchone()
            return dict(row) if row else None
        return None
    
    def get_active_rentals(self, member_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """활성 대여 기록 조회
        
        Args:
            member_id: 회원 ID (선택사항)
            
        Returns:
            활성 대여 기록 리스트
        """
        if member_id:
            cursor = self.execute_query(
                "SELECT * FROM rentals WHERE member_id = ? AND status = 'active'", 
                (member_id,)
            )
        else:
            cursor = self.execute_query(
                "SELECT * FROM rentals WHERE status = 'active'"
            )
        
        if cursor:
            return [dict(row) for row in cursor.fetchall()]
        return []
    
    def get_available_lockers(self, zone: Optional[str] = None) -> List[Dict[str, Any]]:
        """사용 가능한 락카 목록 조회
        
        Args:
            zone: 구역 (선택사항)
            
        Returns:
            사용 가능한 락카 리스트
        """
        if zone:
            cursor = self.execute_query("""
                SELECT * FROM locker_status 
                WHERE zone = ? 
                AND current_member IS NULL 
                AND maintenance_status = 'normal'
                ORDER BY locker_number
            """, (zone,))
        else:
            cursor = self.execute_query("""
                SELECT * FROM locker_status 
                WHERE current_member IS NULL 
                AND maintenance_status = 'normal'
                ORDER BY zone, locker_number
            """)
        
        if cursor:
            return [dict(row) for row in cursor.fetchall()]
        return []
    
    def get_system_setting(self, key: str, default_value: Any = None) -> Any:
        """시스템 설정 조회
        
        Args:
            key: 설정 키
            default_value: 기본값
            
        Returns:
            설정 값
        """
        cursor = self.execute_query(
            "SELECT setting_value, setting_type FROM system_settings WHERE setting_key = ?", 
            (key,)
        )
        
        if cursor:
            row = cursor.fetchone()
            if row:
                value = row['setting_value']
                setting_type = row['setting_type']
                
                # 타입에 따른 변환
                if setting_type == 'integer':
                    return int(value)
                elif setting_type == 'boolean':
                    return value.lower() in ('true', '1', 'yes')
                elif setting_type == 'json':
                    return json.loads(value)
                else:
                    return value
        
        return default_value
    
    def set_system_setting(self, key: str, value: Any, setting_type: str = 'string') -> bool:
        """시스템 설정 저장
        
        Args:
            key: 설정 키
            value: 설정 값
            setting_type: 값 타입
            
        Returns:
            저장 성공 여부
        """
        try:
            # 값을 문자열로 변환
            if setting_type == 'json':
                str_value = json.dumps(value)
            else:
                str_value = str(value)
            
            cursor = self.execute_query("""
                INSERT OR REPLACE INTO system_settings 
                (setting_key, setting_value, setting_type) 
                VALUES (?, ?, ?)
            """, (key, str_value, setting_type))
            
            return cursor is not None
            
        except Exception as e:
            self.logger.error(f"시스템 설정 저장 실패: {key}={value}, 오류: {e}")
            return False
    
    def cleanup_old_transactions(self, hours: int = 24) -> int:
        """오래된 트랜잭션 정리
        
        Args:
            hours: 정리할 시간 (시간)
            
        Returns:
            정리된 트랜잭션 수
        """
        try:
            cursor = self.execute_query("""
                DELETE FROM active_transactions 
                WHERE created_at < datetime('now', '-{} hours')
            """.format(hours))
            
            if cursor:
                count = cursor.rowcount
                self.logger.info(f"오래된 트랜잭션 정리 완료: {count}건")
                return count
            
        except Exception as e:
            self.logger.error(f"트랜잭션 정리 실패: {e}")
        
        return 0
    
    def get_database_stats(self) -> Dict[str, Any]:
        """데이터베이스 통계 정보
        
        Returns:
            통계 정보 딕셔너리
        """
        stats = {}
        
        try:
            # 테이블별 레코드 수
            tables = ['members', 'rentals', 'locker_status', 'active_transactions']
            
            for table in tables:
                cursor = self.execute_query(f"SELECT COUNT(*) as count FROM {table}")
                if cursor:
                    row = cursor.fetchone()
                    stats[f'{table}_count'] = row['count'] if row else 0
            
            # 활성 대여 수
            cursor = self.execute_query("SELECT COUNT(*) as count FROM rentals WHERE status = 'active'")
            if cursor:
                row = cursor.fetchone()
                stats['active_rentals'] = row['count'] if row else 0
            
            # 사용 가능한 락카 수
            cursor = self.execute_query("""
                SELECT COUNT(*) as count FROM locker_status 
                WHERE current_member IS NULL AND maintenance_status = 'normal'
            """)
            if cursor:
                row = cursor.fetchone()
                stats['available_lockers'] = row['count'] if row else 0
            
            # 데이터베이스 파일 크기
            db_path = Path(self.db_path)
            if db_path.exists():
                stats['db_size_bytes'] = db_path.stat().st_size
                stats['db_size_mb'] = round(stats['db_size_bytes'] / (1024 * 1024), 2)
            
            stats['last_updated'] = datetime.now(timezone.utc).isoformat()
            
        except Exception as e:
            self.logger.error(f"통계 정보 조회 실패: {e}")
        
        return stats


def create_database_manager(db_path: str = 'instance/gym_system.db', initialize: bool = True) -> DatabaseManager:
    """데이터베이스 매니저 생성 및 초기화
    
    Args:
        db_path: 데이터베이스 파일 경로
        initialize: 스키마 초기화 여부
        
    Returns:
        초기화된 DatabaseManager 인스턴스
    """
    manager = DatabaseManager(db_path)
    
    if not manager.connect():
        raise Exception("데이터베이스 연결 실패")
    
    if initialize:
        if not manager.initialize_schema():
            raise Exception("데이터베이스 스키마 초기화 실패")
    
    return manager
