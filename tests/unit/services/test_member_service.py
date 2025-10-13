#!/usr/bin/env python3
"""
MemberService 테스트
"""

import unittest
import os
import sys
from datetime import datetime, timedelta

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.services.member_service import MemberService
from database import DatabaseManager


class TestMemberService(unittest.TestCase):
    """MemberService 테스트 클래스"""
    
    def setUp(self):
        """테스트 전 설정"""
        self.test_db_path = 'test_member_service.db'
        
        # 기존 테스트 DB 삭제
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
        
        # 테스트용 데이터베이스 초기화
        self.db = DatabaseManager(self.test_db_path)
        self.db.connect()
        self.db.initialize_schema()
        
        # MemberService 초기화
        self.member_service = MemberService(self.test_db_path)
        
        # 테스트용 회원 데이터 생성
        self.test_members = [
            {
                'member_id': 'TEST001',
                'member_name': '홍길동',
                'phone': '010-1234-5678',
                'membership_type': 'premium',
                'membership_expires': datetime.now() + timedelta(days=30),
                'status': 'active'
            },
            {
                'member_id': 'TEST002',
                'member_name': '김철수',
                'phone': '010-9876-5432',
                'membership_type': 'basic',
                'membership_expires': datetime.now() + timedelta(days=5),
                'status': 'active'
            },
            {
                'member_id': 'EXPIRED001',
                'member_name': '이만료',
                'phone': '010-0000-0000',
                'membership_type': 'basic',
                'membership_expires': datetime.now() - timedelta(days=5),
                'status': 'active'
            }
        ]
        
        # 테스트 회원들 생성
        for member_data in self.test_members:
            result = self.member_service.create_member(member_data)
            self.assertTrue(result['success'], f"테스트 회원 생성 실패: {result}")
    
    def tearDown(self):
        """테스트 후 정리"""
        self.member_service.close()
        self.db.close()
        
        # 테스트 DB 파일 삭제
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
    
    def test_get_member_success(self):
        """회원 조회 성공 테스트"""
        member = self.member_service.get_member('TEST001')
        
        self.assertIsNotNone(member)
        self.assertEqual(member.id, 'TEST001')
        self.assertEqual(member.name, '홍길동')
        self.assertEqual(member.phone, '010-1234-5678')
        self.assertEqual(member.membership_type, 'premium')
        self.assertEqual(member.status, 'active')
    
    def test_get_member_not_found(self):
        """존재하지 않는 회원 조회 테스트"""
        member = self.member_service.get_member('NOTFOUND')
        self.assertIsNone(member)
    
    def test_validate_member_success(self):
        """유효한 회원 검증 테스트"""
        result = self.member_service.validate_member('TEST001')
        
        self.assertTrue(result['valid'])
        self.assertIsNotNone(result['member'])
        self.assertIn('안녕하세요', result['message'])
        self.assertIn('rental_info', result)
    
    def test_validate_member_not_found(self):
        """존재하지 않는 회원 검증 테스트"""
        result = self.member_service.validate_member('NOTFOUND')
        
        self.assertFalse(result['valid'])
        self.assertEqual(result['error'], '등록되지 않은 회원입니다.')
        self.assertIsNone(result['member'])
    
    def test_validate_member_expired(self):
        """만료된 회원 검증 테스트"""
        result = self.member_service.validate_member('EXPIRED001')
        
        self.assertFalse(result['valid'])
        self.assertIn('만료되었습니다', result['error'])
        self.assertIsNotNone(result['member'])
    
    def test_create_member_success(self):
        """회원 생성 성공 테스트"""
        new_member_data = {
            'member_id': 'NEW001',
            'member_name': '신규회원',
            'phone': '010-1111-2222',
            'membership_type': 'basic',
            'membership_expires': datetime.now() + timedelta(days=365),
            'status': 'active'
        }
        
        result = self.member_service.create_member(new_member_data)
        
        self.assertTrue(result['success'])
        self.assertIsNotNone(result['member'])
        self.assertEqual(result['member'].id, 'NEW001')
        self.assertEqual(result['member'].name, '신규회원')
        
        # 실제로 DB에 저장되었는지 확인
        saved_member = self.member_service.get_member('NEW001')
        self.assertIsNotNone(saved_member)
        self.assertEqual(saved_member.name, '신규회원')
    
    def test_create_member_duplicate(self):
        """중복 회원 생성 테스트"""
        duplicate_data = {
            'member_id': 'TEST001',  # 이미 존재하는 ID
            'member_name': '중복회원',
            'phone': '010-3333-4444'
        }
        
        result = self.member_service.create_member(duplicate_data)
        
        self.assertFalse(result['success'])
        self.assertIn('이미 등록된 회원', result['error'])
    
    def test_update_member_success(self):
        """회원 정보 업데이트 성공 테스트"""
        update_data = {
            'member_name': '홍길동_수정',
            'phone': '010-9999-8888',
            'membership_type': 'vip'
        }
        
        result = self.member_service.update_member('TEST001', update_data)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['member'].name, '홍길동_수정')
        self.assertEqual(result['member'].phone, '010-9999-8888')
        self.assertEqual(result['member'].membership_type, 'vip')
        
        # 실제로 DB에 업데이트되었는지 확인
        updated_member = self.member_service.get_member('TEST001')
        self.assertEqual(updated_member.name, '홍길동_수정')
        self.assertEqual(updated_member.phone, '010-9999-8888')
    
    def test_update_member_not_found(self):
        """존재하지 않는 회원 업데이트 테스트"""
        result = self.member_service.update_member('NOTFOUND', {'member_name': '없는회원'})
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], '존재하지 않는 회원입니다.')
    
    def test_get_all_members(self):
        """전체 회원 목록 조회 테스트"""
        members = self.member_service.get_all_members()
        
        self.assertEqual(len(members), 3)  # 테스트용 회원 3명
        
        # 이름으로 확인
        member_names = [member.name for member in members]
        self.assertIn('홍길동', member_names)
        self.assertIn('김철수', member_names)
        self.assertIn('이만료', member_names)
    
    def test_get_all_members_by_status(self):
        """상태별 회원 목록 조회 테스트"""
        active_members = self.member_service.get_all_members('active')
        
        self.assertEqual(len(active_members), 3)  # 모든 테스트 회원이 active
        
        for member in active_members:
            self.assertEqual(member.status, 'active')
    
    def test_get_members_by_rental_status(self):
        """대여 상태별 회원 조회 테스트"""
        # 대여하지 않은 회원들 (초기 상태)
        not_renting = self.member_service.get_members_by_rental_status(False)
        self.assertEqual(len(not_renting), 3)
        
        # 대여중인 회원들 (초기에는 없음)
        renting = self.member_service.get_members_by_rental_status(True)
        self.assertEqual(len(renting), 0)
        
        # 한 명을 대여중으로 변경
        self.member_service.update_member('TEST001', {'currently_renting': 'A01'})
        
        # 다시 조회
        not_renting = self.member_service.get_members_by_rental_status(False)
        renting = self.member_service.get_members_by_rental_status(True)
        
        self.assertEqual(len(not_renting), 2)
        self.assertEqual(len(renting), 1)
        self.assertEqual(renting[0].currently_renting, 'A01')
    
    def test_reset_daily_rental_counts(self):
        """일일 대여 횟수 리셋 테스트"""
        # 일부 회원의 대여 횟수 증가
        self.member_service.update_member('TEST001', {'daily_rental_count': 2})
        self.member_service.update_member('TEST002', {'daily_rental_count': 1})
        
        # 리셋 실행
        result = self.member_service.reset_daily_rental_counts()
        
        self.assertTrue(result['success'])
        self.assertEqual(result['affected_count'], 2)
        
        # 실제로 리셋되었는지 확인
        member1 = self.member_service.get_member('TEST001')
        member2 = self.member_service.get_member('TEST002')
        
        self.assertEqual(member1.daily_rental_count, 0)
        self.assertEqual(member2.daily_rental_count, 0)


if __name__ == '__main__':
    print("🧪 MemberService 테스트 시작...")
    unittest.main(verbosity=2)
