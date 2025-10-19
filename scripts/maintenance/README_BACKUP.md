# 🗄️ 데이터베이스 백업 및 동기화 가이드

## 개요

SQLite WAL (Write-Ahead Logging) 모드를 완벽하게 지원하는 백업 및 동기화 스크립트입니다.

---

## 📋 스크립트 목록

### 1. `backup_database.py`
로컬 데이터베이스를 안전하게 백업합니다.

**주요 기능:**
- ✅ WAL 체크포인트 실행 (최신 데이터 병합)
- ✅ .db, .db-wal, .db-shm 파일 모두 백업
- ✅ MD5 체크섬 검증
- ✅ DB 무결성 검증
- ✅ 오래된 백업 자동 정리
- ✅ 백업 통계 조회

### 2. `sync_db_from_pi.py`
라즈베리파이에서 데이터베이스를 동기화합니다.

**주요 기능:**
- ✅ SCP 파일 복사 (빠름)
- ✅ Python 쿼리 동기화 (안전, WAL 자동 처리)
- ✅ 원격 DB 정보 조회
- ✅ 동기화 검증

---

## 🚀 사용법

### 로컬 백업

#### 기본 백업 (체크포인트 포함)
```bash
python3 scripts/maintenance/backup_database.py
```

#### Flask 앱 실행 중 백업 (체크포인트 건너뛰기)
```bash
python3 scripts/maintenance/backup_database.py --skip-checkpoint
```

#### 백업 + 오래된 파일 정리
```bash
python3 scripts/maintenance/backup_database.py --cleanup --keep-days 14 --keep-count 10
```

#### 통계만 조회 (백업 안함)
```bash
python3 scripts/maintenance/backup_database.py --stats-only
```

#### 도움말
```bash
python3 scripts/maintenance/backup_database.py --help
```

---

### 라즈베리파이 동기화

#### 방법 1: Python 쿼리 (권장, 안전)
```bash
python3 scripts/maintenance/sync_db_from_pi.py --method query
```

**장점:**
- WAL 파일 자동 처리
- Flask 앱 실행 중에도 안전
- 데이터 무결성 보장

**단점:**
- 느림 (큰 DB는 시간 소요)

#### 방법 2: SCP 파일 복사 (빠름)
```bash
python3 scripts/maintenance/sync_db_from_pi.py --method scp
```

**장점:**
- 매우 빠름
- 완전한 파일 복사

**단점:**
- Flask 앱 실행 중이면 최신 데이터 누락 가능

#### 라즈베리파이 정보만 조회
```bash
python3 scripts/maintenance/sync_db_from_pi.py --info-only
```

#### 도움말
```bash
python3 scripts/maintenance/sync_db_from_pi.py --help
```

---

## 📊 WAL 모드란?

### Write-Ahead Logging (WAL)

SQLite의 고성능 저널링 모드입니다.

**동작 방식:**
```
변경사항 발생
    ↓
.db-wal 파일에 먼저 기록 (빠름!)
    ↓
1000 페이지마다 자동 체크포인트
    ↓
.db 파일로 병합
```

**장점:**
- ⚡ 쓰기 성능 30~50% 향상
- 🔄 읽기/쓰기 동시 처리 가능
- 🛡️ 안정성 향상

**주의사항:**
- Flask 앱 실행 중에는 .db 파일에 최신 데이터가 없을 수 있음
- 백업시 .db-wal 파일도 함께 백업해야 함

---

## 🔧 자동화 설정

### Cron으로 정기 백업 (라즈베리파이)

```bash
# crontab 편집
crontab -e

# 매일 새벽 3시 백업 + 정리 (7일 이상 오래된 백업 삭제)
0 3 * * * cd /home/pi/gym-controller && python3 scripts/maintenance/backup_database.py --cleanup --keep-days 7 >> logs/backup.log 2>&1
```

### 맥미니에서 자동 동기화

```bash
# crontab 편집
crontab -e

# 매일 오전 9시 라즈베리파이에서 동기화
0 9 * * * cd /Users/yunseong-geun/Projects/raspberry-pi-gym-controller && python3 scripts/maintenance/sync_db_from_pi.py --method query >> logs/sync.log 2>&1
```

---

## 📂 백업 파일 구조

```
data/backups/database/
├── gym_system_backup_20251019_155538.db       # 메인 DB
├── gym_system_backup_20251019_155538.db-wal   # WAL 파일 (있는 경우)
├── gym_system_backup_20251019_155538.db-shm   # 공유 메모리 (있는 경우)
├── gym_system_backup_20251019_120000.db
└── ...
```

**파일명 형식:**
```
gym_system_backup_YYYYMMDD_HHMMSS.db
```

---

## 🔍 백업 검증

### 백업 파일 무결성 확인
```python
python3 << 'EOF'
import sqlite3

conn = sqlite3.connect('data/backups/database/gym_system_backup_20251019_155538.db')
cursor = conn.cursor()

# 무결성 검증
cursor.execute('PRAGMA integrity_check;')
result = cursor.fetchone()[0]

if result == 'ok':
    print('✅ DB 무결성 정상')
else:
    print(f'❌ DB 손상: {result}')

# 테이블 수 확인
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print(f'테이블 수: {len(tables)}개')

for table_name, in tables:
    if not table_name.startswith('sqlite_'):
        cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
        count = cursor.fetchone()[0]
        print(f'  {table_name}: {count}건')

conn.close()
EOF
```

---

## 🚨 트러블슈팅

### 문제 1: "database is locked" 에러

**원인:** Flask 앱이 DB를 사용 중

**해결:**
```bash
# 체크포인트 건너뛰기
python3 scripts/maintenance/backup_database.py --skip-checkpoint
```

### 문제 2: 최신 데이터가 백업에 없음

**원인:** WAL 파일에만 존재

**해결 방법 1:** 체크포인트 실행
```bash
python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('instance/gym_system.db')
conn.execute('PRAGMA wal_checkpoint(TRUNCATE);')
conn.close()
EOF
```

**해결 방법 2:** WAL 파일도 함께 복사
```bash
# 모든 관련 파일 복사
cp instance/gym_system.db* data/backups/database/
```

### 문제 3: SCP 동기화 후 데이터 누락

**원인:** Flask 앱 실행 중, WAL 파일 복사 실패

**해결:**
```bash
# Python 쿼리 방식으로 변경 (권장)
python3 scripts/maintenance/sync_db_from_pi.py --method query
```

### 문제 4: SSH 연결 실패

**원인:** 라즈베리파이 연결 문제

**확인:**
```bash
# 연결 테스트
ssh raspberry-pi "echo 'OK'"

# ~/.ssh/config 확인
cat ~/.ssh/config | grep -A 5 raspberry-pi
```

---

## 📈 성능 비교

### 백업 시간 (344명 회원, 21건 대여 기록 기준)

| 방법 | 시간 | 장점 | 단점 |
|------|------|------|------|
| 로컬 백업 (체크포인트 포함) | ~0.5초 | 완전한 백업 | 앱 실행 중 느림 |
| 로컬 백업 (체크포인트 제외) | ~0.1초 | 매우 빠름 | WAL 파일 별도 처리 필요 |
| Pi 동기화 (query) | ~3초 | 안전, WAL 자동처리 | 느림 |
| Pi 동기화 (scp) | ~0.5초 | 매우 빠름 | 앱 실행 중 데이터 누락 가능 |

---

## 💡 권장 사항

### 일일 운영

**라즈베리파이 (운영 서버):**
```bash
# 매일 새벽 3시 자동 백업
0 3 * * * cd /home/pi/gym-controller && python3 scripts/maintenance/backup_database.py --cleanup --keep-days 7
```

**맥미니 (개발/분석):**
```bash
# 필요시 수동 동기화 (권장)
python3 scripts/maintenance/sync_db_from_pi.py --method query

# 또는 매일 자동 동기화
0 9 * * * cd ~/Projects/raspberry-pi-gym-controller && python3 scripts/maintenance/sync_db_from_pi.py --method query
```

### 긴급 백업

**시스템 업데이트 전:**
```bash
# 1. 라즈베리파이에서 백업
ssh raspberry-pi "cd /home/pi/gym-controller && python3 scripts/maintenance/backup_database.py"

# 2. 맥미니로 동기화
python3 scripts/maintenance/sync_db_from_pi.py --method query

# 3. 로컬 백업
python3 scripts/maintenance/backup_database.py
```

---

## 📝 체크리스트

### 백업 전
- [ ] Flask 앱 실행 여부 확인
- [ ] 디스크 용량 충분한지 확인
- [ ] 백업 디렉토리 존재 확인

### 백업 후
- [ ] 백업 파일 크기 확인
- [ ] 무결성 검증 성공 확인
- [ ] 통계 데이터 확인

### 동기화 전
- [ ] 라즈베리파이 연결 확인
- [ ] 로컬 DB 백업 (덮어쓰기 방지)
- [ ] 동기화 방법 선택 (query/scp)

### 동기화 후
- [ ] 테이블 수 일치 확인
- [ ] 레코드 수 일치 확인
- [ ] 최신 데이터 존재 확인

---

## 🆘 도움말

### 추가 옵션 보기
```bash
python3 scripts/maintenance/backup_database.py --help
python3 scripts/maintenance/sync_db_from_pi.py --help
```

### 로그 확인
```bash
# 백업 로그
tail -f logs/backup.log

# 동기화 로그
tail -f logs/sync.log
```

---

**작성일:** 2025-10-19  
**버전:** 1.0  
**작성자:** AI Assistant

