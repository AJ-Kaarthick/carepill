# CarePill — Smart Pill Dispenser & Caregiver Guardian System
### College Innovative Design Project (IDP) Prototype

CarePill is a senior-friendly, mobile-first smart medication dispenser system designed for elderly patients, family caregivers, and an ESP32-controlled physical pill box with a rotary servo dispensing mechanism and two optical feedback sensors.

---

## 1. System Architecture Overview

```
                          +------------------------------------------+
                          |   CarePill Web Application (Frontend)    |
                          |   - Senior-friendly, tactile UI          |
                          |   - WCAG AAA palette (#F7F6F1, #145A4A)  |
                          |   - Configurable Carousel (4/6/8 Slots)  |
                          |   - Caregiver SMS & WhatsApp Settings    |
                          |   - PWA Installable & Web Audio Cues     |
                          +--------------------+---------------------+
                                               |
                                     REST / JSON Protocols
                                               |
                          +--------------------v---------------------+
                          |      FastAPI Backend Engine (Port 8000)  |
                          |   - 2-Sensor State Machine Orchestrator  |
                          |   - Configurable 4/6/8 Hardware Service  |
                          |   - 4-Tier Reminder Timing Engine        |
                          |   - Deterministic Virtual Clock          |
                          |   - Auditable Stock Decrement Engine     |
                          |   - Prescription OCR & Review Gatekeeper |
                          |   - Multi-Channel Twilio SMS & WhatsApp  |
                          +----------+--------------------+----------+
                                     |                    |
                 +-------------------v---+    +-----------v----------+
                 | SQLite (pillbox.db)   |    | Hardware Sync Layer  |
                 | SQLAlchemy ORM Schema |    | REST Protocol Adapter|
                 +-----------------------+    +---+--------------+---+
                                                  |              |
                      +---------------------------+              +---------------------------+
                      |                                                                      |
           +----------v-----------+                                               +----------v-----------+
           | ESP32 Real Hardware  |                                               | Hardware Simulator   |
           | Firmware Scaffold    |                                               | - Interactive Drawer |
           | - Rotary Servo (PWM) |                                               | - 14 Test Scenarios  |
           | - Sensor 1 (Counter) |                                               | - Synthetic Buzzer   |
           | - Sensor 2 (Pickup)  |                                               | - Pre-Dose Timers    |
           | - LittleFS Cache     |                                               | - Offline Simulation |
           +----------------------+                                               +----------------------+
```

---

## 2. Key Hardened Features

### A. Configurable Patient-Specific Hardware (4, 6, or 8 Cartridges)
- **Default Count**: 4 circular cartridges.
- **Supported Expansions**: 6 or 8 circular cartridges.
- **Independent Device Scoping**: Each device (`device_id`) maintains isolated cartridge instances with calibrated servo offsets (e.g. 0°, 45°, 90°, etc.). Multiple patients with different cartridge configurations operate without collision.
- **Safe Reconfiguration**: When reducing cartridge count (e.g. 8 to 4), the backend verifies whether slots 5–8 contain active medication assignments or remaining stock. If found, reduction is safely blocked with details of affected cartridges unless explicitly confirmed (`force=True`).

### B. Four Deterministic Reminder & Escalation Timings
1. **-10 Minutes (Pre-Dose Reminder 1)**: Amber soft pulse + gentle double-chirp tone (`PRE_DOSE_REMINDER`).
2. **-5 Minutes (Pre-Dose Reminder 2)**: Prompts patient that medicine will drop soon (`PRE_DOSE_REMINDER`).
3. **+5 Minutes (Post-Dispense Collection Reminder)**: Triggered if medicine remains in tray 5m after drop. Amber strobe + repeating 3-beep tone (`COLLECTION_REMINDER`).
4. **+10 Minutes (Post-Dispense Escalation)**: Triggered if medicine remains in tray 10m after drop. Red siren strobe + urgent escalation dispatched to caregiver (`ESCALATED`).
- **Sensor 2 Cancellation**: Whenever Sensor 2 registers pill cup pickup, active reminders and escalations are immediately cleared (`COLLECTED`).

### C. Multi-Channel Caregiver Notifications & Explicit Opt-In Consent
- **Channels Supported**:
  - `simulated`: Local audit log with zero external credentials needed.
  - `sms`: Twilio cellular SMS.
  - `whatsapp`: Twilio WhatsApp messaging with standard `whatsapp:` prefixing.
  - `webhook`: Outbound JSON HTTP POST.
- **Opt-In Consent Gating**: Caregivers must explicitly consent to SMS and WhatsApp alerts in settings (`sms_consent`, `whatsapp_consent`). Attempted alerts without opt-in are rejected with clear compliance error messages.
- **Minimal Notification Copy**: All escalation messages follow the exact required format:
  `"CarePill alert: A scheduled medication has not been collected. Please check on the patient. Time: [time]."`
- **Idempotency**: Duplicate alerts for the same uncollected dose are blocked from re-dispatching.

---

## 3. Directory Structure

```
IDP Pill Box/
├── backend/
│   ├── app/
│   │   ├── api/             # REST Routers (auth, doses, cartridges, device, caregiver, simulator)
│   │   ├── models/          # SQLAlchemy relational models (User, Cartridge, DoseOccurrence, etc.)
│   │   ├── schemas/         # Typed Pydantic v2 schemas
│   │   ├── services/        # Orchestrator, device, inventory, notifications, OCR, clock
│   │   ├── config.py        # Settings (Twilio SMS/WhatsApp, pre-dose timings, supported counts)
│   │   ├── database.py      # SQLite engine & session management
│   │   ├── main.py          # FastAPI application entrypoint
│   │   └── seed.py          # Demo seeds (Eleanor & Marcus Vance)
│   ├── tests/
│   │   ├── test_two_sensors.py                # 7 unit tests (Sensor 1, Sensor 2, corrections)
│   │   ├── test_device_api.py                 # 3 hardware API & simulator tests
│   │   ├── test_hardening_and_notifications.py# 10 tests (4/6/8 cartridges, -10m/-5m, Twilio WhatsApp)
│   │   ├── conftest.py                        # Pytest StaticPool fixtures
│   │   └── verify_system.py                   # Full end-to-end verification script
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/      # Navbar, BottomNav, RefillModal, SetupCartridgeModal, Simulator
│   │   ├── pages/           # PatientDashboard, Medicines, Cartridges, Caregiver, Device
│   │   ├── services/        # API client and Web Audio synthesizer
│   │   ├── types/           # TypeScript data interfaces
│   │   ├── App.tsx          # Application shell & polling
│   │   └── index.css        # Tailwind CSS 4 accessible theme
│   ├── package.json
│   └── vite.config.ts
├── firmware/
│   ├── esp32_pillbox.ino        # ESP32 C++ firmware scaffold with FreeRTOS & LittleFS
│   └── HARDWARE_CALIBRATION.md  # Wiring schematic, servo angles, sensor debouncing
└── README.md
```

---

## 4. Quick Start & Launch Commands

### Prerequisites
- Python 3.10+ (Python 3.12 verified)
- Node.js 18+ (Node v24 verified)

### Step 1: Backend Setup & Launch
```bash
# Navigate to repository root
cd "IDP Pill Box"

# Activate Python virtual environment
source venv/bin/activate

# Launch the FastAPI backend
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
- **Backend API Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health Check**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

### Step 2: Frontend Setup & Launch
```bash
# Open a second terminal window
cd "IDP Pill Box/frontend"

# Launch the Vite development server
npm run dev
```
- **Web Application URL**: [http://localhost:5174](http://localhost:5174)
  *(Configured with `port: 5174` and `strictPort: true` to guarantee complete origin isolation from LearnFlow or any other application using port 5173).*

---

## 5. Environment Variables & Twilio Setup

Copy `.env.example` to `backend/.env`:
```bash
cp backend/.env.example backend/.env
```

To enable live SMS or WhatsApp delivery:
```ini
# Notification Provider: "simulated" (default), "twilio", or "webhook"
NOTIFICATION_PROVIDER=twilio

# Twilio Credentials
TWILIO_ACCOUNT_SID=ACXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_FROM_NUMBER=+15551234567

# Twilio WhatsApp Configuration
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
# Optional Twilio Content Template SID
TWILIO_WHATSAPP_TEMPLATE_SID=
```

---

## 6. How to Test & Verify

### A. Run Automated Pytest Suite (30 Tests)
```bash
cd backend
PYTHONPATH=. ../venv/bin/pytest -v
```
**Test Coverage Includes (30/30 Passing)**:
- `test_default_4_cartridges_and_expansion_to_6_and_8`: Verifies dynamic 4 -> 6 -> 8 hardware reconfiguration.
- `test_device_isolation_between_multiple_patients`: Confirms 4-, 6-, and 8-cartridge patient devices operate independently.
- `test_safe_downsizing_prevented_when_stocked_or_assigned`: Blocks silent stock loss when reducing carousel capacity.
- `test_all_four_reminder_timings_deterministic_clock`: Tests -10m, -5m, +5m, and +10m timings with virtual test clock.
- `test_sensor2_pickup_cancels_reminders_and_escalations`: Validates Sensor 2 cup pickup event.
- `test_caregiver_settings_and_test_notification_api`: Tests caregiver profile, contact update, and test alert trigger.
- `test_consent_gating_for_sms_and_whatsapp_with_twilio`: Enforces explicit caregiver opt-in consent.
- `test_twilio_whatsapp_formatting_and_prefix`: Validates `whatsapp:` prefixing and Content Template handling.
- `test_uncollected_alert_idempotency_protection`: Validates duplicate alert suppression.
- `test_exact_schedule_clock_times_and_prescribed_dose_qty`: Validates nested exact clock-time schedules (08:30, 20:30) and 1-5 dose quantities.
- `test_human_name_validation_and_medicine_name`: Enforces digit rejection in patient/caregiver names while permitting numbers in medications.
- `test_phone_number_validation_and_e164_normalization`: Validates International Phone input and E.164 normalization.
- `test_safe_medication_archival_and_dependencies`: Tests dependency analysis, draft deletion, stock guards, safe archival, and reactivation.
- `test_inactive_medication_excluded_from_daily_dose_generation`: Ensures archived medications generate zero future doses.
- `test_prescription_intelligence_extraction_and_hardware_sizing`: Tests OCR parsing with explicit meal choices.
- `test_simulated_dispensing_vs_physical_dispensing`: Verifies virtual vs physical telemetry pathways.
- `test_two_sensors.py`: Exact dispense, under-dispense correction, over-dispense halt, chute jam fault.

### B. Run End-to-End System Verification Script
```bash
PYTHONPATH=backend ./venv/bin/python backend/tests/verify_system.py
```
**Verification Output**:
```
==================================================
STARTING CAREPILL END-TO-END SYSTEM VERIFICATION
==================================================
[PASS] 1. /health check: OK
[PASS] 2. Users loaded: 2 users (Patient Eleanor, Caregiver Marcus)
[PASS] 3. 4 Physical Cartridges loaded and mapped correctly (Default count)
[TESTING] Configurable Hardware: 4 -> 6 -> 8 Cartridges
   [PASS] Successfully expanded to 6 circular cartridges
   [PASS] Successfully expanded to 8 circular cartridges
   [PASS] Successfully reconfigured back to standard 4 cartridges
[PASS] 5. Medication Schedules: 4 active schedules
[PASS] 6. Today's Chronological Dose Timeline: 4 doses generated
[TESTING] Pre-Dose Reminders (-10m and -5m)
   [PASS] -10m Pre-Dose Reminder: Triggered pre-dose reminder(s).
   [PASS] -5m Pre-Dose Reminder: Triggered pre-dose reminder(s).
[TESTING] Scenario: 2-Tablet Prescribed Dose with Under-dispense & Correction
   [A] Triggered Dispense -> State: dispensing
   [B] Sensor 1 detected 1 pill -> State: corrective_dispensing (Missing 1 pill)
   [C] Sensor 1 detected corrective pill -> State: awaiting_collection (2/2 confirmed)
[TESTING] Clock: Advancing 5 Minutes -> State: collection_reminder
[TESTING] Clock: Advancing another 5 Minutes -> State: escalated
   [F] Caregiver Alert Created with minimal text copy
   [G] Caregiver Acknowledged Alert successfully
   [H] Sensor 2 detected Medicine Cup Pickup -> State: collected!
[TESTING] Caregiver Notification Preferences & Test Alert
[TESTING] ESP32 Device Hardware Protocol Heartbeat & Offline Schedule Sync
[PASS] 11. Auditable Inventory Ledger: 5 transactions recorded
==================================================
ALL VERIFICATION CHECKS PASSED (100% SUCCESS)
==================================================
```

### C. Build Frontend Production Bundle
```bash
npm --prefix frontend run build
```
- **Result**: Zero TypeScript or lint errors. Built production client in ~500ms.

---

## 7. Service Worker Isolation & Browser Origin Hygiene

### The Issue & Root Cause
When two separate web applications run on `http://localhost:5173`, modern browsers (such as Firefox) bind registered Service Workers to the entire origin (`scheme://host:port`). If CarePill previously registered a service worker on `localhost:5173`, and LearnFlow was subsequently served on the same origin, Firefox routed LearnFlow requests through CarePill's service worker cache, leading to failed script imports (`/src/main.tsx`) and white-screen errors.

### Solution & Guardrails
1. **Dedicated Development Port**: CarePill now uses `port: 5174` with `strictPort: true` in `frontend/vite.config.ts`. If port 5174 is busy, Vite terminates with an error instead of automatically falling back to 5173.
2. **Dev Mode Unregistration**: In development (`import.meta.env.DEV`), `frontend/src/main.tsx` actively unregisters any existing Service Workers and never registers new ones.
3. **Production PWA Preservation**: In production (`import.meta.env.PROD`), `/sw.js` is registered cleanly on window `load` for offline capability.
4. **Safe Cleanup for Stale Browsers (No modifications to LearnFlow files)**:
   If a developer or user previously visited `http://localhost:5173` while CarePill was running, run this one-liner in the browser DevTools Console on `http://localhost:5173`:
   ```javascript
   navigator.serviceWorker.getRegistrations().then(r => r.forEach(reg => reg.unregister()));
   caches.keys().then(keys => keys.forEach(k => caches.delete(k)));
   ```

---

## 8. Clinical Medication Safety Safeguards

### PRN / As-Needed Medication Safeguards
- **Dispenser Sizing**: Non-solid dosage forms (syrups, liquids, ointments) and PRN (as-needed) medications are flagged as `is_dispenser_supported: false`.
- **No Autonomous Dispense**: PRN medications are taken strictly on-demand based on clinical symptoms. They are excluded from:
  - Daily automatic dose occurrence generation in `DoseOrchestrator`.
  - ESP32 LittleFS offline schedule payloads (`/api/device/schedule` and `/api/device/schedule-sync`).
  - The schedule builder recurring time slots dropdown.

### Cartridge Stock Reconciliation & Quarantine Safeguards
- **No Silent Stock Deallocation**: If a caregiver attempts to archive a medication while physical pills remain in a cartridge, the system rejects the operation (`400 Bad Request`) unless explicit confirmation is provided.
- **Audit Logging**: Force-archiving a stocked medication requires caregiver identity and an archival rationale, generating an auditable `InventoryTransaction` (`reason: "archival_quarantine"`).
- **Physical Quarantine Lock**: The affected rotary slot is flagged with `needs_reconciliation = True` and a descriptive `quarantine_reason`. While in quarantine:
  - Dispensing is blocked (`dispensing_fault`).
  - Refills are blocked (`400 Bad Request`).
  - Reassignment to another medication is blocked (`400 Bad Request`).
- **Physical Clearance Verification**: Caregivers clear the quarantine state via `POST /api/cartridges/{num}/reconcile` after physically verifying that the carousel slot has been emptied.

---

## 9. ESP32 Hardware Integration & Firmware Scaffold

Firmware source: `firmware/esp32_pillbox.ino`
Wiring & calibration manual: `firmware/HARDWARE_CALIBRATION.md`

### Toolchain & Build Verification Status
- **Environment Status**: The Linux environment does not have embedded cross-compilers (`arduino-cli`, `platformio`, or `idf.py`) installed.
- **Board Configuration**:
  - Target Core: `esp32:esp32` (Espressif ESP32 Arduino Core >= 2.0.0)
  - Board Identifier: `esp32:esp32:esp32` (or `esp32:esp32:nodemcu-32s` / `esp32:esp32:esp32wrover`)
  - Target Microcontroller: ESP32-WROOM-32 / ESP-WROOM-32D
- **External Dependencies**:
  - `ArduinoJson` (v6.x or v7.x)
  - `ESP32Servo` (by Kevin Harrington / John K. Bennett)
  - `LittleFS` (built-in with ESP32 Arduino Core)
  - `WiFi` & `HTTPClient` (built-in with ESP32 Arduino Core)

### Compiling and Flashing with `arduino-cli`:
```bash
# 1. Install ESP32 Core and libraries
arduino-cli config init
arduino-cli config add board_manager.additional_urls https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
arduino-cli core update-index
arduino-cli core install esp32:esp32
arduino-cli lib install "ArduinoJson"
arduino-cli lib install "ESP32Servo"

# 2. Compile firmware
arduino-cli compile --fqbn esp32:esp32:esp32 firmware/esp32_pillbox.ino

# 3. Flash to ESP32 (replace /dev/ttyUSB0 with your device port)
arduino-cli upload -p /dev/ttyUSB0 --fqbn esp32:esp32:esp32 firmware/esp32_pillbox.ino
```

### LAN Binding for Physical Microcontroller Connection
When pairing the physical ESP32 over Wi-Fi, run FastAPI listening on `0.0.0.0` so other devices on your home or lab network can connect:
```bash
./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Update `WIFI_SSID`, `WIFI_PASSWORD`, and `BACKEND_HOST` in `firmware/esp32_pillbox.ino` with your local IP address (e.g., `http://192.168.1.150:8000`).

### LittleFS Flash Persistence
The ESP32 downloads the daily dosing queue into LittleFS on-board flash storage upon boot via `GET /api/device/schedule-sync`. If Wi-Fi drops, internal timers trigger acoustic and LED reminders autonomously. Event logs are stored locally in flash and re-synced via `POST /api/device/reconcile` when network connection restores.
