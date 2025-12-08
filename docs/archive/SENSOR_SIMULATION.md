# 센서 값 가상 주입 가이드

## 테스트 목적
실제 하드웨어(ESP32, IR 센서) 없이 키오스크 UI의 대여/반납 프로세스를 테스트할 때 사용합니다.

---

## 사용할 API

### `/api/test/inject-sensor` ✅ (권장)

**sensor_queue에 직접 주입** - 프론트엔드가 `/api/sensor/poll`로 폴링하여 이벤트를 수신합니다.

```bash
curl -X POST http://localhost:5000/api/test/inject-sensor \
  -H 'Content-Type: application/json' \
  -d '{"sensor_num": 11, "state": "LOW"}'
```

#### 파라미터
| 파라미터 | 설명 | 값 |
|---------|------|-----|
| `sensor_num` | 센서 번호 (1-60) | 11 = M01, 1 = S01, 51 = F01 등 |
| `state` | 센서 상태 | `"HIGH"` = 키 없음 (뽑힘), `"LOW"` = 키 있음 (꽂힘) |

#### 센서 번호 → 락커 매핑
- **S01-S10 (교직원):** 센서 1-10
- **M01-M40 (남성):** 센서 11-50
- **F01-F10 (여성):** 센서 51-60

---

## 테스트 시나리오

### 1. 대여 테스트

```bash
# 1) 바코드 주입 (xdotool)
export DISPLAY=:0
xdotool type '20240673' && xdotool key Return

# 2) 4초 대기 (대여 대기 화면 표시)
sleep 4

# 3) 센서 주입 (HIGH = 키 뽑음 = 대여)
curl -X POST http://localhost:5000/api/test/inject-sensor \
  -H 'Content-Type: application/json' \
  -d '{"sensor_num": 11, "state": "HIGH"}'
```

**결과:** "대여가 완료되었습니다" 화면

---

### 2. 반납 테스트

**전제조건:** 해당 회원이 락커키를 대여 중이어야 함

```bash
# 1) 바코드 주입 (xdotool)
export DISPLAY=:0
xdotool type '20240673' && xdotool key Return

# 2) 4초 대기 (반납 대기 화면 표시)
sleep 4

# 3) 센서 주입 (LOW = 키 꽂음 = 반납)
curl -X POST http://localhost:5000/api/test/inject-sensor \
  -H 'Content-Type: application/json' \
  -d '{"sensor_num": 11, "state": "LOW"}'
```

**결과:** "반납이 완료되었습니다" 화면

---

## 주의사항

### 트랜잭션 설정 필요
반납 테스트 시, DB의 `active_transactions` 테이블에 `locker_number`가 설정되어 있어야 합니다.

```sql
-- 활성 트랜잭션에 락커 번호 설정
UPDATE active_transactions 
SET locker_number = 'M01', status = 'active'
WHERE member_id = '20240673';
```

### 대여 기록 필요
반납 테스트 시, `rentals` 테이블에 활성 대여 기록이 있어야 합니다.

```sql
-- 대여 기록 확인
SELECT * FROM rentals WHERE member_id = '20240673' AND status = 'active';
```

---

## 다른 API (참고용)

### `/api/hardware/simulate_sensor`
`recent_sensor_events`에 추가하지만, 프론트엔드가 주로 `/api/sensor/poll`을 폴링하므로 
**UI 반응이 불안정**할 수 있습니다. 테스트용으로는 `/api/test/inject-sensor`를 권장합니다.

---

## 스크린샷 캡처

```bash
# 라즈베리파이에서 스크린샷 캡처
export DISPLAY=:0
scrot /tmp/screenshot.png

# Mac으로 복사
scp raspberry-pi:/tmp/screenshot.png ./
```

---

## 관련 파일
- `app/api/routes.py` - API 엔드포인트 정의
- `app/templates/pages/member_check.html` - 프론트엔드 센서 폴링 로직
- `config/sensor_mapping.json` - 센서 번호 → 락커 ID 매핑

