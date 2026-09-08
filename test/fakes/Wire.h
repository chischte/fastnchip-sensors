#pragma once
#include <stdint.h>
struct TwoWire {
  int index;
  void begin() {}
  void setClock(uint32_t) {}
};
inline TwoWire Wire{0};
inline TwoWire Wire1{1};
