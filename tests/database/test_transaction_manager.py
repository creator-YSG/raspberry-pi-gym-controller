"""
트랜잭션 매니저 테스트
"""

import unittest
import tempfile
import os
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from database.database_manager import create_database_manager
from database.transaction_manager import (
    TransactionManager, TransactionType, TransactionStatus, TransactionStep
)


class TestTransactionManager(unittest.TestCase):
    """트랜잭션 매니저 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        # 임시 데이터베이스 생성
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        self.db_manager = create_database_manager(self.db_path, initialize=True)
        self.tx_manager = TransactionManager(self.db_manager)
        
        # 테스트용 회원들 추가
        self.test_member_id = 'TEST_MEMBER_001'
        self.db_manager.execute_query("""
            INSERT INTO members (member_id, member_name, status, expiry_date)
            VALUES (?, ?, ?, ?)
        """, (self.test_member_id, '테스트 회원', 'active', '2025-12-31'))
        
        # 추가 테스트 회원
        self.db_manager.execute_query("""
            INSERT INTO members (member_id, member_name, status, expiry_date)
            VALUES (?, ?, ?, ?)
        """, ('MEMBER_002', '테스트 회원2', 'active', '2025-12-31'))
    
    def tearDown(self):
        """테스트 정리"""
        if self.db_manager:
            self.db_manager.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_transaction_creation(self):
        """트랜잭션 생성 테스트"""
        async def run_test():
            # 트랜잭션 시작
            result = await self.tx_manager.start_transaction(
                self.test_member_id, 
                TransactionType.RENTAL
            )
            
            self.assertTrue(result['success'])
            self.assertIn('transaction_id', result)
            self.assertIn('timeout_at', result)
            
            tx_id = result['transaction_id']
            
            # 트랜잭션 상태 확인
            status = await self.tx_manager.get_transaction_status(tx_id)
            self.assertIsNotNone(status)
            self.assertEqual(status['member_id'], self.test_member_id)
            self.assertEqual(status['transaction_type'], TransactionType.RENTAL.value)
            self.assertEqual(status['status'], TransactionStatus.ACTIVE.value)
            self.assertEqual(status['step'], TransactionStep.STARTED.value)
            
            # 트랜잭션 종료
            end_result = await self.tx_manager.end_transaction(tx_id)
            self.assertTrue(end_result)
        
        asyncio.run(run_test())
    
    def test_concurrent_transaction_limit(self):
        """동시 트랜잭션 제한 테스트"""
        async def run_test():
            # 첫 번째 트랜잭션 시작
            result1 = await self.tx_manager.start_transaction(
                self.test_member_id, 
                TransactionType.RENTAL
            )
            self.assertTrue(result1['success'])
            
            # 두 번째 트랜잭션 시작 시도 (실패해야 함)
            result2 = await self.tx_manager.start_transaction(
                self.test_member_id,  # 같은 회원으로 테스트
                TransactionType.RENTAL
            )
            self.assertFalse(result2['success'])
            # 동시성 제어로 인해 TRANSACTION_ACTIVE 또는 MEMBER_TRANSACTION_ACTIVE 가능
            self.assertIn(result2['error'], ['TRANSACTION_ACTIVE', 'MEMBER_TRANSACTION_ACTIVE'])
            
            # 첫 번째 트랜잭션 종료
            await self.tx_manager.end_transaction(result1['transaction_id'])
            
            # 이제 새 트랜잭션 시작 가능
            result3 = await self.tx_manager.start_transaction(
                self.test_member_id, 
                TransactionType.RENTAL
            )
            self.assertTrue(result3['success'])
            
            # 정리
            await self.tx_manager.end_transaction(result3['transaction_id'])
        
        asyncio.run(run_test())
    
    def test_member_duplicate_transaction(self):
        """회원별 중복 트랜잭션 테스트"""
        async def run_test():
            # 첫 번째 트랜잭션 시작
            result1 = await self.tx_manager.start_transaction(
                self.test_member_id, 
                TransactionType.RENTAL
            )
            self.assertTrue(result1['success'])
            
            # 같은 회원의 두 번째 트랜잭션 시도 (실패해야 함)
            result2 = await self.tx_manager.start_transaction(
                self.test_member_id, 
                TransactionType.RETURN
            )
            self.assertFalse(result2['success'])
            # 동시성 제어로 인해 TRANSACTION_ACTIVE 또는 MEMBER_TRANSACTION_ACTIVE 가능
            self.assertIn(result2['error'], ['TRANSACTION_ACTIVE', 'MEMBER_TRANSACTION_ACTIVE'])
            
            # 첫 번째 트랜잭션 종료
            await self.tx_manager.end_transaction(result1['transaction_id'])
            
            # 이제 같은 회원의 새 트랜잭션 시작 가능
            result3 = await self.tx_manager.start_transaction(
                self.test_member_id, 
                TransactionType.RETURN
            )
            self.assertTrue(result3['success'])
            
            # 정리
            await self.tx_manager.end_transaction(result3['transaction_id'])
        
        asyncio.run(run_test())
    
    def test_transaction_step_update(self):
        """트랜잭션 단계 업데이트 테스트"""
        async def run_test():
            # 트랜잭션 시작
            result = await self.tx_manager.start_transaction(
                self.test_member_id, 
                TransactionType.RENTAL
            )
            self.assertTrue(result['success'])
            tx_id = result['transaction_id']
            
            # 단계별 업데이트
            steps = [
                TransactionStep.MEMBER_VERIFIED,
                TransactionStep.LOCKER_SELECTED,
                TransactionStep.HARDWARE_SENT,
                TransactionStep.SENSOR_WAIT,
                TransactionStep.SENSOR_VERIFIED,
                TransactionStep.COMPLETED
            ]
            
            for step in steps:
                update_result = await self.tx_manager.update_transaction_step(
                    tx_id, step, {'test_data': f'step_{step.value}'}
                )
                self.assertTrue(update_result)
                
                # 상태 확인
                status = await self.tx_manager.get_transaction_status(tx_id)
                self.assertEqual(status['step'], step.value)
            
            # 트랜잭션 종료
            await self.tx_manager.end_transaction(tx_id)
        
        asyncio.run(run_test())
    
    def test_sensor_event_recording(self):
        """센서 이벤트 기록 테스트"""
        async def run_test():
            # 트랜잭션 시작
            result = await self.tx_manager.start_transaction(
                self.test_member_id, 
                TransactionType.RENTAL
            )
            self.assertTrue(result['success'])
            tx_id = result['transaction_id']
            
            # 센서 이벤트 기록
            sensor_data1 = {'active': False, 'pin': 3, 'locker': 'A01'}
            record_result1 = await self.tx_manager.record_sensor_event(
                tx_id, 'A01', sensor_data1
            )
            self.assertTrue(record_result1)
            
            # 두 번째 센서 이벤트 기록
            sensor_data2 = {'active': True, 'pin': 5, 'locker': 'A02'}
            record_result2 = await self.tx_manager.record_sensor_event(
                tx_id, 'A02', sensor_data2
            )
            self.assertTrue(record_result2)
            
            # 트랜잭션 상태에서 센서 이벤트 확인
            status = await self.tx_manager.get_transaction_status(tx_id)
            self.assertIsNotNone(status)
            
            # 데이터베이스에서 직접 확인
            cursor = self.db_manager.execute_query("""
                SELECT sensor_events FROM active_transactions 
                WHERE transaction_id = ?
            """, (tx_id,))
            
            self.assertIsNotNone(cursor)
            row = cursor.fetchone()
            self.assertIsNotNone(row)
            self.assertIsNotNone(row['sensor_events'])
            
            import json
            events = json.loads(row['sensor_events'])
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0]['locker_number'], 'A01')
            self.assertEqual(events[1]['locker_number'], 'A02')
            
            # 트랜잭션 종료
            await self.tx_manager.end_transaction(tx_id)
        
        asyncio.run(run_test())
    
    def test_timeout_cleanup(self):
        """타임아웃 정리 테스트"""
        async def run_test():
            # 트랜잭션 시작
            result = await self.tx_manager.start_transaction(
                self.test_member_id, 
                TransactionType.RENTAL
            )
            self.assertTrue(result['success'])
            tx_id = result['transaction_id']
            
            # 수동으로 타임아웃 시간을 과거로 설정
            past_time = datetime.now(timezone.utc) - timedelta(seconds=10)
            cursor = self.db_manager.execute_query("""
                UPDATE active_transactions 
                SET timeout_at = ?
                WHERE transaction_id = ?
            """, (past_time.isoformat(), tx_id))
            
            self.assertIsNotNone(cursor)
            
            # 타임아웃 정리 실행
            cleanup_count = await self.tx_manager._cleanup_timeout_transactions()
            self.assertGreaterEqual(cleanup_count, 1)
            
            # 트랜잭션 상태 확인 (타임아웃 상태여야 함)
            cursor = self.db_manager.execute_query("""
                SELECT status FROM active_transactions 
                WHERE transaction_id = ?
            """, (tx_id,))
            
            self.assertIsNotNone(cursor)
            row = cursor.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row['status'], TransactionStatus.TIMEOUT.value)
        
        asyncio.run(run_test())
    
    def test_active_transactions_list(self):
        """활성 트랜잭션 목록 테스트"""
        async def run_test():
            # 여러 트랜잭션 시작 (순차적으로)
            tx_ids = []
            
            # 첫 번째 트랜잭션
            result1 = await self.tx_manager.start_transaction(
                self.test_member_id, 
                TransactionType.RENTAL
            )
            self.assertTrue(result1['success'])
            tx_ids.append(result1['transaction_id'])
            
            # 첫 번째 종료 후 두 번째 시작
            await self.tx_manager.end_transaction(tx_ids[0])
            
            result2 = await self.tx_manager.start_transaction(
                'MEMBER_002', 
                TransactionType.RETURN
            )
            self.assertTrue(result2['success'])
            tx_ids.append(result2['transaction_id'])
            
            # 활성 트랜잭션 목록 조회
            active_transactions = await self.tx_manager.get_active_transactions()
            self.assertEqual(len(active_transactions), 1)  # 하나만 활성
            self.assertEqual(active_transactions[0]['transaction_id'], tx_ids[1])
            self.assertEqual(active_transactions[0]['member_id'], 'MEMBER_002')
            
            # 정리
            await self.tx_manager.end_transaction(tx_ids[1])
        
        asyncio.run(run_test())
    
    def test_locker_locking(self):
        """락카 잠금 테스트"""
        async def run_test():
            # 트랜잭션 시작 전 락카 상태 확인
            cursor = self.db_manager.execute_query("""
                SELECT COUNT(*) as count FROM locker_status 
                WHERE current_transaction IS NOT NULL
            """)
            self.assertIsNotNone(cursor)
            row = cursor.fetchone()
            self.assertEqual(row['count'], 0)  # 잠금된 락카 없음
            
            # 트랜잭션 시작
            result = await self.tx_manager.start_transaction(
                self.test_member_id, 
                TransactionType.RENTAL
            )
            self.assertTrue(result['success'])
            tx_id = result['transaction_id']
            
            # 모든 락카가 잠금되었는지 확인
            cursor = self.db_manager.execute_query("""
                SELECT COUNT(*) as count FROM locker_status 
                WHERE current_transaction = ?
            """, (tx_id,))
            self.assertIsNotNone(cursor)
            row = cursor.fetchone()
            self.assertGreater(row['count'], 0)  # 잠금된 락카 존재
            
            # 트랜잭션 종료
            await self.tx_manager.end_transaction(tx_id)
            
            # 락카 잠금 해제 확인
            cursor = self.db_manager.execute_query("""
                SELECT COUNT(*) as count FROM locker_status 
                WHERE current_transaction IS NOT NULL
            """)
            self.assertIsNotNone(cursor)
            row = cursor.fetchone()
            self.assertEqual(row['count'], 0)  # 잠금 해제됨
        
        asyncio.run(run_test())


if __name__ == '__main__':
    # 로깅 설정
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # 테스트 실행
    unittest.main(verbosity=2)
