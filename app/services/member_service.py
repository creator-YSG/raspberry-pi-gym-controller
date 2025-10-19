"""
회원 관리 서비스 (SQLite 기반)
"""

from typing import Optional, List, Dict
from app.models.member import Member
from database import DatabaseManager
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class MemberService:
    """회원 관리 비즈니스 로직 (SQLite 연동)"""
    
    def __init__(self, db_path: str = 'instance/gym_system.db'):
        """MemberService 초기화
        
        Args:
            db_path: SQLite 데이터베이스 파일 경로
        """
        self.db = DatabaseManager(db_path)
        self.db.connect()
        logger.info("MemberService 초기화 완료 (SQLite 연동)")
    
    def get_member(self, member_id: str) -> Optional[Member]:
        """SQLite에서 회원 정보 조회
        
        Args:
            member_id: 회원 바코드 ID
            
        Returns:
            Member 객체 또는 None
        """
        try:
            import time
            t_db_start = time.time()
            
            # SQLite에서 회원 정보 조회
            cursor = self.db.execute_query("""
                SELECT * FROM members 
                WHERE member_id = ?
            """, (member_id,))
            
            t_db_query = time.time()
            
            if cursor:
                row = cursor.fetchone()
                t_db_fetch = time.time()
                
                if row:
                    member = Member.from_db_row(row)
                    t_db_parse = time.time()
                    
                    logger.info(f"⏱️ [PERF-DB] 회원 조회: {member_id} | "
                               f"쿼리: {(t_db_query - t_db_start)*1000:.2f}ms | "
                               f"Fetch: {(t_db_fetch - t_db_query)*1000:.2f}ms | "
                               f"파싱: {(t_db_parse - t_db_fetch)*1000:.2f}ms | "
                               f"전체: {(t_db_parse - t_db_start)*1000:.2f}ms")
                    return member
                else:
                    logger.warning(f"회원 없음: {member_id}")
                    return None
            else:
                logger.error(f"쿼리 실행 실패: {member_id}")
                return None
                
        except Exception as e:
            logger.error(f"회원 조회 오류: {member_id}, {e}")
            return None
    
    def validate_member(self, member_id: str) -> dict:
        """회원 유효성 검증 (대여 가능 여부 포함)
        
        Args:
            member_id: 회원 바코드 ID
            
        Returns:
            검증 결과 딕셔너리
        """
        try:
            member = self.get_member(member_id)
            
            if not member:
                return {
                    'valid': False,
                    'error': '등록되지 않은 회원입니다.',
                    'member': None
                }
            
            # 기본 회원 상태 검증
            if not member.is_valid:
                if member.status != 'active':
                    error = '정지된 회원입니다. 프론트에 문의하세요.'
                elif member.membership_expires and member.membership_expires < datetime.now():
                    error = f'회원권이 만료되었습니다. (만료일: {member.membership_expires.strftime("%Y-%m-%d")})'
                else:
                    error = '회원 상태를 확인할 수 없습니다.'
                
                return {
                    'valid': False,
                    'error': error,
                    'member': member
                }
            
            # 모든 검증 통과 - 대여중인 회원도 유효한 회원으로 처리
            remaining_days = member.days_remaining
            
            # 대여중인 회원인 경우
            if member.is_renting:
                return {
                    'valid': True,
                    'member': member,
                    'message': f'안녕하세요, {member.name}님! 현재 {member.currently_renting}번 락카를 사용중입니다.',
                    'rental_info': {
                        'daily_count': member.daily_rental_count,
                        'can_rent': member.can_rent_more,
                        'is_renting': True,
                        'current_locker': member.currently_renting
                    },
                    'action_type': 'return_process'  # 반납 프로세스 표시
                }
            
            # 대여하지 않은 회원인 경우
            if not member.can_rent_more:
                return {
                    'valid': False,
                    'error': f'오늘 대여 횟수를 초과했습니다. ({member.daily_rental_count}/3)',
                    'member': member
                }
            
            # 새로운 대여 가능한 회원
            return {
                'valid': True,
                'member': member,
                'message': f'안녕하세요, {member.name}님! (회원권 {remaining_days}일 남음)',
                'rental_info': {
                    'daily_count': member.daily_rental_count,
                    'can_rent': member.can_rent_more,
                    'is_renting': False
                },
                'action_type': 'rental_process'  # 대여 프로세스 표시
            }
            
        except Exception as e:
            logger.error(f"회원 검증 오류: {member_id}, {e}")
            return {
                'valid': False,
                'error': '회원 검증 중 시스템 오류가 발생했습니다.',
                'member': None
            }
    
    def create_member(self, member_data: Dict) -> Dict:
        """새 회원 생성
        
        Args:
            member_data: 회원 정보 딕셔너리
            
        Returns:
            생성 결과
        """
        try:
            # 중복 회원 확인
            existing_member = self.get_member(member_data['member_id'])
            if existing_member:
                return {
                    'success': False,
                    'error': f'이미 등록된 회원입니다: {member_data["member_id"]}'
                }
            
            # Member 객체 생성
            member = Member(
                id=member_data['member_id'],
                name=member_data['member_name'],
                phone=member_data.get('phone', ''),
                membership_type=member_data.get('membership_type', 'basic'),
                program_name=member_data.get('program_name', ''),
                membership_expires=member_data.get('membership_expires'),
                status=member_data.get('status', 'active'),
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            # 데이터베이스에 저장
            db_data = member.to_db_dict()
            self.db.execute_query("""
                INSERT INTO members (
                    member_id, member_name, phone, membership_type, program_name,
                    expiry_date, status, currently_renting, daily_rental_count,
                    last_rental_time, sync_date, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                db_data['member_id'], db_data['member_name'], db_data['phone'],
                db_data['membership_type'], db_data['program_name'], db_data['expiry_date'], db_data['status'],
                db_data['currently_renting'], db_data['daily_rental_count'],
                db_data['last_rental_time'], db_data['sync_date'],
                db_data['created_at'], db_data['updated_at']
            ))
            
            logger.info(f"회원 생성 성공: {member.id} ({member.name})")
            return {
                'success': True,
                'member': member,
                'message': f'{member.name}님이 성공적으로 등록되었습니다.'
            }
            
        except Exception as e:
            logger.error(f"회원 생성 오류: {e}")
            return {
                'success': False,
                'error': '회원 생성 중 오류가 발생했습니다.'
            }
    
    def update_member(self, member_id: str, update_data: Dict) -> Dict:
        """회원 정보 업데이트
        
        Args:
            member_id: 회원 ID
            update_data: 업데이트할 데이터
            
        Returns:
            업데이트 결과
        """
        try:
            member = self.get_member(member_id)
            if not member:
                return {
                    'success': False,
                    'error': '존재하지 않는 회원입니다.'
                }
            
            # 업데이트 가능한 필드들
            allowed_fields = [
                'member_name', 'phone', 'membership_type', 'expiry_date', 
                'status', 'currently_renting', 'daily_rental_count'
            ]
            
            update_fields = []
            update_values = []
            
            for field, value in update_data.items():
                if field in allowed_fields:
                    update_fields.append(f"{field} = ?")
                    update_values.append(value)
            
            if not update_fields:
                return {
                    'success': False,
                    'error': '업데이트할 필드가 없습니다.'
                }
            
            # updated_at 추가
            update_fields.append("updated_at = ?")
            update_values.append(datetime.now().isoformat())
            update_values.append(member_id)
            
            # 데이터베이스 업데이트
            query = f"UPDATE members SET {', '.join(update_fields)} WHERE member_id = ?"
            self.db.execute_query(query, update_values)
            
            # 업데이트된 회원 정보 조회
            updated_member = self.get_member(member_id)
            
            logger.info(f"회원 정보 업데이트 성공: {member_id}")
            return {
                'success': True,
                'member': updated_member,
                'message': '회원 정보가 성공적으로 업데이트되었습니다.'
            }
            
        except Exception as e:
            logger.error(f"회원 업데이트 오류: {member_id}, {e}")
            return {
                'success': False,
                'error': '회원 정보 업데이트 중 오류가 발생했습니다.'
            }
    
    def get_all_members(self, status: str = None) -> List[Member]:
        """모든 회원 목록 조회
        
        Args:
            status: 필터링할 상태 (None이면 전체)
            
        Returns:
            Member 객체 리스트
        """
        try:
            if status:
                cursor = self.db.execute_query("""
                    SELECT * FROM members 
                    WHERE status = ?
                    ORDER BY created_at DESC
                """, (status,))
            else:
                cursor = self.db.execute_query("""
                    SELECT * FROM members 
                    ORDER BY created_at DESC
                """)
            
            if cursor:
                rows = cursor.fetchall()
                members = [Member.from_db_row(row) for row in rows]
                logger.info(f"회원 목록 조회: {len(members)}명 (status: {status or 'all'})")
                return members
            else:
                logger.error("회원 목록 쿼리 실행 실패")
                return []
            
        except Exception as e:
            logger.error(f"회원 목록 조회 오류: {e}")
            return []
    
    def get_members_by_rental_status(self, is_renting: bool) -> List[Member]:
        """대여 상태별 회원 조회
        
        Args:
            is_renting: True면 대여중인 회원, False면 대여하지 않은 회원
            
        Returns:
            Member 객체 리스트
        """
        try:
            if is_renting:
                cursor = self.db.execute_query("""
                    SELECT * FROM members 
                    WHERE currently_renting IS NOT NULL
                    ORDER BY last_rental_time DESC
                """)
            else:
                cursor = self.db.execute_query("""
                    SELECT * FROM members 
                    WHERE currently_renting IS NULL
                    ORDER BY member_name
                """)
            
            if cursor:
                rows = cursor.fetchall()
                members = [Member.from_db_row(row) for row in rows]
                logger.info(f"대여 상태별 회원 조회: {len(members)}명 (대여중: {is_renting})")
                return members
            else:
                logger.error("대여 상태별 회원 쿼리 실행 실패")
                return []
            
        except Exception as e:
            logger.error(f"대여 상태별 회원 조회 오류: {e}")
            return []
    
    def reset_daily_rental_counts(self) -> Dict:
        """모든 회원의 일일 대여 횟수 리셋 (자정에 실행)
        
        Returns:
            리셋 결과
        """
        try:
            cursor = self.db.execute_query("""
                UPDATE members 
                SET daily_rental_count = 0, updated_at = ?
                WHERE daily_rental_count > 0
            """, (datetime.now().isoformat(),))
            
            affected_rows = cursor.rowcount if cursor and hasattr(cursor, 'rowcount') else 0
            
            logger.info(f"일일 대여 횟수 리셋 완료: {affected_rows}명")
            return {
                'success': True,
                'affected_count': affected_rows,
                'message': f'{affected_rows}명의 일일 대여 횟수가 리셋되었습니다.'
            }
            
        except Exception as e:
            logger.error(f"일일 대여 횟수 리셋 오류: {e}")
            return {
                'success': False,
                'error': '일일 대여 횟수 리셋 중 오류가 발생했습니다.'
            }
    
    def close(self):
        """데이터베이스 연결 종료"""
        if self.db:
            self.db.close()
            logger.info("MemberService 데이터베이스 연결 종료")
