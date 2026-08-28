#pragma once

#include <Arduino.h>

inline bool hasElapsed(uint32_t now, uint32_t since, uint32_t interval) {
  return static_cast<uint32_t>(now - since) >= interval;
}
