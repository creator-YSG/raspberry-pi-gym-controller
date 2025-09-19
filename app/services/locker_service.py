"""
락카 관리 서비스
"""

from datetime import datetime
from typing import List, Dict, Optional
from app.models.locker import Locker
from app.models.rental import Rental


class LockerService:
    """락카 대여/반납 비즈니스 로직"""
    
    def __init__(self):
        self.google_sheets = None  # 구글시트 매니저
        self.esp32_manager = None  # ESP32 매니저
        
        # TODO: 의존성 주입으로 개선
        self._initialize_dependencies()
    
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
        """사용 가능한 락카 목록 조회"""
        try:
            # TODO: 구글시트에서 실제 데이터 조회
            # 임시 데이터
            available_lockers = []
            
            for i in range(1, 25):  # 24개 락카
                locker_id = f"{zone}{i:02d}"
                if i % 3 != 0:  # 임시로 1/3은 사용중으로 설정
                    available_lockers.append(Locker(
                        id=locker_id,
                        zone=zone,
                        number=i,
                        status='available',
                        size='medium'
                    ))
            
            return available_lockers
            
        except Exception as e:
            print(f"사용 가능한 락카 조회 오류: {e}")
            return []
    
    def get_occupied_lockers(self, zone: str = 'A') -> List[Locker]:
        """사용중인 락카 목록 조회"""
        try:
            # TODO: 구글시트에서 실제 데이터 조회
            occupied_lockers = []
            
            for i in range(1, 25):
                if i % 3 == 0:  # 임시로 1/3은 사용중으로 설정
                    locker_id = f"{zone}{i:02d}"
                    occupied_lockers.append(Locker(
                        id=locker_id,
                        zone=zone,
                        number=i,
                        status='occupied',
                        size='medium',
                        rented_at=datetime.now(),
                        rented_by='test_member'
                    ))
            
            return occupied_lockers
            
        except Exception as e:
            print(f"사용중인 락카 조회 오류: {e}")
            return []
    
    def get_all_lockers(self, zone: str = 'A') -> List[Locker]:
        """모든 락카 목록 조회"""
        available = self.get_available_lockers(zone)
        occupied = self.get_occupied_lockers(zone)
        return available + occupied
    
    def rent_locker(self, locker_id: str, member_id: str) -> Dict:
        """락카 대여"""
        try:
            # 락카 상태 확인
            locker = self.get_locker_by_id(locker_id)
            if not locker:
                return {
                    'success': False,
                    'error': f'{locker_id}번 락카를 찾을 수 없습니다.'
                }
            
            if locker.status == 'occupied':
                return {
                    'success': False,
                    'error': f'{locker_id}번 락카는 이미 사용중입니다.'
                }
            
            # 회원이 이미 대여중인 락카가 있는지 확인
            existing_rental = self.get_active_rental_by_member(member_id)
            if existing_rental:
                return {
                    'success': False,
                    'error': f'이미 {existing_rental.locker_id}번 락카를 대여중입니다.'
                }
            
            # 대여 처리
            rental = Rental(
                id=f"rental_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                locker_id=locker_id,
                member_id=member_id,
                rented_at=datetime.now()
            )
            
            # ESP32에 락카 열기 명령 전송
            success = self._open_locker_hardware(locker_id)
            if not success:
                return {
                    'success': False,
                    'error': '락카 열기에 실패했습니다. 관리자에게 문의하세요.'
                }
            
            # 구글시트에 대여 기록 저장
            # TODO: 실제 구글시트 저장 로직
            
            # 락카 상태 업데이트
            locker.status = 'occupied'
            locker.rented_at = rental.rented_at
            locker.rented_by = member_id
            
            return {
                'success': True,
                'rental': rental,
                'locker': locker,
                'message': f'{locker_id}번 락카가 성공적으로 대여되었습니다.'
            }
            
        except Exception as e:
            print(f"락카 대여 오류: {e}")
            return {
                'success': False,
                'error': '락카 대여 중 시스템 오류가 발생했습니다.'
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
    
    def _open_locker_hardware(self, locker_id: str) -> bool:
        """ESP32를 통해 실제 락카 열기"""
        try:
            if not self.esp32_manager:
                print("ESP32 매니저가 초기화되지 않았습니다.")
                return False
            
            # 락카 ID에 따라 적절한 ESP32 모터 컨트롤러 선택
            if locker_id.startswith('A'):
                device_id = 'esp32_motor1'
            elif locker_id.startswith('B'):
                device_id = 'esp32_motor2'
            else:
                device_id = 'esp32_motor1'  # 기본값
            
            # 락카 열기 명령 전송
            # success = await self.esp32_manager.send_command(
            #     device_id, "OPEN_LOCKER",
            #     locker_id=locker_id, duration_ms=3000
            # )
            
            # 임시로 성공으로 반환 (실제 ESP32 연결 전까지)
            success = True
            
            if success:
                print(f"🔓 락카 열기 성공: {locker_id}")
            else:
                print(f"❌ 락카 열기 실패: {locker_id}")
            
            return success
            
        except Exception as e:
            print(f"락카 하드웨어 제어 오류: {e}")
            return False
