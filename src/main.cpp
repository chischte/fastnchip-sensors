#include <Arduino.h>

#include "firmware/application.h"

namespace {
Application& application() {
  static Application instance;
  return instance;
}
}

void setup() {
  application().begin();
}

void loop() {
  application().poll();
}

