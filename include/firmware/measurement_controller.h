#pragma once

#include <Arduino.h>

#include "config.h"
#include "firmware/measurement.h"
#include "firmware/qspi_storage.h"
#include "firmware/sensor_manager.h"

class MeasurementController {
 public:
  MeasurementController(SensorManager& sensors, QspiStorage& storage);

  void begin(uint32_t now);
  void poll(uint32_t now);

  const Measurement& current() const;
  const Measurement& historyAt(size_t chronologicalIndex) const;
  size_t historyCount() const;
  uint32_t bootId() const;
  bool sensorReady() const;
  uint16_t sensorErrorCount() const;

 private:
  void acquire(uint32_t now);
  void addToHistory(const Measurement& measurement);
  void printMeasurement(const Measurement& measurement) const;
  void printValue(float value, bool valid) const;

  SensorManager& sensors_;
  QspiStorage& storage_;
  Measurement current_;
  Measurement history_[Config::HISTORY_SIZE];
  size_t historyCount_ = 0;
  size_t nextHistoryIndex_ = 0;
  uint32_t bootId_ = 0;
  uint32_t lastMeasurementAt_ = 0;
};
