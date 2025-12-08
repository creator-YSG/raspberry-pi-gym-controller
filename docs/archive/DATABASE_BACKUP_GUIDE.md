# 🗄️ 데이터베이스 백업 가이드

> **중요**: SQLite WAL 모드를 사용하므로 일반 파일 복사로는 최신 데이터가 누락될 수 있습니다!

---

## ⚠️ WAL 모드 주의사항

현재 시스템은 SQLite **WAL (Write-Ahead Logging)** 모드를 사용합니다.

### WAL 파일 구조
\`\`\`
instance/
├── gym_system.db       # 메인 DB (안정된 데이터)
├── gym_system.db-wal   # WAL 파일 (최신 변경사항!)
└── gym_system.db-shm   # 공유 메모리 (동시성 관리)
\`\`\`

### 문제 상황
\`\`\`bash
# ❌ 잘못된 방법: .db 파일만 복사
cp gym_system.db backup.db
# → 최신 데이터 누락! WAL 파일에만 있는 데이터 손실!

# ❌ 잘못된 방법: 원격에서 .db만 복사
scp raspberry-pi:gym_system.db .
# → Flask 앱 실행 중이면 최신 데이터 누락!
\`\`\`

---

## ✅ 올바른 백업 방법

### 방법 1: 백업 스크립트 사용 (권장)

\`\`\`bash
# 로컬 백업
python3 scripts/maintenance/backup_database.py --skip-checkpoint

# 라즈베리파이에서 동기화
python3 scripts/maintenance/sync_db_from_pi.py --method query
\`\`\`

**장점:**
- ✅ WAL 파일 자동 처리
- ✅ 체크포인트 실행 (선택적)
- ✅ 무결성 검증
- ✅ MD5 체크섬 확인

### 방법 2: 모든 파일 복사

\`\`\`bash
# 로컬
cp instance/gym_system.db* data/backups/database/

# 원격
scp 'raspberry-pi:/home/pi/gym-controller/instance/gym_system.db*' instance/
\`\`\`

**주의:** Flask 앱 실행 중에는 .db-wal 파일이 0 bytes로 복사될 수 있음

### 방법 3: 체크포인트 후 복사

\`\`\`bash
# 1. Flask 앱 정지
ssh raspberry-pi "pkill -f run.py"

# 2. 체크포인트 실행 (WAL → DB 병합)
ssh raspberry-pi "cd /home/pi/gym-controller && python3 -c 'import sqlite3; conn=sqlite3.connect(\"instance/gym_system.db\"); conn.execute(\"PRAGMA wal_checkpoint(TRUNCATE)\"); conn.close()'"

# 3. 복사
scp raspberry-pi:/home/pi/gym-controller/instance/gym_system.db instance/

# 4. Flask 앱 재시작
ssh raspberry-pi "cd /home/pi/gym-controller && nohup python3 run.py > logs/flask.log 2>&1 &"
\`\`\`

---

## 📋 빠른 명령어

\`\`\`bash
# 통계 조회
python3 scripts/maintenance/backup_database.py --stats-only

# 백업 (체크포인트 제외, 빠름)
python3 scripts/maintenance/backup_database.py --skip-checkpoint

# 백업 + 오래된 파일 정리
python3 scripts/maintenance/backup_database.py --cleanup --keep-days 7

# 라즈베리파이 정보 조회
python3 scripts/maintenance/sync_db_from_pi.py --info-only

# 라즈베리파이 동기화 (안전)
python3 scripts/maintenance/sync_db_from_pi.py --method query

# 라즈베리파이 동기화 (빠름)
python3 scripts/maintenance/sync_db_from_pi.py --method scp
\`\`\`

---

## 🔧 자동 백업 설정

### 라즈베리파이 (Cron)

\`\`\`bash
crontab -e

# 매일 새벽 3시 백업 + 7일 이상 오래된 백업 삭제
0 3 * * * cd /home/pi/gym-controller && python3 scripts/maintenance/backup_database.py --cleanup --keep-days 7 >> logs/backup.log 2>&1
\`\`\`

### 맥미니 (Cron)

\`\`\`bash
crontab -e

# 매일 오전 9시 라즈베리파이에서 동기화
0 9 * * * cd ~/Projects/raspberry-pi-gym-controller && python3 scripts/maintenance/sync_db_from_pi.py --method query >> logs/sync.log 2>&1
\`\`\`

---

## 📚 추가 문서

상세한 내용은 [scripts/maintenance/README_BACKUP.md](../../scripts/maintenance/README_BACKUP.md) 참조

---

**작성일:** 2025-10-19  
**버전:** 1.0
