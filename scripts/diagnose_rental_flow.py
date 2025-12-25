#!/usr/bin/env python3
"""
대여 흐름 진단 스크립트
- 센서 이벤트 큐 상태 확인
- DB 정합성 확인
- 프로세스 상태 확인
- Pending 레코드 정리

Usage:
    python scripts/diagnose_rental_flow.py --check    # 상태 확인만
    python scripts/diagnose_rental_flow.py --fix      # 문제 자동 수정
    python scripts/diagnose_rental_flow.py --clean    # 중복 프로세스 정리 (sudo 필요)
"""

import os
import sys
import sqlite3
import subprocess
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "instance" / "gym_system.db"


def print_header(title: str):
    """섹션 헤더 출력"""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def check_processes():
    """실행 중인 관련 프로세스 확인"""
    print_header("🔍 프로세스 상태 확인")
    
    # Python 서버 프로세스
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True
        )
        
        lines = result.stdout.split('\n')
        python_procs = [l for l in lines if 'python' in l.lower() and 'run.py' in l]
        flask_procs = [l for l in lines if 'flask' in l.lower() or 'gunicorn' in l.lower()]
        chromium_procs = [l for l in lines if 'chromium' in l.lower()]
        
        print(f"\n📦 Python 서버 프로세스 ({len(python_procs)}개):")
        for p in python_procs[:5]:  # 최대 5개만 표시
            parts = p.split()
            if len(parts) > 1:
                print(f"   PID {parts[1]}: {' '.join(parts[10:])[:60]}...")
        
        if len(python_procs) > 1:
            print(f"\n   ⚠️  경고: Python 서버가 {len(python_procs)}개 실행 중!")
            print("   👉 `pkill -f 'python.*run.py'`로 모두 종료 후 재시작 권장")
        elif len(python_procs) == 1:
            print("   ✅ 정상: 단일 서버 프로세스 실행 중")
        else:
            print("   ❌ 서버 프로세스 없음")
        
        print(f"\n🌐 Chromium 브라우저 ({len(chromium_procs)}개):")
        if len(chromium_procs) > 5:
            print(f"   ⚠️  경고: Chromium 프로세스가 {len(chromium_procs)}개 - 메모리 문제 가능")
        elif len(chromium_procs) > 0:
            print(f"   ✅ 정상: {len(chromium_procs)}개 Chromium 프로세스")
        else:
            print("   ℹ️  Chromium 없음 (키오스크 모드 아님)")
            
    except Exception as e:
        print(f"   ❌ 프로세스 확인 실패: {e}")


def check_database():
    """데이터베이스 상태 확인"""
    print_header("🗄️  데이터베이스 상태 확인")
    
    if not DB_PATH.exists():
        print(f"   ❌ DB 파일 없음: {DB_PATH}")
        return
    
    # WAL 파일 확인
    wal_path = Path(str(DB_PATH) + "-wal")
    shm_path = Path(str(DB_PATH) + "-shm")
    
    print(f"\n📁 파일 상태:")
    print(f"   DB: {DB_PATH.stat().st_size / 1024:.1f} KB")
    if wal_path.exists():
        wal_size = wal_path.stat().st_size
        print(f"   WAL: {wal_size / 1024:.1f} KB ({wal_size / 4096:.0f} 페이지)")
        if wal_size > 1024 * 1024:  # 1MB 이상
            print(f"   ⚠️  WAL 파일이 큼 - CHECKPOINT 권장")
    if shm_path.exists():
        print(f"   SHM: {shm_path.stat().st_size / 1024:.1f} KB")
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Pending 레코드 확인
        cursor.execute("""
            SELECT rental_id, member_id, locker_number, status, 
                   rental_barcode_time, created_at
            FROM rentals 
            WHERE status = 'pending'
            ORDER BY created_at DESC
            LIMIT 10
        """)
        pending = cursor.fetchall()
        
        print(f"\n⏳ Pending 대여 레코드 ({len(pending)}개):")
        if pending:
            for r in pending:
                print(f"   ID:{r['rental_id']} | 회원:{r['member_id']} | "
                      f"락커:{r['locker_number']} | {r['rental_barcode_time'][:16] if r['rental_barcode_time'] else 'N/A'}")
        else:
            print("   ✅ Pending 레코드 없음")
        
        # Active 레코드 확인
        cursor.execute("""
            SELECT rental_id, member_id, locker_number, status, 
                   rental_barcode_time
            FROM rentals 
            WHERE status = 'active'
            ORDER BY created_at DESC
            LIMIT 5
        """)
        active = cursor.fetchall()
        
        print(f"\n✅ Active 대여 레코드 ({len(active)}개 최근):")
        for r in active:
            print(f"   ID:{r['rental_id']} | 회원:{r['member_id']} | 락커:{r['locker_number']}")
        
        # locker_status vs rentals 정합성 확인
        print("\n🔗 데이터 정합성 확인:")
        cursor.execute("""
            SELECT ls.locker_number, ls.current_member, r.member_id as rental_member
            FROM locker_status ls
            LEFT JOIN rentals r ON ls.locker_number = r.locker_number 
                AND r.status = 'active'
            WHERE ls.current_member IS NOT NULL
        """)
        locker_data = cursor.fetchall()
        
        inconsistent = []
        for row in locker_data:
            if row['current_member'] != row['rental_member']:
                inconsistent.append(row)
        
        if inconsistent:
            print(f"   ⚠️  불일치 발견 ({len(inconsistent)}개):")
            for row in inconsistent:
                print(f"      락커 {row['locker_number']}: "
                      f"locker_status={row['current_member']}, rentals={row['rental_member']}")
        else:
            print("   ✅ locker_status와 rentals 테이블 정합성 OK")
        
        # members.currently_renting 확인
        cursor.execute("""
            SELECT m.member_id, m.currently_renting, r.locker_number as active_rental
            FROM members m
            LEFT JOIN rentals r ON m.member_id = r.member_id 
                AND r.status = 'active'
            WHERE m.currently_renting IS NOT NULL 
                OR r.locker_number IS NOT NULL
        """)
        member_data = cursor.fetchall()
        
        member_inconsistent = []
        for row in member_data:
            if row['currently_renting'] != row['active_rental']:
                member_inconsistent.append(row)
        
        if member_inconsistent:
            print(f"   ⚠️  members 테이블 불일치 ({len(member_inconsistent)}개):")
            for row in member_inconsistent:
                print(f"      회원 {row['member_id']}: "
                      f"currently_renting={row['currently_renting']}, "
                      f"active_rental={row['active_rental']}")
        else:
            print("   ✅ members.currently_renting 정합성 OK")
        
        conn.close()
        
    except Exception as e:
        print(f"   ❌ DB 조회 오류: {e}")


def check_sensor_api():
    """센서 API 상태 확인"""
    print_header("📡 센서 API 상태 확인")
    
    import requests
    
    try:
        # 센서 폴링 API 호출
        response = requests.get("http://localhost:5000/api/sensor/poll", timeout=3)
        data = response.json()
        
        print(f"\n📊 /api/sensor/poll 응답:")
        print(f"   has_events: {data.get('has_events', False)}")
        if data.get('events'):
            print(f"   events: {len(data['events'])}개")
            for evt in data['events'][:3]:
                print(f"      센서{evt.get('sensor_num')}: {evt.get('state')}")
        
        # 하드웨어 상태 API
        response = requests.get("http://localhost:5000/api/hardware/status", timeout=3)
        hw_data = response.json()
        
        print(f"\n🔧 /api/hardware/status:")
        print(f"   ESP32 연결: {'✅' if hw_data.get('data', {}).get('esp32Connection') else '❌'}")
        
        # 센서 상태 API
        response = requests.get("http://localhost:5000/api/hardware/sensor_status", timeout=3)
        sensor_data = response.json()
        
        if sensor_data.get('success'):
            sensors = sensor_data.get('sensors', {})
            low_sensors = [k for k, v in sensors.items() if v == 'LOW']
            print(f"\n📍 현재 센서 상태:")
            print(f"   총 센서: {len(sensors)}개")
            print(f"   LOW 상태 (키 꽂힘): {len(low_sensors)}개")
            if low_sensors:
                print(f"   LOW 센서들: {low_sensors[:10]}...")
                
    except requests.exceptions.ConnectionError:
        print("   ❌ 서버 연결 실패 - Flask 서버가 실행 중인지 확인하세요")
    except Exception as e:
        print(f"   ❌ API 호출 오류: {e}")


def fix_pending_records():
    """Pending 레코드 정리"""
    print_header("🔧 Pending 레코드 정리")
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # 1시간 이상 된 pending 레코드를 cancelled로 변경
        one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
        
        cursor.execute("""
            UPDATE rentals 
            SET status = 'cancelled', 
                error_code = 'TIMEOUT_CLEANUP',
                error_details = '자동 정리: 1시간 이상 pending 상태',
                updated_at = ?
            WHERE status = 'pending' AND created_at < ?
        """, (datetime.now().isoformat(), one_hour_ago))
        
        cancelled_count = cursor.rowcount
        
        # 최근 pending 레코드 (30분 이내)는 유지
        cursor.execute("""
            SELECT COUNT(*) FROM rentals 
            WHERE status = 'pending' AND created_at >= ?
        """, (one_hour_ago,))
        recent_pending = cursor.fetchone()[0]
        
        conn.commit()
        conn.close()
        
        print(f"   ✅ {cancelled_count}개 오래된 pending 레코드 취소됨")
        print(f"   ℹ️  {recent_pending}개 최근 pending 레코드 유지됨")
        
    except Exception as e:
        print(f"   ❌ Pending 정리 오류: {e}")


def fix_data_consistency():
    """데이터 정합성 복구"""
    print_header("🔧 데이터 정합성 복구")
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # 1. locker_status에 current_member가 있지만 rentals에 active 레코드가 없는 경우
        cursor.execute("""
            SELECT ls.locker_number, ls.current_member
            FROM locker_status ls
            LEFT JOIN rentals r ON ls.locker_number = r.locker_number 
                AND r.status = 'active'
            WHERE ls.current_member IS NOT NULL AND r.rental_id IS NULL
        """)
        orphan_lockers = cursor.fetchall()
        
        if orphan_lockers:
            print(f"\n   🔄 고아 locker_status 레코드 정리 ({len(orphan_lockers)}개):")
            for locker_num, member_id in orphan_lockers:
                print(f"      {locker_num} (회원: {member_id}) → current_member = NULL")
                cursor.execute("""
                    UPDATE locker_status 
                    SET current_member = NULL, updated_at = ?
                    WHERE locker_number = ?
                """, (datetime.now().isoformat(), locker_num))
        
        # 2. members.currently_renting이 있지만 rentals에 active 레코드가 없는 경우
        cursor.execute("""
            SELECT m.member_id, m.currently_renting
            FROM members m
            LEFT JOIN rentals r ON m.member_id = r.member_id 
                AND r.status = 'active'
            WHERE m.currently_renting IS NOT NULL AND r.rental_id IS NULL
        """)
        orphan_members = cursor.fetchall()
        
        if orphan_members:
            print(f"\n   🔄 고아 members 레코드 정리 ({len(orphan_members)}개):")
            for member_id, renting in orphan_members:
                print(f"      {member_id} (대여: {renting}) → currently_renting = NULL")
                cursor.execute("""
                    UPDATE members 
                    SET currently_renting = NULL, updated_at = ?
                    WHERE member_id = ?
                """, (datetime.now().isoformat(), member_id))
        
        # 3. WAL 체크포인트 실행
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        checkpoint_result = cursor.fetchone()
        print(f"\n   📦 WAL 체크포인트: blocked={checkpoint_result[0]}, "
              f"log={checkpoint_result[1]}, checkpointed={checkpoint_result[2]}")
        
        conn.commit()
        conn.close()
        
        if not orphan_lockers and not orphan_members:
            print("   ✅ 데이터 정합성 문제 없음")
        else:
            print(f"\n   ✅ 총 {len(orphan_lockers) + len(orphan_members)}개 레코드 수정됨")
        
    except Exception as e:
        print(f"   ❌ 정합성 복구 오류: {e}")


def kill_duplicate_processes():
    """중복 프로세스 정리"""
    print_header("🧹 중복 프로세스 정리")
    
    print("\n   ⚠️  sudo 권한이 필요할 수 있습니다")
    
    try:
        # Python 서버 프로세스 종료
        result = subprocess.run(
            ["pkill", "-f", "python.*run.py"],
            capture_output=True,
            text=True
        )
        print(f"   🔄 Python 서버 프로세스 종료 시도: "
              f"{'성공' if result.returncode == 0 else '없거나 실패'}")
        
        # Chromium 프로세스 종료 (옵션)
        # result = subprocess.run(
        #     ["pkill", "-f", "chromium"],
        #     capture_output=True,
        #     text=True
        # )
        # print(f"   🔄 Chromium 종료: {'성공' if result.returncode == 0 else '없거나 실패'}")
        
        print("\n   👉 프로세스 정리 완료. 다음 명령으로 서버 재시작:")
        print("      cd /home/pi/raspberry-pi-gym-controller")
        print("      bash scripts/start_kiosk.sh")
        
    except Exception as e:
        print(f"   ❌ 프로세스 정리 오류: {e}")


def main():
    parser = argparse.ArgumentParser(description="대여 흐름 진단 스크립트")
    parser.add_argument('--check', action='store_true', help='상태 확인만')
    parser.add_argument('--fix', action='store_true', help='문제 자동 수정')
    parser.add_argument('--clean', action='store_true', help='중복 프로세스 정리')
    parser.add_argument('--all', action='store_true', help='모든 작업 실행')
    
    args = parser.parse_args()
    
    print("\n" + "🔬 대여 흐름 진단 스크립트 v1.0 ".center(60, "="))
    print(f"   실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   DB 경로: {DB_PATH}")
    
    # 기본적으로 check 실행
    if not any([args.check, args.fix, args.clean]):
        args.check = True
    
    if args.check or args.all:
        check_processes()
        check_database()
        check_sensor_api()
    
    if args.fix or args.all:
        fix_pending_records()
        fix_data_consistency()
    
    if args.clean or args.all:
        kill_duplicate_processes()
    
    print("\n" + "=" * 60)
    print("   진단 완료!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()

