#include "firmware/measurement_controller.h"

#include "firmware/time_utils.h"

MeasurementController::MeasurementController(SensorManager& sensors,
                                             QspiStorage& storage)
    : sensors_(sensors), storage_(storage) {}

void MeasurementController::begin(uint32_t now) {
  bootId_ = storage_.nextBootId();
  lastMeasurementAt_ = now - Config::MEASUREMENT_INTERVAL_MS;
}

void MeasurementController::poll(uint32_t now) {
  sensors_.poll(now);
  if (!hasElapsed(now, lastMeasurementAt_, Config::MEASUREMENT_INTERVAL_MS)) {
    return;
  }

  lastMeasurementAt_ += Config::MEASUREMENT_INTERVAL_MS;
  if (hasElapsed(now, lastMeasurementAt_, Config::MEASUREMENT_INTERVAL_MS)) {
    lastMeasurementAt_ = now;
  }
  acquire(now);
}

const Measurement& MeasurementController::current() const {
  return current_;
}

const Measurement& MeasurementController::historyAt(
    size_t chronologicalIndex) const {
  const size_t oldestIndex =
      historyCount_ == Config::HISTORY_SIZE ? nextHistoryIndex_ : 0;
  return history_[(oldestIndex + chronologicalIndex) % Config::HISTORY_SIZE];
}

size_t MeasurementController::historyCount() const {
  return historyCount_;
}

uint32_t MeasurementController::bootId() const {
  return bootId_;
}

bool MeasurementController::sensorReady() const {
  return sensors_.isReady();
}

uint16_t MeasurementController::sensorErrorCount() const {
  return sensors_.errorCount();
}

void MeasurementController::acquire(uint32_t now) {
  Measurement measurement;
  measurement.sequence = current_.sequence + 1;
  measurement.uptimeMs = now;
  sensors_.read(measurement, now);

  current_ = measurement;
  addToHistory(measurement);
  storage_.append(measurement, bootId_);
  printMeasurement(measurement);
}

void MeasurementController::addToHistory(const Measurement& measurement) {
  history_[nextHistoryIndex_] = measurement;
  nextHistoryIndex_ = (nextHistoryIndex_ + 1) % Config::HISTORY_SIZE;
  if (historyCount_ < Config::HISTORY_SIZE) {
    ++historyCount_;
  }
}

void MeasurementController::printMeasurement(
    const Measurement& measurement) const {
  Serial.print("#");
  Serial.print(measurement.sequence);
  Serial.print(" CO2=");
  if (measurement.co2Valid) {
    Serial.print(measurement.co2);
  } else {
    Serial.print("invalid");
  }
  Serial.print(" box=");
  printValue(measurement.boxTemperature,
             measurement.boxTemperatureValid);
  Serial.print(" outer=");
  if (measurement.outerTemperatureValid) {
    Serial.println(measurement.outerTemperature);
  } else {
    Serial.println("invalid");
  }
}

void MeasurementController::printValue(float value, bool valid) const {
  if (valid) {
    Serial.print(value);
  } else {
    Serial.print("invalid");
  }
}
