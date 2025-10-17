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
        
        # 락카키 바코드 패턴 (예: LOCKER_M01, KEY_F15, LOCKER_S05)
        if re.match(r'^(LOCKER|KEY)_[MFS]\d{2}$', barcode):
            return 'locker_key'
        
        # 락카 ID 패턴 (예: M01, F50, S20)
        if re.match(r'^[MFS]\d{2}$', barcode):
            return 'locker_key'
        
        # 구 시스템 호환 (A01, B15 등)
        if re.match(r'^(LOCKER|KEY)_[A-Z]\d{2}$', barcode):
            return 'locker_key'
        if re.match(r'^[A-Z]\d{2}$', barcode):
            return 'locker_key'
        
        # 회원 바코드는 숫자로 가정
        if barcode.isdigit():
            return 'member'
        
        # 기타 영숫자 조합은 회원 바코드로 가정
        return 'member'
    
    def _process_member_barcode(self, barcode: str) -> Dict:
        """회원 바코드 처리 (센서 기반 자동 대여/반납)"""
        try:
            # 회원 정보 조회 및 검증
            validation = self.member_service.validate_member(barcode)
            
            if not validation['valid']:
                # 에러 타입 결정
                error_type = 'member_not_found'
                if 'expired' in validation.get('error', '').lower() or '만료' in validation.get('error', ''):
                    error_type = 'member_expired'
                elif 'not found' in validation.get('error', '').lower() or '찾을 수 없' in validation.get('error', ''):
                    error_type = 'member_not_found'
                
                return {
                    'success': False,
                    'error': validation['error'],
                    'error_type': error_type
                }
            
            member = validation['member']
            
            # 현재 대여 중인지 확인하여 대여/반납 모드 자동 판별
            if member.currently_renting:
                # 반납 모드: 센서 기반 자동 반납
                return {
                    'success': True,
                    'action': 'return',
                    'member_id': member.member_id,
                    'current_locker': member.currently_renting,
                    'message': f'현재 {member.currently_renting}번 락카를 사용중입니다. 반납을 진행합니다.'
                }
            else:
                # 대여 모드: 센서 기반 자동 대여
                return {
                    'success': True,
                    'action': 'rental',
                    'member_id': member.member_id,
                    'message': f'{member.name}님, 대여를 진행합니다.'
                }
            
        except Exception as e:
            import logging
            import traceback
            logger = logging.getLogger(__name__)
            logger.error(f"❌ 회원 바코드 처리 오류: {e}")
            logger.error(f"📍 Traceback: {traceback.format_exc()}")
            return {
                'success': False,
                'error': f'회원 바코드 처리 중 오류가 발생했습니다: {str(e)}',
                'error_type': 'system_error'
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
        
        # LOCKER_M01, KEY_F15, LOCKER_S05 형태 (새 시스템)
        match = re.match(r'^(LOCKER|KEY)_([MFS]\d{2})$', barcode)
        if match:
            return match.group(2)
        
        # M01, F50, S20 형태 (직접 락카 ID - 새 시스템)
        if re.match(r'^[MFS]\d{2}$', barcode):
            return barcode
        
        # 구 시스템 호환: LOCKER_A01, KEY_B15 형태
        match = re.match(r'^(LOCKER|KEY)_([A-Z]\d{2})$', barcode)
        if match:
            return match.group(2)
        
        # A01, B15 형태 (직접 락카 ID - 구 시스템)
        if re.match(r'^[A-Z]\d{2}$', barcode):
            return barcode
        
        # 숫자만 있는 경우 - 새 시스템 기준으로 변환
        # 예: 001~070 → M01~M70, 071~120 → F01~F50, 121~140 → S01~S20
        if barcode.isdigit():
            num = int(barcode)
            if 1 <= num <= 70:
                return f"M{num:02d}"
            elif 71 <= num <= 120:
                return f"F{(num-70):02d}"
            elif 121 <= num <= 140:
                return f"S{(num-120):02d}"
        
        return ""
