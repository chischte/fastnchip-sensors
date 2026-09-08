#pragma once

#include <stddef.h>
#include <stdint.h>
#define NAN (__builtin_nanf(""))
inline bool isfinite(float value) { return __builtin_isfinite(value); }
struct FakeSerial {
  template <typename T> void print(T) {}
  template <typename T> void println(T) {}
};
inline FakeSerial Serial;
