#!/usr/bin/env python3
"""
회원 만료일자 테스트 스크립트
"""

import sys
import os
from datetime import datetime, date

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.member_service import MemberService


def test_expiry_dates():
    """회원 만료일자 테스트"""
    print("📅 회원 만료일자 테스트")
    print("=" * 50)
    
    member_service = MemberService('instance/gym_system.db')
    
    # 테스트 회원들
    test_members = [
        '20156111',  # 김현 (대학교수)
        '20240838',  # 손준표 (학부)
        '20211131',  # 엘레나 (학부)
        '20211377',  # 김진서 (대학직원)
    ]
    
    for member_id in test_members:
        print(f"\n👤 회원: {member_id}")
        
        member = member_service.get_member(member_id)
        if not member:
            print(f"   ❌ 회원을 찾을 수 없습니다.")
            continue
        
        print(f"   📋 이름: {member.name}")
        print(f"   👔 구분: {member.customer_type}")
        print(f"   📅 만료일: {member.membership_expires}")
        
        if member.membership_expires:
            days_remaining = member.days_remaining
            print(f"   ⏰ 남은 일수: {days_remaining}일")
            
            if member.is_valid:
                print(f"   ✅ 상태: 유효한 회원")
            else:
                print(f"   ❌ 상태: 만료된 회원")
        else:
            print(f"   ⚠️  만료일이 설정되지 않음")
    
    print("\n" + "=" * 50)
    print("✅ 만료일자 테스트 완료!")


def main():
    """메인 함수"""
    try:
        test_expiry_dates()
    except Exception as e:
        print(f"❌ 테스트 오류: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
