#!/usr/bin/env python3
"""
NFC 태그 등록 스크립트

60개 락커키에 부착된 NFC 태그를 스캔하여 데이터베이스에 등록합니다.
인터랙티브 모드로 실행되며, 관리자가 하나씩 등록할 수 있습니다.
"""

import sys
import os
from pathlib import Path
import asyncio
import time

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.services.nfc_service import NFCService
from database.database_manager import DatabaseManager


def print_header():
    """헤더 출력"""
    print("\n" + "=" * 70)
    print("NFC 태그 등록 시스템")
    print("=" * 70)


def print_status(nfc_service):
    """현재 등록 상태 출력"""
    mappings = nfc_service.get_all_nfc_mappings()
    unregistered = nfc_service.get_unregistered_lockers()
    
    total = len(mappings)
    registered = total - len(unregistered)
    
    print(f"\n📊 등록 현황: {registered}/{total}개 완료 ({(registered/total*100):.1f}%)")
    
    if unregistered:
        print(f"\n📝 미등록 락커 ({len(unregistered)}개):")
        # 구역별로 그룹화
        staff = [l for l in unregistered if l.startswith('S')]
        male = [l for l in unregistered if l.startswith('M')]
        female = [l for l in unregistered if l.startswith('F')]
        
        if staff:
            print(f"   교직원: {', '.join(staff)}")
        if male:
            print(f"   남성: {', '.join(male)}")
        if female:
            print(f"   여성: {', '.join(female)}")


def interactive_registration(nfc_service):
    """인터랙티브 등록 모드"""
    print("\n🔧 인터랙티브 등록 모드")
    print("   - 락커 번호를 입력하고 NFC 태그를 스캔하세요")
    print("   - 'list'를 입력하면 미등록 락커 목록을 볼 수 있습니다")
    print("   - 'status'를 입력하면 전체 현황을 볼 수 있습니다")
    print("   - 'quit' 또는 'exit'를 입력하면 종료합니다")
    print()
    
    while True:
        try:
            # 락커 번호 입력
            locker_input = input("\n락커 번호 (예: M01, F05, S03): ").strip().upper()
            
            if not locker_input:
                continue
            
            if locker_input in ['QUIT', 'EXIT', 'Q']:
                print("\n👋 등록 종료")
                break
            
            if locker_input in ['LIST', 'L']:
                unregistered = nfc_service.get_unregistered_lockers()
                if unregistered:
                    print(f"\n미등록 락커: {', '.join(unregistered)}")
                else:
                    print("\n✅ 모든 락커가 등록되었습니다!")
                continue
            
            if locker_input in ['STATUS', 'S']:
                print_status(nfc_service)
                continue
            
            # 락커 유효성 확인
            db_manager = DatabaseManager()
            cursor = db_manager.conn.cursor()
            cursor.execute("""
                SELECT locker_number, zone, nfc_uid
                FROM locker_status
                WHERE locker_number = ?
            """, (locker_input,))
            
            locker = cursor.fetchone()
            
            if not locker:
                print(f"   ❌ 락커 {locker_input}를 찾을 수 없습니다.")
                continue
            
            locker_number, zone, existing_nfc = locker
            
            if existing_nfc:
                print(f"   ⚠️  락커 {locker_number}에 이미 NFC UID가 등록되어 있습니다: {existing_nfc}")
                overwrite = input("   덮어쓰시겠습니까? (y/n): ").strip().lower()
                if overwrite != 'y':
                    print("   ⏭️  건너뜀")
                    continue
            
            # NFC UID 입력
            print(f"\n🔖 락커 {locker_number} ({zone}) - NFC 태그를 스캔하세요...")
            nfc_uid = input("   NFC UID: ").strip().upper()
            
            if not nfc_uid:
                print("   ❌ NFC UID가 비어있습니다.")
                continue
            
            if nfc_uid in ['QUIT', 'EXIT', 'Q']:
                print("\n👋 등록 종료")
                break
            
            # 등록 실행
            result = nfc_service.register_nfc_tag(locker_number, nfc_uid)
            
            if result['success']:
                print(f"   ✅ {result['message']}")
                print(f"   락커: {locker_number} → NFC: {nfc_uid}")
            else:
                print(f"   ❌ {result['error']}")
                
        except KeyboardInterrupt:
            print("\n\n⚠️  중단됨")
            break
        except Exception as e:
            print(f"   ❌ 오류: {e}")


def auto_registration_from_esp32(nfc_service):
    """ESP32에서 NFC 스캔을 받아 자동 등록 (실시간 모드)"""
    print("\n🤖 자동 등록 모드 (ESP32 연동)")
    print("   - ESP32를 연결하고 NFC 태그를 스캔하세요")
    print("   - 미등록 락커를 순서대로 등록합니다")
    print("   - Ctrl+C를 눌러 종료합니다")
    print()
    
    try:
        # ESP32 매니저 초기화
        from core.esp32_manager import create_auto_esp32_manager
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        print("🔍 ESP32 연결 중...")
        manager = loop.run_until_complete(create_auto_esp32_manager())
        
        if not manager or not manager.devices:
            print("❌ ESP32를 찾을 수 없습니다.")
            return
        
        print(f"✅ ESP32 연결됨: {list(manager.devices.keys())}")
        
        # 미등록 락커 목록
        unregistered = nfc_service.get_unregistered_lockers()
        
        if not unregistered:
            print("✅ 모든 락커가 이미 등록되었습니다!")
            return
        
        print(f"\n📝 미등록 락커 ({len(unregistered)}개): {', '.join(unregistered[:10])}...")
        print("\n대기 중... NFC 태그를 스캔하세요")
        
        current_index = 0
        
        async def handle_nfc_event(event_data):
            nonlocal current_index
            
            nfc_uid = event_data.get('nfc_uid')
            if not nfc_uid:
                return
            
            if current_index >= len(unregistered):
                print("\n✅ 모든 락커가 등록되었습니다!")
                return
            
            locker_number = unregistered[current_index]
            
            print(f"\n🔖 NFC 스캔: {nfc_uid}")
            print(f"   → 락커 {locker_number}에 등록 중...")
            
            result = nfc_service.register_nfc_tag(locker_number, nfc_uid)
            
            if result['success']:
                print(f"   ✅ {result['message']}")
                current_index += 1
                
                if current_index < len(unregistered):
                    print(f"\n다음 락커: {unregistered[current_index]}")
                else:
                    print("\n🎉 모든 락커 등록 완료!")
            else:
                print(f"   ❌ {result['error']}")
        
        # NFC 이벤트 핸들러 등록
        manager.register_event_handler("nfc_scanned", handle_nfc_event)
        
        print(f"\n시작 락커: {unregistered[current_index]}")
        
        # 이벤트 루프 실행
        loop.run_forever()
        
    except KeyboardInterrupt:
        print("\n\n⚠️  종료됨")
    except Exception as e:
        print(f"\n❌ ESP32 연동 오류: {e}")
        import traceback
        traceback.print_exc()


def bulk_test_registration(nfc_service):
    """테스트용 대량 등록 (모의 NFC UID)"""
    print("\n🧪 테스트 모드 - 모의 NFC UID 생성")
    
    confirm = input("   60개 락커에 테스트 NFC UID를 등록하시겠습니까? (y/n): ").strip().lower()
    
    if confirm != 'y':
        print("   ⏭️  취소됨")
        return
    
    unregistered = nfc_service.get_unregistered_lockers()
    
    if not unregistered:
        print("   ✅ 모든 락커가 이미 등록되어 있습니다.")
        return
    
    print(f"\n   {len(unregistered)}개 락커에 테스트 UID 등록 중...")
    
    success_count = 0
    fail_count = 0
    
    for locker_number in unregistered:
        # 테스트용 NFC UID 생성 (예: NFC_M01, NFC_F05, NFC_S03)
        test_uid = f"NFC_{locker_number}"
        
        result = nfc_service.register_nfc_tag(locker_number, test_uid)
        
        if result['success']:
            success_count += 1
            print(f"   ✅ {locker_number}: {test_uid}")
        else:
            fail_count += 1
            print(f"   ❌ {locker_number}: {result['error']}")
    
    print(f"\n   완료: 성공 {success_count}개, 실패 {fail_count}개")


def view_all_mappings(nfc_service):
    """전체 NFC 매핑 조회"""
    mappings = nfc_service.get_all_nfc_mappings()
    
    print("\n📋 전체 NFC 매핑 (60개)")
    print("=" * 70)
    
    # 구역별로 그룹화
    for zone in ['STAFF', 'MALE', 'FEMALE']:
        zone_mappings = [m for m in mappings if m['zone'] == zone]
        
        zone_name = {'STAFF': '교직원', 'MALE': '남성', 'FEMALE': '여성'}[zone]
        print(f"\n{zone_name} 구역 ({len(zone_mappings)}개):")
        
        for mapping in zone_mappings:
            locker = mapping['locker_number']
            nfc_uid = mapping['nfc_uid'] or "(미등록)"
            status = "✅" if mapping['registered'] else "❌"
            
            print(f"   {status} {locker}: {nfc_uid}")


def main():
    """메인 함수"""
    print_header()
    
    nfc_service = NFCService()
    
    # 현재 상태 출력
    print_status(nfc_service)
    
    print("\n\n등록 모드를 선택하세요:")
    print("  1. 인터랙티브 등록 (수동 입력)")
    print("  2. 자동 등록 (ESP32 연동)")
    print("  3. 테스트 등록 (모의 데이터)")
    print("  4. 전체 매핑 조회")
    print("  5. 종료")
    
    while True:
        choice = input("\n선택 (1-5): ").strip()
        
        if choice == '1':
            interactive_registration(nfc_service)
            print_status(nfc_service)
        elif choice == '2':
            auto_registration_from_esp32(nfc_service)
            print_status(nfc_service)
        elif choice == '3':
            bulk_test_registration(nfc_service)
            print_status(nfc_service)
        elif choice == '4':
            view_all_mappings(nfc_service)
        elif choice == '5':
            print("\n👋 종료합니다.")
            break
        else:
            print("❌ 잘못된 선택입니다.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  프로그램 종료")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

