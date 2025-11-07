#!/usr/bin/env python3
"""
데이터베이스 초기화 스크립트

SQLite 데이터베이스를 생성하고 스키마를 초기화합니다.
"""

import sys
import os
import logging
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.database_manager import create_database_manager


def setup_logging():
    """로깅 설정"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('logs/database_init.log', encoding='utf-8')
        ]
    )


def main():
    """메인 함수"""
    print("🚀 락카키 대여기 시스템 데이터베이스 초기화")
    print("=" * 50)
    
    # 로깅 설정
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # 로그 디렉토리 생성
        logs_dir = project_root / 'logs'
        logs_dir.mkdir(exist_ok=True)
        
        # 데이터베이스 파일 경로
        db_path = project_root / 'locker.db'
        
        # 기존 데이터베이스 백업 (존재하는 경우)
        if db_path.exists():
            backup_path = project_root / f'locker_backup_{int(os.path.getmtime(db_path))}.db'
            print(f"📦 기존 데이터베이스 백업: {backup_path}")
            os.rename(db_path, backup_path)
        
        # 데이터베이스 매니저 생성 및 초기화
        print("🔧 데이터베이스 매니저 생성 중...")
        db_manager = create_database_manager(str(db_path), initialize=True)
        
        # 초기화 확인
        stats = db_manager.get_database_stats()
        print("📊 데이터베이스 초기화 완료!")
        print(f"   • 회원 테이블: {stats.get('members_count', 0)}명")
        print(f"   • 락카 상태: {stats.get('locker_status_count', 0)}개")
        print(f"   • 대여 기록: {stats.get('rentals_count', 0)}건")
        print(f"   • 활성 트랜잭션: {stats.get('active_transactions_count', 0)}개")
        print(f"   • 사용 가능한 락카: {stats.get('available_lockers', 0)}개")
        print(f"   • 데이터베이스 크기: {stats.get('db_size_mb', 0)}MB")
        
        # 시스템 설정 확인
        print("\n⚙️ 시스템 설정:")
        settings = [
            'transaction_timeout_seconds',
            'max_daily_rentals', 
            'sensor_verification_timeout',
            'sync_interval_minutes',
            'system_version'
        ]
        
        for setting in settings:
            value = db_manager.get_system_setting(setting)
            print(f"   • {setting}: {value}")
        
        # 연결 종료
        db_manager.close()
        
        print("\n✅ 데이터베이스 초기화가 성공적으로 완료되었습니다!")
        print(f"📁 데이터베이스 파일: {db_path}")
        
        return True
        
    except Exception as e:
        logger.error(f"데이터베이스 초기화 실패: {e}")
        print(f"\n❌ 초기화 실패: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
