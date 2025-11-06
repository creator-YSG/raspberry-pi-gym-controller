"""
NFC 서비스

NFC UID와 락커 번호 간의 매핑을 관리하고,
NFC 태그 등록 및 조회 기능을 제공합니다.
"""

import logging
from typing import Optional, Dict, List
from database.database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class NFCService:
    """NFC UID-락커 매핑 서비스"""
    
    def __init__(self):
        # 항상 명시적으로 DB 경로 지정
        from pathlib import Path
        db_path = Path(__file__).parent.parent.parent / "instance" / "gym_system.db"
        self.db_manager = DatabaseManager(str(db_path))
        self.db_manager.connect()  # ← 핵심! DB 연결 필수
    
    def get_locker_by_nfc_uid(self, nfc_uid: str) -> Optional[str]:
        """NFC UID로 락커 번호 조회
        
        Args:
            nfc_uid: NFC 태그 UID
            
        Returns:
            락커 번호 (예: 'M01', 'F05', 'S03') 또는 None
        """
        try:
            if not nfc_uid or not nfc_uid.strip():
                logger.warning("빈 NFC UID 조회 시도")
                return None
            
            nfc_uid = nfc_uid.strip().upper()
            
            cursor = self.db_manager.conn.cursor()
            cursor.execute("""
                SELECT locker_number, zone, current_member
                FROM locker_status
                WHERE nfc_uid = ?
            """, (nfc_uid,))
            
            result = cursor.fetchone()
            
            if result:
                locker_number, zone, current_member = result
                logger.info(f"NFC UID '{nfc_uid}' → 락커 {locker_number} (구역: {zone}, 대여자: {current_member or '없음'})")
                return locker_number
            else:
                logger.warning(f"등록되지 않은 NFC UID: {nfc_uid}")
                return None
                
        except Exception as e:
            logger.error(f"NFC UID 조회 오류: {e}")
            return None
    
    def register_nfc_tag(self, locker_number: str, nfc_uid: str) -> Dict:
        """락커에 NFC UID 등록
        
        Args:
            locker_number: 락커 번호 (예: 'M01', 'F05', 'S03')
            nfc_uid: NFC 태그 UID
            
        Returns:
            결과 딕셔너리 (success, message, locker_number, nfc_uid)
        """
        try:
            if not locker_number or not locker_number.strip():
                return {
                    'success': False,
                    'error': '락커 번호가 비어있습니다.',
                    'locker_number': None,
                    'nfc_uid': None
                }
            
            if not nfc_uid or not nfc_uid.strip():
                return {
                    'success': False,
                    'error': 'NFC UID가 비어있습니다.',
                    'locker_number': locker_number,
                    'nfc_uid': None
                }
            
            locker_number = locker_number.strip().upper()
            nfc_uid = nfc_uid.strip().upper()
            
            cursor = self.db_manager.conn.cursor()
            
            # 1. 락커 존재 여부 확인
            cursor.execute("""
                SELECT locker_number, zone, nfc_uid
                FROM locker_status
                WHERE locker_number = ?
            """, (locker_number,))
            
            locker = cursor.fetchone()
            
            if not locker:
                return {
                    'success': False,
                    'error': f'락커 {locker_number}를 찾을 수 없습니다.',
                    'locker_number': locker_number,
                    'nfc_uid': nfc_uid
                }
            
            existing_nfc = locker[2]
            
            # 2. NFC UID 중복 확인
            cursor.execute("""
                SELECT locker_number
                FROM locker_status
                WHERE nfc_uid = ? AND locker_number != ?
            """, (nfc_uid, locker_number))
            
            duplicate = cursor.fetchone()
            
            if duplicate:
                return {
                    'success': False,
                    'error': f'NFC UID {nfc_uid}가 이미 락커 {duplicate[0]}에 등록되어 있습니다.',
                    'locker_number': locker_number,
                    'nfc_uid': nfc_uid,
                    'duplicate_locker': duplicate[0]
                }
            
            # 3. NFC UID 등록 또는 업데이트
            cursor.execute("""
                UPDATE locker_status
                SET nfc_uid = ?, updated_at = CURRENT_TIMESTAMP
                WHERE locker_number = ?
            """, (nfc_uid, locker_number))
            
            self.db_manager.conn.commit()
            
            action = "업데이트" if existing_nfc else "등록"
            logger.info(f"NFC UID {action}: 락커 {locker_number} → {nfc_uid}")
            
            return {
                'success': True,
                'message': f'락커 {locker_number}에 NFC UID가 {action}되었습니다.',
                'locker_number': locker_number,
                'nfc_uid': nfc_uid,
                'action': action,
                'previous_nfc_uid': existing_nfc
            }
            
        except Exception as e:
            self.db_manager.conn.rollback()
            logger.error(f"NFC UID 등록 오류: {e}")
            return {
                'success': False,
                'error': f'NFC UID 등록 중 오류가 발생했습니다: {str(e)}',
                'locker_number': locker_number,
                'nfc_uid': nfc_uid
            }
    
    def unregister_nfc_tag(self, locker_number: str) -> Dict:
        """락커의 NFC UID 등록 해제
        
        Args:
            locker_number: 락커 번호
            
        Returns:
            결과 딕셔너리
        """
        try:
            locker_number = locker_number.strip().upper()
            
            cursor = self.db_manager.conn.cursor()
            cursor.execute("""
                UPDATE locker_status
                SET nfc_uid = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE locker_number = ?
            """, (locker_number,))
            
            self.db_manager.conn.commit()
            
            logger.info(f"NFC UID 등록 해제: 락커 {locker_number}")
            
            return {
                'success': True,
                'message': f'락커 {locker_number}의 NFC UID가 해제되었습니다.',
                'locker_number': locker_number
            }
            
        except Exception as e:
            self.db_manager.conn.rollback()
            logger.error(f"NFC UID 등록 해제 오류: {e}")
            return {
                'success': False,
                'error': f'NFC UID 등록 해제 중 오류가 발생했습니다: {str(e)}'
            }
    
    def get_all_nfc_mappings(self) -> List[Dict]:
        """모든 NFC UID-락커 매핑 조회
        
        Returns:
            매핑 리스트 [{'locker_number': 'M01', 'nfc_uid': 'ABC123', 'zone': 'MALE'}, ...]
        """
        try:
            cursor = self.db_manager.conn.cursor()
            cursor.execute("""
                SELECT locker_number, zone, nfc_uid, current_member
                FROM locker_status
                ORDER BY locker_number
            """)
            
            mappings = []
            for row in cursor.fetchall():
                locker_number, zone, nfc_uid, current_member = row
                mappings.append({
                    'locker_number': locker_number,
                    'zone': zone,
                    'nfc_uid': nfc_uid,
                    'current_member': current_member,
                    'registered': nfc_uid is not None
                })
            
            logger.info(f"전체 NFC 매핑 조회: {len(mappings)}개")
            return mappings
            
        except Exception as e:
            logger.error(f"NFC 매핑 조회 오류: {e}")
            return []
    
    def get_unregistered_lockers(self) -> List[str]:
        """NFC UID가 등록되지 않은 락커 목록 조회
        
        Returns:
            락커 번호 리스트
        """
        try:
            cursor = self.db_manager.conn.cursor()
            cursor.execute("""
                SELECT locker_number
                FROM locker_status
                WHERE nfc_uid IS NULL
                ORDER BY locker_number
            """)
            
            lockers = [row[0] for row in cursor.fetchall()]
            logger.info(f"미등록 락커: {len(lockers)}개")
            return lockers
            
        except Exception as e:
            logger.error(f"미등록 락커 조회 오류: {e}")
            return []
    
    def validate_nfc_uid(self, nfc_uid: str) -> Dict:
        """NFC UID 유효성 검증
        
        Args:
            nfc_uid: NFC 태그 UID
            
        Returns:
            검증 결과 딕셔너리 (valid, locker_number, current_member, message)
        """
        try:
            locker_number = self.get_locker_by_nfc_uid(nfc_uid)
            
            if not locker_number:
                return {
                    'valid': False,
                    'locker_number': None,
                    'current_member': None,
                    'message': '등록되지 않은 NFC 태그입니다.'
                }
            
            # 현재 대여 상태 확인
            cursor = self.db_manager.conn.cursor()
            cursor.execute("""
                SELECT current_member, zone
                FROM locker_status
                WHERE locker_number = ?
            """, (locker_number,))
            
            result = cursor.fetchone()
            
            if result:
                current_member, zone = result
                return {
                    'valid': True,
                    'locker_number': locker_number,
                    'zone': zone,
                    'current_member': current_member,
                    'is_rented': current_member is not None,
                    'message': f'유효한 NFC 태그입니다. (락커: {locker_number}, 구역: {zone})'
                }
            else:
                return {
                    'valid': False,
                    'locker_number': locker_number,
                    'current_member': None,
                    'message': '락커 정보를 찾을 수 없습니다.'
                }
                
        except Exception as e:
            logger.error(f"NFC UID 검증 오류: {e}")
            return {
                'valid': False,
                'locker_number': None,
                'current_member': None,
                'message': f'검증 중 오류가 발생했습니다: {str(e)}'
            }

