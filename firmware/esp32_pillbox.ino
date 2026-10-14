/*
 * ==============================================================================
 * Smart Pill Dispenser — ESP32 Firmware Integration Scaffold
 * College Innovative Design Project (IDP)
 *
 * Microcontroller: ESP32 (ESP-WROOM-32 / NodeMCU-32S)
 * Actuators: Rotary Dispensing Mechanism (Servo / Stepper via PWM)
 * Sensors:
 *   - Sensor 1 (GPIO 18): Breakbeam / Optical Drop Counter (Interrupt-driven)
 *   - Sensor 2 (GPIO 19): Pill Cup / Pickup Detection (Debounced Optical / Switch)
 * Indicators:
 *   - RGB Status LED (GPIO 21, 22, 23 or WS2812B on GPIO 21)
 *   - Piezo Buzzer (GPIO 25 - PWM Tone Channel 0)
 * Storage: LittleFS / Non-Volatile Storage (NVS) for offline schedule cache
 * Connectivity: Wi-Fi (HTTP REST Client + Offline Event Reconciler)
 * ==============================================================================
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <LittleFS.h>
#include <ESP32Servo.h>

// -----------------------------------------------------------------------------
// 1. HARDWARE PIN ASSIGNMENTS (Configurable Placeholders)
// -----------------------------------------------------------------------------
#define PIN_SERVO_PWM          13  // Rotary dispensing servo signal
#define PIN_SENSOR1_DROP       18  // Sensor 1: Optical pill drop counter (Interrupt)
#define PIN_SENSOR2_PICKUP     19  // Sensor 2: Pill cup pickup detection (Digital IN)
#define PIN_LED_RED            21  // Red LED pin (Urgent faults / Escalation)
#define PIN_LED_GREEN          22  // Green LED pin (Confirmed pickup)
#define PIN_LED_BLUE           23  // Blue LED pin (Dispensing in progress)
#define PIN_BUZZER             25  // Active/Passive Piezo buzzer (LEDC PWM)

// -----------------------------------------------------------------------------
// 2. TIMING & SAFETY LIMITS
// -----------------------------------------------------------------------------
#define MAX_CORRECTION_ATTEMPTS  3     // Bounded correction limit
#define SERVO_NUDGE_DEG          45    // Degrees per dispensing attempt
#define SERVO_SETTLE_MS          800   // Wait time for pill to fall past Sensor 1
#define SENSOR1_DEBOUNCE_US      25000 // 25ms optical beam break debounce
#define SENSOR2_POLL_INTERVAL_MS 500   // Pickup sensor polling interval
#define REMINDER_5M_MS           300000
#define ESCALATION_10M_MS        600000

// Wi-Fi & Backend Endpoint Configuration
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* BACKEND_HOST  = "http://192.168.1.100:8000"; // Local FastAPI Server
const char* DEVICE_ID     = "ESP32_PILLBOX_01";

// -----------------------------------------------------------------------------
// 3. SYSTEM STATE MACHINE
// -----------------------------------------------------------------------------
enum SystemState {
  STATE_IDLE,
  STATE_PRE_DOSE_REMINDER,
  STATE_DISPENSING,
  STATE_DISPENSING_VERIFY,
  STATE_CORRECTIVE_DISPENSING,
  STATE_AWAITING_COLLECTION,
  STATE_COLLECTION_REMINDER,
  STATE_COLLECTED,
  STATE_ESCALATED,
  STATE_DISPENSING_FAULT,
  STATE_SENSOR_FAULT
};

SystemState currentState = STATE_IDLE;
Servo dispenserServo;

// Telemetry & Sensor Counters
volatile unsigned long sensor1PulseCount = 0;
volatile unsigned long lastSensor1InterruptUs = 0;
bool cupPresent = false;
unsigned long dispenseCompletedTime = 0;
int currentCorrectionAttempt = 0;
int targetPillCount = 0;
String currentDoseId = "";

// -----------------------------------------------------------------------------
// 4. INTERRUPT SERVICE ROUTINES (Sensor 1 - Breakbeam Pill Counter)
// -----------------------------------------------------------------------------
void IRAM_ATTR isr_sensor1_pill_drop() {
  unsigned long nowUs = micros();
  if (nowUs - lastSensor1InterruptUs > SENSOR1_DEBOUNCE_US) {
    sensor1PulseCount++;
    lastSensor1InterruptUs = nowUs;
  }
}

// -----------------------------------------------------------------------------
// 5. SOUND & LED PATTERN GENERATOR (Matching Application Table)
// -----------------------------------------------------------------------------
void setIndicators(SystemState state) {
  switch (state) {
    case STATE_IDLE:
      digitalWrite(PIN_LED_RED, LOW);
      digitalWrite(PIN_LED_GREEN, LOW);
      digitalWrite(PIN_LED_BLUE, LOW);
      ledcWriteTone(0, 0); // Silent
      break;

    case STATE_PRE_DOSE_REMINDER:
      // Soft amber: Red + Green low pulse
      digitalWrite(PIN_LED_RED, HIGH);
      digitalWrite(PIN_LED_GREEN, HIGH);
      digitalWrite(PIN_LED_BLUE, LOW);
      ledcWriteTone(0, 1000); delay(100); ledcWriteTone(0, 0); delay(100);
      ledcWriteTone(0, 1000); delay(100); ledcWriteTone(0, 0);
      break;

    case STATE_DISPENSING:
      // Blue running indication + motor operational tick
      digitalWrite(PIN_LED_RED, LOW);
      digitalWrite(PIN_LED_GREEN, LOW);
      digitalWrite(PIN_LED_BLUE, HIGH);
      ledcWriteTone(0, 2000); delay(50); ledcWriteTone(0, 0);
      break;

    case STATE_AWAITING_COLLECTION:
      // Amber slow breathe
      digitalWrite(PIN_LED_RED, HIGH);
      digitalWrite(PIN_LED_GREEN, HIGH);
      digitalWrite(PIN_LED_BLUE, LOW);
      ledcWriteTone(0, 0);
      break;

    case STATE_COLLECTION_REMINDER:
      // 5-min uncollected reminder: Rapid amber strobe + 3 distinct beeps
      for (int i = 0; i < 3; i++) {
        digitalWrite(PIN_LED_RED, HIGH); digitalWrite(PIN_LED_GREEN, HIGH);
        ledcWriteTone(0, 1500); delay(150);
        digitalWrite(PIN_LED_RED, LOW); digitalWrite(PIN_LED_GREEN, LOW);
        ledcWriteTone(0, 0); delay(150);
      }
      break;

    case STATE_COLLECTED:
      // Confirmed pickup: Green flash + cheerful ascending 2-tone chime
      digitalWrite(PIN_LED_RED, LOW);
      digitalWrite(PIN_LED_GREEN, HIGH);
      digitalWrite(PIN_LED_BLUE, LOW);
      ledcWriteTone(0, 1200); delay(120);
      ledcWriteTone(0, 1800); delay(200);
      ledcWriteTone(0, 0);
      delay(1500);
      digitalWrite(PIN_LED_GREEN, LOW);
      break;

    case STATE_ESCALATED:
      // 10-min caregiver escalation: Urgent red strobe + hi-lo siren
      for (int i = 0; i < 4; i++) {
        digitalWrite(PIN_LED_RED, HIGH);
        ledcWriteTone(0, 2400); delay(200);
        digitalWrite(PIN_LED_RED, LOW);
        ledcWriteTone(0, 800); delay(200);
      }
      ledcWriteTone(0, 0);
      break;

    case STATE_DISPENSING_FAULT:
    case STATE_SENSOR_FAULT:
      // Solid red warning + continuous alert
      digitalWrite(PIN_LED_RED, HIGH);
      digitalWrite(PIN_LED_GREEN, LOW);
      digitalWrite(PIN_LED_BLUE, LOW);
      ledcWriteTone(0, 500); delay(500); ledcWriteTone(0, 0);
      break;
  }
}

// -----------------------------------------------------------------------------
// 6. LOCAL TWO-SENSOR DISPENSING AND CORRECTION LOGIC
// -----------------------------------------------------------------------------
void executeDispenseSequence(String doseId, int cartridgeNum, int requiredPills) {
  currentDoseId = doseId;
  targetPillCount = requiredPills;
  currentCorrectionAttempt = 0;
  currentState = STATE_DISPENSING;
  setIndicators(currentState);

  unsigned long totalConfirmedPills = 0;

  while (totalConfirmedPills < targetPillCount && currentCorrectionAttempt < MAX_CORRECTION_ATTEMPTS) {
    currentCorrectionAttempt++;
    int missingThisStep = targetPillCount - totalConfirmedPills;
    Serial.printf("[DISPENSER] Attempt %d: Requesting %d pills from Cartridge %d\n",
                  currentCorrectionAttempt, missingThisStep, cartridgeNum);

    // Reset Sensor 1 counter before activating rotary servo
    sensor1PulseCount = 0;

    // Rotate servo to drop chamber
    dispenserServo.write(SERVO_NUDGE_DEG * currentCorrectionAttempt);
    delay(SERVO_SETTLE_MS);
    dispenserServo.write(0); // Return to neutral gate

    // Wait for optical drop sensor settling
    delay(300);
    unsigned long detectedThisStep = sensor1PulseCount;
    totalConfirmedPills += detectedThisStep;
    Serial.printf("[SENSOR 1] Detected %lu drop(s) this attempt. Total confirmed: %lu/%d\n",
                  detectedThisStep, totalConfirmedPills, targetPillCount);

    // Safety Check 1: Over-dispense detection
    if (totalConfirmedPills > targetPillCount) {
      Serial.println("[FAULT] Over-dispense detected! Halting rotary mechanism immediately.");
      currentState = STATE_DISPENSING_FAULT;
      setIndicators(currentState);
      reportDispenseResultToBackend(doseId, cartridgeNum, totalConfirmedPills, "over_dispense");
      return;
    }

    // Exact count reached
    if (totalConfirmedPills == targetPillCount) {
      break;
    }

    // Under-dispensed: Enter bounded correction state
    if (currentCorrectionAttempt < MAX_CORRECTION_ATTEMPTS) {
      currentState = STATE_CORRECTIVE_DISPENSING;
      setIndicators(currentState);
      delay(1000); // Wait 1 second before corrective retry
    }
  }

  // Safety Check 2: Max attempts exceeded
  if (totalConfirmedPills < targetPillCount) {
    Serial.printf("[FAULT] Under-dispense limit reached (%d attempts). Halted for patient safety.\n", currentCorrectionAttempt);
    currentState = STATE_DISPENSING_FAULT;
    setIndicators(currentState);
    reportDispenseResultToBackend(doseId, cartridgeNum, totalConfirmedPills, "under_dispense");
    return;
  }

  // Dispensing successful: Handover to Sensor 2 for pickup monitoring
  currentState = STATE_AWAITING_COLLECTION;
  dispenseCompletedTime = millis();
  setIndicators(currentState);
  reportDispenseResultToBackend(doseId, cartridgeNum, totalConfirmedPills, "success");
}

// -----------------------------------------------------------------------------
// 7. SENSOR 2 (PICKUP MONITORING & TIMED ESCALATIONS)
// -----------------------------------------------------------------------------
void monitorPickupSensor() {
  if (currentState != STATE_AWAITING_COLLECTION &&
      currentState != STATE_COLLECTION_REMINDER &&
      currentState != STATE_ESCALATED) {
    return;
  }

  // Read Sensor 2 (e.g. HIGH = cup lifted / pills removed)
  bool pickupDetected = (digitalRead(PIN_SENSOR2_PICKUP) == HIGH);

  if (pickupDetected) {
    Serial.println("[SENSOR 2] Pill cup pickup detected! Dose completed.");
    currentState = STATE_COLLECTED;
    setIndicators(currentState);
    reportPickupEventToBackend(currentDoseId, true);
    currentState = STATE_IDLE;
    setIndicators(currentState);
    return;
  }

  unsigned long elapsedMs = millis() - dispenseCompletedTime;

  // Escalation: 10 minutes uncollected
  if (elapsedMs >= ESCALATION_10M_MS && currentState != STATE_ESCALATED) {
    Serial.println("[ALARM] 10 Minutes uncollected. Triggering Caregiver Escalation!");
    currentState = STATE_ESCALATED;
    setIndicators(currentState);
  }
  // Reminder: 5 minutes uncollected
  else if (elapsedMs >= REMINDER_5M_MS && currentState == STATE_AWAITING_COLLECTION) {
    Serial.println("[REMINDER] 5 Minutes uncollected. Beeping reminder tone.");
    currentState = STATE_COLLECTION_REMINDER;
    setIndicators(currentState);
  }
}

// -----------------------------------------------------------------------------
// 8. WI-FI & BACKEND REPORTING (With Offline Queue Fallback)
// -----------------------------------------------------------------------------
void reportDispenseResultToBackend(String doseId, int cartNum, int confirmedPills, String status) {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(String(BACKEND_HOST) + "/api/device/dispense-result");
    http.addHeader("Content-Type", "application/json");

    StaticJsonDocument<256> doc;
    doc["command_id"] = "CMD_" + String(millis());
    doc["dose_id"] = doseId;
    doc["cartridge_number"] = cartNum;
    doc["requested_pills"] = targetPillCount;
    doc["confirmed_pills"] = confirmedPills;
    doc["correction_attempts"] = currentCorrectionAttempt;
    doc["status"] = status;
    doc["raw_telemetry"] = "ESP32 Breakbeam ISR counts confirmed: " + String(confirmedPills);

    String payload;
    serializeJson(doc, payload);
    int httpCode = http.POST(payload);
    Serial.printf("[HTTP] Dispense result reported: Code %d\n", httpCode);
    http.end();
  } else {
    Serial.println("[OFFLINE] Wi-Fi unavailable. Caching dispense event locally in LittleFS.");
    cacheOfflineEvent("dispense_result", doseId, confirmedPills, status);
  }
}

void reportPickupEventToBackend(String doseId, bool isCollected) {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(String(BACKEND_HOST) + "/api/device/pickup-event");
    http.addHeader("Content-Type", "application/json");

    StaticJsonDocument<256> doc;
    doc["device_id"] = DEVICE_ID;
    doc["dose_id"] = doseId;
    doc["is_collected"] = isCollected;

    String payload;
    serializeJson(doc, payload);
    int httpCode = http.POST(payload);
    Serial.printf("[HTTP] Pickup event reported: Code %d\n", httpCode);
    http.end();
  } else {
    Serial.println("[OFFLINE] Caching pickup event locally in LittleFS.");
    cacheOfflineEvent("pickup_event", doseId, 1, "collected");
  }
}

void cacheOfflineEvent(String type, String doseId, int pills, String status) {
  // Store offline events for batch reconciliation upon reconnect
  File f = LittleFS.open("/offline_events.json", "a");
  if (f) {
    StaticJsonDocument<200> doc;
    doc["type"] = type;
    doc["dose_id"] = doseId;
    doc["confirmed_pills"] = pills;
    doc["status"] = status;
    doc["timestamp"] = millis();
    serializeJson(doc, f);
    f.println();
    f.close();
  }
}

// -----------------------------------------------------------------------------
// 9. SETUP & MAIN LOOP
// -----------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n[BOOT] Smart Pill Dispenser Firmware Starting...");

  // Initialize GPIOs
  pinMode(PIN_SENSOR1_DROP, INPUT_PULLUP);
  pinMode(PIN_SENSOR2_PICKUP, INPUT_PULLUP);
  pinMode(PIN_LED_RED, OUTPUT);
  pinMode(PIN_LED_GREEN, OUTPUT);
  pinMode(PIN_LED_BLUE, OUTPUT);

  // Setup Buzzer PWM (Channel 0, 2000Hz, 8-bit)
  ledcSetup(0, 2000, 8);
  ledcAttachPin(PIN_BUZZER, 0);

  // Attach Interrupt for Sensor 1 (Falling edge on breakbeam optical drop)
  attachInterrupt(digitalPinToInterrupt(PIN_SENSOR1_DROP), isr_sensor1_pill_drop, FALLING);

  // Attach Servo
  dispenserServo.attach(PIN_SERVO_PWM);
  dispenserServo.write(0);

  // Initialize Local Filesystem for Offline Schedule Storage
  if (!LittleFS.begin(true)) {
    Serial.println("[WARN] LittleFS mount failed, formatting...");
  }

  // Connect to Wi-Fi
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("[WIFI] Connecting");
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 10) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n[WIFI] Connected! IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("\n[WIFI] Running in Autonomous Offline Mode.");
  }

  setIndicators(STATE_IDLE);
}

void loop() {
  // 1. Monitor Sensor 2 (pickup cup removal & timed reminders)
  monitorPickupSensor();

  // 2. Poll heartbeat & check pending server commands every 5 seconds
  static unsigned long lastHeartbeatMs = 0;
  if (millis() - lastHeartbeatMs > 5000) {
    lastHeartbeatMs = millis();
    // In full implementation, send /api/device/heartbeat and execute pending commands
  }

  delay(50);
}
