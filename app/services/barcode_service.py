"""
바코드 처리 서비스
"""

import re
from typing import Dict
from app.services.member_service import MemberService
from app.services.locker_service import LockerService


class BarcodeService:
    """바코드 스캔 및 처리 비즈니스 로직"""
    
    def __init__(self):
        self.member_service = MemberService()
        self.locker_service = LockerService()
    
    def process_barcode(self, barcode: str, scan_type: str = 'auto') -> Dict:
        """바코드 처리 메인 로직"""
        try:
            if not barcode or not barcode.strip():
                return {
                    'success': False,
                    'error': '바코드 데이터가 없습니다.'
                }
            
            barcode = barcode.strip()
            
            # 바코드 타입 자동 판별
            if scan_type == 'auto':
                scan_type = self._detect_barcode_type(barcode)
            
            if scan_type == 'member':
                return self._process_member_barcode(barcode)
            elif scan_type == 'locker_key':
                return self._process_locker_key_barcode(barcode)
            else:
                # 알 수 없는 바코드 - 회원 바코드로 시도
                result = self._process_member_barcode(barcode)
                if result['success']:
                    return result
                
                # 락카키 바코드로 시도
                return self._process_locker_key_barcode(barcode)
                
        except Exception as e:
            print(f"바코드 처리 오류: {e}")
            return {
                'success': False,
                'error': '바코드 처리 중 시스템 오류가 발생했습니다.'
            }
    
    def _detect_barcode_type(self, barcode: str) -> str:
        """바코드 타입 자동 감지"""
        
        # 락카키 바코드 패턴 (예: LOCKER_A01, KEY_B15)
        if re.match(r'^(LOCKER|KEY)_[A-Z]\d{2}$', barcode):
            return 'locker_key'
        
        # 락카 ID 패턴 (예: A01, B15)
        if re.match(r'^[A-Z]\d{2}$', barcode):
            return 'locker_key'
        
        # 회원 바코드는 숫자로 가정
        if barcode.isdigit():
            return 'member'
        
        # 기타 영숫자 조합은 회원 바코드로 가정
        return 'member'
    
    def _process_member_barcode(self, barcode: str) -> Dict:
        """회원 바코드 처리"""
        try:
            # 회원 정보 조회 및 검증
            validation = self.member_service.validate_member(barcode)
            
            if not validation['valid']:
                return {
                    'success': False,
                    'error': validation['error'],
                    'type': 'member_invalid'
                }
            
            member = validation['member']
            
            # 이미 대여중인 락카가 있는지 확인
            existing_rental = self.locker_service.get_active_rental_by_member(barcode)
            if existing_rental:
                return {
                    'success': True,
                    'action': 'show_existing_rental',
                    'type': 'member_has_rental',
                    'member': member.to_dict(),
                    'rental': existing_rental.to_dict(),
                    'message': f'현재 {existing_rental.locker_id}번 락카를 사용중입니다.'
                }
            
            # 새로운 대여 - 락카 선택 화면으로
            return {
                'success': True,
                'action': 'show_locker_select',
                'type': 'member_valid',
                'member': member.to_dict(),
                'message': validation['message']
            }
            
        except Exception as e:
            print(f"회원 바코드 처리 오류: {e}")
            return {
                'success': False,
                'error': '회원 바코드 처리 중 오류가 발생했습니다.'
            }
    
    def _process_locker_key_barcode(self, barcode: str) -> Dict:
        """락카키 바코드 처리 (반납)"""
        try:
            # 바코드에서 락카 ID 추출
            locker_id = self._extract_locker_id(barcode)
            
            if not locker_id:
                return {
                    'success': False,
                    'error': '올바르지 않은 락카키 바코드입니다.',
                    'type': 'invalid_locker_key'
                }
            
            # 락카 반납 처리
            result = self.locker_service.return_locker(locker_id)
            
            if result['success']:
                return {
                    'success': True,
                    'action': 'process_return',
                    'type': 'locker_returned',
                    'locker': result['locker'].to_dict(),
                    'rental': result['rental'].to_dict(),
                    'message': result['message']
                }
            else:
                return {
                    'success': False,
                    'error': result['error'],
                    'type': 'return_failed'
                }
                
        except Exception as e:
            print(f"락카키 바코드 처리 오류: {e}")
            return {
                'success': False,
                'error': '락카키 바코드 처리 중 오류가 발생했습니다.'
            }
    
    def _extract_locker_id(self, barcode: str) -> str:
        """바코드에서 락카 ID 추출"""
        
        # LOCKER_A01, KEY_B15 형태
        match = re.match(r'^(LOCKER|KEY)_([A-Z]\d{2})$', barcode)
        if match:
            return match.group(2)
        
        # A01, B15 형태 (직접 락카 ID)
        if re.match(r'^[A-Z]\d{2}$', barcode):
            return barcode
        
        # 숫자만 있는 경우 (예: 101 -> A01)
        if barcode.isdigit() and len(barcode) == 3:
            zone = 'A' if barcode.startswith('1') else 'B'
            number = barcode[1:]
            return f"{zone}{number}"
        
        return ""
