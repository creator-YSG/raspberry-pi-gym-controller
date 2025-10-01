"""
Google Sheets와 SQLite 간 양방향 동기화 매니저

기존 Google Sheets 연동을 유지하면서 SQLite와 동기화
"""

import asyncio
import logging
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

from .database_manager import DatabaseManager

# 기존 Google Sheets 매니저 import
try:
    from data_sources.google_sheets import GoogleSheetsManager, MemberInfo, LockerInfo, RentalRecord
    SHEETS_AVAILABLE = True
except ImportError:
    SHEETS_AVAILABLE = False
    print("[SYNC] Google Sheets 모듈을 찾을 수 없습니다. 스텁 모드로 실행됩니다.")


class SyncManager:
    """Google Sheets와 SQLite 간 양방향 동기화"""
    
    def __init__(self, db_manager: DatabaseManager, sheets_manager: Optional['GoogleSheetsManager'] = None):
        """
        Args:
            db_manager: 데이터베이스 매니저
            sheets_manager: Google Sheets 매니저 (선택사항)
        """
        self.db = db_manager
        self.sheets = sheets_manager
        self.logger = logging.getLogger(__name__)
        
        # 동기화 설정
        self.sync_enabled = SHEETS_AVAILABLE and sheets_manager is not None
        self.last_sync_time: Optional[datetime] = None
        self.sync_interval = timedelta(minutes=30)  # 기본 30분 간격
        
        # 동기화 통계
        self.sync_stats = {
            'members_synced': 0,
            'rentals_synced': 0,
            'last_sync_duration': 0,
            'sync_errors': 0,
            'last_error': None
        }
        
        if not self.sync_enabled:
            self.logger.warning("Google Sheets 동기화가 비활성화되었습니다")
        else:
            self.logger.info("Google Sheets 동기화 매니저 초기화 완료")
    
    async def initialize(self) -> bool:
        """동기화 매니저 초기화
        
        Returns:
            초기화 성공 여부
        """
        try:
            if not self.sync_enabled:
                return True
            
            # Google Sheets 연결 확인
            if not await self.sheets.connect():
                self.logger.error("Google Sheets 연결 실패")
                return False
            
            # 마지막 동기화 시간 로드
            last_sync_str = self.db.get_system_setting('last_sync_time', '')
            if last_sync_str:
                try:
                    self.last_sync_time = datetime.fromisoformat(last_sync_str)
                except ValueError:
                    self.logger.warning("마지막 동기화 시간 파싱 실패")
            
            # 동기화 간격 설정 로드
            sync_interval_minutes = self.db.get_system_setting('sync_interval_minutes', 30)
            self.sync_interval = timedelta(minutes=sync_interval_minutes)
            
            self.logger.info("동기화 매니저 초기화 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"동기화 매니저 초기화 실패: {e}")
            return False
    
    async def sync_all(self, force: bool = False) -> bool:
        """전체 동기화 실행
        
        Args:
            force: 강제 동기화 여부
            
        Returns:
            동기화 성공 여부
        """
        if not self.sync_enabled:
            self.logger.info("동기화가 비활성화되어 있습니다")
            return True
        
        # 동기화 필요 여부 확인
        if not force and not self._should_sync():
            self.logger.debug("동기화 간격이 아직 되지 않았습니다")
            return True
        
        start_time = datetime.now()
        self.logger.info("🔄 전체 동기화 시작...")
        
        try:
            # 1. 회원 정보 동기화 (Sheets → SQLite)
            members_success = await self.sync_members_from_sheets()
            
            # 2. 대여 기록 동기화 (SQLite → Sheets)
            rentals_success = await self.sync_rentals_to_sheets()
            
            # 3. 락카 상태 동기화 (양방향)
            lockers_success = await self.sync_locker_status()
            
            # 동기화 완료 처리
            success = members_success and rentals_success and lockers_success
            
            if success:
                self.last_sync_time = start_time
                self.db.set_system_setting('last_sync_time', start_time.isoformat())
                
                duration = (datetime.now() - start_time).total_seconds()
                self.sync_stats['last_sync_duration'] = duration
                
                self.logger.info(f"✅ 전체 동기화 완료 ({duration:.2f}초)")
            else:
                self.sync_stats['sync_errors'] += 1
                self.logger.error("❌ 동기화 중 일부 실패")
            
            return success
            
        except Exception as e:
            self.sync_stats['sync_errors'] += 1
            self.sync_stats['last_error'] = str(e)
            self.logger.error(f"전체 동기화 실패: {e}")
            return False
    
    async def sync_members_from_sheets(self) -> bool:
        """Google Sheets에서 회원 정보 동기화
        
        Returns:
            동기화 성공 여부
        """
        if not self.sync_enabled:
            return True
        
        try:
            self.logger.info("📥 회원 정보 동기화 시작 (Sheets → SQLite)")
            
            # Google Sheets에서 회원 데이터 새로고침
            await self.sheets.refresh_cache()
            
            synced_count = 0
            
            # SQLite에 회원 정보 업데이트
            for member_id, member_info in self.sheets._members_cache.items():
                try:
                    # 기존 회원 정보 조회
                    existing_member = self.db.get_member(member_id)
                    
                    # 회원 정보 업데이트 또는 삽입
                    cursor = self.db.execute_query("""
                        INSERT OR REPLACE INTO members 
                        (member_id, member_name, phone, membership_type, status, expiry_date, 
                         currently_renting, daily_rental_count, last_rental_time, sync_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        member_info.member_id,
                        member_info.name,
                        member_info.phone,
                        member_info.membership_type,
                        'active' if member_info.is_active else 'inactive',
                        member_info.expiry_date,
                        existing_member['currently_renting'] if existing_member else None,
                        existing_member['daily_rental_count'] if existing_member else 0,
                        existing_member['last_rental_time'] if existing_member else None,
                        datetime.now(timezone.utc).isoformat()
                    ))
                    
                    if cursor:
                        synced_count += 1
                        
                except Exception as e:
                    self.logger.error(f"회원 동기화 실패: {member_id}, {e}")
            
            self.sync_stats['members_synced'] = synced_count
            self.logger.info(f"✅ 회원 정보 동기화 완료: {synced_count}명")
            return True
            
        except Exception as e:
            self.logger.error(f"회원 정보 동기화 실패: {e}")
            return False
    
    async def sync_rentals_to_sheets(self) -> bool:
        """대여 기록을 Google Sheets로 업로드
        
        Returns:
            동기화 성공 여부
        """
        if not self.sync_enabled:
            return True
        
        try:
            self.logger.info("📤 대여 기록 동기화 시작 (SQLite → Sheets)")
            
            # 미동기화 대여 기록 조회
            cursor = self.db.execute_query("""
                SELECT r.*, m.member_name 
                FROM rentals r
                LEFT JOIN members m ON r.member_id = m.member_id
                WHERE r.sync_status = 0 
                AND r.status IN ('returned', 'active')
                ORDER BY r.created_at
            """)
            
            if not cursor:
                return False
            
            records = cursor.fetchall()
            synced_count = 0
            
            if not records:
                self.logger.info("동기화할 대여 기록이 없습니다")
                return True
            
            # Google Sheets에 업로드
            for record in records:
                try:
                    # 대여 기록을 Google Sheets 형식으로 변환
                    success = await self.sheets.record_rental(
                        record['member_id'],
                        record['locker_number'],
                        f"KEY_{record['locker_number']}"  # 임시 키 바코드
                    )
                    
                    if success:
                        # 동기화 완료 표시
                        self.db.execute_query("""
                            UPDATE rentals 
                            SET sync_status = 1 
                            WHERE rental_id = ?
                        """, (record['rental_id'],))
                        
                        synced_count += 1
                        
                except Exception as e:
                    self.logger.error(f"대여 기록 동기화 실패: {record['rental_id']}, {e}")
            
            self.sync_stats['rentals_synced'] = synced_count
            self.logger.info(f"✅ 대여 기록 동기화 완료: {synced_count}건")
            return True
            
        except Exception as e:
            self.logger.error(f"대여 기록 동기화 실패: {e}")
            return False
    
    async def sync_locker_status(self) -> bool:
        """락카 상태 동기화 (양방향)
        
        Returns:
            동기화 성공 여부
        """
        if not self.sync_enabled:
            return True
        
        try:
            self.logger.info("🔄 락카 상태 동기화 시작")
            
            # Google Sheets에서 락카 정보 로드
            await self.sheets._load_lockers()
            
            # SQLite의 락카 상태와 비교하여 업데이트
            for locker_id, locker_info in self.sheets._lockers_cache.items():
                try:
                    # SQLite에서 현재 락카 상태 조회
                    current_status = self.db.get_locker_status(locker_id)
                    
                    if current_status:
                        # 현재 사용자 정보가 다르면 업데이트
                        if current_status['current_member'] != locker_info.current_user:
                            self.db.execute_query("""
                                UPDATE locker_status 
                                SET current_member = ?, last_change_time = ?
                                WHERE locker_number = ?
                            """, (
                                locker_info.current_user,
                                datetime.now(timezone.utc).isoformat(),
                                locker_id
                            ))
                    
                except Exception as e:
                    self.logger.error(f"락카 상태 동기화 실패: {locker_id}, {e}")
            
            self.logger.info("✅ 락카 상태 동기화 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"락카 상태 동기화 실패: {e}")
            return False
    
    def _should_sync(self) -> bool:
        """동기화 필요 여부 확인
        
        Returns:
            동기화 필요 여부
        """
        if not self.last_sync_time:
            return True
        
        elapsed = datetime.now() - self.last_sync_time
        return elapsed >= self.sync_interval
    
    async def force_sync(self) -> bool:
        """강제 동기화 실행
        
        Returns:
            동기화 성공 여부
        """
        self.logger.info("🔄 강제 동기화 실행")
        return await self.sync_all(force=True)
    
    def get_sync_status(self) -> Dict[str, Any]:
        """동기화 상태 정보 조회
        
        Returns:
            동기화 상태 딕셔너리
        """
        return {
            'sync_enabled': self.sync_enabled,
            'last_sync_time': self.last_sync_time.isoformat() if self.last_sync_time else None,
            'sync_interval_minutes': self.sync_interval.total_seconds() / 60,
            'next_sync_time': (self.last_sync_time + self.sync_interval).isoformat() if self.last_sync_time else None,
            'should_sync': self._should_sync(),
            'stats': self.sync_stats.copy()
        }
    
    async def start_periodic_sync(self, interval_minutes: int = 30):
        """주기적 동기화 시작
        
        Args:
            interval_minutes: 동기화 간격 (분)
        """
        self.sync_interval = timedelta(minutes=interval_minutes)
        self.logger.info(f"주기적 동기화 시작: {interval_minutes}분 간격")
        
        while True:
            try:
                if self._should_sync():
                    await self.sync_all()
                
                # 1분마다 체크
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                self.logger.info("주기적 동기화 중단")
                break
            except Exception as e:
                self.logger.error(f"주기적 동기화 오류: {e}")
                await asyncio.sleep(60)  # 오류 시 1분 대기


def create_sync_manager(db_manager: DatabaseManager, 
                       sheets_manager: Optional['GoogleSheetsManager'] = None) -> SyncManager:
    """동기화 매니저 생성
    
    Args:
        db_manager: 데이터베이스 매니저
        sheets_manager: Google Sheets 매니저
        
    Returns:
        초기화된 SyncManager 인스턴스
    """
    sync_manager = SyncManager(db_manager, sheets_manager)
    return sync_manager
