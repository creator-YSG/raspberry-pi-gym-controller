#!/usr/bin/env python3
"""
서비스 로직 전체 플로우 테스트
바코드 스캔 → 회원 검증 → 대여/반납 판단 → 락커 구역 선택 → 락커 열기
"""

import sys
import os
import asyncio
from datetime import datetime

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.member_service import MemberService
from app.services.locker_service import LockerService


class ServiceFlowTester:
    """서비스 플로우 테스터"""
    
    def __init__(self):
        self.member_service = MemberService('instance/gym_system.db')
        self.locker_service = LockerService('instance/gym_system.db')
    
    def scan_barcode(self, barcode: str) -> dict:
        """1단계: 바코드 스캔 시뮬레이션"""
        print(f"📱 바코드 스캔: {barcode}")
        return {'barcode': barcode, 'timestamp': datetime.now().isoformat()}
    
    def validate_member(self, member_id: str) -> dict:
        """2단계: 회원 검증"""
        print(f"🔍 회원 검증 중: {member_id}")
        
        # 회원 조회
        member = self.member_service.get_member(member_id)
        if not member:
            return {
                'valid': False,
                'error': '등록되지 않은 회원입니다.',
                'member': None
            }
        
        # 유효성 검사
        if not member.is_valid:
            return {
                'valid': False,
                'error': f'만료된 회원입니다. (만료일: {member.membership_expires})',
                'member': member
            }
        
        print(f"   ✅ 유효한 회원: {member.name} ({member.customer_type})")
        print(f"   📅 만료일: {member.membership_expires} ({member.days_remaining}일 남음)")
        print(f"   🔑 접근 가능 구역: {member.allowed_zones}")
        
        return {
            'valid': True,
            'member': member,
            'error': None
        }
    
    def determine_action(self, member) -> dict:
        """3단계: 대여/반납 판단"""
        print(f"🤔 대여/반납 판단 중...")
        
        if member.is_renting:
            action = 'return'
            current_locker = member.currently_renting
            print(f"   🔄 반납 모드: {current_locker}번 락커 반납")
            return {
                'action': action,
                'current_locker': current_locker,
                'message': f'{current_locker}번 락커를 반납하시겠습니까?'
            }
        else:
            action = 'rental'
            print(f"   🆕 대여 모드: 새 락커 대여")
            return {
                'action': action,
                'current_locker': None,
                'message': '사용할 락커를 선택해주세요.'
            }
    
    def get_available_zones_and_lockers(self, member) -> dict:
        """4단계: 접근 가능한 구역과 락커 조회"""
        print(f"🏢 접근 가능한 구역 조회 중...")
        
        zones_info = {}
        total_available = 0
        
        for zone in member.allowed_zones:
            available_lockers = self.locker_service.get_available_lockers(zone, member.id)
            zones_info[zone] = {
                'name': {'MALE': '남자', 'FEMALE': '여자', 'STAFF': '교직원'}.get(zone, zone),
                'available_count': len(available_lockers),
                'lockers': [locker.id for locker in available_lockers[:5]]  # 처음 5개만
            }
            total_available += len(available_lockers)
            
            print(f"   🏢 {zones_info[zone]['name']} 구역: {len(available_lockers)}개 사용 가능")
        
        return {
            'zones': zones_info,
            'total_available': total_available
        }
    
    async def rent_locker_flow(self, member, selected_locker_id: str) -> dict:
        """5단계: 락커 대여 플로우"""
        print(f"🔐 락커 대여 시도: {selected_locker_id}")
        
        # 락커 대여 실행
        result = await self.locker_service.rent_locker(selected_locker_id, member.id)
        
        if result['success']:
            print(f"   ✅ 대여 성공: {result['message']}")
            print(f"   🔑 트랜잭션 ID: {result['transaction_id']}")
        else:
            print(f"   ❌ 대여 실패: {result['error']}")
        
        return result
    
    def return_locker_flow(self, member) -> dict:
        """5단계: 락커 반납 플로우"""
        print(f"🔓 락커 반납 시도: {member.currently_renting}")
        
        # 락커 반납 실행
        result = self.locker_service.return_locker(member.currently_renting)
        
        if result['success']:
            print(f"   ✅ 반납 성공: {result['message']}")
        else:
            print(f"   ❌ 반납 실패: {result['error']}")
        
        return result
    
    async def test_complete_flow(self, member_id: str, selected_locker_id: str = None):
        """전체 플로우 테스트"""
        print(f"\n🧪 서비스 플로우 테스트 시작: {member_id}")
        print("=" * 60)
        
        try:
            # 1단계: 바코드 스캔
            scan_result = self.scan_barcode(member_id)
            
            # 2단계: 회원 검증
            validation_result = self.validate_member(member_id)
            if not validation_result['valid']:
                print(f"❌ 회원 검증 실패: {validation_result['error']}")
                return
            
            member = validation_result['member']
            
            # 3단계: 대여/반납 판단
            action_result = self.determine_action(member)
            
            if action_result['action'] == 'return':
                # 반납 플로우
                return_result = self.return_locker_flow(member)
                if return_result['success']:
                    print(f"🎉 반납 완료!")
                else:
                    print(f"💥 반납 실패!")
            
            else:
                # 대여 플로우
                # 4단계: 사용 가능한 구역과 락커 조회
                zones_result = self.get_available_zones_and_lockers(member)
                
                if zones_result['total_available'] == 0:
                    print(f"❌ 사용 가능한 락커가 없습니다.")
                    return
                
                # 5단계: 락커 선택 및 대여
                if not selected_locker_id:
                    # 첫 번째 사용 가능한 락커 자동 선택
                    first_zone = list(zones_result['zones'].keys())[0]
                    first_lockers = self.locker_service.get_available_lockers(first_zone, member.id)
                    if first_lockers:
                        selected_locker_id = first_lockers[0].id
                
                if selected_locker_id:
                    rental_result = await self.rent_locker_flow(member, selected_locker_id)
                    if rental_result['success']:
                        print(f"🎉 대여 완료! 센서 검증 대기 중...")
                    else:
                        print(f"💥 대여 실패!")
                else:
                    print(f"❌ 선택할 락커가 없습니다.")
        
        except Exception as e:
            print(f"💥 플로우 테스트 오류: {e}")
        
        print("=" * 60)


async def main():
    """메인 테스트 함수"""
    tester = ServiceFlowTester()
    
    # 테스트 시나리오들
    test_scenarios = [
        {
            'member_id': '20156111',  # 김현 (남자 교직원)
            'description': '남자 교직원 - 남자구역 + 교직원구역 접근 가능',
            'selected_locker': 'M01'  # 남자 구역 락커
        },
        {
            'member_id': '20211377',  # 김진서 (여자 교직원)
            'description': '여자 교직원 - 여자구역 + 교직원구역 접근 가능',
            'selected_locker': 'S01'  # 교직원 구역 락커
        },
        {
            'member_id': '20240838',  # 손준표 (남자 일반회원)
            'description': '남자 일반회원 - 남자구역만 접근 가능',
            'selected_locker': 'M02'  # 남자 구역 락커
        },
        {
            'member_id': '20211131',  # 엘레나 (여자 일반회원)
            'description': '여자 일반회원 - 여자구역만 접근 가능',
            'selected_locker': 'F01'  # 여자 구역 락커
        },
        {
            'member_id': '99999999',  # 존재하지 않는 회원
            'description': '존재하지 않는 회원 - 오류 처리 테스트',
            'selected_locker': None
        }
    ]
    
    print("🚀 헬스장 락커 시스템 서비스 플로우 테스트")
    print("=" * 80)
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n📋 시나리오 {i}: {scenario['description']}")
        await tester.test_complete_flow(
            scenario['member_id'], 
            scenario['selected_locker']
        )
        
        if i < len(test_scenarios):
            print("\n" + "⏳ 다음 시나리오까지 잠시 대기...")
            await asyncio.sleep(1)
    
    print(f"\n🎯 모든 시나리오 테스트 완료!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
