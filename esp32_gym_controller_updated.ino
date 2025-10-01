// ESP32 완전 통합 시스템: GM65 바코드 + MCP23017 IR센서 + TB6600 스테퍼모터
// OTA 업데이트 지원 버전 - JSON 프로토콜 통합
// 하드웨어 구성:
// - GM65 Scanner: UART2 (RX2=GPIO16, TX2=GPIO17)
// - MCP23017: I2C (SDA=GPIO21, SCL=GPIO22)
// - TB6600 Stepper: STEP=GPIO25, DIR=GPIO26, EN=GPIO27
// - LED: GPIO2, Buzzer: GPIO4

#include <Wire.h>
#include <Adafruit_MCP23X17.h>
#include <ArduinoJson.h>
#include <WiFi.h>
#include <ArduinoOTA.h>

// ==================== WiFi 설정 ====================
const char* ssid = "sya";
const char* password = "fitbox9497748";
const char* hostname = "ESP32-GYM-LOCKER-V1";

// ==================== 디바이스 식별 ====================
const String DEVICE_ID = "esp32_gym";
const String DEVICE_TYPE = "gym_controller";

// ==================== 하드웨어 핀 설정 ====================
// UART2 (바코드 스캐너)
constexpr int RX2_PIN = 16;
constexpr int TX2_PIN = 17;

// I2C (MCP23017)
constexpr int SDA_PIN = 21;
constexpr int SCL_PIN = 22;
constexpr uint32_t I2C_CLOCK_HZ = 100000;

// TB6600 스테퍼 모터 (공통음극 방식)
constexpr int PIN_STEP = 25;  // PUL+ 연결
constexpr int PIN_DIR = 26;   // DIR+ 연결
constexpr int PIN_EN = 27;    // ENA+ 연결

// 출력 장치
constexpr int LED_PIN = 2;
constexpr int BUZZER_PIN = 4;

// ==================== 통신 설정 ====================
constexpr uint32_t PC_BAUD = 115200;
constexpr uint32_t SCN_BAUD = 9600;

// ==================== 스테퍼 모터 설정 ====================
constexpr int FULL_STEPS_PER_REV = 200;
constexpr int MICROSTEP = 2;  // 1/2 스텝 (부드러움과 토크 균형)
constexpr unsigned int STEP_PULSE_HIGH_US = 5;    // TB6600용 펄스 폭 (5μs)
constexpr unsigned int STEP_PULSE_LOW_US = 5;     // TB6600용 펄스 간격 (5μs)
constexpr unsigned int DIR_SETUP_US = 100;        // 방향 설정 시간

// 모터 가속 파라미터 (속도 감소로 토크 증가)
float motorStartRPM = 2.0;        // 시작 속도를 더 낮게
float motorAccelRPMps = 150.0;    // 가속도를 절반으로 감소
float motorDefaultRPM = 25.0;     // 기본 속도를 절반 이하로 감소

// 모터 상태
bool motorEnabled = false;
int motorDirState = 0;
bool motorBusy = false;
unsigned long motorLastMoveTime = 0;

// 바코드 스캔 후 역방향 회전 타이머
unsigned long reverseMoveScheduledTime = 0;
bool reverseMoveScheduled = false;
int lastMoveDirection = 1;
constexpr unsigned long REVERSE_DELAY_MS = 5000;  // 5초
constexpr double BARCODE_ROTATION_DEGREES = 330.0;  // 330도
constexpr double BARCODE_ROTATION_REVS = BARCODE_ROTATION_DEGREES / 360.0;

// ==================== MCP23017 설정 ====================
constexpr uint8_t MCP_ADDR_FIRST = 0x20;
constexpr uint8_t MCP_ADDR_LAST = 0x27;
constexpr int MAX_MCP = 8;
constexpr bool ACTIVE_LOW = false;
constexpr bool USE_MCP_INTERNAL_PULLUPS = false;
constexpr unsigned long DEBOUNCE_MS = 15;

int watchPins[] = {
  0, 1, 2, 3, 4, 5, 6, 7,
  8, 9, 10, 11, 12, 13, 14, 15
};

// ==================== 데이터 구조체 ====================
struct Debounce {
  bool lastRead = HIGH;
  bool stable = HIGH;
  unsigned long lastChangeMs = 0;
  uint32_t risingCnt = 0;
  uint32_t fallingCnt = 0;
};

struct MCPUnit {
  Adafruit_MCP23X17 dev;
  uint8_t addr = 0xFF;
  Debounce db[16];
  bool inited = false;
};

// ==================== 전역 변수 ====================
MCPUnit mcpUnits[MAX_MCP];
int mcpCount = 0;

String scanBuffer = "";
unsigned long lastScanTime = 0;
constexpr unsigned long SCAN_TIMEOUT = 500;

bool hexMode = false;
bool debugMode = false;
bool systemReady = false;
bool autoMotorMode = true;  // 바코드 스캔 시 자동 회전
bool wifiConnected = false;
unsigned long systemStartTime = 0;

uint32_t totalBarcodeScans = 0;
uint32_t totalIREvents = 0;
uint32_t totalMotorMoves = 0;

// OTA 상태
unsigned long lastOTACheck = 0;
constexpr unsigned long OTA_CHECK_INTERVAL = 100;  // 100ms마다 체크

// ==================== WiFi 및 OTA 초기화 ====================
void setupWiFi() {
  Serial.print("[WiFi] 연결 중: ");
  Serial.println(ssid);
  
  WiFi.mode(WIFI_STA);
  WiFi.setHostname(hostname);
  WiFi.begin(ssid, password);
  
  // 최대 10초 대기
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    wifiConnected = true;
    Serial.println("\n[WiFi] 연결 성공!");
    Serial.print("[WiFi] IP 주소: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n[WiFi] 연결 실패 - WiFi 없이 계속 실행");
    wifiConnected = false;
  }
}

void setupOTA() {
  if (!wifiConnected) return;
  
  ArduinoOTA.setHostname(hostname);
  ArduinoOTA.setPassword("gym1234");  // OTA 비밀번호
  
  ArduinoOTA.onStart([]() {
    Serial.println("\n[OTA] 업데이트 시작...");
    // 모터 정지
    digitalWrite(PIN_EN, HIGH);
    motorBusy = true;  // OTA 중 모터 동작 차단
  });
  
  ArduinoOTA.onEnd([]() {
    Serial.println("\n[OTA] 업데이트 완료!");
  });
  
  ArduinoOTA.onProgress([](unsigned int progress, unsigned int total) {
    Serial.printf("[OTA] 진행률: %u%%\r", (progress / (total / 100)));
    // LED 깜빡임
    digitalWrite(LED_PIN, (progress / 10) % 2);
  });
  
  ArduinoOTA.onError([](ota_error_t error) {
    Serial.printf("[OTA] 오류[%u]: ", error);
    if (error == OTA_AUTH_ERROR) Serial.println("인증 실패");
    else if (error == OTA_BEGIN_ERROR) Serial.println("시작 실패");
    else if (error == OTA_CONNECT_ERROR) Serial.println("연결 실패");
    else if (error == OTA_RECEIVE_ERROR) Serial.println("수신 실패");
    else if (error == OTA_END_ERROR) Serial.println("종료 실패");
    motorBusy = false;  // 모터 동작 재개
  });
  
  ArduinoOTA.begin();
  Serial.println("[OTA] 준비 완료");
  Serial.println("[OTA] Arduino IDE에서 도구 > 포트에서 네트워크 포트 선택");
}

// ==================== 라즈베리파이 호환 메시지 함수 ====================
String getCurrentTimestamp() {
  unsigned long ms = millis();
  unsigned long seconds = ms / 1000;
  unsigned long minutes = seconds / 60;
  unsigned long hours = minutes / 60;
  
  return String("2025-09-23T") + 
         String(hours % 24) + ":" + 
         String(minutes % 60) + ":" + 
         String(seconds % 60) + "Z";
}

void sendRPiMessage(String messageType, String eventType, JsonObject data) {
  StaticJsonDocument<512> doc;
  
  doc["device_id"] = DEVICE_ID;
  doc["message_type"] = messageType;
  doc["timestamp"] = getCurrentTimestamp();
  
  if (eventType != "") {
    doc["event_type"] = eventType;
  }
  
  doc["data"] = data;
  
  String jsonString;
  serializeJson(doc, jsonString);
  Serial.println(jsonString);
}

void sendBarcodeEvent(String barcode, String format) {
  StaticJsonDocument<256> dataDoc;
  dataDoc["barcode"] = barcode;
  dataDoc["scan_type"] = "barcode";
  dataDoc["format"] = format;
  dataDoc["quality"] = 95;  // 고정값
  dataDoc["scan_count"] = totalBarcodeScans;
  
  JsonObject data = dataDoc.as<JsonObject>();
  sendRPiMessage("event", "barcode_scanned", data);
}

void sendIREvent(int chipIdx, uint8_t addr, int pin, bool state) {
  bool active = ACTIVE_LOW ? (state == LOW) : (state == HIGH);
  
  StaticJsonDocument<256> dataDoc;
  dataDoc["chip_idx"] = chipIdx;
  dataDoc["addr"] = String("0x") + String(addr, HEX);
  dataDoc["pin"] = pin;
  dataDoc["raw"] = state ? "HIGH" : "LOW";
  dataDoc["active"] = active;
  
  JsonObject data = dataDoc.as<JsonObject>();
  sendRPiMessage("event", "sensor_triggered", data);
}

void sendMotorEvent(String action, String status, JsonObject details = JsonObject()) {
  StaticJsonDocument<256> dataDoc;
  dataDoc["action"] = action;
  dataDoc["status"] = status;
  dataDoc["enabled"] = motorEnabled;
  dataDoc["direction"] = motorDirState == HIGH ? 1 : 0;
  dataDoc["busy"] = motorBusy;
  dataDoc["total_moves"] = totalMotorMoves;
  
  if (!details.isNull()) {
    dataDoc["details"] = details;
  }
  
  JsonObject data = dataDoc.as<JsonObject>();
  sendRPiMessage("event", "motor_completed", data);
}

void sendStatusResponse(String status, String message) {
  StaticJsonDocument<512> dataDoc;
  dataDoc["status"] = status;
  dataDoc["message"] = message;
  dataDoc["uptime_ms"] = millis() - systemStartTime;
  dataDoc["free_heap"] = ESP.getFreeHeap();
  dataDoc["wifi_connected"] = wifiConnected;
  
  if (wifiConnected) {
    dataDoc["ip_address"] = WiFi.localIP().toString();
    dataDoc["rssi"] = WiFi.RSSI();
  }
  
  // 스캐너 상태
  JsonObject scanner = dataDoc.createNestedObject("scanner");
  scanner["total_scans"] = totalBarcodeScans;
  scanner["hex_mode"] = hexMode;
  
  // MCP 상태
  JsonObject mcp = dataDoc.createNestedObject("mcp23017");
  mcp["count"] = mcpCount;
  mcp["total_events"] = totalIREvents;
  
  // 모터 상태
  JsonObject motor = dataDoc.createNestedObject("motor");
  motor["enabled"] = motorEnabled;
  motor["direction"] = motorDirState == HIGH ? 1 : 0;
  motor["busy"] = motorBusy;
  motor["auto_mode"] = autoMotorMode;
  motor["total_moves"] = totalMotorMoves;
  
  JsonObject data = dataDoc.as<JsonObject>();
  sendRPiMessage("response", "", data);
}

void sendErrorResponse(String errorCode, String errorMessage) {
  StaticJsonDocument<256> dataDoc;
  dataDoc["error_code"] = errorCode;
  dataDoc["error_message"] = errorMessage;
  
  JsonObject data = dataDoc.as<JsonObject>();
  sendRPiMessage("response", "error", data);
}

// ==================== 기본 유틸리티 함수 ====================
void blinkLED(int times = 1, int onMs = 50, int offMs = 50) {
  for (int i = 0; i < times; i++) {
    digitalWrite(LED_PIN, HIGH);
    delay(onMs);
    digitalWrite(LED_PIN, LOW);
    if (i < times - 1) delay(offMs);
  }
}

void beep(int duration = 100) {
  digitalWrite(BUZZER_PIN, HIGH);
  delay(duration);
  digitalWrite(BUZZER_PIN, LOW);
}

String repeatString(String str, int times) {
  String result = "";
  for (int i = 0; i < times; i++) {
    result += str;
  }
  return result;
}

bool isDigitsOnly(String str) {
  for (size_t i = 0; i < str.length(); i++) {
    if (!isDigit(str.charAt(i))) return false;
  }
  return true;
}

// ==================== 스테퍼 모터 함수 ====================
void setMotorEnable(bool on) {
  motorEnabled = on;
  digitalWrite(PIN_EN, on ? LOW : HIGH);  // TB6600: LOW=Enable
}

void setMotorDir(int d) {
  motorDirState = d ? HIGH : LOW;
  digitalWrite(PIN_DIR, motorDirState);
  delayMicroseconds(DIR_SETUP_US);
}

inline void applyEffectiveDirForRevs(double revs) {
  int eff = (revs < 0) ? ((motorDirState == HIGH) ? LOW : HIGH) : motorDirState;
  digitalWrite(PIN_DIR, eff);
  delayMicroseconds(DIR_SETUP_US);
}

// TB6600용 펄스 함수 (LOW→HIGH 엣지 트리거)
inline void stepPulse() {
  digitalWrite(PIN_STEP, LOW);
  delayMicroseconds(STEP_PULSE_HIGH_US);
  digitalWrite(PIN_STEP, HIGH);
  delayMicroseconds(STEP_PULSE_LOW_US);
}

inline unsigned long rpmToUS(double rpm) {
  if (rpm < 0.1) rpm = 0.1;  // 최소 RPM을 더 안전한 값으로 설정
  const double spr = FULL_STEPS_PER_REV * (double)MICROSTEP;
  const double sps = rpm * spr / 60.0;
  double us = 1e6 / sps;
  if (us < 1.0) us = 1.0;
  return (unsigned long)us;
}

void moveMotorConstant(double revs, double rpm) {
  if (revs == 0 || rpm <= 0 || motorBusy) return;
  
  motorBusy = true;
  setMotorEnable(true);  // 회전 직전 활성화
  motorLastMoveTime = millis();
  
  long totalSteps = llround(fabs(revs) * FULL_STEPS_PER_REV * MICROSTEP);
  if (totalSteps <= 0) {
    setMotorEnable(false);  // 발열 방지
    motorBusy = false;
    return;
  }

  applyEffectiveDirForRevs(revs);
  unsigned long us = rpmToUS(rpm);

  for (long i = 0; i < totalSteps; i++) {
    stepPulse();
    delayMicroseconds(us);
  }
  
  // 모터 회전 완료 후 잠시 대기 (실제 회전 보장)
  delay(500);  // 500ms 대기 후 비활성화
  setMotorEnable(false);  // 발열 방지를 위한 비활성화
  motorBusy = false;
  totalMotorMoves++;
}

void moveMotorAccel(double revs, double targetRPM) {
  if (revs == 0 || targetRPM <= 0 || motorBusy) return;
  
  motorBusy = true;
  setMotorEnable(true);  // 회전 직전 활성화
  motorLastMoveTime = millis();
  
  long totalSteps = llround(fabs(revs) * FULL_STEPS_PER_REV * MICROSTEP);
  if (totalSteps <= 0) {
    setMotorEnable(false);  // 발열 방지
    motorBusy = false;
    return;
  }

  applyEffectiveDirForRevs(revs);

  const double usStart = rpmToUS(motorStartRPM);
  const double usTarget = rpmToUS(targetRPM);

  long accelSteps = max(50L, totalSteps * 3 / 10);
  long decelSteps = max(50L, totalSteps * 3 / 10);
  long cruiseSteps = totalSteps - accelSteps - decelSteps;

  if (cruiseSteps < 0) {
    long borrow = -cruiseSteps / 2 + 1;
    accelSteps -= borrow;
    decelSteps -= borrow;
    cruiseSteps = 0;
    if (accelSteps < 20) accelSteps = 20;
    if (decelSteps < 20) decelSteps = 20;
  }

  // 가속
  for (long i = 0; i < accelSteps; i++) {
    double t = (double)(i + 1) / (double)accelSteps;
    double us = usStart + (usTarget - usStart) * t;
    stepPulse();
    delayMicroseconds((unsigned int)us);
  }
  // 크루즈
  for (long i = 0; i < cruiseSteps; i++) {
    stepPulse();
    delayMicroseconds((unsigned int)usTarget);
  }
  // 감속
  for (long i = decelSteps; i > 0; i--) {
    double t = (double)i / (double)decelSteps;
    double us = usStart + (usTarget - usStart) * t;
    stepPulse();
    delayMicroseconds((unsigned int)us);
  }
  
  // 모터 회전 완료 후 잠시 대기 (실제 회전 보장)
  delay(500);  // 500ms 대기 후 비활성화
  setMotorEnable(false);  // 발열 방지를 위한 비활성화
  motorBusy = false;
  totalMotorMoves++;
}

// ==================== MCP23017 함수 ====================
void scanAndInitMCPs() {
  Serial.println(F("[I2C] MCP23017 스캔 시작..."));
  
  for (uint8_t addr = MCP_ADDR_FIRST; addr <= MCP_ADDR_LAST; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      Serial.printf("[I2C] 장치 발견: 0x%02X\n", addr);
      
      if (mcpCount < MAX_MCP) {
        MCPUnit &u = mcpUnits[mcpCount];
        u.addr = addr;
        
        if (!u.dev.begin_I2C(addr, &Wire)) {
          Serial.printf("[ERROR] MCP23017 초기화 실패: 0x%02X\n", addr);
          continue;
        }
        
        for (int pin = 0; pin < 16; pin++) {
          if (USE_MCP_INTERNAL_PULLUPS) {
            u.dev.pinMode(pin, INPUT_PULLUP);
          } else {
            u.dev.pinMode(pin, INPUT);
          }
          
          bool r = u.dev.digitalRead(pin);
          u.db[pin].lastRead = r;
          u.db[pin].stable = r;
          u.db[pin].lastChangeMs = millis();
        }
        
        u.inited = true;
        mcpCount++;
      }
    }
  }
  
  Serial.printf("[I2C] MCP23017 %d개 활성화\n", mcpCount);
}

void processMCPInputs() {
  unsigned long now = millis();
  
  for (int ci = 0; ci < mcpCount; ci++) {
    MCPUnit &u = mcpUnits[ci];
    if (!u.inited) continue;
    
    for (size_t i = 0; i < sizeof(watchPins) / sizeof(int); i++) {
      int pin = watchPins[i];
      bool raw = u.dev.digitalRead(pin);
      
      if (raw != u.db[pin].lastRead) {
        u.db[pin].lastRead = raw;
        u.db[pin].lastChangeMs = now;
      }
      
      if ((now - u.db[pin].lastChangeMs) >= DEBOUNCE_MS) {
        if (u.db[pin].stable != u.db[pin].lastRead) {
          u.db[pin].stable = u.db[pin].lastRead;
          
          if (u.db[pin].stable == HIGH) {
            u.db[pin].risingCnt++;
          } else {
            u.db[pin].fallingCnt++;
          }
          
          // IR 센서 이벤트 전송 (라즈베리파이 호환)
          sendIREvent(ci, u.addr, pin, u.db[pin].stable);
          totalIREvents++;
          blinkLED(1, 30, 0);
        }
      }
    }
  }
}

// ==================== 바코드 스캐너 함수 ====================
String detectBarcodeFormat(String barcode) {
  if (barcode.length() == 13 && isDigit(barcode.charAt(0))) {
    return "EAN13";
  } else if (barcode.length() == 12 && isDigitsOnly(barcode)) {
    return "UPC-A";
  } else if (barcode.length() == 8 && isDigitsOnly(barcode)) {
    return "EAN8";
  } else {
    return "CODE128";
  }
}

void processBarcodeData(String barcode) {
  barcode.trim();
  if (barcode.length() == 0) return;
  
  blinkLED(2, 50, 50);
  beep(50);
  
  totalBarcodeScans++;
  
  // 라즈베리파이 호환 바코드 이벤트 전송
  sendBarcodeEvent(barcode, detectBarcodeFormat(barcode));
  
  // 자동 모터 모드 처리
  if (autoMotorMode && !motorBusy) {
    handleAutoMotorForBarcode(barcode);
  }
}

void handleScannerData() {
  while (Serial2.available()) {
    char c = Serial2.read();
    
    if (hexMode) {
      Serial.printf("%02X ", (uint8_t)c);
      continue;
    }
    
    if (c == '\r' || c == '\n') {
      if (scanBuffer.length() > 0) {
        processBarcodeData(scanBuffer);
        scanBuffer = "";
        lastScanTime = 0;
      }
    } else if (isPrintable(c)) {
      scanBuffer += c;
      lastScanTime = millis();
    }
  }
}

void checkScanTimeout() {
  if (scanBuffer.length() > 0 && lastScanTime > 0) {
    if (millis() - lastScanTime > SCAN_TIMEOUT) {
      processBarcodeData(scanBuffer);
      scanBuffer = "";
      lastScanTime = 0;
    }
  }
}

// ==================== 자동 모터 제어 ====================
void handleAutoMotorForBarcode(String barcode) {
  // 정방향 회전 (moveMotorAccel이 Enable 처리)
  setMotorDir(0);
  lastMoveDirection = 0;
  moveMotorAccel(BARCODE_ROTATION_REVS, motorDefaultRPM);
  
  // 5초 후 역방향 회전 예약
  reverseMoveScheduled = true;
  reverseMoveScheduledTime = millis() + REVERSE_DELAY_MS;
  
  // 모터 시작 이벤트 전송
  StaticJsonDocument<128> details;
  details["degrees"] = BARCODE_ROTATION_DEGREES;
  details["direction"] = "forward";
  details["trigger"] = "barcode_scan";
  sendMotorEvent("rotate", "started", details.as<JsonObject>());
}

void checkReverseMoveTimer() {
  if (reverseMoveScheduled && !motorBusy) {
    if (millis() >= reverseMoveScheduledTime) {
      reverseMoveScheduled = false;
      
      // 반대 방향으로 회전 (moveMotorAccel이 Enable 처리)
      setMotorDir(lastMoveDirection == 0 ? 1 : 0);
      moveMotorAccel(BARCODE_ROTATION_REVS, motorDefaultRPM);
      
      // 모터 완료 이벤트 전송
      StaticJsonDocument<128> details;
      details["degrees"] = BARCODE_ROTATION_DEGREES;
      details["direction"] = "reverse";
      details["trigger"] = "auto_return";
      sendMotorEvent("rotate", "completed", details.as<JsonObject>());
    }
  }
}

// ==================== 라즈베리파이 명령 처리 ====================
void handleRPiCommands() {
  static String rpiBuffer = "";
  
  while (Serial.available()) {
    char c = Serial.read();
    
    if (c == '\n' || c == '\r') {
      if (rpiBuffer.length() > 0) {
        processRPiCommand(rpiBuffer);
        rpiBuffer = "";
      }
    } else {
      rpiBuffer += c;
    }
  }
}

void processRPiCommand(String command) {
  command.trim();
  
  // JSON 명령 처리
  if (command.startsWith("{") && command.endsWith("}")) {
    processJSONCommand(command);
  } 
  // 텍스트 명령 처리
  else {
    processTextCommand(command);
  }
}

void processJSONCommand(String jsonString) {
  StaticJsonDocument<384> doc;
  DeserializationError error = deserializeJson(doc, jsonString);
  
  if (error) {
    sendErrorResponse("JSON_PARSE_ERROR", error.c_str());
    return;
  }
  
  String cmd = doc["command"] | "";
  
  // 시스템 명령
  if (cmd == "get_status") {
    sendStatusResponse("READY", "시스템 정상 동작 중");
  } 
  else if (cmd == "reset") {
    sendStatusResponse("RESET", "시스템 재시작...");
    delay(1000);
    ESP.restart();
  }
  
  // 모터 명령 (라즈베리파이 호환)
  else if (cmd == "open_locker") {
    String lockerId = doc["locker_id"] | "";
    int duration = doc["duration_ms"] | 3000;
    
    if (motorBusy) {
      sendErrorResponse("MOTOR_BUSY", "모터가 작동 중입니다");
      return;
    }
    
    // 락카 열기 = 330도 회전
    setMotorDir(0);  // 정방향
    moveMotorAccel(BARCODE_ROTATION_REVS, motorDefaultRPM);
    
    StaticJsonDocument<128> details;
    details["locker_id"] = lockerId;
    details["duration_ms"] = duration;
    sendMotorEvent("open_locker", "completed", details.as<JsonObject>());
  }
  
  // 직접 모터 제어 (회전수, RPM, 가속 지원)
  else if (cmd == "motor_move") {
    if (motorBusy) {
      sendErrorResponse("MOTOR_BUSY", "모터가 작동 중입니다");
      return;
    }
    
    double revs = doc["revs"] | 0.0;
    double rpm = doc["rpm"] | motorDefaultRPM;
    bool accel = doc["accel"] | true;
    
    if (revs == 0.0) {
      sendErrorResponse("INVALID_REVS", "회전수가 0입니다");
      return;
    }
    
    // 회전 방향 설정 (음수면 역방향)
    if (revs < 0) {
      setMotorDir(1);  // 역방향
      revs = -revs;    // 절댓값으로 변환
    } else {
      setMotorDir(0);  // 정방향
    }
    
    // 모터 회전 실행
    if (accel) {
      moveMotorAccel(revs, rpm);
    } else {
      moveMotorConstant(revs, rpm);
    }
    
    StaticJsonDocument<128> details;
    details["revs"] = revs;
    details["rpm"] = rpm;
    details["accel"] = accel;
    sendMotorEvent("motor_move", "completed", details.as<JsonObject>());
  }
  
  // 자동 모드 설정
  else if (cmd == "set_auto_mode") {
    autoMotorMode = doc["enabled"] | !autoMotorMode;
    sendStatusResponse("AUTO_MODE", autoMotorMode ? "활성화" : "비활성화");
  }
  
  // 모터 속도 파라미터 설정
  else if (cmd == "set_motor_params") {
    if (doc["default_rpm"].is<float>()) {
      motorDefaultRPM = doc["default_rpm"];
    }
    if (doc["start_rpm"].is<float>()) {
      motorStartRPM = doc["start_rpm"];
    }
    if (doc["accel_rpmps"].is<float>()) {
      motorAccelRPMps = doc["accel_rpmps"];
    }
    
    StaticJsonDocument<128> response;
    response["default_rpm"] = motorDefaultRPM;
    response["start_rpm"] = motorStartRPM;
    response["accel_rpmps"] = motorAccelRPMps;
    
    JsonObject data = response.as<JsonObject>();
    sendRPiMessage("response", "", data);
  }
  
  else {
    sendErrorResponse("UNKNOWN_COMMAND", cmd);
  }
}

void processTextCommand(String command) {
  command.toLowerCase();
  
  if (command == "status") {
    sendStatusResponse("READY", "텍스트 명령으로 상태 조회");
  } else if (command == "test") {
    blinkLED(3, 100, 100);
    beep(200);
    sendStatusResponse("TEST", "LED/부저 테스트 완료");
  } else if (command == "wifi") {
    if (wifiConnected) {
      Serial.print("WiFi 연결됨: ");
      Serial.println(WiFi.localIP());
      Serial.print("신호 강도: ");
      Serial.print(WiFi.RSSI());
      Serial.println(" dBm");
    } else {
      Serial.println("WiFi 연결 안됨");
    }
  } else if (command == "reset") {
    ESP.restart();
  } else {
    sendErrorResponse("UNKNOWN_TEXT_CMD", command);
  }
}

// ==================== 메인 함수 ====================
void setup() {
  // 핀 초기화
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(PIN_STEP, OUTPUT);
  pinMode(PIN_DIR, OUTPUT);
  pinMode(PIN_EN, OUTPUT);
  
  digitalWrite(LED_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);
  digitalWrite(PIN_STEP, LOW);  // TB6600용 초기값 (LOW에서 시작)
  setMotorEnable(false);
  setMotorDir(0);
  
  // 시리얼 초기화
  Serial.begin(PC_BAUD);
  delay(500);
  
  Serial2.begin(SCN_BAUD, SERIAL_8N1, RX2_PIN, TX2_PIN);
  
  // 시작 메시지 (디버그용)
  Serial.println("\n" + repeatString("=", 70));
  Serial.println("ESP32 헬스장 컨트롤러 v6.0 - TB6600 드라이버 + OTA");
  Serial.println("Device ID: " + DEVICE_ID);
  Serial.println("Device Type: " + DEVICE_TYPE);
  Serial.println(repeatString("=", 70));
  
  // WiFi 연결
  setupWiFi();
  
  // OTA 초기화
  setupOTA();
  
  // I2C 초기화
  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(I2C_CLOCK_HZ);
  
  // MCP23017 스캔
  scanAndInitMCPs();
  
  // 시스템 준비
  systemStartTime = millis();
  systemReady = true;
  
  // 시작 알림
  blinkLED(3, 200, 200);
  beep(100);
  delay(100);
  beep(100);
  
  // 라즈베리파이에 준비 완료 알림
  sendStatusResponse("SYSTEM_READY", "ESP32 헬스장 컨트롤러 준비 완료");
}

void loop() {
  // OTA 처리 (WiFi 연결된 경우만)
  if (wifiConnected && millis() - lastOTACheck > OTA_CHECK_INTERVAL) {
    ArduinoOTA.handle();
    lastOTACheck = millis();
  }
  
  // 라즈베리파이 명령 처리
  handleRPiCommands();
  
  // 바코드 스캐너 처리
  handleScannerData();
  checkScanTimeout();
  
  // MCP23017 입력 처리
  if (mcpCount > 0) {
    processMCPInputs();
  }
  
  // 5초 후 역방향 회전 체크
  checkReverseMoveTimer();
  
  // CPU 부하 감소
  delay(5);
}