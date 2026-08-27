#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <SensirionI2cScd4x.h>
#include <SensirionErrors.h>
#include <Arduino_PortentaMachineControl.h>
#include "secrets.h"
#include "web_ui.h"

#define RTD_RREF     400.0f
#define RTD_RNOMINAL 100.0f

SensirionI2cScd4x scd4x;
WiFiServer server(80);
TwoWire* activeWire = &Wire;
const char* activeWireName = "Wire";

const uint32_t WIFI_RETRY_DELAY_MS = 500;
const uint32_t WIFI_CONNECT_TIMEOUT_MS = 30000;
const uint32_t WIFI_RECONNECT_INTERVAL_MS = 10000;
const uint32_t SERIAL_WAIT_TIMEOUT_MS = 2000;
const uint32_t SENSOR_INIT_DELAY_MS = 1000;
const uint32_t SENSOR_WAKE_DELAY_MS = 30;
const uint32_t MEASUREMENT_INTERVAL_MS = 5000;
const uint32_t SENSOR_STARTUP_WAIT_MS = 5000;

uint16_t currentCo2 = 0;
float currentHumidity = 0.0f;
float currentBoxTemp = 0.0f;   // PT100 channel 0 (in box)
float currentOuterTemp = 0.0f; // PT100 channel 1 (outside)
unsigned long lastMeasurement = 0;
const uint8_t HISTORY_SIZE = 240;
uint16_t co2History[HISTORY_SIZE];
float boxtempHistory[HISTORY_SIZE];
float humidityHistory[HISTORY_SIZE];
float outertempHistory[HISTORY_SIZE];
uint8_t historyCount = 0;
uint8_t historyIndex = 0;

void recordMeasurement() {
  co2History[historyIndex] = currentCo2;
  boxtempHistory[historyIndex] = currentBoxTemp;
  humidityHistory[historyIndex] = currentHumidity;
  outertempHistory[historyIndex] = currentOuterTemp;
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
                ",\"boxtemp\":" + String(currentBoxTemp, 1) +
                ",\"humidity\":" + String(currentHumidity, 1) +
                ",\"outertemp\":" + String(currentOuterTemp, 1) +
                ",\"history\":[";
  uint8_t firstIndex = (historyCount == HISTORY_SIZE) ? historyIndex : 0;
  for (uint8_t i = 0; i < historyCount; i++) {
    uint8_t index = (firstIndex + i) % HISTORY_SIZE;
    if (i > 0) {
      json += ',';
    }
    json += "{\"co2\":" + String(co2History[index]) +
            ",\"boxtemp\":" + String(boxtempHistory[index], 1) +
            ",\"humidity\":" + String(humidityHistory[index], 1) +
            ",\"outertemp\":" + String(outertempHistory[index], 1) + "}";
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

void haltWithDelay() {
  while (1) {
    delay(SENSOR_INIT_DELAY_MS);
  }
}

bool waitForSerial(uint32_t timeoutMs) {
  unsigned long start = millis();
  while (!Serial && millis() - start < timeoutMs) {
    delay(10);
  }
  return static_cast<bool>(Serial);
}

bool connectWiFi(uint32_t timeoutMs) {
  if (WiFi.status() == WL_CONNECTED) {
    return true;
  }

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < timeoutMs) {
    delay(WIFI_RETRY_DELAY_MS);
    Serial.print('.');
  }
  return WiFi.status() == WL_CONNECTED;
}

bool initializeSCD4x(TwoWire& bus, const char* busName) {
  bus.begin();
  bus.setClock(100000);
  delay(SENSOR_INIT_DELAY_MS);

  scd4x.begin(bus, SCD41_I2C_ADDR_62);
  scd4x.wakeUp();
  delay(SENSOR_WAKE_DELAY_MS);

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
  waitForSerial(SERIAL_WAIT_TIMEOUT_MS);

  Serial.print("Connecting to ");
  Serial.println(WIFI_SSID);
  bool wifiConnected = connectWiFi(WIFI_CONNECT_TIMEOUT_MS);
  Serial.println();
  if (wifiConnected) {
    Serial.print("Webseite: http://");
    Serial.println(WiFi.localIP());
    server.begin();
  } else {
    Serial.println("WiFi not connected yet, starting in offline mode.");
  }

  Serial.println("Initializing SCD4x...");
  bool sensorReady = false;
  sensorReady = initializeSCD4x(Wire, "Wire") ||
                initializeSCD4x(Wire1, "Wire1");
  if (!sensorReady) {
    Serial.println("No SCD4x detected on Wire or Wire1.");
    haltWithDelay();
  }

  MachineControl_RTDTempProbe.begin(THREE_WIRE);
  MachineControl_RTDTempProbe.selectChannel(0);
  Serial.println("PT100 RTD initialized (ch0=box, ch1=outer).");

  uint16_t error = scd4x.startPeriodicMeasurement();
  if (error) {
    printMeasurementError("start periodic measurement", error);
    Serial.println("Check the I2C wiring, bus selection, and sensor power.");
    haltWithDelay();
  }
  Serial.println("Waiting for SCD4x measurement...");
  delay(SENSOR_STARTUP_WAIT_MS);
}

void loop() {
  static unsigned long lastReconnectAttempt = 0;
  if (WiFi.status() != WL_CONNECTED &&
      millis() - lastReconnectAttempt >= WIFI_RECONNECT_INTERVAL_MS) {
    lastReconnectAttempt = millis();
    Serial.println("Reconnecting WiFi...");
    if (connectWiFi(WIFI_CONNECT_TIMEOUT_MS)) {
      Serial.println();
      Serial.print("Webseite: http://");
      Serial.println(WiFi.localIP());
      server.begin();
    } else {
      Serial.println();
      Serial.println("WiFi reconnect timed out.");
    }
  }

  handleHttpClient();
  if (millis() - lastMeasurement < MEASUREMENT_INTERVAL_MS) {
    return;
  }
  lastMeasurement = millis();

  uint16_t error;
  float scdTemp = 0.0f; // SCD41 temperature used only for humidity compensation
  error = scd4x.readMeasurement(currentCo2, scdTemp, currentHumidity);
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

  // Read PT100 box temperature (channel 1)
  MachineControl_RTDTempProbe.selectChannel(1);
  currentBoxTemp = MachineControl_RTDTempProbe.readTemperature(RTD_RNOMINAL, RTD_RREF);
  uint8_t faultBox = MachineControl_RTDTempProbe.readFault();
  if (faultBox) {
    MachineControl_RTDTempProbe.clearFault();
    currentBoxTemp = 0.0f;
  }

  // Read PT100 outer temperature (channel 0)
  MachineControl_RTDTempProbe.selectChannel(0);
  currentOuterTemp = MachineControl_RTDTempProbe.readTemperature(RTD_RNOMINAL, RTD_RREF);
  uint8_t faultOuter = MachineControl_RTDTempProbe.readFault();
  if (faultOuter) {
    MachineControl_RTDTempProbe.clearFault();
    currentOuterTemp = 0.0f;
  }

  recordMeasurement();

  Serial.print("CO2: ");
  Serial.print(currentCo2);
  Serial.print(" ppm | Box: ");
  Serial.print(currentBoxTemp, 2);
  Serial.print(" C | Outer: ");
  Serial.print(currentOuterTemp, 2);
  Serial.print(" C | Hum: ");
  Serial.print(currentHumidity, 2);
  Serial.println(" %RH");

}
