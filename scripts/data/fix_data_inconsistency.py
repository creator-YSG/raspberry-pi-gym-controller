#!/usr/bin/env python3
"""
데이터 불일치 문제 해결 스크립트

문제:
- 회원 테이블에는 대여 정보가 있지만 대여 테이블의 상태가 'pending'
- 대여 테이블의 상태를 'active'로 업데이트 필요
- 락카 상태 테이블과의 동기화 필요

작성자: AI Assistant
작성일: 2025-10-12
"""

import sys
import sqlite3
from datetime import datetime
import traceback

def fix_data_inconsistency():
    """데이터 불일치 문제 해결"""
    
    print("🔧 데이터 불일치 문제 해결 시작")
    print("=" * 60)
    
    db_path = "./locker.db"
    
    try:
        # 데이터베이스 연결
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print(f"📁 데이터베이스 연결: {db_path}")
        
        # 1. 현재 상황 분석
        print("\n🔍 현재 데이터 상황 분석:")
        
        # 회원 테이블에서 대여중인 회원
        cursor.execute("""
            SELECT member_id, member_name, currently_renting, daily_rental_count
            FROM members 
            WHERE currently_renting IS NOT NULL AND currently_renting != ""
        """)
        renting_members = cursor.fetchall()
        
        print(f"대여중인 회원: {len(renting_members)}명")
        for member in renting_members:
            print(f"  👤 {member['member_id']} ({member['member_name']}): {member['currently_renting']}번 락카")
        
        # 대여 테이블 상태 확인
        cursor.execute("""
            SELECT rental_id, member_id, locker_number, status, rental_barcode_time
            FROM rentals 
            WHERE member_id IN (SELECT member_id FROM members WHERE currently_renting IS NOT NULL AND currently_renting != "")
        """)
        rental_records = cursor.fetchall()
        
        print(f"\n대여 테이블 기록: {len(rental_records)}개")
        for rental in rental_records:
            print(f"  📝 {rental['rental_id']}: {rental['member_id']} → {rental['locker_number']}, 상태: {rental['status']}")
        
        # 2. 데이터 수정 작업
        print(f"\n🔧 데이터 수정 작업:")
        
        fixes_applied = 0
        
        # pending 상태의 대여 기록을 active로 변경
        for rental in rental_records:
            if rental['status'] == 'pending':
                print(f"\n📝 대여 기록 {rental['rental_id']} 수정:")
                print(f"   회원: {rental['member_id']}")
                print(f"   락카: {rental['locker_number']}")
                print(f"   상태: {rental['status']} → active")
                
                # 대여 기록 상태 업데이트
                cursor.execute("""
                    UPDATE rentals 
                    SET status = 'active',
                        updated_at = ?
                    WHERE rental_id = ?
                """, (datetime.now().isoformat(), rental['rental_id']))
                
                fixes_applied += 1
                print(f"   ✅ 대여 기록 상태 업데이트 완료")
        
        # 3. 추가 검증 및 동기화
        print(f"\n🔍 수정 후 검증:")
        
        # 활성 대여 기록 재확인
        cursor.execute("""
            SELECT rental_id, member_id, locker_number, status
            FROM rentals 
            WHERE status = 'active'
        """)
        active_rentals = cursor.fetchall()
        
        print(f"활성 대여 기록: {len(active_rentals)}개")
        for rental in active_rentals:
            print(f"  ✅ {rental['rental_id']}: {rental['member_id']} → {rental['locker_number']} (active)")
        
        # 4. 변경사항 커밋
        if fixes_applied > 0:
            conn.commit()
            print(f"\n✅ {fixes_applied}개의 수정사항이 데이터베이스에 저장되었습니다.")
        else:
            print(f"\n📋 수정할 데이터가 없습니다.")
        
        # 5. 최종 상태 확인
        print(f"\n📊 최종 데이터 상태:")
        
        # 회원-대여 일치 확인
        cursor.execute("""
            SELECT m.member_id, m.member_name, m.currently_renting,
                   r.rental_id, r.locker_number, r.status
            FROM members m
            LEFT JOIN rentals r ON m.member_id = r.member_id AND r.status = 'active'
            WHERE m.currently_renting IS NOT NULL AND m.currently_renting != ""
        """)
        
        final_check = cursor.fetchall()
        
        all_consistent = True
        for row in final_check:
            member_locker = row['currently_renting']
            rental_locker = row['locker_number']
            rental_status = row['status']
            
            if rental_status == 'active' and member_locker == rental_locker:
                print(f"  ✅ {row['member_id']} ({row['member_name']}): 데이터 일치 ({member_locker}번 락카)")
            else:
                print(f"  ❌ {row['member_id']} ({row['member_name']}): 데이터 불일치")
                print(f"     회원 테이블: {member_locker}, 대여 테이블: {rental_locker} ({rental_status})")
                all_consistent = False
        
        if all_consistent:
            print(f"\n🎉 모든 데이터가 일치합니다!")
        else:
            print(f"\n⚠️  일부 데이터 불일치가 남아있습니다.")
        
        conn.close()
        
        return fixes_applied, all_consistent
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        traceback.print_exc()
        return 0, False

def main():
    """메인 함수"""
    
    print("🏥 락카키 대여 시스템 데이터 정합성 복구")
    print("=" * 60)
    
    # 백업 확인
    print("⚠️  주의: 이 스크립트는 데이터베이스를 수정합니다.")
    print("💾 실행 전에 데이터베이스 백업을 권장합니다.")
    
    response = input("\n계속 진행하시겠습니까? (y/N): ").strip().lower()
    if response != 'y':
        print("❌ 작업이 취소되었습니다.")
        return
    
    # 데이터 수정 실행
    fixes_applied, all_consistent = fix_data_inconsistency()
    
    # 결과 요약
    print(f"\n📋 작업 완료 요약:")
    print(f"수정된 기록: {fixes_applied}개")
    print(f"데이터 일치 여부: {'✅ 일치' if all_consistent else '❌ 불일치'}")
    
    if all_consistent:
        print(f"\n🎯 이제 시스템이 정상적으로 작동할 것입니다!")
        print(f"다음 명령으로 시스템을 테스트해보세요:")
        print(f"python3 scripts/test_complete_flow.py")
    else:
        print(f"\n⚠️  추가 수정이 필요할 수 있습니다.")

if __name__ == "__main__":
    main()
