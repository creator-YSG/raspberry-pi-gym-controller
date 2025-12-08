# 60개 락커 시스템 설정 완료

## 📊 시스템 구성

### 하드웨어
- **총 60개 락커** (10개 x 6줄)
- 교직원: 1줄 (10개)
- 남녀 혼성: 5줄 (50개)

### 락커 배치
```
교직원: S01~S10 (10개)  - ESP32 #1 (esp32_staff)
남성:   M01~M40 (40개)  - ESP32 #2 (esp32_male_female)  
여성:   F01~F10 (10개)  - ESP32 #2 (esp32_male_female)
─────────────────────────────────────────
총계:   60개
```

### ESP32 구성
- **ESP32 #1** (`/dev/ttyUSB1`): 교직원 구역 전용
- **ESP32 #2** (`/dev/ttyUSB2`): 남녀 구역 (문은 함께 열림, 데이터는 구분)

---

## 🗂️ 수정된 파일

### 1. 데이터베이스 스키마
**파일**: `database/schema.sql`

- 60개 락커로 재정의 (S01~S10, M01~M40, F01~F10)
- `device_id`를 `esp32_staff`, `esp32_male_female`로 매핑
- 모든 락커 사이즈 `medium`으로 통일

### 2. ESP32 포트 매핑
**파일**: `config/esp32_mapping.json`

```json
{
  "/dev/ttyUSB1": {
    "device_id": "esp32_male_female",
    "zones": ["MALE", "FEMALE"]
  },
  "/dev/ttyUSB2": {
    "device_id": "esp32_staff",
    "zones": ["STAFF"]
  }
}
```

### 3. 센서 매핑 설정
**파일**: `config/sensor_mapping.json`

- 센서 1-60번의 기본 순차 매핑 제공
- **주의**: 실제 물리적 연결은 규칙성이 없으므로 테스트 필요!

**기본 매핑 (임시):**
- 센서 1-10: S01~S10 (교직원)
- 센서 11-50: M01~M40 (남성)  
- 센서 51-60: F01~F10 (여성)

### 4. 센서 이벤트 핸들러
**파일**: `app/services/sensor_event_handler.py`

- `config/sensor_mapping.json`에서 매핑을 로드
- 파일이 없으면 기본 순차 매핑 사용

### 5. ESP32 매니저
**파일**: `core/esp32_manager.py`

- 설정 파일 기반 ESP32 구역 매핑
- 자동 감지 시 포트별로 구역 할당

### 6. 락커 서비스
**파일**: `app/services/locker_service.py`

- M/F 락커는 `esp32_male_female`로 매핑
- S 락커는 `esp32_staff`로 매핑

---

## 🔧 다음 할 일: 센서 매핑 테스트

센서 신호선이 규칙성 없이 연결되어 있으므로 **실제 테스트가 필수**입니다!

### 센서 매핑 테스트 방법

**1. 테스트 스크립트 실행**
```bash
ssh raspberry-pi
cd ~/gym-controller
python3 scripts/testing/test_sensor_mapping.py
```

**2. 모드 선택**
```
1. 센서 모니터링 (실시간 센서 이벤트 보기)
2. 대화형 매핑 편집
```

**3. 센서 모니터링 모드 사용법**
```
1) 락커에서 키를 빼세요
2) 터미널에 표시되는 센서 번호를 확인
3) 메모: "센서 15번 = M05번 락커"
4) 다음 락커로 진행
5) 60개 모두 테스트
```

**4. 매핑 편집 모드에서 입력**
```
명령> add 15 M05
명령> add 23 S03
...
명령> save
```

### 센서 매핑 파일 위치
```
config/sensor_mapping.json
```

이 파일을 직접 수정해도 됩니다:
```json
{
  "mapping": {
    "1": "S01",   ← 센서 1번이 S01 락커에 연결
    "2": "M15",   ← 센서 2번이 M15 락커에 연결
    ...
  }
}
```

---

## ✅ 현재 상태

### 완료된 작업
- ✅ 데이터베이스 60개 락커로 재구성
- ✅ ESP32 2개 구역 매핑 설정
- ✅ 센서 매핑 시스템 구축
- ✅ 센서 매핑 테스트 도구 제공
- ✅ 락커 서비스 로직 업데이트

### 필요한 작업
- ⚠️ **센서 매핑 테스트 (필수)**
  - 60개 락커 모두 실제 테스트
  - `sensor_mapping.json` 업데이트
  
- 📋 **검증 작업**
  - ESP32 2개 모두 정상 인식 확인
  - 각 구역별 문 열림 테스트
  - 센서 감지 테스트

---

## 🚀 시스템 재시작

```bash
# SSH 접속
ssh raspberry-pi

# 키오스크 중지
cd ~/gym-controller
bash scripts/deployment/stop_kiosk.sh

# 키오스크 시작
bash scripts/deployment/start_kiosk.sh
```

---

## 📝 주요 변경 사항 요약

| 항목 | 이전 | 현재 |
|------|------|------|
| 총 락커 수 | 140개 | 60개 |
| 교직원 | S01~S20 (20개) | S01~S10 (10개) |
| 남성 | M01~M70 (70개) | M01~M40 (40개) |
| 여성 | F01~F50 (50개) | F01~F10 (10개) |
| ESP32 구성 | 3개 (male/female/staff) | 2개 (male_female/staff) |
| 센서 매핑 | 하드코딩 | 설정 파일 기반 |

---

## 🔍 트러블슈팅

### 센서가 감지 안 됨
1. ESP32 연결 확인: `ls /dev/ttyUSB*`
2. 서버 로그 확인: `journalctl -u user@1000 -f`
3. 센서 매핑 파일 확인: `cat config/sensor_mapping.json`

### 잘못된 락커가 열림
- 센서 매핑이 잘못됨 → `test_sensor_mapping.py`로 재테스트

### ESP32 구역 인식 안 됨
- `config/esp32_mapping.json` 확인
- 포트 번호 변경 시 매핑 파일 수정

---

## 📞 문의

센서 매핑 테스트는 물리적 하드웨어가 있는 현장에서 진행해야 합니다.
테스트 완료 후 `sensor_mapping.json` 파일을 백업해두세요!

