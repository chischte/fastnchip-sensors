#include "firmware/application.h"

#include <Arduino.h>

#include "firmware/time_utils.h"

namespace {
constexpr uint32_t SERIAL_BAUD_RATE = 115200;
constexpr uint32_t SERIAL_WAIT_TIMEOUT_MS = 2000;
constexpr uint32_t SERIAL_POLL_INTERVAL_MS = 10;
}  // namespace

Application::Application()
    : firmwareUpdater_(storage_),
      measurements_(sensors_, storage_),
      webServer_(measurements_, storage_, firmwareUpdater_) {}

void Application::begin() {
  beginSerial();
  storage_.begin();
  const uint32_t now = millis();
  sensors_.begin(now);
  measurements_.begin(now);
  webServer_.begin(now);
}

void Application::poll() {
  const uint32_t now = millis();
  measurements_.poll(now);
  webServer_.poll(now);
}

void Application::beginSerial() {
  Serial.begin(SERIAL_BAUD_RATE);
  const uint32_t startedAt = millis();
  while (!Serial &&
         !hasElapsed(millis(), startedAt, SERIAL_WAIT_TIMEOUT_MS)) {
    delay(SERIAL_POLL_INTERVAL_MS);
  }
}
