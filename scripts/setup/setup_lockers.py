#!/usr/bin/env python3
"""
락커 구성 설정 스크립트

실제 락커 개수와 분류에 맞게 데이터베이스를 재설정합니다.
- 남성용: 1-60번 (60개)
- 교직원: 1-20번 (20개) 
- 여성용: 1-60번 (60개)
총 140개
"""

import sys
import os
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.database_manager import DatabaseManager


def create_locker_configuration() -> dict:
    """락커 구성 정보 생성
    
    Returns:
        락커 구성 딕셔너리
    """
    config = {
        'MALE': {
            'count': 60,
            'prefix': 'M',
            'device_id': 'esp32_male',
            'size': 'medium',
            'description': '남성용 락커'
        },
        'STAFF': {
            'count': 20,
            'prefix': 'S', 
            'device_id': 'esp32_staff',
            'size': 'large',
            'description': '교직원용 락커'
        },
        'FEMALE': {
            'count': 60,
            'prefix': 'F',
            'device_id': 'esp32_female', 
            'size': 'medium',
            'description': '여성용 락커'
        }
    }
    return config


def generate_locker_insert_sql(config: dict) -> str:
    """락커 INSERT SQL 생성
    
    Args:
        config: 락커 구성 정보
        
    Returns:
        INSERT SQL 문자열
    """
    sql_parts = []
    
    for zone, info in config.items():
        prefix = info['prefix']
        count = info['count']
        device_id = info['device_id']
        size = info['size']
        
        # 각 구역별 락커 생성
        lockers = []
        for i in range(1, count + 1):
            locker_number = f"{prefix}{i:02d}"  # M01, S01, F01 형식
            lockers.append(f"('{locker_number}', '{zone}', '{device_id}', '{size}')")
        
        sql_parts.extend(lockers)
    
    # INSERT 문 생성
    insert_sql = f"""
INSERT INTO locker_status (locker_number, zone, device_id, size) VALUES
{','.join(sql_parts)};
"""
    
    return insert_sql


def setup_lockers(db_path: str = 'instance/gym_system.db', reset: bool = False) -> bool:
    """락커 설정 적용
    
    Args:
        db_path: 데이터베이스 파일 경로
        reset: 기존 락커 데이터 초기화 여부
        
    Returns:
        설정 성공 여부
    """
    try:
        print("🔧 락커 구성 설정 시작")
        print("=" * 50)
        
        # 데이터베이스 연결
        db = DatabaseManager(db_path)
        if not db.connect():
            print("❌ 데이터베이스 연결 실패")
            return False
        
        # 락커 구성 정보
        config = create_locker_configuration()
        
        print("📋 락커 구성 계획:")
        total_lockers = 0
        for zone, info in config.items():
            print(f"  🏷️  {zone} ({info['description']}): {info['count']}개 ({info['prefix']}01-{info['prefix']}{info['count']:02d})")
            total_lockers += info['count']
        
        print(f"  📊 총 락커 수: {total_lockers}개")
        print()
        
        # 기존 락커 데이터 확인
        cursor = db.execute_query("SELECT COUNT(*) as count FROM locker_status")
        if cursor:
            existing_count = cursor.fetchone()['count']
            print(f"📦 기존 락커 데이터: {existing_count}개")
            
            if existing_count > 0:
                if reset:
                    print("🗑️  기존 락커 데이터 삭제 중...")
                    db.execute_query("DELETE FROM locker_status")
                    print("✅ 기존 데이터 삭제 완료")
                else:
                    print("⚠️  기존 락커 데이터가 존재합니다.")
                    print("   --reset 옵션을 사용하여 초기화하거나")
                    print("   기존 데이터를 유지하려면 계속 진행하세요.")
                    
                    choice = input("계속 진행하시겠습니까? (y/N): ")
                    if choice.lower() not in ['y', 'yes']:
                        print("취소되었습니다.")
                        return False
        
        # 새 락커 데이터 삽입
        print("📥 새 락커 데이터 생성 중...")
        insert_sql = generate_locker_insert_sql(config)
        
        # SQL 실행
        db.conn.executescript(insert_sql)
        print("✅ 락커 데이터 삽입 완료")
        
        # 결과 확인
        print("\n📊 설정 결과 확인:")
        for zone, info in config.items():
            cursor = db.execute_query(
                "SELECT COUNT(*) as count FROM locker_status WHERE zone = ?", 
                (zone,)
            )
            if cursor:
                actual_count = cursor.fetchone()['count']
                status = "✅" if actual_count == info['count'] else "❌"
                print(f"  {status} {zone}: {actual_count}/{info['count']}개")
        
        # 전체 통계
        cursor = db.execute_query("SELECT COUNT(*) as total FROM locker_status")
        if cursor:
            total_actual = cursor.fetchone()['total']
            print(f"  📊 전체: {total_actual}/{total_lockers}개")
        
        # 샘플 락커 확인
        print("\n🔍 샘플 락커 확인:")
        cursor = db.execute_query("""
            SELECT locker_number, zone, device_id, size 
            FROM locker_status 
            WHERE locker_number IN ('M01', 'M60', 'S01', 'S20', 'F01', 'F60')
            ORDER BY locker_number
        """)
        
        if cursor:
            samples = cursor.fetchall()
            for sample in samples:
                print(f"  • {sample['locker_number']} ({sample['zone']}) - {sample['device_id']} - {sample['size']}")
        
        db.close()
        
        print("\n🎉 락커 구성 설정 완료!")
        print(f"📁 데이터베이스: {db_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ 락커 설정 실패: {e}")
        return False


def main():
    """메인 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description='락커 구성 설정')
    parser.add_argument('--db-path', default='instance/gym_system.db', help='데이터베이스 파일 경로')
    parser.add_argument('--reset', action='store_true', help='기존 락커 데이터 초기화')
    parser.add_argument('--preview', action='store_true', help='설정 미리보기만 표시')
    
    args = parser.parse_args()
    
    if args.preview:
        print("🔍 락커 구성 미리보기")
        print("=" * 50)
        
        config = create_locker_configuration()
        total = 0
        
        for zone, info in config.items():
            print(f"🏷️  {zone} ({info['description']}):")
            print(f"   • 개수: {info['count']}개")
            print(f"   • 번호: {info['prefix']}01 ~ {info['prefix']}{info['count']:02d}")
            print(f"   • 디바이스: {info['device_id']}")
            print(f"   • 크기: {info['size']}")
            print()
            total += info['count']
        
        print(f"📊 총 락커 수: {total}개")
        print("\n📝 생성될 SQL 미리보기:")
        print(generate_locker_insert_sql(config)[:200] + "...")
        
        return
    
    # 실제 설정 실행
    success = setup_lockers(args.db_path, args.reset)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
