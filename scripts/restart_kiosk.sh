#!/bin/bash
# 락카키 대여기 키오스크 재시작 (캐시 초기화 포함)

echo "🔄 락카키 대여기 키오스크 재시작"
echo "==============================="

# 기존 키오스크 종료
/home/pi/gym-controller/scripts/stop_kiosk.sh

# 잠깐 대기
sleep 2

# 브라우저 캐시 삭제
echo "🧹 브라우저 캐시 삭제 중..."
rm -rf ~/.cache/chromium/Default/Cache/* 2>/dev/null
rm -rf ~/.config/chromium/Default/Cache/* 2>/dev/null

# 폰트 캐시 새로고침
echo "🔤 폰트 캐시 새로고침..."
fc-cache -fv 2>/dev/null

# 키오스크 다시 시작
echo "🚀 키오스크 재시작..."
/home/pi/gym-controller/scripts/start_kiosk.sh
