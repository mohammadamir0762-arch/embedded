#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <Wire.h>
#include <Adafruit_BMP280.h>
#include <SoftwareSerial.h>
#include <TinyGPSPlus.h>
#include <math.h>

/* -------- WIFI ACCESS POINT -------- */
const char* ssid = "VIT-Telemetry";
const char* password = "telemetry123";

/* -------- HARDWARE -------- */
ESP8266WebServer server(80);
Adafruit_BMP280 bmp;

const int Z_PIN = A0;
bool bmpFound = false;

float groundPressure = 1013.25;
int zBaseline = 0;

/* -------- GPS (u-blox NEO-6M, GPS6MV2 board) -------- */
// Wiring: GPS TX -> D5 (GPIO14), GPS RX -> D6 (GPIO12), VCC -> 3V3 or VIN, GND -> GND.
// If your wires are on other pins, change these two lines only.
const int GPS_RX_PIN = D5;   // ESP8266 receives here (connect to GPS TX)
const int GPS_TX_PIN = D6;   // ESP8266 sends here (connect to GPS RX)
const long GPS_BAUD = 9600;  // NEO-6M factory default

SoftwareSerial gpsSerial(GPS_RX_PIN, GPS_TX_PIN);
TinyGPSPlus gps;

unsigned long bootTime;
unsigned long lastGPSReport = 0;

/* -------- WEBPAGE -------- */
const char webpage[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Flight Data Recorder</title>

<style>
* { box-sizing: border-box; }

body {
  font-family: 'Segoe UI', Arial, sans-serif;
  background: #0d1117;
  color: #c9d1d9;
  margin: 0;
  padding: 15px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  border-bottom: 1px solid #30363d;
  padding-bottom: 14px;
  margin-bottom: 20px;
}

.heading {
  font-weight: bold;
  color: #f0f6fc;
}

.live {
  color: #3fb950;
  font-size: 0.78rem;
  font-weight: bold;
}

.dot {
  display: inline-block;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #3fb950;
  margin-right: 6px;
  animation: pulse 1.3s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}

.card, .panel {
  background: #161b22;
  padding: 15px;
  border-radius: 10px;
  border: 1px solid #30363d;
}

.card { text-align: center; }

.label {
  font-size: 0.7rem;
  color: #8b949e;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.value {
  font-size: 1.65rem;
  font-weight: bold;
  color: #58a6ff;
  margin: 8px 0;
  font-family: 'Courier New', monospace;
  overflow-wrap: anywhere;
}

.unit {
  font-size: 0.8rem;
  color: #8b949e;
}

.panel { margin-bottom: 18px; }

.panel-title {
  font-size: 0.9rem;
  font-weight: bold;
  color: #f0f6fc;
  margin-bottom: 12px;
}

.chart-box {
  height: 230px;
  width: 100%;
  position: relative;
}

canvas {
  width: 100%;
  height: 100%;
  display: block;
}

.gps-value {
  color: #3fb950;
  font-size: 1.1rem;
  font-family: 'Courier New', monospace;
  overflow-wrap: anywhere;
  line-height: 1.8;
}

.small {
  font-size: 0.75rem;
  color: #8b949e;
  line-height: 1.6;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.75rem;
}

th, td {
  padding: 9px 5px;
  text-align: left;
  border-bottom: 1px solid #30363d;
}

th {
  color: #8b949e;
  background: #21262d;
}

@media (max-width: 380px) {
  body { padding: 9px; }
  .value { font-size: 1.3rem; }
  th, td { font-size: 0.68rem; }
}
</style>
</head>

<body>

<div class="header">
  <div class="heading">FLIGHT DATA RECORDER</div>
  <div class="live"><span class="dot"></span>LIVE TELEMETRY</div>
</div>

<div class="grid">
  <div class="card">
    <div class="label">Altitude</div>
    <div class="value" id="alt">--</div>
    <div class="unit">Meters (relative)</div>
  </div>

  <div class="card">
    <div class="label">Pressure</div>
    <div class="value" id="pre">--</div>
    <div class="unit">hPa</div>
  </div>

  <div class="card">
    <div class="label">Temperature</div>
    <div class="value" id="tmp">--</div>
    <div class="unit">°C</div>
  </div>

  <div class="card">
    <div class="label">ADXL335 Z-axis</div>
    <div class="value" id="zraw">--</div>
    <div class="unit">ADC counts</div>
    <div class="small">Change: <span id="zchange">--</span></div>
  </div>
</div>

<div class="panel">
  <div class="panel-title">ALTITUDE WAVEFORM</div>
  <div class="chart-box">
    <canvas id="altChart"></canvas>
  </div>
  <div class="small">Live BMP280 pressure-based altitude • Last 60 samples</div>
</div>

<div class="panel">
  <div class="panel-title">
    <span class="dot" id="gpsDot"></span>LIVE GPS (NEO-6M)
  </div>

  <div class="small" id="gpsStatus">WAITING FOR GPS DATA...</div>
  <div class="gps-value" id="coords">--</div>
  <div class="small" id="gpsInfo">--</div>
</div>

<div class="panel">
  <div class="panel-title">TELEMETRY LOG</div>
  <table>
    <thead>
      <tr>
        <th>Time</th>
        <th>Alt (m)</th>
        <th>Pressure</th>
        <th>Z ADC</th>
      </tr>
    </thead>
    <tbody id="log"></tbody>
  </table>
</div>

<div class="small" style="text-align:center">
  ESP8266 SENSOR DASHBOARD
</div>

<script>
/* -------- ALTITUDE WAVEFORM -------- */
const canvas = document.getElementById("altChart");
const ctx = canvas.getContext("2d");
let altHistory = [];
let lastLogTime = 0;

function drawChart() {
  const rect = canvas.getBoundingClientRect();
  const w = rect.width;
  const h = rect.height;
  const ratio = window.devicePixelRatio || 1;

  canvas.width = Math.round(w * ratio);
  canvas.height = Math.round(h * ratio);
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);

  ctx.clearRect(0, 0, w, h);

  const left = 42, right = 8, top = 12, bottom = 25;
  const cw = w - left - right;
  const ch = h - top - bottom;

  let values = altHistory.map(p => p.alt);

  if (values.length < 2) {
    ctx.fillStyle = "#8b949e";
    ctx.fillText("Collecting altitude data...", 10, 25);
    return;
  }

  let min = Math.min(...values);
  let max = Math.max(...values);

  // Give the graph a visible range even if readings barely change.
  if (max - min < 1) {
    min -= 0.5;
    max += 0.5;
  }

  const padding = (max - min) * 0.15;
  min -= padding;
  max += padding;

  ctx.font = "10px Arial";
  ctx.strokeStyle = "#30363d";
  ctx.fillStyle = "#8b949e";
  ctx.lineWidth = 1;

  for (let i = 0; i <= 4; i++) {
    const y = top + ch * i / 4;
    ctx.beginPath();
    ctx.moveTo(left, y);
    ctx.lineTo(w - right, y);
    ctx.stroke();

    const label = (max - (max - min) * i / 4).toFixed(1);
    ctx.fillText(label, 1, y + 3);
  }

  const points = values.map((v, i) => ({
    x: left + (values.length === 1 ? 0 : i * cw / 59),
    y: top + (max - v) * ch / (max - min)
  }));

  // Filled waveform
  ctx.beginPath();
  ctx.moveTo(points[0].x, top + ch);
  points.forEach(p => ctx.lineTo(p.x, p.y));
  ctx.lineTo(points[points.length - 1].x, top + ch);
  ctx.closePath();
  ctx.fillStyle = "rgba(35, 134, 54, 0.14)";
  ctx.fill();

  // Waveform line
  ctx.beginPath();
  points.forEach((p, i) => {
    if (i === 0) ctx.moveTo(p.x, p.y);
    else ctx.lineTo(p.x, p.y);
  });
  ctx.strokeStyle = "#3fb950";
  ctx.lineWidth = 2;
  ctx.stroke();
}

/* -------- GPS PANEL -------- */
function toDMS(value, isLatitude) {
  const absolute = Math.abs(value);
  const degrees = Math.floor(absolute);
  const minutesFull = (absolute - degrees) * 60;
  const minutes = Math.floor(minutesFull);
  const seconds = ((minutesFull - minutes) * 60).toFixed(2);

  const direction = isLatitude
    ? (value >= 0 ? "N" : "S")
    : (value >= 0 ? "E" : "W");

  return degrees + "°" + minutes + "'" + seconds + '"' + direction;
}

function updateGPS(d) {
  const status = document.getElementById("gpsStatus");
  const dot = document.getElementById("gpsDot");
  const coords = document.getElementById("coords");
  const info = document.getElementById("gpsInfo");

  // No characters at all means the module is not talking to the ESP8266.
  if (!d.gpsChars) {
    dot.style.background = "#f85149";
    status.textContent = "NO DATA FROM GPS MODULE - CHECK WIRING (GPS TX -> D5)";
    coords.textContent = "--";
    info.textContent = "";
    return;
  }

  // Data is arriving but there is no position fix yet.
  if (!d.gpsFix) {
    dot.style.background = "#d29922";
    status.textContent = "SEARCHING FOR SATELLITES (" + d.sats + " in use)";
    coords.textContent = "Waiting for fix...";
    info.textContent = "Needs open sky. The first fix can take a few minutes.";
    return;
  }

  dot.style.background = "#3fb950";
  status.textContent = "GPS FIX - " + d.sats + " SATELLITES - HDOP " + d.hdop.toFixed(1);
  coords.textContent = toDMS(d.lat, true) + "  " + toDMS(d.lon, false);
  info.textContent = d.lat.toFixed(6) + ", " + d.lon.toFixed(6) +
    "  |  GPS altitude " + d.gpsAlt.toFixed(1) + " m  |  " +
    d.speed.toFixed(1) + " km/h  |  fix age " + (d.gpsAge / 1000).toFixed(1) + " s";
}

/* -------- SENSOR DATA -------- */
async function updateSensors() {
  try {
    const response = await fetch("/data", {cache: "no-store"});
    if (!response.ok) throw new Error("HTTP error");
    const d = await response.json();

    document.getElementById("alt").textContent = d.alt.toFixed(2);
    document.getElementById("pre").textContent = d.pre.toFixed(2);
    document.getElementById("tmp").textContent = d.tmp.toFixed(2);
    document.getElementById("zraw").textContent = d.zRaw;
    document.getElementById("zchange").textContent =
      (d.zRaw - d.zBase > 0 ? "+" : "") + (d.zRaw - d.zBase);

    updateGPS(d);

    altHistory.push({alt: d.alt});
    if (altHistory.length > 60) altHistory.shift();
    drawChart();

    const now = Date.now();

    // Add one log entry approximately every 2 seconds.
    if (now - lastLogTime > 2000) {
      lastLogTime = now;

      const time = new Date().toLocaleTimeString();
      const tbody = document.getElementById("log");
      const row = tbody.insertRow(0);

      [time, d.alt.toFixed(2), d.pre.toFixed(2), d.zRaw]
        .forEach(value => {
          const cell = row.insertCell();
          cell.textContent = value;
        });

      while (tbody.rows.length > 8) tbody.deleteRow(8);
    }
  } catch (error) {
    // The next polling cycle will retry.
  }
}

setInterval(updateSensors, 500);
updateSensors();
window.addEventListener("resize", drawChart);
</script>

</body>
</html>
)rawliteral";

/* -------- GPS INPUT -------- */
// Hand every waiting NMEA character to TinyGPSPlus. Called often so the
// software-serial buffer never overflows while the web server is busy.
void feedGPS() {
  while (gpsSerial.available() > 0) {
    gps.encode(gpsSerial.read());
  }
}

/* -------- ROOT PAGE -------- */
void handleRoot() {
  feedGPS();
  server.send_P(200, "text/html; charset=utf-8", webpage);
}

/* -------- SENSOR API -------- */
void handleData() {
  feedGPS();

  float alt = 0;
  float pre = 0;
  float tmp = 0;

  if (bmpFound) {
    pre = bmp.readPressure() / 100.0F;
    tmp = bmp.readTemperature();

    // Relative altitude using startup pressure as the reference.
    alt = bmp.readAltitude(groundPressure);
  }

  int zRaw = analogRead(Z_PIN);

  // A fix counts as live only if the last position is under 3 s old.
  bool gpsFix = gps.location.isValid() && gps.location.age() < 3000;

  String json = "{";
  json += "\"alt\":" + String(alt, 3) + ",";
  json += "\"pre\":" + String(pre, 2) + ",";
  json += "\"tmp\":" + String(tmp, 2) + ",";
  json += "\"zRaw\":" + String(zRaw) + ",";
  json += "\"zBase\":" + String(zBaseline) + ",";
  json += "\"bmpFound\":";
  json += bmpFound ? "true" : "false";
  json += ",\"gpsChars\":" + String(gps.charsProcessed());
  json += ",\"gpsFix\":";
  json += gpsFix ? "true" : "false";
  json += ",\"lat\":" + String(gpsFix ? gps.location.lat() : 0.0, 6);
  json += ",\"lon\":" + String(gpsFix ? gps.location.lng() : 0.0, 6);
  json += ",\"sats\":" + String(gps.satellites.isValid() ? gps.satellites.value() : 0);
  json += ",\"hdop\":" + String(gps.hdop.isValid() ? gps.hdop.hdop() : 0.0, 1);
  json += ",\"gpsAlt\":" + String(gps.altitude.isValid() ? gps.altitude.meters() : 0.0, 1);
  json += ",\"speed\":" + String(gps.speed.isValid() ? gps.speed.kmph() : 0.0, 1);
  json += ",\"gpsAge\":" + String(gpsFix ? (long)gps.location.age() : -1L);
  json += "}";

  server.send(200, "application/json", json);
}

/* -------- SETUP -------- */
void setup() {
  Serial.begin(115200);
  delay(500);

  // GPS on software serial (the hardware UART stays free for USB debugging).
  gpsSerial.begin(GPS_BAUD);

  // BMP280: SDA = GPIO4 (D2), SCL = GPIO5 (D1)
  Wire.begin(4, 5);

  bmpFound = bmp.begin(0x76);

  if (!bmpFound) {
    Serial.println("BMP280 not found at 0x76!");
  } else {
    Serial.println("BMP280 detected.");

    // Calibrate reference pressure at startup.
    float sum = 0;
    for (int i = 0; i < 20; i++) {
      sum += bmp.readPressure() / 100.0F;
      delay(50);
    }

    groundPressure = sum / 20.0F;

    Serial.print("Reference pressure: ");
    Serial.println(groundPressure);
  }

  // Establish the ADXL335 Z-axis startup baseline.
  long zSum = 0;
  for (int i = 0; i < 20; i++) {
    zSum += analogRead(Z_PIN);
    delay(5);
  }
  zBaseline = zSum / 20;

  Serial.print("Z-axis baseline: ");
  Serial.println(zBaseline);

  // Create Wi-Fi hotspot.
  WiFi.mode(WIFI_AP);
  WiFi.softAP(ssid, password);

  Serial.println();
  Serial.print("Connect Wi-Fi: ");
  Serial.println(ssid);
  Serial.print("Password: ");
  Serial.println(password);
  Serial.print("Dashboard: http://");
  Serial.println(WiFi.softAPIP());

  server.on("/", HTTP_GET, handleRoot);
  server.on("/data", HTTP_GET, handleData);
  server.begin();

  bootTime = millis();

  Serial.println("Dashboard is ready.");
}

/* -------- MAIN LOOP -------- */
void loop() {
  feedGPS();
  server.handleClient();

  // GPS status on the Serial Monitor every 5 s, for checking the wiring.
  if (millis() - lastGPSReport > 5000) {
    lastGPSReport = millis();
    Serial.print("GPS chars: ");
    Serial.print(gps.charsProcessed());
    Serial.print("  fix: ");
    Serial.print(gps.location.isValid() ? "yes" : "no");
    Serial.print("  sats: ");
    Serial.print(gps.satellites.isValid() ? gps.satellites.value() : 0);
    if (gps.location.isValid()) {
      Serial.print("  lat: ");
      Serial.print(gps.location.lat(), 6);
      Serial.print("  lon: ");
      Serial.print(gps.location.lng(), 6);
    }
    Serial.println();
  }
}
