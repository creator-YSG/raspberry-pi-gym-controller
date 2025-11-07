#!/usr/bin/env python3
"""
테스트용 회원 데이터 추가 스크립트
"""

import sys
import os
from datetime import datetime, timedelta

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.member_service import MemberService


def add_test_members():
    """테스트용 회원 데이터 추가"""
    
    print("🚀 테스트용 회원 데이터 추가 시작...")
    
    # MemberService 초기화
    member_service = MemberService('locker.db')
    
    # 테스트용 회원 데이터
    test_members = [
        {
            'member_id': '12345',
            'member_name': '홍길동',
            'phone': '010-1234-5678',
            'membership_type': 'premium',
            'membership_expires': datetime.now() + timedelta(days=30),
            'status': 'active'
        },
        {
            'member_id': '54321',
            'member_name': '김철수',
            'phone': '010-9876-5432',
            'membership_type': 'basic',
            'membership_expires': datetime.now() + timedelta(days=5),
            'status': 'active'
        },
        {
            'member_id': 'expired123',
            'member_name': '이만료',
            'phone': '010-0000-0000',
            'membership_type': 'basic',
            'membership_expires': datetime.now() - timedelta(days=5),
            'status': 'active'
        },
        {
            'member_id': 'TEST001',
            'member_name': '테스트회원1',
            'phone': '010-1111-1111',
            'membership_type': 'vip',
            'membership_expires': datetime.now() + timedelta(days=365),
            'status': 'active'
        },
        {
            'member_id': 'TEST002',
            'member_name': '테스트회원2',
            'phone': '010-2222-2222',
            'membership_type': 'basic',
            'membership_expires': datetime.now() + timedelta(days=10),
            'status': 'active'
        }
    ]
    
    # 회원 추가
    success_count = 0
    for member_data in test_members:
        result = member_service.create_member(member_data)
        if result['success']:
            print(f"✅ 회원 추가 성공: {member_data['member_id']} ({member_data['member_name']})")
            success_count += 1
        else:
            if '이미 등록된 회원' in result['error']:
                print(f"ℹ️  이미 존재: {member_data['member_id']} ({member_data['member_name']})")
            else:
                print(f"❌ 회원 추가 실패: {member_data['member_id']}, {result['error']}")
    
    print(f"\n📊 결과: {success_count}명 추가 완료")
    
    # 전체 회원 목록 확인
    all_members = member_service.get_all_members()
    print(f"📋 전체 회원 수: {len(all_members)}명")
    
    for member in all_members:
        status_icon = "✅" if member.is_valid else "❌"
        rental_info = f" (대여중: {member.currently_renting})" if member.is_renting else ""
        print(f"  {status_icon} {member.id}: {member.name} ({member.membership_type}){rental_info}")
    
    # 회원 검증 테스트
    print(f"\n🔍 회원 검증 테스트:")
    test_ids = ['12345', '54321', 'expired123', 'NOTFOUND']
    
    for member_id in test_ids:
        result = member_service.validate_member(member_id)
        status_icon = "✅" if result['valid'] else "❌"
        message = result.get('message', result.get('error', ''))
        print(f"  {status_icon} {member_id}: {message}")
    
    member_service.close()
    print("\n✅ 테스트용 회원 데이터 추가 완료!")


if __name__ == '__main__':
    add_test_members()
