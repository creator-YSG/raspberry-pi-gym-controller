"""
데이터베이스 매니저 테스트

SQLite 데이터베이스 기본 기능 테스트
"""

import unittest
import tempfile
import os
from datetime import datetime, timezone
from pathlib import Path
import sys

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from database.database_manager import DatabaseManager, create_database_manager


class TestDatabaseManager(unittest.TestCase):
    """데이터베이스 매니저 테스트 클래스"""
    
    def setUp(self):
        """테스트 설정"""
        # 임시 데이터베이스 파일 생성
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        
        # 데이터베이스 매니저 생성
        self.db_manager = create_database_manager(self.db_path, initialize=True)
    
    def tearDown(self):
        """테스트 정리"""
        if self.db_manager:
            self.db_manager.close()
        
        # 임시 파일 삭제
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_database_connection(self):
        """데이터베이스 연결 테스트"""
        self.assertIsNotNone(self.db_manager.conn)
        self.assertTrue(self.db_manager.conn)
    
    def test_schema_initialization(self):
        """스키마 초기화 테스트"""
        # 테이블 존재 확인
        tables = ['members', 'rentals', 'locker_status', 'active_transactions', 'system_settings']
        
        for table in tables:
            cursor = self.db_manager.execute_query(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", 
                (table,)
            )
            self.assertIsNotNone(cursor)
            row = cursor.fetchone()
            self.assertIsNotNone(row, f"테이블 {table}이 존재하지 않습니다")
    
    def test_system_settings(self):
        """시스템 설정 테스트"""
        # 기본 설정 확인
        timeout = self.db_manager.get_system_setting('transaction_timeout_seconds', 0)
        self.assertEqual(timeout, 30)
        
        max_rentals = self.db_manager.get_system_setting('max_daily_rentals', 0)
        self.assertEqual(max_rentals, 3)
        
        # 새 설정 저장
        self.assertTrue(self.db_manager.set_system_setting('test_setting', 'test_value'))
        
        # 저장된 설정 확인
        value = self.db_manager.get_system_setting('test_setting')
        self.assertEqual(value, 'test_value')
    
    def test_member_operations(self):
        """회원 관련 작업 테스트"""
        # 회원 추가
        member_id = 'TEST001'
        cursor = self.db_manager.execute_query("""
            INSERT INTO members (member_id, member_name, status, expiry_date)
            VALUES (?, ?, ?, ?)
        """, (member_id, '테스트 회원', 'active', '2025-12-31'))
        
        self.assertIsNotNone(cursor)
        
        # 회원 조회
        member = self.db_manager.get_member(member_id)
        self.assertIsNotNone(member)
        self.assertEqual(member['member_name'], '테스트 회원')
        self.assertEqual(member['status'], 'active')
    
    def test_locker_operations(self):
        """락카 관련 작업 테스트"""
        # 사용 가능한 락카 조회
        available_lockers = self.db_manager.get_available_lockers()
        self.assertGreater(len(available_lockers), 0)
        
        # A구역 락카만 조회
        a_zone_lockers = self.db_manager.get_available_lockers('A')
        self.assertGreater(len(a_zone_lockers), 0)
        
        # 모든 A구역 락카인지 확인
        for locker in a_zone_lockers:
            self.assertEqual(locker['zone'], 'A')
    
    def test_rental_operations(self):
        """대여 관련 작업 테스트"""
        # 테스트 회원 추가
        member_id = 'TEST002'
        self.db_manager.execute_query("""
            INSERT INTO members (member_id, member_name, status)
            VALUES (?, ?, ?)
        """, (member_id, '테스트 회원2', 'active'))
        
        # 대여 기록 추가
        cursor = self.db_manager.execute_query("""
            INSERT INTO rentals (transaction_id, member_id, locker_number, status)
            VALUES (?, ?, ?, ?)
        """, ('TX001', member_id, 'A01', 'active'))
        
        self.assertIsNotNone(cursor)
        
        # 활성 대여 기록 조회
        active_rentals = self.db_manager.get_active_rentals(member_id)
        self.assertEqual(len(active_rentals), 1)
        self.assertEqual(active_rentals[0]['locker_number'], 'A01')
    
    def test_database_stats(self):
        """데이터베이스 통계 테스트"""
        stats = self.db_manager.get_database_stats()
        
        # 필수 통계 항목 확인
        required_stats = [
            'members_count', 'rentals_count', 'locker_status_count', 
            'active_transactions_count', 'active_rentals', 'available_lockers'
        ]
        
        for stat in required_stats:
            self.assertIn(stat, stats)
            self.assertIsInstance(stats[stat], int)
    
    def test_transaction_operations(self):
        """트랜잭션 테스트"""
        # 트랜잭션 시작
        self.db_manager.begin_transaction()
        
        # 테스트 데이터 삽입
        cursor = self.db_manager.execute_query("""
            INSERT INTO members (member_id, member_name, status)
            VALUES (?, ?, ?)
        """, ('TX_TEST', '트랜잭션 테스트', 'active'))
        
        self.assertIsNotNone(cursor)
        
        # 롤백
        self.db_manager.rollback()
        
        # 데이터가 롤백되었는지 확인
        member = self.db_manager.get_member('TX_TEST')
        self.assertIsNone(member)
        
        # 다시 트랜잭션 시작하고 커밋
        self.db_manager.begin_transaction()
        
        cursor = self.db_manager.execute_query("""
            INSERT INTO members (member_id, member_name, status)
            VALUES (?, ?, ?)
        """, ('TX_TEST2', '트랜잭션 테스트2', 'active'))
        
        self.db_manager.commit()
        
        # 데이터가 커밋되었는지 확인
        member = self.db_manager.get_member('TX_TEST2')
        self.assertIsNotNone(member)
        self.assertEqual(member['member_name'], '트랜잭션 테스트2')


class TestDatabaseIntegration(unittest.TestCase):
    """데이터베이스 통합 테스트"""
    
    def setUp(self):
        """테스트 설정"""
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
    
    def test_complete_rental_flow(self):
        """완전한 대여 플로우 테스트"""
        # 1. 회원 등록
        member_id = 'FLOW_TEST'
        cursor = self.db_manager.execute_query("""
            INSERT INTO members (member_id, member_name, status, expiry_date)
            VALUES (?, ?, ?, ?)
        """, (member_id, '플로우 테스트', 'active', '2025-12-31'))
        
        self.assertIsNotNone(cursor)
        
        # 2. 사용 가능한 락카 확인
        available_lockers = self.db_manager.get_available_lockers()
        self.assertGreater(len(available_lockers), 0)
        
        locker_number = available_lockers[0]['locker_number']
        
        # 3. 대여 기록 생성
        transaction_id = 'FLOW_TX_001'
        cursor = self.db_manager.execute_query("""
            INSERT INTO rentals (transaction_id, member_id, locker_number, 
                               rental_barcode_time, rental_verified, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (transaction_id, member_id, locker_number, 
              datetime.now(timezone.utc).isoformat(), True, 'active'))
        
        self.assertIsNotNone(cursor)
        
        # 4. 락카 상태 업데이트
        cursor = self.db_manager.execute_query("""
            UPDATE locker_status 
            SET current_member = ?, last_change_time = ?
            WHERE locker_number = ?
        """, (member_id, datetime.now(timezone.utc).isoformat(), locker_number))
        
        self.assertIsNotNone(cursor)
        
        # 5. 회원 상태 업데이트
        cursor = self.db_manager.execute_query("""
            UPDATE members 
            SET currently_renting = ?, last_rental_time = ?
            WHERE member_id = ?
        """, (locker_number, datetime.now(timezone.utc).isoformat(), member_id))
        
        self.assertIsNotNone(cursor)
        
        # 6. 결과 확인
        # 회원이 락카를 대여중인지 확인
        member = self.db_manager.get_member(member_id)
        self.assertEqual(member['currently_renting'], locker_number)
        
        # 락카가 사용중인지 확인
        locker_status = self.db_manager.get_locker_status(locker_number)
        self.assertEqual(locker_status['current_member'], member_id)
        
        # 활성 대여 기록 확인
        active_rentals = self.db_manager.get_active_rentals(member_id)
        self.assertEqual(len(active_rentals), 1)
        self.assertEqual(active_rentals[0]['locker_number'], locker_number)


if __name__ == '__main__':
    # 로깅 설정
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # 테스트 실행
    unittest.main(verbosity=2)
