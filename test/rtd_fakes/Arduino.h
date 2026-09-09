#pragma once
#include <stdint.h>
#include <stddef.h>
constexpr int OUTPUT = 1, HIGH = 1, LOW = 0;
inline void pinMode(int, int) {}
inline void digitalWrite(int, int) {}
void delay(unsigned long milliseconds);
inline double sqrt(double value) { return __builtin_sqrt(value); }
