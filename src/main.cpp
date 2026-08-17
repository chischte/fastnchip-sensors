#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <SensirionI2cScd4x.h>
#include <SensirionErrors.h>
#include "secrets.h"

SensirionI2cScd4x scd4x;
WiFiServer server(80);
TwoWire* activeWire = &Wire;
const char* activeWireName = "Wire";

uint16_t currentCo2 = 0;
float currentTemperature = 0.0f;
float currentHumidity = 0.0f;
unsigned long lastMeasurement = 0;
const uint8_t HISTORY_SIZE = 60;
uint16_t co2History[HISTORY_SIZE];
float temperatureHistory[HISTORY_SIZE];
float humidityHistory[HISTORY_SIZE];
uint8_t historyCount = 0;
uint8_t historyIndex = 0;

const char INDEX_HTML[] = R"rawliteral(
<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sensoren</title>
<style>
body{font-family:system-ui,sans-serif;max-width:1000px;margin:0 auto;padding:20px;background:#f3f6f4;color:#17211d}
h1{margin:0 0 4px}h2{margin:0 0 10px;font-size:1rem;color:#2a3630}p{color:#607068}.values{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.value,section{background:white;border:1px solid #d9e2dc;border-radius:8px;padding:16px;box-shadow:0 2px 8px #173b2412}.value strong{display:block;font-size:2rem;margin-top:8px}.unit{color:#607068}section{margin-top:16px}canvas{width:100%;height:220px;display:block}@media(max-width:650px){.values{grid-template-columns:1fr}.value strong{font-size:1.7rem}}
</style></head><body>
<div class="values"><div class="value">CO2<strong id="co2">--</strong><span class="unit">ppm</span></div>
<div class="value">Temperatur<strong id="temperature">--</strong><span class="unit">&deg;C</span></div>
<div class="value">Luftfeuchtigkeit<strong id="humidity">--</strong><span class="unit">%RH</span></div></div>
<section><h2>CO2 (0-20000 ppm)</h2><canvas id="chart-co2" width="900" height="220"></canvas></section>
<section><h2>Temperatur (20-40 &deg;C)</h2><canvas id="chart-temperature" width="900" height="220"></canvas></section>
<section><h2>Luftfeuchtigkeit (80-100 %RH)</h2><canvas id="chart-humidity" width="900" height="220"></canvas></section>
<script>
const series=[
  {id:'chart-co2',key:'co2',color:'#d65a4a',min:0,max:20000,unit:'ppm'},
  {id:'chart-temperature',key:'temperature',color:'#2878a8',min:20,max:40,unit:'°C'},
  {id:'chart-humidity',key:'humidity',color:'#3b8c62',min:80,max:100,unit:'%RH'}
];

function drawSeries(canvasId, history, cfg){
  const c=document.getElementById(canvasId),ctx=c.getContext('2d'),w=c.width,h=c.height;
  const left=62,right=12,top=12,bottom=30;
  const pw=w-left-right,ph=h-top-bottom;
  ctx.clearRect(0,0,w,h);
  if(!history.length){return;}

  ctx.strokeStyle='#d9e2dc';
  ctx.fillStyle='#607068';
  ctx.font='12px system-ui,sans-serif';
  ctx.textAlign='right';
  for(let i=0;i<=4;i++){
    const y=top+i*ph/4;
    const value=cfg.max-(cfg.max-cfg.min)*i/4;
    ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(left+pw,y);ctx.stroke();
    ctx.fillText(value.toFixed(cfg.key==='co2'?0:1),left-6,y+4);
  }

  ctx.beginPath();
  ctx.moveTo(left,top);
  ctx.lineTo(left,top+ph);
  ctx.lineTo(left+pw,top+ph);
  ctx.strokeStyle='#93a39a';
  ctx.stroke();

  const values=history.map(v=>Number(v[cfg.key]));
  ctx.strokeStyle=cfg.color;
  ctx.lineWidth=2;
  ctx.beginPath();
  values.forEach((v,i)=>{
    const clamped=Math.max(cfg.min,Math.min(cfg.max,v));
    const px=left+i*pw/Math.max(1,values.length-1);
    const py=top+(cfg.max-clamped)*ph/(cfg.max-cfg.min);
    i?ctx.lineTo(px,py):ctx.moveTo(px,py);
  });
  ctx.stroke();

  ctx.fillStyle='#607068';
  ctx.textAlign='center';
  const secs=Math.max(1,(history.length-1)*5);
  for(let i=0;i<=4;i++){
    const x=left+i*pw/4;
    const t=Math.round((secs-(secs*i/4))/60*10)/10;
    ctx.fillText(i===4?'jetzt':'-'+t+'m',x,h-8);
  }
}

function draw(history){series.forEach(s=>drawSeries(s.id,history,s));}
async function update(){try{let r=await fetch('/api/measurement'),d=await r.json();document.querySelector('#co2').textContent=d.co2;document.querySelector('#temperature').textContent=d.temperature.toFixed(1);document.querySelector('#humidity').textContent=d.humidity.toFixed(1);draw(d.history)}catch(e){console.log(e)}}update();setInterval(update,5000);
</script></body></html>
)rawliteral";

void recordMeasurement() {
  co2History[historyIndex] = currentCo2;
  temperatureHistory[historyIndex] = currentTemperature;
  humidityHistory[historyIndex] = currentHumidity;
  historyIndex = (historyIndex + 1) % HISTORY_SIZE;
  if (historyCount < HISTORY_SIZE) {
    historyCount++;
  }
}

void sendHttpResponse(WiFiClient &client, const char *contentType, const String &body) {
  client.println("HTTP/1.1 200 OK");
  client.print("Content-Type: ");
  client.println(contentType);
  client.print("Content-Length: ");
  client.println(body.length());
  client.println("Connection: close");
  client.println();
  client.print(body);
}

String measurementJson() {
  String json = "{\"co2\":" + String(currentCo2) +
                ",\"temperature\":" + String(currentTemperature, 1) +
                ",\"humidity\":" + String(currentHumidity, 1) +
                ",\"history\":[";
  uint8_t firstIndex = (historyCount == HISTORY_SIZE) ? historyIndex : 0;
  for (uint8_t i = 0; i < historyCount; i++) {
    uint8_t index = (firstIndex + i) % HISTORY_SIZE;
    if (i > 0) {
      json += ',';
    }
    json += "{\"co2\":" + String(co2History[index]) +
            ",\"temperature\":" + String(temperatureHistory[index], 1) +
            ",\"humidity\":" + String(humidityHistory[index], 1) + "}";
  }
  json += "]}";
  return json;
}

void handleHttpClient() {
  WiFiClient client = server.available();
  if (!client) {
    return;
  }

  String request = client.readStringUntil('\n');
  while (client.connected() && client.available()) {
    if (client.readStringUntil('\n') == "\r") {
      break;
    }
  }
  if (request.startsWith("GET /api/measurement")) {
    sendHttpResponse(client, "application/json", measurementJson());
  } else {
    sendHttpResponse(client, "text/html", INDEX_HTML);
  }
  delay(1);
  client.stop();
}

void printMeasurementError(const char* action, uint16_t error) {
  char message[96];
  errorToString(error, message, sizeof(message));
  Serial.print("SCD4x ");
  Serial.print(action);
  Serial.print(" error: ");
  Serial.print(error);
  Serial.print(" (");
  Serial.print(message);
  Serial.println(")");
}

bool initializeSCD4x(TwoWire& bus, const char* busName) {
  bus.begin();
  bus.setClock(100000);
  delay(1000);

  scd4x.begin(bus, SCD41_I2C_ADDR_62);
  scd4x.wakeUp();
  delay(30);

  uint16_t stopError = scd4x.stopPeriodicMeasurement();
  if (stopError) {
    printMeasurementError("stop periodic measurement", stopError);
  }

  uint64_t serialNumber = 0;
  uint16_t error = scd4x.getSerialNumber(serialNumber);
  if (error) {
    printMeasurementError("get serial number", error);
    return false;
  }

  activeWire = &bus;
  activeWireName = busName;
  Serial.print("SCD4x found on ");
  Serial.print(activeWireName);
  Serial.print(" (serial ");
  Serial.print((unsigned long)(serialNumber >> 32), HEX);
  Serial.print((unsigned long)(serialNumber & 0xFFFFFFFFUL), HEX);
  Serial.println(")");
  return true;
}

void setup() {
  Serial.begin(115200);
  while (!Serial) {
    delay(10);
  }

  Serial.print("Connecting to ");
  Serial.println(WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print('.');
  }
  Serial.println();
  Serial.print("Webseite: http://");
  Serial.println(WiFi.localIP());
  server.begin();

  Serial.println("Initializing SCD4x...");
  bool sensorReady = false;
  sensorReady = initializeSCD4x(Wire, "Wire") ||
                initializeSCD4x(Wire1, "Wire1");
  if (!sensorReady) {
    Serial.println("No SCD4x detected on Wire or Wire1.");
    while (1) {
      delay(1000);
    }
  }

  uint16_t error = scd4x.startPeriodicMeasurement();
  if (error) {
    printMeasurementError("start periodic measurement", error);
    Serial.println("Check the I2C wiring, bus selection, and sensor power.");
    while (1) {
      delay(1000);
    }
  }
  Serial.println("Waiting for SCD4x measurement...");
  delay(5000);
}

void loop() {
  handleHttpClient();
  if (millis() - lastMeasurement < 5000) {
    return;
  }
  lastMeasurement = millis();

  uint16_t error;

  error = scd4x.readMeasurement(currentCo2, currentTemperature, currentHumidity);
  if (error) {
    printMeasurementError("read measurement", error);
    delay(1000);
    return;
  }

  if (currentCo2 == 0) {
    Serial.println("No measurement available yet.");
    delay(1000);
    return;
  }

  recordMeasurement();

  Serial.print("CO2: ");
  Serial.print(currentCo2);
  Serial.print(" ppm | Temperature: ");
  Serial.print(currentTemperature, 2);
  Serial.print(" C | Humidity: ");
  Serial.print(currentHumidity, 2);
  Serial.println(" %RH");

}
