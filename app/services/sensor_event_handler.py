"""
센서 이벤트 핸들러 (트랜잭션 연동)
"""

import asyncio
from datetime import datetime
from typing import Dict, Optional
from database import DatabaseManager, TransactionManager
from database.transaction_manager import TransactionStep, TransactionStatus
import logging

logger = logging.getLogger(__name__)


class SensorEventHandler:
    """ESP32 센서 이벤트를 트랜잭션 시스템과 연동하는 핸들러"""
    
    def __init__(self, db_path: str = 'instance/gym_system.db'):
        """SensorEventHandler 초기화
        
        Args:
            db_path: SQLite 데이터베이스 파일 경로
        """
        self.db = DatabaseManager(db_path)
        self.db.connect()
        self.tx_manager = TransactionManager(self.db)
        
        # 센서 번호 → 락카 ID 매핑
        self.sensor_to_locker_map = self._build_sensor_locker_map()
        
        logger.info("SensorEventHandler 초기화 완료")
    
    def _build_sensor_locker_map(self) -> Dict[int, str]:
        """센서 번호와 락카 ID 매핑 테이블 생성
        
        Returns:
            센서 번호 → 락카 ID 매핑 딕셔너리
        """
        # 새로운 시스템 (140개 락카)
        # 남성 구역: 센서 1-70 → M01-M70
        # 여성 구역: 센서 71-120 → F01-F50
        # 교직원 구역: 센서 121-140 → S01-S20
        mapping = {}
        
        # 남성 구역 매핑 (센서 1-70 → M01-M70)
        for i in range(1, 71):
            sensor_num = i
            locker_id = f"M{i:02d}"
            mapping[sensor_num] = locker_id
        
        # 여성 구역 매핑 (센서 71-120 → F01-F50)
        for i in range(1, 51):
            sensor_num = i + 70
            locker_id = f"F{i:02d}"
            mapping[sensor_num] = locker_id
        
        # 교직원 구역 매핑 (센서 121-140 → S01-S20)
        for i in range(1, 21):
            sensor_num = i + 120
            locker_id = f"S{i:02d}"
            mapping[sensor_num] = locker_id
        
        logger.info(f"센서-락카 매핑 생성: {len(mapping)}개 (남성 70개, 여성 50개, 교직원 20개)")
        return mapping
    
    async def handle_sensor_event(self, sensor_num: int, state: str, timestamp: Optional[float] = None) -> Dict:
        """센서 이벤트 처리 및 트랜잭션 연동
        
        Args:
            sensor_num: 센서 번호 (1-140)
            state: 센서 상태 ('HIGH' 또는 'LOW')
            timestamp: 이벤트 발생 시간 (None이면 현재 시간)
            
        Returns:
            처리 결과 딕셔너리
        """
        try:
            if timestamp is None:
                timestamp = datetime.now().timestamp()
            
            # 센서 번호 → 락카 ID 변환
            locker_id = self.sensor_to_locker_map.get(sensor_num)
            if not locker_id:
                logger.warning(f"알 수 없는 센서 번호: {sensor_num}")
                return {
                    'success': False,
                    'error': f'알 수 없는 센서 번호: {sensor_num}'
                }
            
            logger.info(f"센서 이벤트 처리: 센서{sensor_num} ({locker_id}) → {state}")
            
            # 활성 트랜잭션 조회
            active_transactions = await self.tx_manager.get_active_transactions()
            
            # 해당 락카와 관련된 트랜잭션 찾기
            relevant_transaction = None
            for tx in active_transactions:
                # 트랜잭션에서 락카 정보 확인
                if tx.get('locker_number') == locker_id:
                    relevant_transaction = tx
                    break
            
            if not relevant_transaction:
                logger.info(f"센서 이벤트 무시: {locker_id}에 대한 활성 트랜잭션 없음")
                return {
                    'success': True,
                    'message': f'센서 이벤트 기록됨 (활성 트랜잭션 없음): {locker_id}',
                    'sensor_num': sensor_num,
                    'locker_id': locker_id,
                    'state': state
                }
            
            tx_id = relevant_transaction['transaction_id']
            tx_step = relevant_transaction['step']
            tx_type = relevant_transaction['transaction_type']
            
            logger.info(f"관련 트랜잭션 발견: {tx_id} (단계: {tx_step}, 타입: {tx_type})")
            
            # 센서 이벤트를 트랜잭션에 기록
            await self.tx_manager.record_sensor_event(
                tx_id, locker_id, 
                {
                    'sensor_num': sensor_num,
                    'state': state,
                    'active': state == 'LOW',
                    'timestamp': timestamp
                }
            )
            
            # 트랜잭션 단계에 따른 처리
            if tx_step == TransactionStep.SENSOR_WAIT.value or tx_step == 'sensor_wait':
                return await self._handle_sensor_wait_event(
                    tx_id, tx_type, locker_id, sensor_num, state, timestamp
                )
            else:
                logger.info(f"센서 이벤트 기록만 수행: {tx_id} (단계: {tx_step})")
                return {
                    'success': True,
                    'message': f'센서 이벤트 기록됨: {locker_id}',
                    'transaction_id': tx_id,
                    'sensor_num': sensor_num,
                    'locker_id': locker_id,
                    'state': state
                }
                
        except Exception as e:
            logger.error(f"센서 이벤트 처리 오류: 센서{sensor_num}, {e}")
            return {
                'success': False,
                'error': f'센서 이벤트 처리 중 오류: {str(e)}'
            }
    
    async def _handle_sensor_wait_event(self, tx_id: str, tx_type: str, locker_id: str, 
                                      sensor_num: int, state: str, timestamp: float) -> Dict:
        """센서 대기 단계에서의 센서 이벤트 처리
        
        Args:
            tx_id: 트랜잭션 ID
            tx_type: 트랜잭션 타입 ('rental' 또는 'return')
            locker_id: 락카 ID
            sensor_num: 센서 번호
            state: 센서 상태
            timestamp: 이벤트 시간
            
        Returns:
            처리 결과
        """
        try:
            if tx_type == 'rental':
                # 대여: 키 제거 감지 (LOW 상태)
                if state == 'LOW':
                    logger.info(f"🔑 키 제거 감지: {locker_id} (트랜잭션: {tx_id})")
                    
                    # 센서 검증 완료 단계로 이동
                    await self.tx_manager.update_transaction_step(tx_id, TransactionStep.SENSOR_VERIFIED)
                    
                    # 대여 기록 업데이트 (센서 검증 완료)
                    self.db.execute_query("""
                        UPDATE rentals 
                        SET rental_sensor_time = ?, rental_verified = 1, status = 'active'
                        WHERE transaction_id = ?
                    """, (datetime.fromtimestamp(timestamp).isoformat(), tx_id))
                    
                    # 락카 상태 최종 업데이트 (완전히 대여됨)
                    self.db.execute_query("""
                        UPDATE locker_status 
                        SET sensor_status = 0, updated_at = ?
                        WHERE locker_number = ?
                    """, (datetime.now().isoformat(), locker_id))
                    
                    # 트랜잭션 완료
                    await self.tx_manager.end_transaction(tx_id, TransactionStatus.COMPLETED)
                    
                    logger.info(f"✅ 대여 완료: {locker_id} (트랜잭션: {tx_id})")
                    
                    return {
                        'success': True,
                        'completed': True,
                        'message': f'대여가 완료되었습니다: {locker_id}',
                        'transaction_id': tx_id,
                        'locker_id': locker_id,
                        'event_type': 'rental_completed'
                    }
                else:
                    # HIGH 상태: 아직 키를 빼지 않음
                    logger.info(f"대여 대기 중: {locker_id} (키를 빼주세요)")
                    return {
                        'success': True,
                        'completed': False,
                        'message': f'키를 빼주세요: {locker_id}',
                        'transaction_id': tx_id,
                        'locker_id': locker_id,
                        'state': state
                    }
            
            elif tx_type == 'return':
                # 반납: 키 삽입 감지 (HIGH 상태)
                if state == 'HIGH':
                    logger.info(f"🔑 키 삽입 감지: {locker_id} (트랜잭션: {tx_id})")
                    
                    # 센서 검증 완료 단계로 이동
                    await self.tx_manager.update_transaction_step(tx_id, TransactionStep.SENSOR_VERIFIED)
                    
                    # 반납 기록 업데이트 (센서 검증 완료)
                    self.db.execute_query("""
                        UPDATE rentals 
                        SET return_sensor_time = ?, return_verified = 1, status = 'returned'
                        WHERE transaction_id = ?
                    """, (datetime.fromtimestamp(timestamp).isoformat(), tx_id))
                    
                    # 락카 상태 업데이트 (사용 가능으로 변경)
                    self.db.execute_query("""
                        UPDATE locker_status 
                        SET current_member = NULL, current_transaction = NULL, 
                            sensor_status = 1, updated_at = ?
                        WHERE locker_number = ?
                    """, (datetime.now().isoformat(), locker_id))
                    
                    # 회원 대여 상태 해제
                    cursor = self.db.execute_query("""
                        SELECT member_id FROM rentals WHERE transaction_id = ?
                    """, (tx_id,))
                    
                    if cursor:
                        row = cursor.fetchone()
                        if row:
                            member_id = row['member_id']
                            self.db.execute_query("""
                                UPDATE members 
                                SET currently_renting = NULL, updated_at = ?
                                WHERE member_id = ?
                            """, (datetime.now().isoformat(), member_id))
                    
                    # 트랜잭션 완료
                    await self.tx_manager.end_transaction(tx_id, TransactionStatus.COMPLETED)
                    
                    logger.info(f"✅ 반납 완료: {locker_id} (트랜잭션: {tx_id})")
                    
                    return {
                        'success': True,
                        'completed': True,
                        'message': f'반납이 완료되었습니다: {locker_id}',
                        'transaction_id': tx_id,
                        'locker_id': locker_id,
                        'event_type': 'return_completed'
                    }
                else:
                    # LOW 상태: 아직 키를 넣지 않음
                    logger.info(f"반납 대기 중: {locker_id} (키를 넣어주세요)")
                    return {
                        'success': True,
                        'completed': False,
                        'message': f'키를 넣어주세요: {locker_id}',
                        'transaction_id': tx_id,
                        'locker_id': locker_id,
                        'state': state
                    }
            
            else:
                logger.warning(f"알 수 없는 트랜잭션 타입: {tx_type}")
                return {
                    'success': False,
                    'error': f'알 수 없는 트랜잭션 타입: {tx_type}'
                }
                
        except Exception as e:
            logger.error(f"센서 대기 이벤트 처리 오류: {tx_id}, {e}")
            # 트랜잭션 실패 처리
            await self.tx_manager.end_transaction(tx_id, TransactionStatus.FAILED)
            return {
                'success': False,
                'error': f'센서 검증 처리 중 오류: {str(e)}'
            }
    
    def get_sensor_locker_mapping(self) -> Dict[int, str]:
        """센서-락카 매핑 정보 반환"""
        return self.sensor_to_locker_map.copy()
    
    def close(self):
        """데이터베이스 연결 종료"""
        if self.db:
            self.db.close()
        logger.info("SensorEventHandler 데이터베이스 연결 종료")
