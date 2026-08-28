#include "firmware/sensor_manager.h"

#include <Arduino_PortentaMachineControl.h>
#include <SensirionErrors.h>

#include "config.h"
#include "firmware/time_utils.h"

namespace {
constexpr uint8_t PRIMARY_I2C_BUS = 0;
constexpr uint8_t SECONDARY_I2C_BUS = 1;

void printScdError(const char* operation, int16_t error) {
  char message[96];
  errorToString(error, message, sizeof(message));
  Serial.print(operation);
  Serial.print(": ");
  Serial.println(message);
}
}  // namespace

void SensorManager::begin(uint32_t now) {
  MachineControl_RTDTempProbe.begin(THREE_WIRE);
  Serial.print("RTD box=");
  Serial.print(Config::RTD_BOX_CHANNEL);
  Serial.print(" outer=");
  Serial.println(Config::RTD_OUTER_CHANNEL);
  startInitialization(PRIMARY_I2C_BUS, now);
}

void SensorManager::poll(uint32_t now) {
  if (ready_) {
    return;
  }
  if (initializationState_ != InitializationState::idle) {
    continueInitialization(now);
    return;
  }
  if (hasElapsed(now, lastInitializationAt_,
                 Config::SENSOR_RETRY_INTERVAL_MS)) {
    startInitialization(PRIMARY_I2C_BUS, now);
  }
}

void SensorManager::read(Measurement& measurement, uint32_t now) {
  readScd(measurement, now);
  readRtd(Config::RTD_BOX_CHANNEL, measurement.boxTemperature,
          measurement.boxTemperatureValid, measurement.boxFault);
  readRtd(Config::RTD_OUTER_CHANNEL, measurement.outerTemperature,
          measurement.outerTemperatureValid, measurement.outerFault);
}

bool SensorManager::isReady() const {
  return ready_;
}

uint16_t SensorManager::errorCount() const {
  return errorCount_;
}

void SensorManager::startInitialization(uint8_t busIndex, uint32_t now) {
  busIndex_ = busIndex;
  TwoWire& bus = busForIndex(busIndex_);
  bus.begin();
  bus.setClock(Config::I2C_CLOCK_HZ);
  scd4x_.begin(bus, SCD41_I2C_ADDR_62);
  scd4x_.wakeUp();
  stateStartedAt_ = now;
  initializationState_ = InitializationState::waitingAfterWake;
}

void SensorManager::continueInitialization(uint32_t now) {
  if (initializationState_ == InitializationState::waitingAfterWake &&
      hasElapsed(now, stateStartedAt_, Config::SCD_WAKE_DELAY_MS)) {
    scd4x_.stopPeriodicMeasurement();
    stateStartedAt_ = now;
    initializationState_ = InitializationState::waitingAfterStop;
    return;
  }
  if (initializationState_ == InitializationState::waitingAfterStop &&
      hasElapsed(now, stateStartedAt_, Config::SCD_STOP_DELAY_MS)) {
    finishInitialization(now);
  }
}

void SensorManager::finishInitialization(uint32_t now) {
  uint64_t serialNumber = 0;
  if (scd4x_.getSerialNumber(serialNumber)) {
    tryNextBus(now);
    return;
  }

  int16_t error = scd4x_.setTemperatureOffset(
      Config::SCD41_TEMPERATURE_OFFSET_C);
  if (error) {
    printScdError("offset", error);
  }
  error = scd4x_.setSensorAltitude(Config::SCD41_ALTITUDE_M);
  if (error) {
    printScdError("altitude", error);
  }
  error = scd4x_.setAutomaticSelfCalibrationEnabled(
      Config::SCD41_ASC_ENABLED);
  if (error) {
    printScdError("ASC", error);
  }
  if (scd4x_.startPeriodicMeasurement()) {
    tryNextBus(now);
    return;
  }

  ready_ = true;
  errorCount_ = 0;
  initializationState_ = InitializationState::idle;
  Serial.print("SCD4x: ");
  Serial.println(busName(busIndex_));
}

void SensorManager::tryNextBus(uint32_t now) {
  if (busIndex_ == PRIMARY_I2C_BUS) {
    startInitialization(SECONDARY_I2C_BUS, now);
    return;
  }
  initializationState_ = InitializationState::idle;
  lastInitializationAt_ = now;
  Serial.println("SCD4x unavailable; retry scheduled");
}

void SensorManager::readScd(Measurement& measurement, uint32_t now) {
  if (!ready_) {
    return;
  }

  bool dataReady = false;
  int16_t error = scd4x_.getDataReadyStatus(dataReady);
  float ignoredTemperature = NAN;
  if (!error && dataReady) {
    error = scd4x_.readMeasurement(measurement.co2, ignoredTemperature,
                                   measurement.humidity);
  }
  if (error) {
    recordScdError("read", error, now);
    return;
  }
  if (!dataReady || !measurement.co2) {
    return;
  }

  measurement.co2Valid = true;
  measurement.humidityValid = isfinite(measurement.humidity) &&
                              measurement.humidity >= Config::HUMIDITY_MIN_RH &&
                              measurement.humidity <= Config::HUMIDITY_MAX_RH;
  errorCount_ = 0;
}

void SensorManager::readRtd(uint8_t channel, float& value, bool& valid,
                            uint8_t& fault) {
  MachineControl_RTDTempProbe.selectChannel(channel);
  value = MachineControl_RTDTempProbe.readTemperature(
      Config::RTD_NOMINAL_OHMS, Config::RTD_REFERENCE_OHMS);
  fault = MachineControl_RTDTempProbe.readFault();
  valid = !fault && isfinite(value) &&
          value >= Config::RTD_MIN_TEMPERATURE_C &&
          value <= Config::RTD_MAX_TEMPERATURE_C;
  if (fault) {
    MachineControl_RTDTempProbe.clearFault();
  }
  if (!valid) {
    value = NAN;
  }
}

void SensorManager::recordScdError(const char* operation, int16_t error,
                                   uint32_t now) {
  printScdError(operation, error);
  ++errorCount_;
  if (errorCount_ < Config::SCD_MAX_CONSECUTIVE_ERRORS) {
    return;
  }
  ready_ = false;
  initializationState_ = InitializationState::idle;
  lastInitializationAt_ = now;
}

TwoWire& SensorManager::busForIndex(uint8_t busIndex) {
  return busIndex == PRIMARY_I2C_BUS ? Wire : Wire1;
}

const char* SensorManager::busName(uint8_t busIndex) const {
  return busIndex == PRIMARY_I2C_BUS ? "Wire" : "Wire1";
}
