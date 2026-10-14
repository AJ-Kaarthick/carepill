# ESP32 Hardware Integration & Sensor Calibration Guide

This document specifies the exact physical wiring, actuator calibration, optical sensor tuning, and power requirements for the Smart Pill Dispenser physical prototype.

---

## 1. Pin Configuration Table

| Component | ESP32 GPIO | Electrical Type | Description |
|---|---|---|---|
| **Rotary Servo** | GPIO 13 | PWM / 50Hz | MG996R or SG90 180° servo driving rotary gate |
| **Sensor 1 (Pill Drop)** | GPIO 18 | Digital Input (Interrupt, Falling Edge) | 3.3V/5V Optical Breakbeam IR pair across exit chute |
| **Sensor 2 (Cup Pickup)**| GPIO 19 | Digital Input (Internal Pullup) | Microswitch or TCRT5000 optical proximity in cup cradle |
| **Status LED - Red** | GPIO 21 | Digital Output (220Ω resistor) | Urgent faults, caregiver escalation |
| **Status LED - Green** | GPIO 22 | Digital Output (220Ω resistor) | Pickup confirmed |
| **Status LED - Blue** | GPIO 23 | Digital Output (220Ω resistor) | Dispensing operation in progress |
| **Piezo Buzzer** | GPIO 25 | LEDC PWM Channel 0 | 2kHz acoustic buzzer alerts |

---

## 2. Power Supply & Brownout Prevention

> [!CAUTION]
> The ESP32 and rotary servo MUST NOT share an unbuffered 3.3V/5V USB power rail. Servo in-rush current during rotation can drop supply voltage below 2.7V, triggering ESP32 brownout resets and corrupted state.

### Recommended Power Rail Schematic
1. **Input**: 5V 2.5A DC wall adapter or dual 18650 Li-ion battery pack with BMS.
2. **Servo Rail**: Dedicated 5V rail with a 470µF – 1000µF electrolytic capacitor placed directly across the servo `VCC` and `GND` pins.
3. **ESP32 Rail**: AMS1117-3.3V low-dropout regulator feeding the 3.3V pin with 10µF ceramic filter capacitors.
4. **Common Ground**: All grounds (`ESP32 GND`, `Servo GND`, `Sensors GND`) must be tied together.

---

## 3. Sensor 1: Optical Breakbeam Pill Drop Counter

### Working Principle
Sensor 1 comprises an infrared LED emitter and phototransistor receiver positioned orthogonally across the pill exit chute. When a tablet falls, it interrupts the infrared beam, creating a momentary voltage spike or drop.

### Calibration Procedure
1. **Physical Alignment**: Mount emitter and photodiode directly opposite each other inside a blackened, light-shielded chamber to prevent ambient room light interference.
2. **Debounce Tuning**: In `esp32_pillbox.ino`, `SENSOR1_DEBOUNCE_US` is set to `25,000µs` (25ms). If a tablet bounces and triggers multiple counts:
   - Increase debounce to `35,000µs`.
   - If very small tablets are missed during rapid fall, decrease to `18,000µs`.
3. **Verification**: Drop 10 test tablets manually through the chute. Serial monitor should report exactly 10 pulses without duplicate triggers.

---

## 4. Sensor 2: Pickup Detection Sensor

### Working Principle
Sensor 2 establishes whether the medicine cup or pill has been retrieved by the patient.

### Implementation Options
- **Option A (Physical Microswitch - Recommended for prototype)**: Placed beneath the spring-loaded pill cup holder. When the cup is placed in the cradle, switch is depressed (LOW). When lifted, switch opens (HIGH).
- **Option B (IR Reflective Proximity TCRT5000)**: Detects cup proximity. Calibrate the onboard potentiometer until the digital output changes cleanly at 5mm distance.

---

## 5. Rotary Servo Dispenser Gate Timing

1. **Neutral Angle**: 0° (Chute closed).
2. **Dispense Angle**: Rotate in increments of 45° (`SERVO_NUDGE_DEG`) to align cartridge compartment with drop chute.
3. **Settling Delay**: 800ms (`SERVO_SETTLE_MS`) to allow tablet to freefall and clear Sensor 1 breakbeam before returning to neutral.
4. **Corrective Dispense**: If Sensor 1 detects 0 pills after Attempt 1, servo performs a ±10° oscillatory "agitation nudge" to free lodged tablets, then advances to the next position.

---

## 6. LAN Server Binding & LittleFS Offline Schedule Persistence

### Host Server Binding (0.0.0.0 vs 127.0.0.1)
By default, development servers running on `127.0.0.1` (localhost) reject incoming requests from external network devices. The ESP32 communicates over Wi-Fi, meaning FastAPI must bind to `0.0.0.0` so all network interfaces accept traffic:
```bash
./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

1. **Find Laptop IP**: Run `ip addr show` (Linux) or `ifconfig` / `ipconfig` to obtain your LAN IP address (e.g., `192.168.1.150`).
2. **Update Firmware**: In `firmware/esp32_pillbox.ino`, update:
   ```cpp
   const char* WIFI_SSID     = "YourLocalWiFi";
   const char* WIFI_PASSWORD = "YourPassword";
   const char* BACKEND_HOST  = "http://192.168.1.150:8000";
   ```
3. **LittleFS Standalone Resilience**:
   Upon boot, the firmware invokes `GET /api/device/schedule-sync` to download today's dosing queue and saves it to LittleFS flash (`/schedules.json`).
   - If Wi-Fi is lost, the ESP32's internal RTC continues tracking alarm deadlines.
   - When dose time arrives, the device plays the pre-dose buzzer, opens the servo, counts Sensor 1 pulses, and sounds the pickup reminder.
   - Dispense events are written to `/offline_events.json` and flushed back to the FastAPI backend as soon as Wi-Fi reconnects via `POST /api/device/telemetry/heartbeat`.
