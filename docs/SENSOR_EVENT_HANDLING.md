# 센서 이벤트 처리 방식 (Sensor Event Handling)

> **중요**: 이 문서에 설명된 방식은 실제 테스트를 통해 검증된 **유일하게 안정적으로 작동하는 센서 처리 방식**입니다.
> 다른 방식(WebSocket만 사용, 앱 컨텍스트 없이 호출 등)은 모두 실패했습니다.

## 📋 작성일자
- **최초 작성**: 2025-11-07
- **검증 버전**: 2025-10-20 커밋 (225cef6) 기준
- **검증 상태**: ✅ 실제 하드웨어 환경에서 안정적 작동 확인

---

## 🔍 개요

ESP32에서 발생하는 센서 이벤트를 Flask 애플리케이션으로 전달하고 처리하는 방식입니다.
비동기 이벤트 핸들러에서 Flask의 동기 함수들을 안전하게 호출하기 위한 특수한 처리가 필요합니다.

---

## 🏗️ 아키텍처

```
ESP32 센서 감지
    ↓
ESP32Manager (비동기 이벤트 핸들러)
    ↓
handle_sensor_triggered() [async function]
    ↓
    ├─→ Flask App Context 내에서 add_sensor_event() 호출 (API용)
    └─→ sensor_queue에 저장 (폴링용)
```

---

## ✅ 핵심 구현 (app/__init__.py)

### 1. Flask 앱 컨텍스트 사용 (필수!)

```python
async def handle_sensor_triggered(event_data):
    """센서 이벤트 처리"""
    # ... 센서 번호 매핑 로직 ...
    
    if sensor_num:
        # ⚠️ 중요: Flask 컨텍스트 내에서 실행해야 함!
        from app.api.routes import add_sensor_event
        with app.app_context():
            add_sensor_event(sensor_num, raw_state)
        
        app.logger.info(f"🔥 [DEBUG] 센서 이벤트 저장됨: 센서{sensor_num}, 상태{raw_state}")
```

**왜 `with app.app_context():`가 필요한가?**

1. **비동기 컨텍스트 문제**: 
   - `handle_sensor_triggered`는 `async` 함수로, ESP32Manager의 비동기 루프에서 실행됩니다.
   - Flask는 기본적으로 동기 웹 프레임워크이며, 각 HTTP 요청마다 자동으로 앱 컨텍스트를 생성합니다.
   - 하지만 비동기 이벤트 핸들러는 HTTP 요청 컨텍스트 외부에서 실행되므로 수동으로 컨텍스트를 생성해야 합니다.

2. **컨텍스트가 없을 때 발생하는 문제**:
   ```python
   # ❌ 잘못된 방식 (컨텍스트 없이 호출)
   add_sensor_event(sensor_num, raw_state)
   
   # 결과: 
   # - has_app_context() → False
   # - current_app.logger 접근 불가
   # - 로그 출력 안됨
   # - 이벤트 저장 안됨
   ```

3. **올바른 호출 방식**:
   ```python
   # ✅ 올바른 방식 (컨텍스트 생성 후 호출)
   with app.app_context():
       add_sensor_event(sensor_num, raw_state)
   
   # 결과:
   # - has_app_context() → True
   # - current_app.logger 정상 작동
   # - 로그 출력됨
   # - 이벤트가 recent_sensor_events에 저장됨
   ```

### 2. 센서 큐 저장 (필수!)

```python
# 센서 큐에 저장 (폴링용)
sensor_data = {
    'sensor_num': sensor_num,
    'chip_idx': chip_idx,
    'pin': pin,
    'state': raw_state,
    'active': active,
    'timestamp': event_data.get('timestamp')
}
try:
    sensor_queue.put_nowait(sensor_data)
    app.logger.info(f"📦 센서 큐에 저장: 센서{sensor_num}, 상태{raw_state}")
except queue.Full:
    # 큐가 꽉 찼으면 가장 오래된 것 제거하고 새로운 것 추가
    try:
        sensor_queue.get_nowait()
        sensor_queue.put_nowait(sensor_data)
        app.logger.warning(f"⚠️ 센서 큐가 가득 차서 오래된 데이터 제거")
    except:
        pass
```

**왜 센서 큐가 필요한가?**

1. **이중 처리 메커니즘**:
   - `add_sensor_event()`: API 엔드포인트(`/api/hardware/sensor_events`)용 데이터 저장
   - `sensor_queue`: 폴링 방식의 센서 모니터링용 (기존 시스템 호환성)

2. **큐 방식의 장점**:
   - 이벤트 순서 보장
   - 버퍼링으로 순간적인 이벤트 폭주 처리
   - 처리 속도와 무관하게 이벤트 보존

---

## 📊 데이터 흐름

### 1. 센서 이벤트 발생 시

```
1. ESP32에서 센서 감지 (IR 센서 LOW 상태)
   ↓
2. handle_sensor_triggered() 호출
   ↓
3. 핀 번호 → 센서 번호 매핑 (chip_pin_to_sensor 사용)
   ↓
4. Flask 앱 컨텍스트 내에서 add_sensor_event() 호출
   ↓
5. 센서 번호 → 락커 ID 매핑 (sensor_mapping.json 사용)
   ↓
6. recent_sensor_events (deque)에 저장:
   {
       'sensor_num': 2,
       'locker_id': 'S03',
       'state': 'LOW',
       'timestamp': 1762503330.752,
       'active': True
   }
   ↓
7. sensor_queue에도 저장 (폴링용)
```

### 2. 프론트엔드 센서 디버그 모드

```
1. 사용자가 센서 디버그 토글 활성화
   ↓
2. JavaScript에서 200ms마다 폴링:
   fetch('/api/hardware/sensor_events')
   ↓
3. API가 recent_sensor_events에서 최근 3초 이내 이벤트 반환
   ↓
4. 반환 후 해당 이벤트는 deque에서 제거 (중복 방지)
   ↓
5. 프론트엔드에서 locker_id 표시:
   "S03번 센서 감지" (2초간 표시)
```

---

## 🔧 핵심 컴포넌트

### 1. add_sensor_event() 함수 (app/api/routes.py)

```python
def add_sensor_event(sensor_num, state, timestamp=None):
    """센서 이벤트 추가 및 트랜잭션 연동 처리"""
    if timestamp is None:
        timestamp = time.time()
    
    # Flask 애플리케이션 컨텍스트 확인
    from flask import has_app_context
    
    if has_app_context():
        current_app.logger.info(f"🔥 [add_sensor_event] 함수 시작: 센서{sensor_num}, 상태{state}")
    
    # 센서 번호를 락커 ID로 매핑
    locker_id = None
    try:
        import json
        with open('/home/pi/gym-controller/config/sensor_mapping.json', 'r', encoding='utf-8') as f:
            mapping_data = json.load(f)
            locker_id = mapping_data.get('mapping', {}).get(str(sensor_num))
    except Exception as e:
        if has_app_context():
            current_app.logger.warning(f"⚠️ 센서 매핑 로드 실패: {e}")
    
    # 이벤트 저장
    event = {
        'sensor_num': sensor_num,
        'locker_id': locker_id,  # 🔥 락커 ID 포함 (프론트엔드 표시용)
        'state': state,
        'timestamp': timestamp,
        'active': state == 'LOW'
    }
    recent_sensor_events.append(event)
    
    # ... 트랜잭션 시스템 연동 로직 ...
```

### 2. /api/hardware/sensor_events 엔드포인트

```python
@bp.route('/hardware/sensor_events')
def hardware_sensor_events():
    """최근 센서 이벤트 가져오기 (일회성 이벤트 반환)"""
    try:
        current_time = time.time()
        recent_events = []
        
        # 최근 3초 이내의 이벤트만 반환
        for event in list(recent_sensor_events):
            if current_time - event['timestamp'] <= 3:
                recent_events.append(event)
        
        # 이벤트 반환 후 제거 (중복 방지)
        if recent_events:
            for event in recent_events:
                try:
                    recent_sensor_events.remove(event)
                except ValueError:
                    pass
        
        return jsonify(recent_events)
    except Exception as e:
        current_app.logger.error(f'센서 이벤트 조회 오류: {e}')
        return jsonify([])
```

---

## 🚫 작동하지 않는 방식들

### ❌ 방식 1: 앱 컨텍스트 없이 호출

```python
# ❌ 실패: 컨텍스트 오류
async def handle_sensor_triggered(event_data):
    add_sensor_event(sensor_num, raw_state)  # has_app_context() = False
```

**문제점**:
- `current_app` 접근 불가
- 로그 출력 안됨
- 데이터 저장 안됨

### ❌ 방식 2: WebSocket만 사용

```python
# ❌ 실패: 프론트엔드에서 이벤트 수신 불안정
socketio.emit('sensor_event', {...})
```

**문제점**:
- 브라우저 재시작 시 연결 끊김
- 이벤트 누락 발생
- 실시간성 보장 안됨

### ❌ 방식 3: 직접 recent_sensor_events 수정

```python
# ❌ 실패: 센서 매핑 누락
recent_sensor_events.append({
    'sensor_num': sensor_num,
    'state': state
    # locker_id 없음!
})
```

**문제점**:
- `locker_id`가 없어서 프론트엔드에서 표시 불가
- 센서 번호만으로는 사용자가 이해할 수 없음

---

## 📝 설정 파일

### sensor_mapping.json

센서 번호를 락커 ID로 매핑하는 파일입니다.

```json
{
  "description": "센서 번호와 락커 ID 매핑 (실제 물리적 연결 기준)",
  "note": "교직원(S01~S10) + 남성(M01~M10, M31~M40) + 여성(F01~F10) 2025-11-07 재매핑 완료",
  "last_updated": "2025-11-07T16:53:00",
  "total_sensors": 40,
  "mapping": {
    "1": "S04",
    "2": "S03",
    "3": "S08",
    ...
  }
}
```

---

## 🧪 테스트 방법

### 1. 센서 디버그 모드 활성화

1. 키오스크 홈 화면에서 우측 상단 🔧 버튼 클릭
2. 버튼이 🔧✓로 변경되면 활성화 상태

### 2. 센서 감지 확인

1. 락커 문 앞에 손을 갖다대어 센서 감지
2. 화면 중앙에 "S03번 센서 감지" 알림이 2초간 표시되어야 함
3. 로그 확인:
   ```bash
   ssh raspberry-pi "tail -f ~/gym-controller/logs/locker_system.log | grep '센서'"
   ```

### 3. 예상 로그 출력

```
2025-11-07 17:15:30 INFO: 🔥 [DEBUG] 센서 이벤트 핸들러 호출됨!
2025-11-07 17:15:30 INFO: 📡 센서: Chip0 Pin1 = LOW (ACTIVE)
2025-11-07 17:15:30 INFO: 🔥 [DEBUG] 핀 1 -> 센서 2 매핑
2025-11-07 17:15:30 INFO: 🔥 [add_sensor_event] 함수 시작: 센서2, 상태LOW
2025-11-07 17:15:30 INFO: 🔥 [DEBUG] 센서 이벤트 저장됨: 센서2, 상태LOW
2025-11-07 17:15:30 INFO: 📦 센서 큐에 저장: 센서2, 상태LOW
2025-11-07 17:15:30 INFO: 🔥 [센서API] 새로운 이벤트: 1개 반환
```

---

## ⚠️ 주의사항

1. **절대로 `with app.app_context():` 를 제거하지 마세요**
   - 이것이 없으면 센서 이벤트 처리가 완전히 작동하지 않습니다.

2. **센서 큐 저장 로직을 제거하지 마세요**
   - 기존 시스템과의 호환성을 위해 필요합니다.

3. **WebSocket 방식으로 대체하려고 시도하지 마세요**
   - 실제 환경에서 안정적으로 작동하지 않습니다.
   - 폴링 방식(200ms 간격)이 더 안정적입니다.

4. **`locker_id` 매핑을 빼먹지 마세요**
   - 센서 번호만으로는 사용자가 어느 락커인지 알 수 없습니다.

---

## 🔍 트러블슈팅

### 문제: 센서 감지해도 화면에 알림이 안 뜸

**확인 사항**:
1. Flask 서버가 정상 실행 중인가?
   ```bash
   ssh raspberry-pi "ps aux | grep 'python.*run.py' | grep -v grep"
   ```

2. ESP32가 연결되어 있는가?
   ```bash
   ssh raspberry-pi "tail -50 ~/gym-controller/logs/locker_system.log | grep 'ESP32 연결'"
   ```

3. 센서 디버그 모드가 활성화되어 있는가?
   - 우측 상단 버튼이 🔧✓ 상태여야 함

4. 로그에서 센서 이벤트가 감지되는가?
   ```bash
   ssh raspberry-pi "tail -f ~/gym-controller/logs/locker_system.log | grep '센서'"
   ```

5. `with app.app_context():` 가 있는가?
   ```bash
   grep -A 3 "add_sensor_event(sensor_num" app/__init__.py
   ```

### 문제: 로그에는 센서 감지되는데 API가 0개 반환

**원인**: Flask 앱 컨텍스트 없이 `add_sensor_event` 호출됨

**해결**:
```python
# app/__init__.py의 handle_sensor_triggered 함수 확인
with app.app_context():  # 이 줄이 있어야 함!
    add_sensor_event(sensor_num, raw_state)
```

### 문제: 센서 번호는 나오는데 락커 ID가 null

**원인**: `sensor_mapping.json` 파일 로드 실패 또는 매핑 누락

**해결**:
1. 파일 존재 확인:
   ```bash
   ssh raspberry-pi "cat ~/gym-controller/config/sensor_mapping.json"
   ```

2. 매핑 정보 확인:
   ```bash
   ssh raspberry-pi "grep '\"2\"' ~/gym-controller/config/sensor_mapping.json"
   ```

---

## 📚 참고 자료

- **검증된 커밋**: 225cef6 (2025-10-20)
- **관련 파일**:
  - `app/__init__.py`: 센서 이벤트 핸들러
  - `app/api/routes.py`: add_sensor_event 함수, API 엔드포인트
  - `app/templates/pages/home.html`: 센서 디버그 UI
  - `config/sensor_mapping.json`: 센서-락커 매핑 정보

---

## 📌 요약

**센서 이벤트 처리의 3대 원칙**:

1. ✅ **반드시 Flask 앱 컨텍스트 내에서 `add_sensor_event` 호출**
   ```python
   with app.app_context():
       add_sensor_event(sensor_num, raw_state)
   ```

2. ✅ **센서 큐에도 데이터 저장** (기존 시스템 호환성)
   ```python
   sensor_queue.put_nowait(sensor_data)
   ```

3. ✅ **센서 번호를 락커 ID로 매핑** (사용자 가독성)
   ```python
   locker_id = mapping_data.get('mapping', {}).get(str(sensor_num))
   ```

이 3가지를 모두 지켜야만 센서 처리가 정상 작동합니다!

