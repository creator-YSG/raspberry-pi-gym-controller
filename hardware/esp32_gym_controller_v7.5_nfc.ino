// ESP32 헬스장 컨트롤러 v7.5 - NFC 추가 (SPI 모드)
// 기능: 바코드 스캔, IR센서 감지, 모터 제어, NFC 태그 읽기

#include <Wire.h>
#include <SPI.h>
#include <Adafruit_MCP23X17.h>
#include <ArduinoJson.h>
#include <Adafruit_PN532.h>

// ==================== 디바이스 정보 ====================
const String DEVICE_ID = "esp32_gym";
const String VERSION = "v7.5-nfc-spi";

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

// NFC 핀 설정 (SPI)
#define PN532_SS 5

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

// ==================== NFC 설정 ====================
#define NFC_TIMEOUT 100  // 100ms 타임아웃

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
uint32_t totalNFCScans = 0;

// NFC 객체 (SPI)
Adafruit_PN532 nfc(PN532_SS);
bool nfcAvailable = false;
String lastNFCUID = "";
unsigned long lastNFCTime = 0;

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
  data["nfc_available"] = nfcAvailable;
  data["total_scans"] = totalScans;
  data["total_nfc_scans"] = totalNFCScans;
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

// ==================== NFC 초기화 ====================
void initNFC() {
  Serial.println("[NFC] 초기화 중... (SPI 모드)");
  
  nfc.begin();
  delay(100);
  
  uint32_t versiondata = nfc.getFirmwareVersion();
  if (!versiondata) {
    Serial.println("[NFC] PN532를 찾을 수 없습니다!");
    Serial.println("[NFC] 배선과 SPI 모드 확인:");
    Serial.println("  - PN532 CH1=ON, CH2=OFF");
    Serial.println("  - SCK=GPIO18, MISO=GPIO19, MOSI=GPIO23, SS=GPIO5");
    Serial.println("  - 전원 재인가 필요");
    Serial.println("[NFC] NFC 기능 비활성화");
    nfcAvailable = false;
    return;
  }
  
  Serial.print("[NFC] PN532 발견! 펌웨어: v");
  Serial.print((versiondata>>24) & 0xFF, DEC); 
  Serial.print('.');
  Serial.println((versiondata>>16) & 0xFF, DEC);
  
  nfc.SAMConfig();
  nfcAvailable = true;
  
  Serial.println("[NFC] ✓ 준비 완료");
}

// ==================== NFC 처리 ====================
void processNFC() {
  if (!nfcAvailable) return;
  
  uint8_t success;
  uint8_t uid[] = { 0, 0, 0, 0, 0, 0, 0 };
  uint8_t uidLength;
  
  // 빠른 폴링 (100ms 타임아웃)
  success = nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &uidLength, NFC_TIMEOUT);
  
  if (success) {
    // UID를 16진수 문자열로 변환
    String uidString = "";
    for (uint8_t i = 0; i < uidLength; i++) {
      if (uid[i] < 0x10) uidString += "0";
      uidString += String(uid[i], HEX);
    }
    uidString.toUpperCase();
    
    // 중복 방지 (1초 이내 같은 UID 무시)
    if (uidString != lastNFCUID || millis() - lastNFCTime > 1000) {
      lastNFCUID = uidString;
      lastNFCTime = millis();
      totalNFCScans++;
      
      blinkLED(2);
      beep(100);
      
      // JSON 메시지 전송
      StaticJsonDocument<256> data;
      data["nfc_uid"] = uidString;
      data["uid_length"] = uidLength;
      data["scan_count"] = totalNFCScans;
      sendMessage("event", "nfc_scanned", data.as<JsonObject>());
      
      Serial.printf("[NFC] UID: %s\n", uidString.c_str());
    }
  }
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
          
          StaticJsonDocument<256> data;
          data["chip_idx"] = i;
          data["addr"] = String("0x") + String(mcp.addr, HEX);
          data["pin"] = pin;
          data["state"] = current ? "HIGH" : "LOW";
          data["active"] = !current;
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
  digitalWrite(PIN_EN, LOW);
  
  Serial.begin(PC_BAUD);
  Serial2.begin(SCANNER_BAUD, SERIAL_8N1, RX2_PIN, TX2_PIN);
  
  delay(1000);
  
  Serial.println("\n========================================");
  Serial.println("ESP32 헬스장 컨트롤러 " + VERSION);
  Serial.println("1/2 마이크로스텝 (400 스텝/회전)");
  Serial.println("바코드 + NFC 통합 (SPI 모드)");
  Serial.println("========================================");
  
  // I2C 초기화 (MCP23017용)
  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(100000);
  delay(100);
  
  // MCP23017 스캔
  scanMCP();
  
  // SPI 초기화 (PN532용)
  SPI.begin();
  
  // NFC 초기화
  initNFC();
  
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
  if (nfcAvailable) processNFC();
  processCommand();
  
  delay(5);
}

