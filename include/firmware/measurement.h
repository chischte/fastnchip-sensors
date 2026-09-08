#pragma once

#include <Arduino.h>

struct Measurement {
  uint32_t sequence = 0;
  uint32_t uptimeMs = 0;
  uint16_t co2 = 0;
  float boxTemperature = NAN;
  float outerTemperature = NAN;
  float humidity = NAN;
  float scdTemperature = NAN;
  float scdTemperatureOffset = NAN;
  uint64_t scdSerialNumber = 0;
  uint16_t boxRaw = 0;
  uint16_t outerRaw = 0;
  float boxTemperature60Hz = NAN;
  float outerTemperature60Hz = NAN;
  uint16_t boxRaw60Hz = 0;
  uint16_t outerRaw60Hz = 0;
  uint8_t boxFault60Hz = 0;
  uint8_t outerFault60Hz = 0;
  bool rtdComparison = false;
  uint8_t boxFault = 0;
  uint8_t outerFault = 0;
  bool co2Valid = false;
  bool boxTemperatureValid = false;
  bool outerTemperatureValid = false;
  bool humidityValid = false;
};
