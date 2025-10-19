#!/usr/bin/env python3
"""
데이터베이스 백업 스크립트 (WAL 모드 지원)

WAL (Write-Ahead Logging) 모드에서 안전하게 백업을 수행합니다.
- 체크포인트 실행으로 최신 데이터 병합
- .db, .db-wal, .db-shm 파일 모두 백업
- 백업 검증 및 무결성 체크
- 오래된 백업 자동 정리
"""

import sqlite3
import shutil
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
import argparse
import hashlib


class DatabaseBackup:
    def __init__(self, db_path: str, backup_dir: str):
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")
        
        # 백업 디렉토리 생성
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
    def checkpoint_wal(self) -> tuple:
        """WAL 체크포인트 실행 (WAL 데이터를 메인 DB로 병합)"""
        print(f"🔄 WAL 체크포인트 실행 중... ({self.db_path})")
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # TRUNCATE 모드: WAL 파일을 0으로 리셋
            cursor.execute('PRAGMA wal_checkpoint(TRUNCATE);')
            result = cursor.fetchone()
            
            # 결과: (busy, log_pages, checkpointed_pages)
            # busy=0: 성공, busy=1: 다른 연결이 사용중
            busy, log_pages, checkpointed_pages = result
            
            conn.close()
            
            if busy == 0:
                print(f"✅ 체크포인트 완료: {checkpointed_pages} 페이지 병합됨")
            else:
                print(f"⚠️  체크포인트 실행됨 (DB 사용 중, {log_pages} 페이지 남음)")
            
            return result
            
        except Exception as e:
            print(f"❌ 체크포인트 실패: {e}")
            return None
    
    def get_file_md5(self, file_path: Path) -> str:
        """파일의 MD5 해시 계산"""
        md5 = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                md5.update(chunk)
        return md5.hexdigest()
    
    def verify_database(self, db_path: Path) -> bool:
        """데이터베이스 무결성 검증"""
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # PRAGMA integrity_check
            cursor.execute('PRAGMA integrity_check;')
            result = cursor.fetchone()[0]
            
            conn.close()
            
            if result == 'ok':
                print(f"✅ DB 무결성 검증 완료: {db_path.name}")
                return True
            else:
                print(f"❌ DB 무결성 검증 실패: {result}")
                return False
                
        except Exception as e:
            print(f"❌ DB 검증 오류: {e}")
            return False
    
    def backup_database(self, skip_checkpoint: bool = False) -> Path:
        """데이터베이스 백업 수행"""
        print("="*80)
        print("🗄️  데이터베이스 백업 시작")
        print("="*80)
        print(f"원본: {self.db_path}")
        print(f"백업 디렉토리: {self.backup_dir}")
        print()
        
        # 1. 체크포인트 실행 (선택적)
        if not skip_checkpoint:
            checkpoint_result = self.checkpoint_wal()
            if checkpoint_result is None:
                print("⚠️  체크포인트 실패했지만 백업을 계속 진행합니다.")
        else:
            print("⏭️  체크포인트 건너뜀 (--skip-checkpoint)")
        
        print()
        
        # 2. 백업 파일명 생성
        backup_basename = f"{self.db_path.stem}_backup_{self.timestamp}"
        backup_db = self.backup_dir / f"{backup_basename}.db"
        
        # 3. 메인 DB 파일 복사
        print(f"📋 메인 DB 파일 백업 중...")
        try:
            shutil.copy2(self.db_path, backup_db)
            original_size = self.db_path.stat().st_size
            backup_size = backup_db.stat().st_size
            print(f"✅ {self.db_path.name} → {backup_db.name}")
            print(f"   크기: {original_size:,} bytes")
            
            # MD5 체크섬
            original_md5 = self.get_file_md5(self.db_path)
            backup_md5 = self.get_file_md5(backup_db)
            
            if original_md5 == backup_md5:
                print(f"✅ MD5 체크섬 일치: {original_md5[:16]}...")
            else:
                print(f"❌ MD5 체크섬 불일치!")
                return None
                
        except Exception as e:
            print(f"❌ DB 백업 실패: {e}")
            return None
        
        # 4. WAL/SHM 파일 백업 (있는 경우)
        wal_file = Path(str(self.db_path) + '-wal')
        shm_file = Path(str(self.db_path) + '-shm')
        
        if wal_file.exists():
            backup_wal = self.backup_dir / f"{backup_basename}.db-wal"
            try:
                shutil.copy2(wal_file, backup_wal)
                wal_size = wal_file.stat().st_size
                print(f"✅ WAL 파일 백업: {wal_size:,} bytes")
            except Exception as e:
                print(f"⚠️  WAL 파일 백업 실패: {e}")
        else:
            print(f"ℹ️  WAL 파일 없음 (정상)")
        
        if shm_file.exists():
            backup_shm = self.backup_dir / f"{backup_basename}.db-shm"
            try:
                shutil.copy2(shm_file, backup_shm)
                print(f"✅ SHM 파일 백업 완료")
            except Exception as e:
                print(f"⚠️  SHM 파일 백업 실패: {e}")
        
        print()
        
        # 5. 백업 DB 무결성 검증
        print(f"🔍 백업 파일 검증 중...")
        if self.verify_database(backup_db):
            print()
            print("="*80)
            print(f"✅ 백업 완료: {backup_db}")
            print("="*80)
            return backup_db
        else:
            print()
            print("="*80)
            print(f"❌ 백업 실패: 무결성 검증 실패")
            print("="*80)
            return None
    
    def cleanup_old_backups(self, keep_days: int = 7, keep_count: int = 5):
        """오래된 백업 파일 정리
        
        Args:
            keep_days: 이 기간(일) 이내의 백업은 모두 유지
            keep_count: 기간 외에도 최소 이 개수만큼은 유지
        """
        print()
        print("🧹 오래된 백업 정리 중...")
        
        # 백업 파일 목록 (수정 시간 기준 정렬)
        backup_files = []
        for f in self.backup_dir.glob(f"{self.db_path.stem}_backup_*.db"):
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            backup_files.append((f, mtime))
        
        backup_files.sort(key=lambda x: x[1], reverse=True)
        
        if not backup_files:
            print("   백업 파일 없음")
            return
        
        print(f"   총 백업 파일: {len(backup_files)}개")
        
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        to_delete = []
        
        for idx, (file, mtime) in enumerate(backup_files):
            # 최근 keep_count개는 무조건 유지
            if idx < keep_count:
                continue
            
            # keep_days 이내는 유지
            if mtime > cutoff_date:
                continue
            
            to_delete.append(file)
        
        if to_delete:
            print(f"   삭제 예정: {len(to_delete)}개")
            for file in to_delete:
                try:
                    # 관련 WAL/SHM 파일도 삭제
                    file.unlink()
                    print(f"   🗑️  삭제: {file.name}")
                    
                    wal = Path(str(file) + '-wal')
                    shm = Path(str(file) + '-shm')
                    if wal.exists():
                        wal.unlink()
                    if shm.exists():
                        shm.unlink()
                        
                except Exception as e:
                    print(f"   ⚠️  삭제 실패: {file.name} - {e}")
        else:
            print(f"   삭제할 파일 없음 ({keep_days}일 이내 백업 유지)")
    
    def get_database_stats(self) -> dict:
        """데이터베이스 통계 조회"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # 테이블별 레코드 수
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall() if not row[0].startswith('sqlite_')]
            
            stats = {}
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                stats[table] = count
            
            conn.close()
            return stats
            
        except Exception as e:
            print(f"❌ 통계 조회 실패: {e}")
            return {}


def main():
    parser = argparse.ArgumentParser(
        description='데이터베이스 백업 스크립트 (WAL 모드 지원)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예제:
  # 기본 백업 (체크포인트 포함)
  python backup_database.py
  
  # 체크포인트 없이 백업 (앱 실행 중)
  python backup_database.py --skip-checkpoint
  
  # 오래된 백업 정리 (14일, 최소 10개 유지)
  python backup_database.py --cleanup --keep-days 14 --keep-count 10
  
  # 통계만 조회
  python backup_database.py --stats-only
        """
    )
    
    parser.add_argument(
        '--db-path',
        default='instance/gym_system.db',
        help='백업할 DB 파일 경로 (기본: instance/gym_system.db)'
    )
    
    parser.add_argument(
        '--backup-dir',
        default='data/backups/database',
        help='백업 저장 디렉토리 (기본: data/backups/database)'
    )
    
    parser.add_argument(
        '--skip-checkpoint',
        action='store_true',
        help='체크포인트 건너뛰기 (앱 실행 중일 때 사용)'
    )
    
    parser.add_argument(
        '--cleanup',
        action='store_true',
        help='오래된 백업 정리'
    )
    
    parser.add_argument(
        '--keep-days',
        type=int,
        default=7,
        help='백업 유지 기간 (일) (기본: 7)'
    )
    
    parser.add_argument(
        '--keep-count',
        type=int,
        default=5,
        help='최소 유지할 백업 개수 (기본: 5)'
    )
    
    parser.add_argument(
        '--stats-only',
        action='store_true',
        help='통계만 조회하고 백업하지 않음'
    )
    
    args = parser.parse_args()
    
    try:
        backup = DatabaseBackup(args.db_path, args.backup_dir)
        
        # 통계 조회
        if args.stats_only:
            print("📊 데이터베이스 통계")
            print("="*80)
            stats = backup.get_database_stats()
            for table, count in stats.items():
                print(f"  {table:25} : {count:,}건")
            return 0
        
        # 백업 수행
        result = backup.backup_database(skip_checkpoint=args.skip_checkpoint)
        
        if result:
            # 통계 출력
            print()
            print("📊 백업된 데이터 통계:")
            stats = backup.get_database_stats()
            for table, count in stats.items():
                print(f"  {table:25} : {count:,}건")
            
            # 정리 수행
            if args.cleanup:
                backup.cleanup_old_backups(
                    keep_days=args.keep_days,
                    keep_count=args.keep_count
                )
            
            return 0
        else:
            return 1
            
    except Exception as e:
        print(f"❌ 에러: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

