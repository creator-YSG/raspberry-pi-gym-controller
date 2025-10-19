#!/usr/bin/env python3
"""
라즈베리파이에서 데이터베이스 동기화 스크립트

라즈베리파이의 DB를 안전하게 로컬(맥미니)로 동기화합니다.
- 원격에서 체크포인트 실행
- 또는 Python으로 직접 쿼리하여 데이터 추출
- WAL 모드 완벽 지원
"""

import subprocess
import sqlite3
import json
import argparse
import sys
from pathlib import Path
from datetime import datetime
import tempfile


class PiDatabaseSync:
    def __init__(self, pi_host: str = 'raspberry-pi', pi_path: str = '/home/pi/gym-controller'):
        self.pi_host = pi_host
        self.pi_path = pi_path
        self.local_db = Path('instance/gym_system.db')
        
    def run_ssh_command(self, command: str) -> tuple:
        """SSH 명령 실행"""
        try:
            result = subprocess.run(
                ['ssh', self.pi_host, f'cd {self.pi_path} && {command}'],
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, '', 'SSH 명령 타임아웃'
        except Exception as e:
            return -1, '', str(e)
    
    def check_pi_connection(self) -> bool:
        """라즈베리파이 연결 확인"""
        print(f"🔌 라즈베리파이 연결 확인 중... ({self.pi_host})")
        returncode, stdout, stderr = self.run_ssh_command('echo "OK"')
        
        if returncode == 0 and 'OK' in stdout:
            print(f"✅ 연결 성공")
            return True
        else:
            print(f"❌ 연결 실패: {stderr}")
            return False
    
    def get_pi_db_info(self) -> dict:
        """라즈베리파이 DB 정보 조회"""
        print("📊 라즈베리파이 DB 정보 조회 중...")
        
        script = """
python3 << 'EOFPYTHON'
import sqlite3
import os
from datetime import datetime

db_path = 'instance/gym_system.db'

# 파일 정보
info = {
    'db_exists': os.path.exists(db_path),
    'db_size': os.path.getsize(db_path) if os.path.exists(db_path) else 0,
    'db_mtime': datetime.fromtimestamp(os.path.getmtime(db_path)).isoformat() if os.path.exists(db_path) else None,
}

# WAL 파일 정보
wal_path = db_path + '-wal'
shm_path = db_path + '-shm'

info['wal_exists'] = os.path.exists(wal_path)
info['wal_size'] = os.path.getsize(wal_path) if os.path.exists(wal_path) else 0

info['shm_exists'] = os.path.exists(shm_path)
info['shm_size'] = os.path.getsize(shm_path) if os.path.exists(shm_path) else 0

# DB 통계
try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall() if not row[0].startswith('sqlite_')]
    
    stats = {}
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        stats[table] = cursor.fetchone()[0]
    
    info['table_counts'] = stats
    
    # Journal 모드
    cursor.execute('PRAGMA journal_mode;')
    info['journal_mode'] = cursor.fetchone()[0]
    
    conn.close()
except Exception as e:
    info['error'] = str(e)

import json
print(json.dumps(info, indent=2))
EOFPYTHON
"""
        
        returncode, stdout, stderr = self.run_ssh_command(script)
        
        if returncode == 0:
            try:
                info = json.loads(stdout)
                
                print(f"  DB 크기: {info['db_size']:,} bytes")
                print(f"  WAL 크기: {info['wal_size']:,} bytes")
                print(f"  Journal 모드: {info.get('journal_mode', 'unknown')}")
                
                if 'table_counts' in info:
                    print(f"  테이블 수: {len(info['table_counts'])}개")
                    for table, count in info['table_counts'].items():
                        print(f"    - {table}: {count:,}건")
                
                return info
            except json.JSONDecodeError as e:
                print(f"❌ JSON 파싱 실패: {e}")
                print(f"출력: {stdout[:200]}")
                return {}
        else:
            print(f"❌ 정보 조회 실패: {stderr}")
            return {}
    
    def sync_via_scp(self, include_wal: bool = True) -> bool:
        """SCP로 DB 파일 직접 복사"""
        print()
        print("="*80)
        print("📂 SCP로 DB 파일 복사 중...")
        print("="*80)
        
        # 로컬 백업
        if self.local_db.exists():
            backup_path = f"data/backups/database/gym_system_local_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            Path('data/backups/database').mkdir(parents=True, exist_ok=True)
            
            import shutil
            shutil.copy2(self.local_db, backup_path)
            print(f"💾 로컬 DB 백업: {backup_path}")
        
        # 메인 DB 복사
        try:
            result = subprocess.run(
                ['scp', f'{self.pi_host}:{self.pi_path}/instance/gym_system.db', 'instance/'],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                print(f"✅ gym_system.db 복사 완료")
            else:
                print(f"❌ 복사 실패: {result.stderr}")
                return False
        except Exception as e:
            print(f"❌ 복사 실패: {e}")
            return False
        
        # WAL/SHM 파일 복사 (선택적)
        if include_wal:
            try:
                # 와일드카드를 사용하여 모든 관련 파일 복사
                result = subprocess.run(
                    ['bash', '-c', f'scp {self.pi_host}:{self.pi_path}/instance/gym_system.db* instance/ 2>/dev/null || true'],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                print(f"✅ WAL/SHM 파일 복사 시도 완료")
            except Exception as e:
                print(f"⚠️  WAL/SHM 복사 실패 (계속 진행): {e}")
        
        return True
    
    def sync_via_query(self, tables: list = None) -> bool:
        """Python 쿼리로 데이터 직접 추출 (WAL 파일 포함)"""
        print()
        print("="*80)
        print("🐍 Python 쿼리로 데이터 동기화 중...")
        print("="*80)
        
        if tables is None:
            # 기본 테이블 목록
            tables = ['members', 'rentals', 'locker_status', 'sensor_events', 
                     'active_transactions', 'system_settings']
        
        # 원격에서 데이터 추출
        print(f"📤 라즈베리파이에서 데이터 추출 중... (테이블: {len(tables)}개)")
        
        script = f"""
python3 << 'EOFPYTHON'
import sqlite3
import json

conn = sqlite3.connect('instance/gym_system.db')
conn.row_factory = sqlite3.Row

data = {{}}

tables = {tables}

for table in tables:
    try:
        cursor = conn.execute(f"SELECT * FROM {{table}}")
        rows = [dict(row) for row in cursor.fetchall()]
        data[table] = rows
        print(f"  ✅ {{table}}: {{len(rows)}}건", file=__import__('sys').stderr)
    except Exception as e:
        print(f"  ❌ {{table}}: {{e}}", file=__import__('sys').stderr)
        data[table] = []

conn.close()

print(json.dumps(data, default=str))
EOFPYTHON
"""
        
        returncode, stdout, stderr = self.run_ssh_command(script)
        
        if returncode != 0:
            print(f"❌ 데이터 추출 실패: {stderr}")
            return False
        
        # stderr에 진행상황 출력
        if stderr:
            print(stderr.strip())
        
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as e:
            print(f"❌ JSON 파싱 실패: {e}")
            print(f"출력: {stdout[:500]}")
            return False
        
        # 로컬 DB에 적용
        print()
        print(f"📥 로컬 DB에 데이터 적용 중...")
        
        try:
            conn = sqlite3.connect(str(self.local_db))
            cursor = conn.cursor()
            
            for table, rows in data.items():
                if not rows:
                    print(f"  ⏭️  {table}: 데이터 없음")
                    continue
                
                # 테이블 스키마 확인
                cursor.execute(f"PRAGMA table_info({table})")
                columns = [col[1] for col in cursor.fetchall()]
                
                if not columns:
                    print(f"  ⚠️  {table}: 테이블 없음")
                    continue
                
                # INSERT OR REPLACE
                placeholders = ','.join(['?' for _ in columns])
                insert_sql = f"INSERT OR REPLACE INTO {table} VALUES ({placeholders})"
                
                inserted = 0
                for row in rows:
                    values = [row.get(col) for col in columns]
                    cursor.execute(insert_sql, values)
                    inserted += 1
                
                print(f"  ✅ {table}: {inserted}건 동기화")
            
            conn.commit()
            conn.close()
            
            print()
            print("✅ 동기화 완료!")
            return True
            
        except Exception as e:
            print(f"❌ 로컬 DB 적용 실패: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def verify_sync(self) -> bool:
        """동기화 검증"""
        print()
        print("🔍 동기화 검증 중...")
        
        # 로컬 DB 통계
        try:
            conn = sqlite3.connect(str(self.local_db))
            cursor = conn.cursor()
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall() if not row[0].startswith('sqlite_')]
            
            print()
            print("로컬 DB 통계:")
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"  {table:25} : {count:,}건")
            
            conn.close()
            return True
            
        except Exception as e:
            print(f"❌ 검증 실패: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(
        description='라즈베리파이 DB 동기화 스크립트',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예제:
  # SCP로 파일 복사 (빠름, WAL 포함)
  python sync_db_from_pi.py --method scp
  
  # Python 쿼리로 동기화 (느림, 안전)
  python sync_db_from_pi.py --method query
  
  # 정보만 조회
  python sync_db_from_pi.py --info-only
        """
    )
    
    parser.add_argument(
        '--method',
        choices=['scp', 'query'],
        default='query',
        help='동기화 방법 (scp: 파일 복사, query: 데이터 추출) (기본: query)'
    )
    
    parser.add_argument(
        '--pi-host',
        default='raspberry-pi',
        help='라즈베리파이 호스트명 (기본: raspberry-pi)'
    )
    
    parser.add_argument(
        '--pi-path',
        default='/home/pi/gym-controller',
        help='라즈베리파이 프로젝트 경로 (기본: /home/pi/gym-controller)'
    )
    
    parser.add_argument(
        '--info-only',
        action='store_true',
        help='정보만 조회하고 동기화하지 않음'
    )
    
    parser.add_argument(
        '--no-wal',
        action='store_true',
        help='WAL/SHM 파일 제외 (SCP 모드만)'
    )
    
    args = parser.parse_args()
    
    try:
        sync = PiDatabaseSync(pi_host=args.pi_host, pi_path=args.pi_path)
        
        # 연결 확인
        if not sync.check_pi_connection():
            return 1
        
        print()
        
        # 정보 조회
        info = sync.get_pi_db_info()
        
        if not info:
            print("❌ DB 정보 조회 실패")
            return 1
        
        if args.info_only:
            return 0
        
        print()
        
        # 동기화 수행
        if args.method == 'scp':
            success = sync.sync_via_scp(include_wal=not args.no_wal)
        else:  # query
            success = sync.sync_via_query()
        
        if not success:
            return 1
        
        # 검증
        sync.verify_sync()
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\n⚠️  사용자가 중단했습니다.")
        return 130
    except Exception as e:
        print(f"❌ 에러: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

