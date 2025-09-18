# 라즈베리파이 헬스장 통합 제어 시스템

## 프로젝트 개요
기존 ESP32 바코드 스캐너 + 모터 제어를 라즈베리파이로 통합하여 터치스크린까지 포함한 시스템

## 라즈베리파이 정보
- **IP**: 192.168.0.23
- **계정**: pi / raspberry
- **용도**: 바코드 스캐너 + 모터 제어 + 터치스크린 GUI

## 폴더 구조
```
raspberry-pi-gym-controller/
├── hardware/          # 하드웨어 제어 모듈
├── gui/              # 터치스크린 GUI
├── config/           # 설정 파일들
├── scripts/          # SSH 연결, 동기화 스크립트
├── tests/            # 테스트 파일
├── requirements.txt  # Python 의존성
└── main.py          # 메인 실행 파일
```

## 개발 환경
- 로컬에서 개발 후 라즈베리파이로 동기화
- SSH 원격 개발 지원
- 기존 gym-entry-locker-system 참조