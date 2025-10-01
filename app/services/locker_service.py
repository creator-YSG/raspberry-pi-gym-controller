"""
락카 관리 서비스 (SQLite + 트랜잭션 기반)
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Optional
from app.models.locker import Locker
from app.models.rental import Rental
from app.services.member_service import MemberService
from database import DatabaseManager, TransactionManager
from database.transaction_manager import TransactionType, TransactionStep, TransactionStatus
import logging

logger = logging.getLogger(__name__)


class LockerService:
    """락카 대여/반납 비즈니스 로직 (트랜잭션 기반)"""
    
    def __init__(self, db_path: str = 'locker.db'):
        """LockerService 초기화
        
        Args:
            db_path: SQLite 데이터베이스 파일 경로
        """
        self.db = DatabaseManager(db_path)
        self.db.connect()
        
        # 트랜잭션 매니저 초기화
        self.tx_manager = TransactionManager(self.db)
        
        # 회원 서비스 초기화
        self.member_service = MemberService(db_path)
        
        # ESP32 매니저 (기존 코드 유지)
        self.esp32_manager = None
        # self._initialize_dependencies()  # 테스트를 위해 임시 비활성화
        
        logger.info("LockerService 초기화 완료 (SQLite + 트랜잭션 기반)")
    
    def _initialize_dependencies(self):
        """의존성 초기화"""
        try:
            from core.esp32_manager import create_default_esp32_manager
            from data_sources.google_sheets import GoogleSheetsManager
            
            self.esp32_manager = create_default_esp32_manager()
            # self.google_sheets = GoogleSheetsManager()
            
        except Exception as e:
            print(f"의존성 초기화 오류: {e}")
    
    def get_available_lockers(self, zone: str = 'A') -> List[Locker]:
        """SQLite에서 사용 가능한 락카 목록 조회
        
        Args:
            zone: 락카 구역 (A, B 등)
            
        Returns:
            사용 가능한 Locker 객체 리스트
        """
        try:
            cursor = self.db.execute_query("""
                SELECT * FROM locker_status 
                WHERE zone = ? AND current_member IS NULL AND maintenance_status = 'normal'
                ORDER BY locker_number
            """, (zone,))
            
            if cursor:
                rows = cursor.fetchall()
                available_lockers = []
                
                for row in rows:
                    locker = Locker(
                        id=row['locker_number'],
                        zone=row['zone'],
                        number=int(row['locker_number'][1:]),  # A01 -> 1
                        status='available',  # 사용 가능 상태
                        size=row['size']
                    )
                    available_lockers.append(locker)
                
                logger.info(f"사용 가능한 락카 조회: {zone}구역 {len(available_lockers)}개")
                return available_lockers
            else:
                logger.error(f"락카 조회 쿼리 실행 실패: {zone}구역")
                return []
            
        except Exception as e:
            logger.error(f"사용 가능한 락카 조회 오류: {zone}구역, {e}")
            return []
    
    def get_occupied_lockers(self, zone: str = 'A') -> List[Locker]:
        """SQLite에서 사용중인 락카 목록 조회
        
        Args:
            zone: 락카 구역 (A, B 등)
            
        Returns:
            사용중인 Locker 객체 리스트
        """
        try:
            cursor = self.db.execute_query("""
                SELECT ls.*, r.member_id, r.rental_barcode_time 
                FROM locker_status ls
                LEFT JOIN rentals r ON ls.locker_number = r.locker_number 
                    AND r.status = 'active'
                WHERE ls.zone = ? AND ls.current_member IS NOT NULL
                ORDER BY ls.locker_number
            """, (zone,))
            
            if cursor:
                rows = cursor.fetchall()
                occupied_lockers = []
                
                for row in rows:
                    # 대여 시간 파싱
                    rented_at = None
                    if row['rental_barcode_time']:
                        try:
                            rented_at = datetime.fromisoformat(row['rental_barcode_time'].replace('Z', '+00:00'))
                        except (ValueError, AttributeError):
                            rented_at = datetime.now()
                    
                    locker = Locker(
                        id=row['locker_number'],
                        zone=row['zone'],
                        number=int(row['locker_number'][1:]),  # A01 -> 1
                        status='occupied',  # 사용중 상태
                        size=row['size'],
                        rented_at=rented_at,
                        rented_by=row['current_member'] or row['member_id']
                    )
                    occupied_lockers.append(locker)
                
                logger.info(f"사용중인 락카 조회: {zone}구역 {len(occupied_lockers)}개")
                return occupied_lockers
            else:
                logger.error(f"사용중인 락카 조회 쿼리 실행 실패: {zone}구역")
                return []
            
        except Exception as e:
            logger.error(f"사용중인 락카 조회 오류: {zone}구역, {e}")
            return []
    
    def get_all_lockers(self, zone: str = 'A') -> List[Locker]:
        """모든 락카 목록 조회"""
        available = self.get_available_lockers(zone)
        occupied = self.get_occupied_lockers(zone)
        return available + occupied
    
    async def rent_locker(self, locker_id: str, member_id: str) -> Dict:
        """트랜잭션 기반 안전한 락카 대여
        
        Args:
            locker_id: 대여할 락카 번호 (예: A01)
            member_id: 회원 바코드 ID
            
        Returns:
            대여 결과 딕셔너리
        """
        try:
            logger.info(f"락카 대여 시작: {locker_id} <- {member_id}")
            
            # 1. 회원 검증
            validation_result = self.member_service.validate_member(member_id)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': validation_result['error'],
                    'step': 'member_validation'
                }
            
            member = validation_result['member']
            
            # 2. 락카 상태 확인
            locker = self.get_locker_by_id(locker_id)
            if not locker:
                return {
                    'success': False,
                    'error': f'{locker_id}번 락카를 찾을 수 없습니다.',
                    'step': 'locker_validation'
                }
            
            if locker.status != 'available':
                return {
                    'success': False,
                    'error': f'{locker_id}번 락카는 현재 사용할 수 없습니다. (상태: {locker.status})',
                    'step': 'locker_validation'
                }
            
            # 3. 트랜잭션 시작
            tx_result = await self.tx_manager.start_transaction(member_id, TransactionType.RENTAL)
            if not tx_result['success']:
                return {
                    'success': False,
                    'error': tx_result['error'],
                    'step': 'transaction_start'
                }
            
            tx_id = tx_result['transaction_id']
            logger.info(f"트랜잭션 시작: {tx_id}")
            
            try:
                # 4. 회원 검증 완료 단계
                await self.tx_manager.update_transaction_step(tx_id, TransactionStep.MEMBER_VERIFIED)
                
                # 5. 락카 선택 완료 단계
                await self.tx_manager.update_transaction_step(tx_id, TransactionStep.LOCKER_SELECTED)
                
                # 6. ESP32에 락카 열기 명령 전송
                hardware_success = await self._open_locker_hardware_async(locker_id)
                if not hardware_success:
                    await self.tx_manager.end_transaction(tx_id, TransactionStatus.FAILED)
                    return {
                        'success': False,
                        'error': '락카 열기에 실패했습니다. 관리자에게 문의하세요.',
                        'step': 'hardware_control',
                        'transaction_id': tx_id
                    }
                
                await self.tx_manager.update_transaction_step(tx_id, TransactionStep.HARDWARE_SENT)
                
                # 7. 센서 검증 대기 단계
                await self.tx_manager.update_transaction_step(tx_id, TransactionStep.SENSOR_WAIT)
                
                # 8. 트랜잭션에 락카 정보 업데이트
                self.db.execute_query("""
                    UPDATE active_transactions 
                    SET locker_number = ?, updated_at = ?
                    WHERE transaction_id = ?
                """, (locker_id, datetime.now().isoformat(), tx_id))
                
                # 9. 데이터베이스에 대여 기록 생성 (센서 검증 전에 미리 생성)
                rental_data = {
                    'transaction_id': tx_id,
                    'member_id': member_id,
                    'locker_number': locker_id,
                    'rental_barcode_time': datetime.now().isoformat(),
                    'status': 'pending'  # 센서 검증 대기 중
                }
                
                self.db.execute_query("""
                    INSERT INTO rentals (
                        transaction_id, member_id, locker_number, 
                        rental_barcode_time, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    rental_data['transaction_id'],
                    rental_data['member_id'],
                    rental_data['locker_number'],
                    rental_data['rental_barcode_time'],
                    rental_data['status'],
                    datetime.now().isoformat()
                ))
                
                # 10. 회원 대여 상태 업데이트
                self.member_service.update_member(member_id, {
                    'currently_renting': locker_id,
                    'daily_rental_count': member.daily_rental_count + 1,
                    'last_rental_time': datetime.now().isoformat()
                })
                
                # 11. 락카 상태를 대여 대기로 변경 (센서 검증 대기)
                self.db.execute_query("""
                    UPDATE locker_status 
                    SET current_member = ?, current_transaction = ?, updated_at = ?
                    WHERE locker_number = ?
                """, (member_id, tx_id, datetime.now().isoformat(), locker_id))
                
                logger.info(f"락카 대여 트랜잭션 준비 완료: {tx_id}, 센서 검증 대기 중...")
                
                # 센서 검증은 별도의 이벤트 핸들러에서 처리됨
                # (ESP32에서 센서 이벤트가 오면 자동으로 완료 처리)
                
                return {
                    'success': True,
                    'transaction_id': tx_id,
                    'locker_id': locker_id,
                    'member_id': member_id,
                    'member_name': member.name,
                    'step': 'sensor_wait',
                    'message': f'{member.name}님, {locker_id}번 락카에서 키를 빼주세요.',
                    'timeout_seconds': 30
                }
                
            except Exception as e:
                # 트랜잭션 실패 시 롤백
                await self.tx_manager.end_transaction(tx_id, TransactionStatus.FAILED)
                logger.error(f"트랜잭션 처리 중 오류: {tx_id}, {e}")
                raise e
                
        except Exception as e:
            logger.error(f"락카 대여 오류: {locker_id} <- {member_id}, {e}")
            return {
                'success': False,
                'error': '락카 대여 중 시스템 오류가 발생했습니다.',
                'step': 'system_error'
            }
    
    def return_locker(self, locker_id: str) -> Dict:
        """락카 반납"""
        try:
            # 락카 대여 기록 확인
            rental = self.get_active_rental_by_locker(locker_id)
            if not rental:
                return {
                    'success': False,
                    'error': f'{locker_id}번 락카는 대여 기록이 없습니다.'
                }
            
            # ESP32에 락카 열기 명령 전송
            success = self._open_locker_hardware(locker_id)
            if not success:
                return {
                    'success': False,
                    'error': '락카 열기에 실패했습니다. 관리자에게 문의하세요.'
                }
            
            # 반납 처리
            rental.returned_at = datetime.now()
            rental.status = 'returned'
            
            # 락카 상태 업데이트
            locker = self.get_locker_by_id(locker_id)
            if locker:
                locker.status = 'available'
                locker.rented_at = None
                locker.rented_by = None
            
            # 구글시트에 반납 기록 저장
            # TODO: 실제 구글시트 저장 로직
            
            return {
                'success': True,
                'rental': rental,
                'locker': locker,
                'message': f'{locker_id}번 락카가 성공적으로 반납되었습니다.'
            }
            
        except Exception as e:
            print(f"락카 반납 오류: {e}")
            return {
                'success': False,
                'error': '락카 반납 중 시스템 오류가 발생했습니다.'
            }
    
    def get_locker_by_id(self, locker_id: str) -> Optional[Locker]:
        """락카 ID로 락카 조회"""
        zone = locker_id[0] if locker_id else 'A'
        all_lockers = self.get_all_lockers(zone)
        
        for locker in all_lockers:
            if locker.id == locker_id:
                return locker
        
        return None
    
    def get_active_rental_by_member(self, member_id: str) -> Optional[Rental]:
        """회원의 활성 대여 기록 조회"""
        # TODO: 구글시트에서 실제 데이터 조회
        return None
    
    def get_active_rental_by_locker(self, locker_id: str) -> Optional[Rental]:
        """락카의 활성 대여 기록 조회"""
        # TODO: 구글시트에서 실제 데이터 조회
        # 임시로 더미 데이터 반환
        if locker_id and locker_id.endswith(('03', '06', '09')):  # 임시 조건
            return Rental(
                id=f"rental_{locker_id}",
                locker_id=locker_id,
                member_id='test_member',
                rented_at=datetime.now()
            )
        return None
    
    async def _open_locker_hardware_async(self, locker_id: str) -> bool:
        """ESP32를 통해 실제 락카 열기 (비동기)"""
        try:
            if not self.esp32_manager:
                logger.warning("ESP32 매니저가 초기화되지 않았습니다. 시뮬레이션 모드로 실행")
                # 시뮬레이션 모드: 항상 성공
                await asyncio.sleep(0.5)  # 하드웨어 지연 시뮬레이션
                logger.info(f"🔓 락카 열기 성공 (시뮬레이션): {locker_id}")
                return True
            
            # 락카 ID에 따라 적절한 ESP32 모터 컨트롤러 선택
            if locker_id.startswith('A'):
                device_id = 'esp32_motor1'
            elif locker_id.startswith('B'):
                device_id = 'esp32_motor2'
            else:
                device_id = 'esp32_motor1'  # 기본값
            
            # 락카 열기 명령 전송
            success = await self.esp32_manager.send_command(
                device_id, "OPEN_LOCKER",
                locker_id=locker_id, duration_ms=3000
            )
            
            if success:
                logger.info(f"🔓 락카 열기 성공: {locker_id}")
            else:
                logger.error(f"❌ 락카 열기 실패: {locker_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"락카 하드웨어 제어 오류: {locker_id}, {e}")
            return False
    
    def _open_locker_hardware(self, locker_id: str) -> bool:
        """ESP32를 통해 실제 락카 열기 (동기 - 기존 호환성)"""
        try:
            # 비동기 메서드를 동기적으로 실행
            return asyncio.run(self._open_locker_hardware_async(locker_id))
        except Exception as e:
            logger.error(f"동기 락카 하드웨어 제어 오류: {locker_id}, {e}")
            return False
    
    def get_locker_by_id(self, locker_id: str) -> Optional[Locker]:
        """락카 ID로 락카 조회 (SQLite 기반)"""
        try:
            cursor = self.db.execute_query("""
                SELECT ls.*, r.member_id, r.rental_barcode_time 
                FROM locker_status ls
                LEFT JOIN rentals r ON ls.locker_number = r.locker_number 
                    AND r.status = 'active'
                WHERE ls.locker_number = ?
            """, (locker_id,))
            
            if cursor:
                row = cursor.fetchone()
                if row:
                    # 대여 시간 파싱
                    rented_at = None
                    if row['rental_barcode_time']:
                        try:
                            rented_at = datetime.fromisoformat(row['rental_barcode_time'].replace('Z', '+00:00'))
                        except (ValueError, AttributeError):
                            pass
                    
                    # 락카 상태 결정
                    if row['current_member']:
                        status = 'occupied'
                    elif row['maintenance_status'] != 'normal':
                        status = 'maintenance'
                    else:
                        status = 'available'
                    
                    locker = Locker(
                        id=row['locker_number'],
                        zone=row['zone'],
                        number=int(row['locker_number'][1:]),  # A01 -> 1
                        status=status,
                        size=row['size'],
                        rented_at=rented_at,
                        rented_by=row['current_member'] or row['member_id']
                    )
                    return locker
                else:
                    logger.warning(f"락카 없음: {locker_id}")
                    return None
            else:
                logger.error(f"락카 조회 쿼리 실행 실패: {locker_id}")
                return None
                
        except Exception as e:
            logger.error(f"락카 조회 오류: {locker_id}, {e}")
            return None
    
    def close(self):
        """데이터베이스 연결 종료"""
        if self.member_service:
            self.member_service.close()
        if self.db:
            self.db.close()
        logger.info("LockerService 데이터베이스 연결 종료")
