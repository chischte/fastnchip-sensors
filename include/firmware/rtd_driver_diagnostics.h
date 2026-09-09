#pragma once

#include <stdint.h>

struct RtdDriverDiagnostics {
  uint8_t configBefore = 0;
  uint8_t configAfter = 0;
  bool configurationValid = false;
  uint32_t recoveries = 0;
};

// Implemented by the build adapter for the single shared MAX31865 converter.
void setRtdFilter50Hz(bool enabled);
uint16_t lastRtdRawCount();
void setRtdLeadCompensation(bool enabled);
RtdDriverDiagnostics lastRtdDiagnostics();
