# 하드웨어 가이드

> ESP32, 센서, 모터 설정 및 연동

## 시스템 구성

### 락커 배치

```
교직원: S01-S10 (10개) - ESP32 #1 (esp32_staff)
남성:   M01-M40 (40개) - ESP32 #2 (esp32_male_female)
여성:   F01-F10 (10개) - ESP32 #2 (esp32_male_female)
총계:   60개
```

### ESP32 장치

| 장치 | 포트 | 담당 구역 |
|------|------|----------|
| esp32_staff | /dev/ttyUSB1 | 교직원 (S01-S10) |
| esp32_male_female | /dev/ttyUSB0 | 남성/여성 (M01-M40, F01-F10) |

---

## ESP32 펌웨어

### 현재 사용 버전

`hardware/esp32_gym_controller_v7.5_nfc.ino`
- WiFi/OTA 제거로 안정성 향상
- 시리얼 통신만 사용 (USB)
- 플러그앤플레이 방식

### 핀 배치

```
ESP32 핀 배치:
- 바코드 스캐너 (UART2): RX2=GPIO16, TX2=GPIO17
- I2C (MCP23017): SDA=GPIO21, SCL=GPIO22
- 스테퍼 모터: STEP=GPIO25, DIR=GPIO26, EN=GPIO27
- LED: GPIO2, BUZZER: GPIO4
```

### MCP23017 IR 센서

- I2C 주소: 0x23, 0x25, 0x26, 0x27
- 센서 수: 60개 (16핀 x 4칩)
- 디바운싱: 15ms

---

## 통신 프로토콜

### ESP32에서 라즈베리파이로 (이벤트)

바코드 스캔:
```json
{
  "device_id": "esp32_gym",
  "event_type": "barcode_scanned",
  "data": {"barcode": "20240673"}
}
```

센서 이벤트:
```json
{
  "device_id": "esp32_gym",
  "event_type": "sensor_triggered",
  "data": {"chip_idx": 0, "addr": "0x26", "pin": 1, "state": "LOW"}
}
```

### 라즈베리파이에서 ESP32로 (명령)

```json
{"command": "open_locker", "locker_id": "M01"}
{"command": "get_status"}
{"command": "motor_move", "revs": 0.917, "rpm": 60}
```

---

## 모터 설정

- 기본 스텝: 200 스텝/회전
- 마이크로스텝: 1/2 (400 스텝/회전)
- 락커 열기: 330도 = 367스텝
- RPM: 기본 30

---

## 설정 파일

### config/esp32_mapping.json

```json
{
  "devices": {
    "/dev/ttyUSB0": {"device_id": "esp32_male_female", "zones": ["MALE", "FEMALE"]},
    "/dev/ttyUSB1": {"device_id": "esp32_staff", "zones": ["STAFF"]}
  }
}
```

### config/sensor_mapping.json

```json
{
  "mapping": {"1": "S01", "11": "M01", "51": "F01"}
}
```

참고: `config/esp32_devices.json`은 DEPRECATED (사용 안 함)

---

## 라즈베리파이 설정

```bash
# 시리얼 권한
sudo usermod -a -G dialout $USER
sudo chmod 666 /dev/ttyUSB0

# 연결 확인
ls -la /dev/ttyUSB*
```

---

## 트러블슈팅

### ESP32 연결 안 됨
```bash
ls -la /dev/ttyUSB*
sudo chmod 666 /dev/ttyUSB0
```

### 센서 감지 안 됨
```bash
tail -f ~/gym-controller/logs/locker_system.log
```

### 모터가 안 돌아감
```json
{"command": "test_motor"}
```

---

## 관련 파일

- `hardware/esp32_gym_controller_v7.5_nfc.ino` - ESP32 펌웨어
- `config/esp32_mapping.json` - ESP32 장치 매핑
- `config/sensor_mapping.json` - 센서-락커 매핑
- `core/esp32_manager.py` - ESP32 통신 관리

