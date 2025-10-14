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
    
    def __init__(self, db_path: str = 'instance/gym_system.db'):
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
    
    def get_available_lockers(self, zone: str = 'MALE', member_id: str = None) -> List[Locker]:
        """SQLite에서 사용 가능한 락카 목록 조회
        
        Args:
            zone: 락카 구역 (MALE, FEMALE, STAFF 등)
            member_id: 회원 ID (권한 체크용, 선택사항)
            
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
                    # device_id 안전하게 가져오기
                    try:
                        device_id = row['device_id'] if 'device_id' in row.keys() else 'esp32_main'
                    except:
                        device_id = 'esp32_main'
                    
                    locker = Locker(
                        id=row['locker_number'],
                        zone=row['zone'],
                        number=int(row['locker_number'][1:]),  # M01 -> 1, F01 -> 1, S01 -> 1
                        status='available',  # 사용 가능 상태
                        size=row['size'],
                        device_id=device_id
                    )
                    available_lockers.append(locker)
                
                # 회원 권한 체크가 필요한 경우
                if member_id:
                    try:
                        member = self.member_service.get_member(member_id)
                        if member and not member.can_access_zone(zone):
                            logger.warning(f"회원 {member_id}는 {zone} 구역에 접근할 수 없음")
                            return []
                    except Exception as e:
                        logger.error(f"회원 권한 체크 오류: {e}")
                
                logger.info(f"사용 가능한 락카 조회: {zone}구역 {len(available_lockers)}개")
                return available_lockers
            else:
                logger.error(f"락카 조회 쿼리 실행 실패: {zone}구역")
                return []
            
        except Exception as e:
            logger.error(f"사용 가능한 락카 조회 오류: {zone}구역, {e}")
            return []
    
    def get_occupied_lockers(self, zone: str = 'MALE') -> List[Locker]:
        """SQLite에서 사용중인 락카 목록 조회
        
        Args:
            zone: 락카 구역 (MALE, FEMALE, STAFF 등)
            
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
                    
                    # device_id 안전하게 가져오기
                    try:
                        device_id = row['device_id'] if 'device_id' in row.keys() else 'esp32_main'
                    except:
                        device_id = 'esp32_main'
                    
                    locker = Locker(
                        id=row['locker_number'],
                        zone=row['zone'],
                        number=int(row['locker_number'][1:]),  # M01 -> 1, F01 -> 1, S01 -> 1
                        status='occupied',  # 사용중 상태
                        size=row['size'],
                        device_id=device_id,
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
    
    def get_all_lockers(self, zone: str = 'MALE') -> List[Locker]:
        """모든 락카 목록 조회"""
        available = self.get_available_lockers(zone)
        occupied = self.get_occupied_lockers(zone)
        return available + occupied
    
    async def rent_locker(self, locker_id: str, member_id: str) -> Dict:
        """트랜잭션 기반 안전한 락카 대여
        
        Args:
            locker_id: 대여할 락카 번호 (예: M01, F01, S01)
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
            
            # 3. 락카 구역 접근 권한 확인
            if not member.can_access_zone(locker.zone):
                zone_names = {
                    'MALE': '남자',
                    'FEMALE': '여자', 
                    'STAFF': '교직원'
                }
                return {
                    'success': False,
                    'error': f'{member.name}님은 {zone_names.get(locker.zone, locker.zone)} 구역 락카를 사용할 수 없습니다.',
                    'step': 'zone_access_denied'
                }
            
            # 4. 트랜잭션 시작
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
                # 5. 회원 검증 완료 단계
                await self.tx_manager.update_transaction_step(tx_id, TransactionStep.MEMBER_VERIFIED)
                
                # 6. 락카 선택 완료 단계
                await self.tx_manager.update_transaction_step(tx_id, TransactionStep.LOCKER_SELECTED)
                
                # 7. ESP32에 락카 열기 명령 전송
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
                
                # 8. 센서 검증 대기 단계 - 실제 락카키 감지 로직
                await self.tx_manager.update_transaction_step(tx_id, TransactionStep.SENSOR_WAIT)
                
                # 🆕 실제 락카키 감지 및 대여 완료 처리 (회원이 선택한 락카키 감지)
                sensor_result = await self._wait_for_any_locker_key_removal(member_id, tx_id)
                if not sensor_result['success']:
                    await self.tx_manager.end_transaction(tx_id, TransactionStatus.FAILED)
                    return {
                        'success': False,
                        'error': sensor_result['error'],
                        'step': 'sensor_detection',
                        'transaction_id': tx_id
                    }
                
                # 실제로 빼간 락카키 정보로 업데이트
                actual_locker_id = sensor_result['locker_id']
                logger.info(f"회원이 실제 선택한 락카키: {actual_locker_id}")
                
                # 9. 트랜잭션에 락카 정보 업데이트
                self.db.execute_query("""
                    UPDATE active_transactions 
                    SET locker_number = ?, updated_at = ?
                    WHERE transaction_id = ?
                """, (locker_id, datetime.now().isoformat(), tx_id))
                
                # 10. 데이터베이스에 대여 기록 생성 (센서 검증 전에 미리 생성)
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
                
                # 11. 회원 대여 상태 업데이트
                self.member_service.update_member(member_id, {
                    'currently_renting': locker_id,
                    'daily_rental_count': member.daily_rental_count + 1,
                    'last_rental_time': datetime.now().isoformat()
                })
                
                # 12. 락카 상태를 대여 대기로 변경 (센서 검증 대기)
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
        zone = locker_id[0] if locker_id else 'M'
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
            
            # 락카 ID에 따라 적절한 ESP32 디바이스 선택
            # M01~M70 → esp32_male, F01~F50 → esp32_female, S01~S20 → esp32_staff
            if locker_id.startswith('M'):
                device_id = 'esp32_male'
            elif locker_id.startswith('F'):
                device_id = 'esp32_female'
            elif locker_id.startswith('S'):
                device_id = 'esp32_staff'
            else:
                # 구 시스템 호환 (A, B)
                if locker_id.startswith('A'):
                    device_id = 'esp32_motor1'
                elif locker_id.startswith('B'):
                    device_id = 'esp32_motor2'
                else:
                    device_id = 'esp32_main'  # 기본값
            
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
    
    async def _wait_for_any_locker_key_removal(self, member_id: str, tx_id: str) -> dict:
        """실제 헬스장 운영 로직: 회원이 선택한 락카키 감지 및 문 닫기"""
        import serial
        import json
        import time
        
        # 센서 핀 → 락카키 번호 매핑 (테스트용)
        def get_locker_id_from_sensor(chip_idx: int, pin: int) -> str:
            # 테스트: 핀 9 → M10 락카키
            if chip_idx == 0 and pin == 9:
                return "M10"
            # 추후 확장 가능
            elif chip_idx == 0 and pin == 0:
                return "M01"
            elif chip_idx == 0 and pin == 1:
                return "M02"
            # 기본값
            return f"M{pin+1:02d}"
        
        try:
            logger.info(f"회원 {member_id} 락카키 선택 대기 시작")
            
            # ESP32 직접 연결
            ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=1)
            await asyncio.sleep(1)
            
            # 1단계: 락카키 제거 대기 (최대 20초)
            logger.info("락카키 제거 대기 중... (최대 20초)")
            selected_locker_id = None
            start_time = time.time()
            
            while time.time() - start_time < 20:  # 20초 대기
                if ser.in_waiting > 0:
                    try:
                        response = ser.readline().decode().strip()
                        if response and 'sensor_triggered' in response:
                            data = json.loads(response)
                            sensor_data = data.get('data', {})
                            
                            # 센서 활성화 (락카키 제거됨) - Python에서 반대로 해석
                            if not sensor_data.get('active'):  # active가 false면 락카키 제거됨
                                chip_idx = sensor_data.get('chip_idx', 0)
                                pin = sensor_data.get('pin', 0)
                                selected_locker_id = get_locker_id_from_sensor(chip_idx, pin)
                                logger.info(f"락카키 제거 감지: 칩{chip_idx}, 핀{pin} → 락카키 {selected_locker_id}")
                                break
                                
                    except Exception as e:
                        logger.debug(f"센서 데이터 파싱 오류: {e}")
                
                await asyncio.sleep(0.1)
            
            if not selected_locker_id:
                ser.close()
                logger.warning(f"락카키 제거 타임아웃: 회원 {member_id}")
                return {
                    'success': False,
                    'error': '락카키를 선택하지 않았거나 센서 오류입니다. 다시 시도해주세요.'
                }
            
            # 2단계: 손 끼임 방지 대기 (3초)
            logger.info("손 끼임 방지 대기 중... (3초)")
            await asyncio.sleep(3)
            
            # 3단계: 락커 문 닫기
            logger.info(f"락커 문 닫기")
            close_cmd = {'command': 'motor_move', 'revs': -0.917, 'rpm': 30}
            ser.write((json.dumps(close_cmd) + '\n').encode())
            
            # 문 닫기 완료 대기 (최대 5초)
            close_completed = False
            start_time = time.time()
            
            while time.time() - start_time < 5:
                if ser.in_waiting > 0:
                    try:
                        response = ser.readline().decode().strip()
                        if response and ('motor_moved' in response or '모터] 완료' in response):
                            logger.info("락커 문 닫기 완료")
                            close_completed = True
                            break
                    except:
                        pass
                await asyncio.sleep(0.1)
            
            ser.close()
            
            if close_completed:
                logger.info(f"락카키 대여 완료: {selected_locker_id}")
                
                # 🆕 대여 완료 처리 - 실제 선택된 락카키로 기록
                await self._complete_rental_process(selected_locker_id, tx_id, member_id)
                
                return {
                    'success': True,
                    'locker_id': selected_locker_id,
                    'message': f'락카키 {selected_locker_id} 대여가 완료되었습니다.'
                }
            else:
                logger.warning(f"문 닫기 미완료: {selected_locker_id}")
                
                # 락카키는 제거되었으므로 대여 완료 처리
                await self._complete_rental_process(selected_locker_id, tx_id, member_id)
                
                return {
                    'success': True,  # 락카키는 제거되었으므로 성공으로 처리
                    'locker_id': selected_locker_id,
                    'message': f'락카키 {selected_locker_id} 대여 완료 (문 닫기 상태 미확인)'
                }
                
        except Exception as e:
            logger.error(f"락카키 제거 감지 오류: 회원 {member_id}, {e}")
            return {
                'success': False,
                'error': f'센서 시스템 오류: {str(e)}'
            }
    
    async def _complete_rental_process(self, locker_id: str, tx_id: str, member_id: str):
        """대여 완료 처리 - 실제 선택된 락카키로 기록 업데이트"""
        try:
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
            
            logger.info(f"대여 완료 처리 성공: 회원 {member_id} → 락커 {locker_id}, 트랜잭션 {tx_id}")
            
        except Exception as e:
            logger.error(f"대여 완료 처리 오류: 회원 {member_id}, 락커 {locker_id}, 트랜잭션 {tx_id}, {e}")
            # 트랜잭션 실패 처리
            await self.tx_manager.end_transaction(tx_id, TransactionStatus.FAILED)
    
    async def _validate_member_for_rental(self, member_id: str) -> dict:
        """회원 대여 검증 (공통 로직)"""
        try:
            # 회원 검증
            validation_result = self.member_service.validate_member(member_id)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': validation_result['error'],
                    'step': 'member_validation'
                }
            
            member = validation_result['member']
            
            # 이미 대여 중인지 확인
            if member.currently_renting:
                return {
                    'success': False,
                    'error': f'{member.name}님은 이미 {member.currently_renting}번 락카를 대여 중입니다.',
                    'step': 'already_renting'
                }
            
            return {
                'success': True,
                'member': member
            }
            
        except Exception as e:
            logger.error(f"회원 검증 오류: {member_id}, {e}")
            return {
                'success': False,
                'error': f'회원 검증 중 오류가 발생했습니다: {str(e)}',
                'step': 'validation_error'
            }
    
    async def rent_locker_by_sensor(self, member_id: str) -> dict:
        """실제 헬스장 운영 로직: 회원 검증 → 문 열림 → 센서로 락카키 감지 → 대여 완료"""
        logger.info(f"실제 헬스장 대여 프로세스 시작: 회원 {member_id}")
        
        try:
            # 1. 회원 검증
            validation_result = await self._validate_member_for_rental(member_id)
            if not validation_result['success']:
                return validation_result
            
            member = validation_result['member']
            logger.info(f"회원 검증 완료: {member.name} ({member.member_category})")
            
            # 2. 트랜잭션 시작
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
                # 3. 회원 검증 완료 단계
                await self.tx_manager.update_transaction_step(tx_id, TransactionStep.MEMBER_VERIFIED)
                
                # 4. 임시 대여 기록 생성 (락카키는 나중에 센서로 결정)
                rental_time = datetime.now().isoformat()
                self.db.execute_query("""
                    INSERT INTO rentals (member_id, locker_number, status, rental_barcode_time, transaction_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (member_id, 'PENDING', 'pending', rental_time, tx_id, rental_time))
                
                # 5. 하드웨어 제어 - 바로 문 열기
                await self.tx_manager.update_transaction_step(tx_id, TransactionStep.HARDWARE_SENT)
                
                logger.info("🔓 락커 문 열기 (회원 검증 완료)")
                hardware_result = await self._open_locker_door_direct()
                if not hardware_result:
                    await self.tx_manager.end_transaction(tx_id, TransactionStatus.FAILED)
                    return {
                        'success': False,
                        'error': '락커 문 열기에 실패했습니다.',
                        'step': 'hardware_control',
                        'transaction_id': tx_id
                    }
                
                # 6. 센서 검증 대기 단계
                await self.tx_manager.update_transaction_step(tx_id, TransactionStep.SENSOR_WAIT)
                
                # 7. 실제 락카키 감지 및 대여 완료 처리
                sensor_result = await self._wait_for_any_locker_key_removal(member_id, tx_id)
                if not sensor_result['success']:
                    await self.tx_manager.end_transaction(tx_id, TransactionStatus.FAILED)
                    return {
                        'success': False,
                        'error': sensor_result['error'],
                        'step': 'sensor_detection',
                        'transaction_id': tx_id
                    }
                
                # 8. 성공 응답
                actual_locker_id = sensor_result['locker_id']
                return {
                    'success': True,
                    'locker_id': actual_locker_id,
                    'member_id': member_id,
                    'transaction_id': tx_id,
                    'message': sensor_result['message'],
                    'step': 'completed'
                }
                
            except Exception as e:
                logger.error(f"대여 프로세스 오류: {member_id}, {e}")
                await self.tx_manager.end_transaction(tx_id, TransactionStatus.FAILED)
                return {
                    'success': False,
                    'error': f'대여 처리 중 오류가 발생했습니다: {str(e)}',
                    'step': 'process_error',
                    'transaction_id': tx_id
                }
                
        except Exception as e:
            logger.error(f"실제 헬스장 대여 프로세스 오류: {member_id}, {e}")
            return {
                'success': False,
                'error': f'시스템 오류: {str(e)}',
                'step': 'system_error'
            }
    
    async def _open_locker_door_direct(self) -> bool:
        """ESP32와 직접 통신으로 락커 문 열기"""
        import serial
        import json
        import time
        
        try:
            logger.info("ESP32 직접 연결로 문 열기")
            ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=2)
            await asyncio.sleep(1)
            
            # 문 열기 명령 전송
            open_cmd = {'command': 'motor_move', 'revs': 0.917, 'rpm': 30}
            ser.write((json.dumps(open_cmd) + '\n').encode())
            
            # 완료 대기 (최대 10초)
            start_time = time.time()
            while time.time() - start_time < 10:
                if ser.in_waiting > 0:
                    try:
                        response = ser.readline().decode().strip()
                        if response and ('motor_moved' in response or '모터] 완료' in response):
                            logger.info("락커 문 열기 완료")
                            ser.close()
                            return True
                    except:
                        pass
                await asyncio.sleep(0.1)
            
            ser.close()
            logger.warning("락커 문 열기 타임아웃")
            return False
            
        except Exception as e:
            logger.error(f"락커 문 열기 오류: {e}")
            return False
    
    async def return_locker_by_sensor(self, member_id: str) -> dict:
        """실제 헬스장 반납 로직: 회원 검증 → 빌린 락카키 확인 → 문 열림 → 센서로 삽입 감지 → 반납 완료"""
        logger.info(f"실제 헬스장 반납 프로세스 시작: 회원 {member_id}")
        
        try:
            # 1. 회원 검증 및 대여 상태 확인
            validation_result = await self._validate_member_for_return(member_id)
            if not validation_result['success']:
                return validation_result
            
            member = validation_result['member']
            rented_locker_id = validation_result['rented_locker_id']
            logger.info(f"반납 대상: {member.name} → 락카키 {rented_locker_id}")
            
            # 2. 트랜잭션 시작
            tx_result = await self.tx_manager.start_transaction(member_id, TransactionType.RETURN)
            if not tx_result['success']:
                return {
                    'success': False,
                    'error': tx_result['error'],
                    'step': 'transaction_start'
                }
            
            tx_id = tx_result['transaction_id']
            logger.info(f"반납 트랜잭션 시작: {tx_id}")
            
            try:
                # 3. 회원 검증 완료 단계
                await self.tx_manager.update_transaction_step(tx_id, TransactionStep.MEMBER_VERIFIED)
                
                # 4. 임시 반납 기록 생성
                return_time = datetime.now().isoformat()
                self.db.execute_query("""
                    INSERT INTO rentals (member_id, locker_number, status, return_barcode_time, transaction_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (member_id, rented_locker_id, 'returning', return_time, tx_id, return_time))
                
                # 5. 하드웨어 제어 - 바로 문 열기
                await self.tx_manager.update_transaction_step(tx_id, TransactionStep.HARDWARE_SENT)
                
                logger.info("🔓 락커 문 열기 (반납 프로세스)")
                hardware_result = await self._open_locker_door_direct()
                if not hardware_result:
                    await self.tx_manager.end_transaction(tx_id, TransactionStatus.FAILED)
                    return {
                        'success': False,
                        'error': '락커 문 열기에 실패했습니다.',
                        'step': 'hardware_control',
                        'transaction_id': tx_id
                    }
                
                # 6. 센서 검증 대기 단계
                await self.tx_manager.update_transaction_step(tx_id, TransactionStep.SENSOR_WAIT)
                
                # 7. 실제 락카키 삽입 감지 및 반납 완료 처리
                sensor_result = await self._wait_for_locker_key_insertion(member_id, rented_locker_id, tx_id)
                if not sensor_result['success']:
                    await self.tx_manager.end_transaction(tx_id, TransactionStatus.FAILED)
                    return {
                        'success': False,
                        'error': sensor_result['error'],
                        'step': 'sensor_detection',
                        'transaction_id': tx_id
                    }
                
                # 8. 성공 응답
                return {
                    'success': True,
                    'locker_id': rented_locker_id,
                    'member_id': member_id,
                    'transaction_id': tx_id,
                    'message': sensor_result['message'],
                    'step': 'completed'
                }
                
            except Exception as e:
                logger.error(f"반납 프로세스 오류: {member_id}, {e}")
                await self.tx_manager.end_transaction(tx_id, TransactionStatus.FAILED)
                return {
                    'success': False,
                    'error': f'반납 처리 중 오류가 발생했습니다: {str(e)}',
                    'step': 'process_error',
                    'transaction_id': tx_id
                }
                
        except Exception as e:
            logger.error(f"실제 헬스장 반납 프로세스 오류: {member_id}, {e}")
            return {
                'success': False,
                'error': f'시스템 오류: {str(e)}',
                'step': 'system_error'
            }
    
    async def _validate_member_for_return(self, member_id: str) -> dict:
        """회원 반납 검증 (현재 대여 중인지 확인)"""
        try:
            # 회원 검증
            validation_result = self.member_service.validate_member(member_id)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': validation_result['error'],
                    'step': 'member_validation'
                }
            
            member = validation_result['member']
            
            # 현재 대여 중인지 확인
            if not member.currently_renting:
                return {
                    'success': False,
                    'error': f'{member.name}님은 현재 대여 중인 락카가 없습니다.',
                    'step': 'no_rental'
                }
            
            return {
                'success': True,
                'member': member,
                'rented_locker_id': member.currently_renting
            }
            
        except Exception as e:
            logger.error(f"회원 반납 검증 오류: {member_id}, {e}")
            return {
                'success': False,
                'error': f'회원 검증 중 오류가 발생했습니다: {str(e)}',
                'step': 'validation_error'
            }
    
    async def _wait_for_locker_key_insertion(self, member_id: str, expected_locker_id: str, tx_id: str) -> dict:
        """실제 헬스장 반납 로직: 정확한 락카키 삽입 감지 및 문 닫기"""
        import serial
        import json
        import time
        
        # 센서 핀 → 락카키 번호 매핑 (테스트용)
        def get_locker_id_from_sensor(chip_idx: int, pin: int) -> str:
            # 테스트: 핀 9 → M10 락카키
            if chip_idx == 0 and pin == 9:
                return "M10"
            # 추후 확장 가능
            elif chip_idx == 0 and pin == 0:
                return "M01"
            elif chip_idx == 0 and pin == 1:
                return "M02"
            # 기본값
            return f"M{pin+1:02d}"
        
        try:
            logger.info(f"회원 {member_id} 락카키 {expected_locker_id} 삽입 대기 시작")
            
            # ESP32 직접 연결
            ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=1)
            await asyncio.sleep(1)
            
            # 1단계: 락카키 삽입 대기 (최대 20초)
            logger.info(f"락카키 {expected_locker_id} 삽입 대기 중... (최대 20초)")
            key_inserted = False
            start_time = time.time()
            
            while time.time() - start_time < 20:  # 20초 대기
                if ser.in_waiting > 0:
                    try:
                        response = ser.readline().decode().strip()
                        if response and 'sensor_triggered' in response:
                            data = json.loads(response)
                            sensor_data = data.get('data', {})
                            
                            # 센서 활성화 (락카키 삽입됨) - Python에서 반대로 해석
                            if sensor_data.get('active'):  # active가 true면 락카키 삽입됨
                                chip_idx = sensor_data.get('chip_idx', 0)
                                pin = sensor_data.get('pin', 0)
                                detected_locker_id = get_locker_id_from_sensor(chip_idx, pin)
                                
                                logger.info(f"락카키 삽입 감지: 칩{chip_idx}, 핀{pin} → 락카키 {detected_locker_id}")
                                
                                # 정확한 락카키인지 확인
                                if detected_locker_id == expected_locker_id:
                                    logger.info(f"✅ 정확한 락카키 {expected_locker_id} 삽입 확인!")
                                    key_inserted = True
                                    break
                                else:
                                    logger.warning(f"❌ 잘못된 락카키 삽입: {detected_locker_id} (예상: {expected_locker_id})")
                                    
                    except Exception as e:
                        logger.debug(f"센서 데이터 파싱 오류: {e}")
                
                await asyncio.sleep(0.1)
            
            if not key_inserted:
                ser.close()
                logger.warning(f"락카키 삽입 타임아웃: 회원 {member_id}, 예상 락카키 {expected_locker_id}")
                return {
                    'success': False,
                    'error': f'락카키 {expected_locker_id}를 제자리에 삽입하지 않았거나 센서 오류입니다.'
                }
            
            # 2단계: 손 끼임 방지 대기 (3초)
            logger.info("손 끼임 방지 대기 중... (3초)")
            await asyncio.sleep(3)
            
            # 3단계: 락커 문 닫기
            logger.info(f"락커 문 닫기")
            close_cmd = {'command': 'motor_move', 'revs': -0.917, 'rpm': 30}
            ser.write((json.dumps(close_cmd) + '\n').encode())
            
            # 문 닫기 완료 대기 (최대 5초)
            close_completed = False
            start_time = time.time()
            
            while time.time() - start_time < 5:
                if ser.in_waiting > 0:
                    try:
                        response = ser.readline().decode().strip()
                        if response and ('motor_moved' in response or '모터] 완료' in response):
                            logger.info("락커 문 닫기 완료")
                            close_completed = True
                            break
                    except:
                        pass
                await asyncio.sleep(0.1)
            
            ser.close()
            
            if close_completed:
                logger.info(f"락카키 반납 완료: {expected_locker_id}")
                
                # 🆕 반납 완료 처리 - 실제 반납된 락카키로 기록
                await self._complete_return_process(expected_locker_id, tx_id, member_id)
                
                return {
                    'success': True,
                    'locker_id': expected_locker_id,
                    'message': f'락카키 {expected_locker_id} 반납이 완료되었습니다.'
                }
            else:
                logger.warning(f"문 닫기 미완료: {expected_locker_id}")
                
                # 락카키는 삽입되었으므로 반납 완료 처리
                await self._complete_return_process(expected_locker_id, tx_id, member_id)
                
                return {
                    'success': True,  # 락카키는 삽입되었으므로 성공으로 처리
                    'locker_id': expected_locker_id,
                    'message': f'락카키 {expected_locker_id} 반납 완료 (문 닫기 상태 미확인)'
                }
                
        except Exception as e:
            logger.error(f"락카키 삽입 감지 오류: 회원 {member_id}, 예상 락카키 {expected_locker_id}, {e}")
            return {
                'success': False,
                'error': f'센서 시스템 오류: {str(e)}'
            }
    
    async def _complete_return_process(self, locker_id: str, tx_id: str, member_id: str):
        """반납 완료 처리 - 대여 기록 종료 및 상태 업데이트"""
        try:
            # 1. 기존 대여 기록을 'returned' 상태로 업데이트
            self.db.execute_query("""
                UPDATE rentals 
                SET status = 'returned', return_barcode_time = ?, updated_at = ?
                WHERE member_id = ? AND locker_number = ? AND status = 'active'
            """, (datetime.now().isoformat(), datetime.now().isoformat(), member_id, locker_id))
            
            # 2. 락커 상태 초기화
            self.db.execute_query("""
                UPDATE locker_status 
                SET current_member = NULL, updated_at = ?
                WHERE locker_number = ?
            """, (datetime.now().isoformat(), locker_id))
            
            # 3. 회원 현재 대여 정보 초기화
            self.db.execute_query("""
                UPDATE members 
                SET currently_renting = NULL, 
                    last_rental_time = ?,
                    updated_at = ?
                WHERE member_id = ?
            """, (datetime.now().isoformat(), datetime.now().isoformat(), member_id))
            
            # 4. 트랜잭션 완료 처리
            await self.tx_manager.end_transaction(tx_id, TransactionStatus.COMPLETED)
            
            logger.info(f"반납 완료 처리 성공: 회원 {member_id} → 락커 {locker_id}, 트랜잭션 {tx_id}")
            
        except Exception as e:
            logger.error(f"반납 완료 처리 오류: 회원 {member_id}, 락커 {locker_id}, 트랜잭션 {tx_id}, {e}")
            # 트랜잭션 실패 처리
            await self.tx_manager.end_transaction(tx_id, TransactionStatus.FAILED)
    
    def get_locker_by_id(self, locker_id: str) -> Optional[Locker]:
        """락카 ID로 락카 조회 (SQLite 기반)"""
        try:
            cursor = self.db.execute_query("""
                SELECT ls.locker_number, ls.zone, ls.device_id, ls.size, 
                       ls.sensor_status, ls.current_member, ls.maintenance_status,
                       r.member_id, r.rental_barcode_time 
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
                    
                    # device_id 안전하게 가져오기
                    try:
                        device_id = row['device_id'] if 'device_id' in row.keys() else 'esp32_main'
                    except:
                        device_id = 'esp32_main'
                    
                    locker = Locker(
                        id=row['locker_number'],
                        zone=row['zone'],
                        number=int(row['locker_number'][1:]),  # M01 -> 1, F01 -> 1, S01 -> 1
                        status=status,
                        size=row['size'],
                        device_id=device_id,
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
