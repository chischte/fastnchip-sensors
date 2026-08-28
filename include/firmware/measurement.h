#pragma once

#include <Arduino.h>

struct Measurement {
  uint32_t sequence = 0;
  uint32_t uptimeMs = 0;
  uint16_t co2 = 0;
  float boxTemperature = NAN;
  float outerTemperature = NAN;
  float humidity = NAN;
  uint8_t boxFault = 0;
  uint8_t outerFault = 0;
  bool co2Valid = false;
  bool boxTemperatureValid = false;
  bool outerTemperatureValid = false;
  bool humidityValid = false;
};
