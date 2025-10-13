#!/bin/bash
# 맥미니에서 라즈베리파이로 완전 동기화 (데이터베이스 포함)

set -e  # 오류 발생 시 스크립트 중단

# 설정
LOCAL_DIR="./"
REMOTE_HOST="raspberry-pi"
REMOTE_DIR="/home/pi/gym-controller"
BACKUP_DIR="/home/pi/gym-controller-backup-$(date +%Y%m%d_%H%M%S)"

echo "🚀 라즈베리파이 완전 동기화 시작"
echo "=" * 60

# 1. 라즈베리파이 연결 확인
echo "🔌 라즈베리파이 연결 확인 중..."
if ! ssh -o ConnectTimeout=5 $REMOTE_HOST "echo 'Connection OK'" > /dev/null 2>&1; then
    echo "❌ 라즈베리파이에 연결할 수 없습니다."
    echo "   다음을 확인하세요:"
    echo "   1. 라즈베리파이가 켜져 있는지"
    echo "   2. 네트워크 연결 상태"
    echo "   3. SSH 키 설정"
    exit 1
fi
echo "✅ 라즈베리파이 연결 성공"

# 2. 기존 디렉토리 백업
echo "📦 기존 디렉토리 백업 중..."
ssh $REMOTE_HOST "
    if [ -d '$REMOTE_DIR' ]; then
        echo '기존 디렉토리를 백업합니다: $BACKUP_DIR'
        cp -r '$REMOTE_DIR' '$BACKUP_DIR'
        echo '✅ 백업 완료: $BACKUP_DIR'
    else
        echo '기존 디렉토리가 없습니다. 새로 생성합니다.'
    fi
    mkdir -p '$REMOTE_DIR'
"

# 3. 현재 상태 정보 수집
echo "📊 현재 시스템 상태 수집 중..."
echo "로컬 시스템 정보:"
echo "  - 회원 수: $(sqlite3 instance/gym_system.db 'SELECT COUNT(*) FROM members')"
echo "  - 락커 수: $(sqlite3 instance/gym_system.db 'SELECT COUNT(*) FROM locker_status')"
echo "  - 데이터베이스 크기: $(ls -lh instance/gym_system.db | awk '{print $5}')"

# 4. 코드 동기화 (데이터베이스 제외)
echo "📂 코드 파일 동기화 중..."
rsync -avz --progress \
    --exclude 'venv/' \
    --exclude '__pycache__/' \
    --exclude '.git/' \
    --exclude '*.pyc' \
    --exclude '.DS_Store' \
    --exclude 'instance/gym_system.db*' \
    --exclude '*.log' \
    $LOCAL_DIR $REMOTE_HOST:$REMOTE_DIR/

echo "✅ 코드 동기화 완료"

# 5. 데이터베이스 동기화
echo "🗄️ 데이터베이스 동기화 중..."

# 라즈베리파이의 기존 데이터베이스 백업
ssh $REMOTE_HOST "
    if [ -f '$REMOTE_DIR/instance/gym_system.db' ]; then
        echo '기존 데이터베이스 백업 중...'
        cp '$REMOTE_DIR/instance/gym_system.db' '$REMOTE_DIR/instance/gym_system.db.backup.$(date +%Y%m%d_%H%M%S)'
    fi
    mkdir -p '$REMOTE_DIR/instance'
"

# 현재 데이터베이스 복사
echo "현재 데이터베이스를 라즈베리파이로 복사 중..."
scp instance/gym_system.db $REMOTE_HOST:$REMOTE_DIR/instance/

echo "✅ 데이터베이스 동기화 완료"

# 6. 권한 설정
echo "🔧 파일 권한 설정 중..."
ssh $REMOTE_HOST "
    cd '$REMOTE_DIR'
    
    # 실행 권한 설정
    chmod +x run.py
    chmod +x scripts/setup/*.py
    chmod +x scripts/data/*.py
    chmod +x scripts/deployment/*.sh
    chmod +x scripts/maintenance/*.sh
    chmod +x scripts/testing/*.py
    
    # 데이터베이스 권한 설정
    chmod 664 instance/gym_system.db
    
    echo '✅ 권한 설정 완료'
"

# 7. Python 환경 확인 및 의존성 설치
echo "🐍 Python 환경 확인 중..."
ssh $REMOTE_HOST "
    cd '$REMOTE_DIR'
    
    echo 'Python 버전:'
    python3 --version
    
    echo '의존성 설치 중...'
    pip3 install -r requirements.txt --user
    
    echo '✅ Python 환경 준비 완료'
"

# 8. 라즈베리파이에서 시스템 테스트
echo "🧪 라즈베리파이에서 시스템 테스트 중..."
ssh $REMOTE_HOST "
    cd '$REMOTE_DIR'
    
    echo '데이터베이스 연결 테스트:'
    python3 -c \"
import sqlite3
try:
    conn = sqlite3.connect('instance/gym_system.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM members')
    member_count = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM locker_status')
    locker_count = cursor.fetchone()[0]
    print(f'✅ 회원 수: {member_count}명')
    print(f'✅ 락커 수: {locker_count}개')
    conn.close()
    print('✅ 데이터베이스 테스트 성공')
except Exception as e:
    print(f'❌ 데이터베이스 오류: {e}')
\"

    echo '모듈 임포트 테스트:'
    PYTHONPATH=. python3 -c \"
try:
    from app.services.member_service import MemberService
    from app.services.locker_service import LockerService
    print('✅ 핵심 모듈 임포트 성공')
except Exception as e:
    print(f'❌ 모듈 임포트 오류: {e}')
\"
"

# 9. 키오스크 서비스 설정 (선택사항)
echo "🖥️ 키오스크 서비스 설정 확인..."
ssh $REMOTE_HOST "
    cd '$REMOTE_DIR'
    
    if [ -f 'scripts/deployment/start_kiosk.sh' ]; then
        echo '✅ 키오스크 스크립트 존재'
        echo '키오스크 시작: ./scripts/deployment/start_kiosk.sh'
        echo '키오스크 종료: ./scripts/deployment/stop_kiosk.sh'
    else
        echo '⚠️ 키오스크 스크립트를 찾을 수 없습니다'
    fi
"

# 10. 동기화 완료 보고
echo ""
echo "🎉 라즈베리파이 동기화 완료!"
echo "=" * 60
echo "📊 동기화 결과:"
echo "  ✅ 코드 파일: 완전 동기화"
echo "  ✅ 데이터베이스: 완전 복사 ($(sqlite3 instance/gym_system.db 'SELECT COUNT(*) FROM members')명 회원 데이터 포함)"
echo "  ✅ 프로젝트 구조: 새로운 구조 적용"
echo "  ✅ 권한 설정: 완료"
echo "  ✅ Python 환경: 준비 완료"
echo ""
echo "🚀 라즈베리파이에서 시스템 실행:"
echo "  ssh raspberry-pi"
echo "  cd $REMOTE_DIR"
echo "  python3 run.py"
echo ""
echo "🖥️ 키오스크 모드 실행:"
echo "  ssh raspberry-pi"
echo "  cd $REMOTE_DIR"
echo "  ./scripts/deployment/start_kiosk.sh"
echo ""
echo "📦 백업 위치: $BACKUP_DIR"
echo "=" * 60
