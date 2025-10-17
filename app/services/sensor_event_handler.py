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
    
    def __init__(self, db_path: str = 'instance/gym_system.db', esp32_manager=None):
        """SensorEventHandler 초기화
        
        Args:
            db_path: SQLite 데이터베이스 파일 경로
            esp32_manager: ESP32 매니저 인스턴스 (문 열기/닫기용)
        """
        self.db = DatabaseManager(db_path)
        self.db.connect()
        self.tx_manager = TransactionManager(self.db)
        self.esp32_manager = esp32_manager
        
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
            
            # 활성 트랜잭션 찾기 (더 유연한 매칭)
            relevant_transaction = None
            for tx in active_transactions:
                # 1. 특정 락카키에 대한 트랜잭션 (반납 시)
                if tx.get('locker_number') == locker_id:
                    relevant_transaction = tx
                    logger.info(f"반납 트랜잭션 발견: {locker_id}")
                    break
                # 2. 대여 시작 트랜잭션 (locker_number가 null이고 rental 타입)
                elif (tx.get('locker_number') is None and 
                      tx.get('transaction_type') == 'rental' and
                      tx.get('status') == 'active'):
                    relevant_transaction = tx
                    logger.info(f"대여 트랜잭션 발견: 회원 {tx.get('member_id')} → 락카키 {locker_id} 선택")
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
            member_id = relevant_transaction['member_id']
            
            logger.info(f"관련 트랜잭션 발견: {tx_id} (단계: {tx_step}, 타입: {tx_type})")
            
            # 대여 프로세스: HIGH 상태 = 락카키 제거 → 바로 대여 완료 처리
            if tx_type == 'rental' and state == 'HIGH':
                logger.info(f"락카키 제거 감지 → 대여 완료 처리 시작: {locker_id}")
                
                # 3초 대기 (손 끼임 방지)
                import asyncio
                await asyncio.sleep(3)
                
                # 문 닫기 명령 (ESP32Manager 사용)
                try:
                    if self.esp32_manager:
                        logger.info("문 닫기 명령 전송")
                        await self.esp32_manager.send_command("esp32_auto_0", "MOTOR_MOVE", revs=-0.917, rpm=30)
                        logger.info("✅ 문 닫기 명령 전송 완료")
                    else:
                        logger.warning("ESP32 매니저가 없어 문 닫기를 건너뜁니다")
                except Exception as e:
                    logger.warning(f"문 닫기 명령 오류: {e}")
                
                # 대여 완료 처리
                await self._complete_rental_process(locker_id, tx_id, member_id)
                
                return {
                    'success': True,
                    'message': f'락카키 {locker_id} 대여 완료',
                    'action': 'rental_completed',
                    'locker_id': locker_id,
                    'member_id': member_id
                }
            
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
    
    async def _complete_rental_process(self, locker_id: str, tx_id: str, member_id: str):
        """[DEPRECATED - 사용 안 함] 대여 완료 처리 - 실제 선택된 락카키로 기록 업데이트
        
        ⚠️ 이 함수는 더 이상 사용되지 않습니다.
        현재는 api/routes.py의 /rentals/process 엔드포인트가 사용됩니다.
        """
        try:
            from datetime import datetime
            from database.transaction_manager import TransactionStatus
            
            # 1. 대여 기록을 실제 선택된 락카키로 업데이트하고 'active' 상태로 변경
            self.db.execute_query("""
                UPDATE rentals 
                SET locker_number = ?, status = 'active', updated_at = ?
                WHERE transaction_id = ? AND member_id = ?
            """, (locker_id, datetime.now().isoformat(), tx_id, member_id))
            
            # 2. 락커 상태 업데이트 (실제 선택된 락카키)
            self.db.execute_query("""
                UPDATE locker_status 
                SET current_member = ?, updated_at = ?
                WHERE locker_number = ?
            """, (member_id, datetime.now().isoformat(), locker_id))
            
            # 3. 회원 현재 대여 정보 업데이트
            self.db.execute_query("""
                UPDATE members 
                SET currently_renting = ?, 
                    daily_rental_count = daily_rental_count + 1,
                    last_rental_time = ?,
                    updated_at = ?
                WHERE member_id = ?
            """, (locker_id, datetime.now().isoformat(), datetime.now().isoformat(), member_id))
            
            # 4. 트랜잭션 완료 처리
            await self.tx_manager.end_transaction(tx_id, TransactionStatus.COMPLETED)
            
            logger.info(f"센서 기반 대여 완료 처리 성공: 회원 {member_id} → 락커 {locker_id}, 트랜잭션 {tx_id}")
            
        except Exception as e:
            logger.error(f"센서 기반 대여 완료 처리 오류: 회원 {member_id}, 락커 {locker_id}, 트랜잭션 {tx_id}, {e}")
            # 트랜잭션 실패 처리
            await self.tx_manager.end_transaction(tx_id, TransactionStatus.FAILED)

    def close(self):
        """데이터베이스 연결 종료"""
        if self.db:
            self.db.close()
            logger.info("SensorEventHandler 데이터베이스 연결 종료")
