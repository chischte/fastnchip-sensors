#pragma once

#include <stdint.h>

// Implemented by the build adapter for the single shared MAX31865 converter.
void setRtdFilter50Hz(bool enabled);
uint16_t lastRtdRawCount();
