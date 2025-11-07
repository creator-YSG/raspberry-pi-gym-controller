"""
확장된 Member 모델 테스트
"""

import unittest
import tempfile
import os
from datetime import datetime, timedelta
from pathlib import Path
import sys

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.models.member import Member
from database.database_manager import create_database_manager


class TestMemberModel(unittest.TestCase):
    """확장된 Member 모델 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        # 임시 데이터베이스 생성
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        self.db_manager = create_database_manager(self.db_path, initialize=True)
    
    def tearDown(self):
        """테스트 정리"""
        if self.db_manager:
            self.db_manager.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_member_creation(self):
        """Member 객체 생성 테스트"""
        member = Member(
            id='TEST001',
            name='테스트 회원',
            phone='010-1234-5678',
            membership_type='premium',
            membership_expires=datetime.now() + timedelta(days=30),
            status='active'
        )
        
        self.assertEqual(member.id, 'TEST001')
        self.assertEqual(member.name, '테스트 회원')
        self.assertEqual(member.phone, '010-1234-5678')
        self.assertEqual(member.membership_type, 'premium')
        self.assertEqual(member.status, 'active')
        self.assertIsNone(member.currently_renting)
        self.assertEqual(member.daily_rental_count, 0)
    
    def test_member_properties(self):
        """Member 프로퍼티 테스트"""
        # 유효한 회원
        future_date = datetime.now() + timedelta(days=30)
        valid_member = Member(
            id='VALID001',
            name='유효한 회원',
            membership_expires=future_date,
            status='active'
        )
        
        self.assertTrue(valid_member.is_valid)
        # days_remaining은 정확히 30일이 아닐 수 있으므로 범위로 체크
        self.assertGreaterEqual(valid_member.days_remaining, 29)
        self.assertLessEqual(valid_member.days_remaining, 30)
        self.assertFalse(valid_member.is_renting)
        self.assertTrue(valid_member.can_rent_more)
        
        # 만료된 회원
        expired_member = Member(
            id='EXPIRED001',
            name='만료된 회원',
            membership_expires=datetime.now() - timedelta(days=5),
            status='active'
        )
        
        self.assertFalse(expired_member.is_valid)
        self.assertEqual(expired_member.days_remaining, 0)
        
        # 정지된 회원
        suspended_member = Member(
            id='SUSPENDED001',
            name='정지된 회원',
            membership_expires=datetime.now() + timedelta(days=30),
            status='suspended'
        )
        
        self.assertFalse(suspended_member.is_valid)
    
    def test_rental_operations(self):
        """대여 관련 작업 테스트"""
        member = Member(
            id='RENTAL001',
            name='대여 테스트',
            status='active'
        )
        
        # 대여 시작
        member.start_rental('A01')
        
        self.assertEqual(member.currently_renting, 'A01')
        self.assertTrue(member.is_renting)
        self.assertEqual(member.daily_rental_count, 1)
        self.assertIsNotNone(member.last_rental_time)
        
        # 대여 종료
        member.end_rental()
        
        self.assertIsNone(member.currently_renting)
        self.assertFalse(member.is_renting)
        self.assertEqual(member.daily_rental_count, 1)  # 횟수는 유지
    
    def test_daily_rental_limit(self):
        """일일 대여 횟수 제한 테스트"""
        member = Member(
            id='LIMIT001',
            name='제한 테스트',
            status='active'
        )
        
        # 3번 대여 (제한)
        for i in range(3):
            member.start_rental(f'A{i+1:02d}')
            member.end_rental()
        
        self.assertEqual(member.daily_rental_count, 3)
        self.assertFalse(member.can_rent_more)
        
        # 일일 횟수 초기화
        member.reset_daily_count()
        
        self.assertEqual(member.daily_rental_count, 0)
        self.assertTrue(member.can_rent_more)
    
    def test_to_dict_conversion(self):
        """딕셔너리 변환 테스트"""
        member = Member(
            id='DICT001',
            name='딕셔너리 테스트',
            phone='010-9999-9999',
            membership_type='vip',
            membership_expires=datetime.now() + timedelta(days=60),
            status='active',
            currently_renting='B05',
            daily_rental_count=2
        )
        
        member_dict = member.to_dict()
        
        self.assertEqual(member_dict['id'], 'DICT001')
        self.assertEqual(member_dict['name'], '딕셔너리 테스트')
        self.assertEqual(member_dict['phone'], '010-9999-9999')
        self.assertEqual(member_dict['membership_type'], 'vip')
        self.assertEqual(member_dict['status'], 'active')
        self.assertEqual(member_dict['currently_renting'], 'B05')
        self.assertEqual(member_dict['daily_rental_count'], 2)
        self.assertTrue(member_dict['is_valid'])
        self.assertTrue(member_dict['is_renting'])
        self.assertIsNotNone(member_dict['membership_expires'])
    
    def test_db_dict_conversion(self):
        """데이터베이스 딕셔너리 변환 테스트"""
        member = Member(
            id='DB001',
            name='DB 테스트',
            phone='010-8888-8888',
            membership_type='basic',
            status='active'
        )
        
        db_dict = member.to_db_dict()
        
        self.assertEqual(db_dict['member_id'], 'DB001')
        self.assertEqual(db_dict['member_name'], 'DB 테스트')
        self.assertEqual(db_dict['phone'], '010-8888-8888')
        self.assertEqual(db_dict['membership_type'], 'basic')
        self.assertEqual(db_dict['status'], 'active')
        self.assertIsNone(db_dict['currently_renting'])
        self.assertEqual(db_dict['daily_rental_count'], 0)
    
    def test_database_integration(self):
        """데이터베이스 통합 테스트"""
        # Member 객체 생성
        member = Member(
            id='INTEGRATION001',
            name='통합 테스트',
            phone='010-7777-7777',
            membership_type='premium',
            membership_expires=datetime.now() + timedelta(days=90),
            status='active'
        )
        
        # 데이터베이스에 저장
        db_dict = member.to_db_dict()
        
        cursor = self.db_manager.execute_query("""
            INSERT INTO members 
            (member_id, member_name, phone, membership_type, expiry_date, status,
             currently_renting, daily_rental_count, last_rental_time, sync_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            db_dict['member_id'],
            db_dict['member_name'],
            db_dict['phone'],
            db_dict['membership_type'],
            db_dict['expiry_date'],
            db_dict['status'],
            db_dict['currently_renting'],
            db_dict['daily_rental_count'],
            db_dict['last_rental_time'],
            db_dict['sync_date']
        ))
        
        self.assertIsNotNone(cursor)
        
        # 데이터베이스에서 조회
        cursor = self.db_manager.execute_query(
            "SELECT * FROM members WHERE member_id = ?",
            (member.id,)
        )
        
        self.assertIsNotNone(cursor)
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        
        # from_db_row로 객체 복원
        restored_member = Member.from_db_row(row)
        
        self.assertEqual(restored_member.id, member.id)
        self.assertEqual(restored_member.name, member.name)
        self.assertEqual(restored_member.phone, member.phone)
        self.assertEqual(restored_member.membership_type, member.membership_type)
        self.assertEqual(restored_member.status, member.status)
        self.assertEqual(restored_member.daily_rental_count, member.daily_rental_count)


if __name__ == '__main__':
    # 로깅 설정
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # 테스트 실행
    unittest.main(verbosity=2)
