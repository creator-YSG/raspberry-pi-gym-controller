"""
트랜잭션 매니저

대여/반납 프로세스의 트랜잭션 기반 안전한 처리를 담당
"""

import uuid
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Any, List
from enum import Enum

from .database_manager import DatabaseManager


class TransactionType(Enum):
    """트랜잭션 타입"""
    RENTAL = "rental"
    RETURN = "return"


class TransactionStatus(Enum):
    """트랜잭션 상태"""
    ACTIVE = "active"
    COMPLETED = "completed"
    TIMEOUT = "timeout"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TransactionStep(Enum):
    """트랜잭션 단계"""
    STARTED = "started"
    MEMBER_VERIFIED = "member_verified"
    LOCKER_SELECTED = "locker_selected"
    HARDWARE_SENT = "hardware_sent"
    SENSOR_WAIT = "sensor_wait"
    SENSOR_VERIFIED = "sensor_verified"
    COMPLETED = "completed"


class TransactionManager:
    """대여/반납 트랜잭션 관리"""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Args:
            db_manager: 데이터베이스 매니저
        """
        self.db = db_manager
        self.logger = logging.getLogger(__name__)
        
        # 트랜잭션 설정
        self.default_timeout_seconds = 30
        self.sensor_timeout_seconds = 30
        self.max_concurrent_transactions = 1  # 동시 트랜잭션 제한
        
        # 활성 트랜잭션 캐시 (메모리 성능 향상)
        self._active_transactions: Dict[str, Dict[str, Any]] = {}
        
        self.logger.info("트랜잭션 매니저 초기화 완료")
    
    async def start_transaction(self, member_id: str, transaction_type: TransactionType = TransactionType.RENTAL) -> Dict[str, Any]:
        """새 트랜잭션 시작
        
        Args:
            member_id: 회원 ID
            transaction_type: 트랜잭션 타입
            
        Returns:
            트랜잭션 시작 결과
        """
        try:
            self.logger.info(f"트랜잭션 시작 요청: {member_id} ({transaction_type.value})")
            
            # 1. 기존 활성 트랜잭션 체크
            active_check = await self._check_active_transactions()
            if not active_check['can_start']:
                return {
                    'success': False,
                    'error': 'TRANSACTION_ACTIVE',
                    'message': active_check['message']
                }
            
            # 2. 회원별 중복 트랜잭션 체크
            member_check = await self._check_member_transaction(member_id)
            if not member_check['can_start']:
                return {
                    'success': False,
                    'error': 'MEMBER_TRANSACTION_ACTIVE',
                    'message': member_check['message']
                }
            
            # 3. 타임아웃된 트랜잭션 정리
            await self._cleanup_timeout_transactions()
            
            # 4. 새 트랜잭션 생성
            tx_id = str(uuid.uuid4())
            timeout_seconds = self.db.get_system_setting('transaction_timeout_seconds', self.default_timeout_seconds)
            timeout_at = datetime.now(timezone.utc) + timedelta(seconds=timeout_seconds)
            
            # 데이터베이스에 트랜잭션 기록
            cursor = self.db.execute_query("""
                INSERT INTO active_transactions 
                (transaction_id, member_id, transaction_type, timeout_at, step, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                tx_id,
                member_id,
                transaction_type.value,
                timeout_at.isoformat(),
                TransactionStep.STARTED.value,
                TransactionStatus.ACTIVE.value
            ))
            
            if not cursor:
                return {
                    'success': False,
                    'error': 'DATABASE_ERROR',
                    'message': '트랜잭션 생성 실패'
                }
            
            # 5. 모든 락카 잠금 (동시성 제어)
            await self._lock_all_lockers(tx_id, timeout_at)
            
            # 6. 캐시에 추가
            self._active_transactions[tx_id] = {
                'transaction_id': tx_id,
                'member_id': member_id,
                'transaction_type': transaction_type.value,
                'status': TransactionStatus.ACTIVE.value,
                'step': TransactionStep.STARTED.value,
                'timeout_at': timeout_at,
                'created_at': datetime.now(timezone.utc)
            }
            
            self.logger.info(f"트랜잭션 시작 성공: {tx_id}")
            
            return {
                'success': True,
                'transaction_id': tx_id,
                'timeout_at': timeout_at.isoformat(),
                'timeout_seconds': timeout_seconds
            }
            
        except Exception as e:
            self.logger.error(f"트랜잭션 시작 실패: {member_id}, {e}")
            return {
                'success': False,
                'error': 'SYSTEM_ERROR',
                'message': f'시스템 오류: {str(e)}'
            }
    
    async def update_transaction_step(self, tx_id: str, step: TransactionStep, data: Optional[Dict[str, Any]] = None) -> bool:
        """트랜잭션 단계 업데이트
        
        Args:
            tx_id: 트랜잭션 ID
            step: 새로운 단계
            data: 추가 데이터
            
        Returns:
            업데이트 성공 여부
        """
        try:
            # 트랜잭션 존재 확인
            if tx_id not in self._active_transactions:
                transaction = await self._load_transaction(tx_id)
                if not transaction:
                    self.logger.error(f"트랜잭션을 찾을 수 없음: {tx_id}")
                    return False
            
            # 단계 업데이트
            cursor = self.db.execute_query("""
                UPDATE active_transactions 
                SET step = ?, last_activity = ?, sensor_events = ?
                WHERE transaction_id = ? AND status = ?
            """, (
                step.value,
                datetime.now(timezone.utc).isoformat(),
                json.dumps(data) if data else None,
                tx_id,
                TransactionStatus.ACTIVE.value
            ))
            
            if cursor and cursor.rowcount > 0:
                # 캐시 업데이트
                if tx_id in self._active_transactions:
                    self._active_transactions[tx_id]['step'] = step.value
                    self._active_transactions[tx_id]['last_activity'] = datetime.now(timezone.utc)
                
                self.logger.debug(f"트랜잭션 단계 업데이트: {tx_id} -> {step.value}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"트랜잭션 단계 업데이트 실패: {tx_id}, {e}")
            return False
    
    async def end_transaction(self, tx_id: str, status: TransactionStatus = TransactionStatus.COMPLETED, error_message: Optional[str] = None) -> bool:
        """트랜잭션 종료
        
        Args:
            tx_id: 트랜잭션 ID
            status: 최종 상태
            error_message: 오류 메시지 (실패 시)
            
        Returns:
            종료 성공 여부
        """
        try:
            self.logger.info(f"트랜잭션 종료: {tx_id} ({status.value})")
            
            # 트랜잭션 상태 업데이트
            cursor = self.db.execute_query("""
                UPDATE active_transactions 
                SET status = ?, last_activity = ?, error_message = ?
                WHERE transaction_id = ?
            """, (
                status.value,
                datetime.now(timezone.utc).isoformat(),
                error_message,
                tx_id
            ))
            
            if not cursor:
                self.logger.error(f"트랜잭션 상태 업데이트 실패: {tx_id}")
                return False
            
            # 락카 잠금 해제
            await self._unlock_all_lockers(tx_id)
            
            # 캐시에서 제거
            if tx_id in self._active_transactions:
                del self._active_transactions[tx_id]
            
            self.logger.info(f"트랜잭션 종료 완료: {tx_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"트랜잭션 종료 실패: {tx_id}, {e}")
            return False
    
    async def get_transaction_status(self, tx_id: str) -> Optional[Dict[str, Any]]:
        """트랜잭션 상태 조회
        
        Args:
            tx_id: 트랜잭션 ID
            
        Returns:
            트랜잭션 상태 정보
        """
        try:
            # 캐시에서 먼저 확인
            if tx_id in self._active_transactions:
                return self._active_transactions[tx_id].copy()
            
            # 데이터베이스에서 조회
            return await self._load_transaction(tx_id)
            
        except Exception as e:
            self.logger.error(f"트랜잭션 상태 조회 실패: {tx_id}, {e}")
            return None
    
    async def get_active_transactions(self) -> List[Dict[str, Any]]:
        """활성 트랜잭션 목록 조회
        
        Returns:
            활성 트랜잭션 리스트
        """
        try:
            current_time = datetime.now(timezone.utc).isoformat()
            cursor = self.db.execute_query("""
                SELECT * FROM active_transactions 
                WHERE status = ? 
                AND ? < timeout_at
                ORDER BY created_at DESC
            """, (TransactionStatus.ACTIVE.value, current_time))
            
            if cursor:
                transactions = []
                for row in cursor.fetchall():
                    transaction = dict(row)
                    # 센서 이벤트 파싱
                    if transaction.get('sensor_events'):
                        try:
                            transaction['sensor_events'] = json.loads(transaction['sensor_events'])
                        except json.JSONDecodeError:
                            transaction['sensor_events'] = None
                    
                    transactions.append(transaction)
                
                return transactions
            
            return []
            
        except Exception as e:
            self.logger.error(f"활성 트랜잭션 조회 실패: {e}")
            return []
    
    async def record_sensor_event(self, tx_id: str, locker_number: str, sensor_data: Dict[str, Any]) -> bool:
        """센서 이벤트 기록
        
        Args:
            tx_id: 트랜잭션 ID
            locker_number: 락카 번호
            sensor_data: 센서 데이터
            
        Returns:
            기록 성공 여부
        """
        try:
            # 기존 센서 이벤트 조회
            cursor = self.db.execute_query("""
                SELECT sensor_events FROM active_transactions 
                WHERE transaction_id = ?
            """, (tx_id,))
            
            if not cursor:
                return False
            
            row = cursor.fetchone()
            if not row:
                return False
            
            # 기존 이벤트 파싱
            existing_events = []
            if row['sensor_events']:
                try:
                    existing_events = json.loads(row['sensor_events'])
                except json.JSONDecodeError:
                    existing_events = []
            
            # 새 이벤트 추가
            new_event = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'locker_number': locker_number,
                'sensor_data': sensor_data
            }
            existing_events.append(new_event)
            
            # 업데이트
            cursor = self.db.execute_query("""
                UPDATE active_transactions 
                SET sensor_events = ?, last_activity = ?
                WHERE transaction_id = ?
            """, (
                json.dumps(existing_events),
                datetime.now(timezone.utc).isoformat(),
                tx_id
            ))
            
            success = cursor and cursor.rowcount > 0
            if success:
                self.logger.debug(f"센서 이벤트 기록: {tx_id} -> {locker_number}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"센서 이벤트 기록 실패: {tx_id}, {e}")
            return False
    
    async def wait_for_sensor_verification(self, tx_id: str, locker_number: str, expected_change: str = "key_removed") -> bool:
        """센서 검증 대기
        
        Args:
            tx_id: 트랜잭션 ID
            locker_number: 대상 락카 번호
            expected_change: 예상되는 센서 변화 ("key_removed", "key_inserted")
            
        Returns:
            검증 성공 여부
        """
        try:
            timeout_seconds = self.db.get_system_setting('sensor_verification_timeout', self.sensor_timeout_seconds)
            start_time = datetime.now(timezone.utc)
            timeout_time = start_time + timedelta(seconds=timeout_seconds)
            
            self.logger.info(f"센서 검증 대기 시작: {tx_id} -> {locker_number} ({expected_change})")
            
            while datetime.now(timezone.utc) < timeout_time:
                # 트랜잭션 상태 확인
                transaction = await self.get_transaction_status(tx_id)
                if not transaction or transaction['status'] != TransactionStatus.ACTIVE.value:
                    self.logger.warning(f"트랜잭션이 비활성 상태: {tx_id}")
                    return False
                
                # 센서 이벤트 확인
                cursor = self.db.execute_query("""
                    SELECT sensor_events FROM active_transactions 
                    WHERE transaction_id = ?
                """, (tx_id,))
                
                if cursor:
                    row = cursor.fetchone()
                    if row and row['sensor_events']:
                        try:
                            events = json.loads(row['sensor_events'])
                            if self._verify_sensor_events(events, locker_number, expected_change):
                                self.logger.info(f"센서 검증 성공: {tx_id}")
                                return True
                        except json.JSONDecodeError:
                            pass
                
                # 500ms 간격으로 체크
                await asyncio.sleep(0.5)
            
            self.logger.warning(f"센서 검증 타임아웃: {tx_id}")
            return False
            
        except Exception as e:
            self.logger.error(f"센서 검증 실패: {tx_id}, {e}")
            return False
    
    def _verify_sensor_events(self, events: List[Dict[str, Any]], locker_number: str, expected_change: str) -> bool:
        """센서 이벤트 검증
        
        Args:
            events: 센서 이벤트 리스트
            locker_number: 대상 락카 번호
            expected_change: 예상되는 변화
            
        Returns:
            검증 성공 여부
        """
        try:
            # 최근 10초 내의 이벤트만 확인
            recent_time = datetime.now(timezone.utc) - timedelta(seconds=10)
            
            for event in reversed(events):  # 최신 이벤트부터 확인
                try:
                    event_time = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
                    if event_time < recent_time:
                        continue
                    
                    if event['locker_number'] == locker_number:
                        sensor_data = event['sensor_data']
                        
                        # 센서 변화 확인
                        if expected_change == "key_removed":
                            # 키가 제거되었는지 확인 (센서 값이 0 또는 False)
                            if not sensor_data.get('active', True):
                                return True
                        elif expected_change == "key_inserted":
                            # 키가 삽입되었는지 확인 (센서 값이 1 또는 True)
                            if sensor_data.get('active', False):
                                return True
                
                except (ValueError, KeyError):
                    continue
            
            return False
            
        except Exception as e:
            self.logger.error(f"센서 이벤트 검증 오류: {e}")
            return False
    
    async def _check_active_transactions(self) -> Dict[str, Any]:
        """활성 트랜잭션 체크"""
        try:
            current_time = datetime.now(timezone.utc).isoformat()
            cursor = self.db.execute_query("""
                SELECT COUNT(*) as count FROM active_transactions 
                WHERE status = ? 
                AND ? < timeout_at
            """, (TransactionStatus.ACTIVE.value, current_time))
            
            if cursor:
                row = cursor.fetchone()
                active_count = row['count'] if row else 0
                
                if active_count >= self.max_concurrent_transactions:
                    return {
                        'can_start': False,
                        'message': '다른 회원이 이용 중입니다. 잠시 후 다시 시도해주세요.'
                    }
            
            return {'can_start': True}
            
        except Exception as e:
            self.logger.error(f"활성 트랜잭션 체크 실패: {e}")
            return {
                'can_start': False,
                'message': '시스템 오류가 발생했습니다.'
            }
    
    async def _check_member_transaction(self, member_id: str) -> Dict[str, Any]:
        """회원별 트랜잭션 체크"""
        try:
            current_time = datetime.now(timezone.utc).isoformat()
            cursor = self.db.execute_query("""
                SELECT transaction_id FROM active_transactions 
                WHERE member_id = ? 
                AND status = ?
                AND ? < timeout_at
            """, (member_id, TransactionStatus.ACTIVE.value, current_time))
            
            if cursor and cursor.fetchone():
                return {
                    'can_start': False,
                    'message': '이미 진행 중인 대여/반납이 있습니다.'
                }
            
            return {'can_start': True}
            
        except Exception as e:
            self.logger.error(f"회원 트랜잭션 체크 실패: {e}")
            return {
                'can_start': False,
                'message': '시스템 오류가 발생했습니다.'
            }
    
    async def _cleanup_timeout_transactions(self) -> int:
        """타임아웃된 트랜잭션 정리"""
        try:
            # 타임아웃된 트랜잭션 조회 (현재 시간과 비교)
            current_time = datetime.now(timezone.utc).isoformat()
            cursor = self.db.execute_query("""
                SELECT transaction_id FROM active_transactions 
                WHERE status = ? 
                AND ? >= timeout_at
            """, (TransactionStatus.ACTIVE.value, current_time))
            
            if not cursor:
                return 0
            
            timeout_transactions = [row['transaction_id'] for row in cursor.fetchall()]
            
            if not timeout_transactions:
                return 0
            
            # 상태 업데이트
            placeholders = ','.join(['?' for _ in timeout_transactions])
            cursor = self.db.execute_query(f"""
                UPDATE active_transactions 
                SET status = ?, last_activity = ?
                WHERE transaction_id IN ({placeholders})
            """, [TransactionStatus.TIMEOUT.value, datetime.now(timezone.utc).isoformat()] + timeout_transactions)
            
            # 락카 잠금 해제
            for tx_id in timeout_transactions:
                await self._unlock_all_lockers(tx_id)
                # 캐시에서 제거
                if tx_id in self._active_transactions:
                    del self._active_transactions[tx_id]
            
            count = len(timeout_transactions)
            if count > 0:
                self.logger.info(f"타임아웃된 트랜잭션 정리: {count}개")
            
            return count
            
        except Exception as e:
            self.logger.error(f"타임아웃 트랜잭션 정리 실패: {e}")
            return 0
    
    async def _lock_all_lockers(self, tx_id: str, timeout_at: datetime):
        """모든 락카 잠금"""
        try:
            cursor = self.db.execute_query("""
                UPDATE locker_status 
                SET current_transaction = ?, locked_until = ?
            """, (tx_id, timeout_at.isoformat()))
            
            if cursor:
                self.logger.debug(f"모든 락카 잠금: {tx_id}")
            
        except Exception as e:
            self.logger.error(f"락카 잠금 실패: {tx_id}, {e}")
    
    async def _unlock_all_lockers(self, tx_id: str):
        """모든 락카 잠금 해제"""
        try:
            cursor = self.db.execute_query("""
                UPDATE locker_status 
                SET current_transaction = NULL, locked_until = NULL
                WHERE current_transaction = ?
            """, (tx_id,))
            
            if cursor:
                self.logger.debug(f"락카 잠금 해제: {tx_id}")
            
        except Exception as e:
            self.logger.error(f"락카 잠금 해제 실패: {tx_id}, {e}")
    
    async def _load_transaction(self, tx_id: str) -> Optional[Dict[str, Any]]:
        """데이터베이스에서 트랜잭션 로드"""
        try:
            cursor = self.db.execute_query("""
                SELECT * FROM active_transactions 
                WHERE transaction_id = ?
            """, (tx_id,))
            
            if cursor:
                row = cursor.fetchone()
                if row:
                    transaction = dict(row)
                    # 센서 이벤트 파싱
                    if transaction.get('sensor_events'):
                        try:
                            transaction['sensor_events'] = json.loads(transaction['sensor_events'])
                        except json.JSONDecodeError:
                            transaction['sensor_events'] = None
                    
                    return transaction
            
            return None
            
        except Exception as e:
            self.logger.error(f"트랜잭션 로드 실패: {tx_id}, {e}")
            return None


def create_transaction_manager(db_manager: DatabaseManager) -> TransactionManager:
    """트랜잭션 매니저 생성
    
    Args:
        db_manager: 데이터베이스 매니저
        
    Returns:
        초기화된 TransactionManager 인스턴스
    """
    return TransactionManager(db_manager)
