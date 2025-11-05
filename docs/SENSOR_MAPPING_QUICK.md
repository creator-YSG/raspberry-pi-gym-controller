# 센서 매핑 빠른 가이드

## 🚀 3단계로 끝내기

### 1️⃣ 로그 모니터링 시작
```bash
ssh raspberry-pi "tail -f ~/gym-controller/logs/locker_system.log | grep -E 'pin.*state.*LOW'"
```

### 2️⃣ 순서대로 락커 키 빼기
- S01 → S02 → ... → S10 (교직원)
- M01 → M02 → ... → M40 (남성)
- F01 → F02 → ... → F10 (여성)

### 3️⃣ Pin 번호 기록하고 매핑
```
Pin 1 = 센서 2번
Pin 0 = 센서 1번
Pin 6 = 센서 7번
...
```

---

## 📝 매핑 파일 수정

**파일**: `config/sensor_mapping.json`

```json
{
  "mapping": {
    "1": "S02",   ← 센서 1번이 S02 락커
    "2": "S01",   ← 센서 2번이 S01 락커
    "3": "S07",
    ...
  }
}
```

---

## 🔄 적용

```bash
# 동기화
rsync -av config/sensor_mapping.json raspberry-pi:~/gym-controller/config/

# 재시작
ssh raspberry-pi "cd ~/gym-controller && bash scripts/deployment/stop_kiosk.sh && sleep 2 && bash scripts/deployment/start_kiosk.sh > /dev/null 2>&1 &"
```

---

## 💡 핵심 공식

```
센서 번호 = Pin + 1

예:
Pin 0 → 센서 1번
Pin 1 → 센서 2번
Pin 9 → 센서 10번
```

---

**상세 가이드**: `docs/SENSOR_MAPPING_GUIDE.md` 참조

