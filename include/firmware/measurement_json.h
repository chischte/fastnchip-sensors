#pragma once

#include <Arduino.h>

#include "firmware/measurement.h"

void appendMeasurementJson(String& json, const Measurement& measurement,
                           uint32_t bootId);

void appendHistoryMeasurementJson(String& json,
                                  const Measurement& measurement);
