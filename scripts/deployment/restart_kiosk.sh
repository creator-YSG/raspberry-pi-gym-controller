#!/bin/bash

# 락카키 대여기 키오스크 완전 재시작 스크립트
# 용도: Flask 서버와 Chromium 키오스크를 안정적으로 재시작

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_FILE="$PROJECT_ROOT/logs/restart_kiosk.log"

cd "$PROJECT_ROOT" || exit 1

echo "========================================"
echo "🔄 락카키 대여기 완전 재시작"
echo "시작 시간: $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"

# 로그 기록 함수
log() {
    echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "1️⃣ 기존 프로세스 종료 중..."

# Flask 서버 종료
pkill -9 -f "run.py" 2>/dev/null
log "   - Flask 서버 종료"

# Chromium 브라우저 종료
pkill -9 chromium 2>/dev/null
log "   - Chromium 브라우저 종료"

# 포트 정리
fuser -k 5000/tcp 2>/dev/null
log "   - 5000 포트 정리"

log "⏳ 프로세스 완전 종료 대기 (3초)..."
sleep 3

# 종료 확인
if pgrep -f "run.py" > /dev/null || pgrep chromium > /dev/null; then
    log "⚠️  프로세스가 남아있음, 재시도..."
    pkill -9 -f "run.py" chromium
    sleep 2
fi

log "✅ 모든 프로세스 종료 완료"
log ""
log "2️⃣ Flask 서버 시작 중..."

# Flask 서버 시작
nohup python3 run.py --host 0.0.0.0 --port 5000 > "$PROJECT_ROOT/logs/flask.log" 2>&1 &
FLASK_PID=$!
log "   - Flask 서버 PID: $FLASK_PID"

log "⏳ Flask 서버 준비 대기 (5초)..."
sleep 5

# Flask 서버 확인
if curl -s http://localhost:5000 > /dev/null 2>&1; then
    log "✅ Flask 서버 정상 시작 (http://localhost:5000)"
else
    log "⚠️  Flask 서버 응답 없음, 추가 대기..."
    sleep 3
    if curl -s http://localhost:5000 > /dev/null 2>&1; then
        log "✅ Flask 서버 응답 확인"
    else
        log "❌ Flask 서버 시작 실패!"
        exit 1
    fi
fi

log ""
log "3️⃣ Chromium 키오스크 시작 중..."

# 화면 보호기 비활성화
export DISPLAY=:0
xset s off 2>/dev/null
xset -dpms 2>/dev/null
xset s noblank 2>/dev/null
log "   - 화면 보호기 비활성화"

# Chromium 캐시 정리 (선택적)
# rm -rf ~/.config/chromium/Default/Cache/* 2>/dev/null

# Chromium 키오스크 모드 시작
DISPLAY=:0 chromium-browser \
    --kiosk \
    --no-sandbox \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --disable-restore-session-state \
    --disable-web-security \
    --disable-features=TranslateUI \
    --noerrdialogs \
    --start-fullscreen \
    --window-size=600,1024 \
    --app=http://localhost:5000 \
    > /dev/null 2>&1 &

CHROMIUM_PID=$!
log "   - Chromium 키오스크 PID: $CHROMIUM_PID"

log "⏳ Chromium 시작 대기 (3초)..."
sleep 3

# Chromium 프로세스 확인
if pgrep chromium > /dev/null; then
    log "✅ Chromium 키오스크 정상 시작"
else
    log "❌ Chromium 시작 실패!"
    exit 1
fi

log ""
log "========================================"
log "✅ 키오스크 재시작 완료!"
log "Flask 서버: http://localhost:5000 (PID: $FLASK_PID)"
log "Chromium: 키오스크 모드 실행 중 (PID: $CHROMIUM_PID)"
log "종료 시간: $(date '+%Y-%m-%d %H:%M:%S')"
log "========================================"

# 프로세스 상태 출력
echo ""
echo "📊 실행 중인 프로세스:"
pgrep -fa "run.py" | head -1
pgrep -fa "chromium" | head -1

exit 0
