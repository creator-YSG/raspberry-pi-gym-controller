// ESP32 헬스장 컨트롤러 v7.4 - WiFi/OTA 제거 (초간단)
// 기능: 바코드 스캔, IR센서 감지, 모터 제어

#include <Wire.h>
#include <Adafruit_MCP23X17.h>
#include <ArduinoJson.h>

// ==================== 디바이스 정보 ====================
const String DEVICE_ID = "esp32_gym";
const String VERSION = "v7.4-simple";

// ==================== 핀 설정 ====================
#define RX2_PIN 16
#define TX2_PIN 17
#define SDA_PIN 21
#define SCL_PIN 22
#define PIN_STEP 25
#define PIN_DIR 26
#define PIN_EN 27
#define LED_PIN 2
#define BUZZER_PIN 4

// ==================== 통신 설정 ====================
#define PC_BAUD 115200
#define SCANNER_BAUD 9600

// ==================== 모터 설정 (1/2 마이크로스텝) ====================
#define STEPS_PER_REV 200
#define MICROSTEP 2
#define ACTUAL_STEPS_PER_REV (STEPS_PER_REV * MICROSTEP)

// ==================== MCP23017 설정 ====================
#define MAX_MCP 8
#define DEBOUNCE_MS 15

// ==================== 전역 변수 ====================
struct MCPUnit {
  Adafruit_MCP23X17 dev;
  uint8_t addr;
  bool lastState[16];
  unsigned long lastChange[16];
  bool active;
} mcpUnits[MAX_MCP];

int mcpCount = 0;
String scanBuffer = "";
unsigned long lastScanTime = 0;
bool motorBusy = false;
uint32_t totalScans = 0;
uint32_t totalIREvents = 0;
uint32_t totalMotorMoves = 0;

// ==================== 유틸리티 ====================
void blinkLED(int times = 1) {
  for (int i = 0; i < times; i++) {
    digitalWrite(LED_PIN, HIGH);
    delay(50);
    digitalWrite(LED_PIN, LOW);
    if (i < times - 1) delay(50);
  }
}

void beep(int duration = 50) {
  digitalWrite(BUZZER_PIN, HIGH);
  delay(duration);
  digitalWrite(BUZZER_PIN, LOW);
}

// ==================== JSON 메시지 ====================
void sendMessage(String msgType, String eventType, JsonObject data) {
  StaticJsonDocument<512> doc;
  doc["device_id"] = DEVICE_ID;
  doc["message_type"] = msgType;
  doc["timestamp"] = millis();
  doc["version"] = VERSION;
  
  if (eventType != "") doc["event_type"] = eventType;
  doc["data"] = data;
  
  String output;
  serializeJson(doc, output);
  Serial.println(output);
}

void sendStatus() {
  StaticJsonDocument<512> data;
  data["status"] = "ready";
  data["version"] = VERSION;
  data["uptime"] = millis();
  data["motor_busy"] = motorBusy;
  data["mcp_count"] = mcpCount;
  data["total_scans"] = totalScans;
  data["total_moves"] = totalMotorMoves;
  data["microstep"] = MICROSTEP;
  data["steps_per_rev"] = ACTUAL_STEPS_PER_REV;
  
  sendMessage("response", "", data.as<JsonObject>());
}

// ==================== 모터 제어 ====================
void rotateMotor(double revs, int rpm = 30) {
  if (motorBusy || revs == 0) return;
  
  motorBusy = true;
  
  // 방향
  if (revs < 0) {
    digitalWrite(PIN_DIR, HIGH);
    revs = -revs;
  } else {
    digitalWrite(PIN_DIR, LOW);
  }
  delay(10);
  
  long totalSteps = (long)(revs * ACTUAL_STEPS_PER_REV);
  
  Serial.printf("[모터] %.2f회전, %d RPM, %ld스텝\n", revs, rpm, totalSteps);
  
  // ⭐ 테스트 코드와 완전히 동일하게 (1000us)
  for (long i = 0; i < totalSteps; i++) {
    digitalWrite(PIN_STEP, LOW);
    delayMicroseconds(1000);
    digitalWrite(PIN_STEP, HIGH);
    delayMicroseconds(1000);
    
    if (i % 100 == 0) {
      digitalWrite(LED_PIN, !digitalRead(LED_PIN));
    }
  }
  
  digitalWrite(LED_PIN, LOW);
  motorBusy = false;
  totalMotorMoves++;
  
  Serial.println("[모터] 완료");
}

// ==================== MCP23017 ====================
void scanMCP() {
  Serial.println("[MCP] 스캔...");
  for (uint8_t addr = 0x20; addr <= 0x27 && mcpCount < MAX_MCP; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      MCPUnit& mcp = mcpUnits[mcpCount];
      mcp.addr = addr;
      if (mcp.dev.begin_I2C(addr, &Wire)) {
        for (int pin = 0; pin < 16; pin++) {
          mcp.dev.pinMode(pin, INPUT_PULLUP);
          mcp.lastState[pin] = mcp.dev.digitalRead(pin);
          mcp.lastChange[pin] = millis();
        }
        mcp.active = true;
        mcpCount++;
        Serial.printf("[MCP] 0x%02X OK\n", addr);
      }
    }
  }
  Serial.printf("[MCP] %d개\n", mcpCount);
}

void processMCP() {
  unsigned long now = millis();
  
  for (int i = 0; i < mcpCount; i++) {
    MCPUnit& mcp = mcpUnits[i];
    if (!mcp.active) continue;
    
    for (int pin = 0; pin < 16; pin++) {
      bool current = mcp.dev.digitalRead(pin);
      if (current != mcp.lastState[pin]) {
        if (now - mcp.lastChange[pin] > DEBOUNCE_MS) {
          mcp.lastState[pin] = current;
          mcp.lastChange[pin] = now;
          totalIREvents++;
          blinkLED(1);
          
          // 🆕 센서 이벤트 JSON 전송 (원래대로)
          StaticJsonDocument<256> data;
          data["chip_idx"] = i;
          data["addr"] = String("0x") + String(mcp.addr, HEX);
          data["pin"] = pin;
          data["state"] = current ? "HIGH" : "LOW";
          data["active"] = !current;  // 센서는 LOW가 활성화 (원래대로)
          sendMessage("event", "sensor_triggered", data.as<JsonObject>());
        }
      }
    }
  }
}

// ==================== 바코드 ====================
void processBarcode() {
  while (Serial2.available()) {
    char c = Serial2.read();
    if (c == '\r' || c == '\n') {
      if (scanBuffer.length() > 0) {
        scanBuffer.trim();
        blinkLED(2);
        beep(50);
        totalScans++;
        
        StaticJsonDocument<256> data;
        data["barcode"] = scanBuffer;
        data["scan_count"] = totalScans;
        sendMessage("event", "barcode_scanned", data.as<JsonObject>());
        
        Serial.printf("[바코드] %s\n", scanBuffer.c_str());
        scanBuffer = "";
        lastScanTime = 0;
      }
    } else if (isPrintable(c)) {
      scanBuffer += c;
      lastScanTime = millis();
    }
  }
  
  if (scanBuffer.length() > 0 && lastScanTime > 0 && millis() - lastScanTime > 500) {
    scanBuffer.trim();
    if (scanBuffer.length() > 0) {
      blinkLED(2);
      beep(50);
      totalScans++;
      
      StaticJsonDocument<256> data;
      data["barcode"] = scanBuffer;
      sendMessage("event", "barcode_scanned", data.as<JsonObject>());
      
      Serial.printf("[바코드] %s\n", scanBuffer.c_str());
    }
    scanBuffer = "";
    lastScanTime = 0;
  }
}

// ==================== 명령 처리 ====================
void processCommand() {
  static String cmdBuffer = "";
  
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (cmdBuffer.length() > 0) {
        cmdBuffer.trim();
        
        if (cmdBuffer.startsWith("{")) {
          StaticJsonDocument<384> doc;
          if (deserializeJson(doc, cmdBuffer) == DeserializationError::Ok) {
            String command = doc["command"] | "";
            
            if (command == "get_status") {
              sendStatus();
            }
            else if (command == "motor_move") {
              if (!motorBusy) {
                double revs = doc["revs"] | 0.0;
                int rpm = doc["rpm"] | 30;
                
                if (revs != 0) {
                  rotateMotor(revs, rpm);
                  
                  StaticJsonDocument<128> data;
                  data["revs"] = revs;
                  data["rpm"] = rpm;
                  sendMessage("response", "motor_moved", data.as<JsonObject>());
                }
              }
            }
            else if (command == "open_locker") {
              if (!motorBusy) {
                rotateMotor(0.917, 30);
                StaticJsonDocument<128> data;
                data["status"] = "opened";
                sendMessage("response", "locker_opened", data.as<JsonObject>());
              }
            }
            else if (command == "test") {
              blinkLED(3);
              beep(200);
              sendStatus();
            }
          }
        } else {
          String cmd = cmdBuffer;
          cmd.toLowerCase();
          if (cmd == "status") sendStatus();
          else if (cmd == "test") { blinkLED(3); beep(200); }
        }
        
        cmdBuffer = "";
      }
    } else {
      cmdBuffer += c;
    }
  }
}

// ==================== 메인 ====================
void setup() {
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(PIN_STEP, OUTPUT);
  pinMode(PIN_DIR, OUTPUT);
  pinMode(PIN_EN, OUTPUT);
  
  digitalWrite(LED_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);
  digitalWrite(PIN_STEP, LOW);
  digitalWrite(PIN_DIR, LOW);
  digitalWrite(PIN_EN, LOW);  // 활성화
  
  Serial.begin(PC_BAUD);
  Serial2.begin(SCANNER_BAUD, SERIAL_8N1, RX2_PIN, TX2_PIN);
  
  delay(1000);
  
  Serial.println("\n========================================");
  Serial.println("ESP32 헬스장 컨트롤러 " + VERSION);
  Serial.println("1/2 마이크로스텝 (400 스텝/회전)");
  Serial.println("WiFi/OTA 제거 - 모터 우선");
  Serial.println("========================================");
  
  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(100000);
  scanMCP();
  
  Serial.println("[모터] 준비 중...");
  delay(2000);
  
  blinkLED(3);
  beep(100);
  
  sendStatus();
  Serial.println("[시스템] ✓ 준비\n");
}

void loop() {
  processBarcode();
  if (mcpCount > 0) processMCP();
  processCommand();
  
  delay(5);
}
