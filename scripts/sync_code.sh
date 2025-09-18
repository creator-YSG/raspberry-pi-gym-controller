#!/bin/bash
# 로컬 코드를 라즈베리파이로 동기화

LOCAL_DIR="./"
REMOTE_DIR="/home/pi/gym-controller"

echo "📦 코드 동기화 중..."
echo "로컬: $LOCAL_DIR"
echo "원격: raspberry-pi:$REMOTE_DIR"

# 원격 디렉토리 생성
ssh raspberry-pi "mkdir -p $REMOTE_DIR"

rsync -avz --progress --exclude 'venv' --exclude '__pycache__' --exclude '.git' \
    $LOCAL_DIR raspberry-pi:$REMOTE_DIR/

echo "✅ 동기화 완료!"
