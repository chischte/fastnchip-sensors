#define assert(condition) do { if (!(condition)) return __LINE__; } while (false)
#ifdef _WIN32
extern "C" { int _fltused = 0; }
#endif
#include "config.h"
#include "firmware/sensor_manager.h"

void setRtdFilter50Hz(bool) {}
uint16_t lastRtdRawCount() { return 9000; }

void finishInitialization(SensorManager& sensor, uint32_t started) {
  sensor.poll(started + Config::SCD_WAKE_DELAY_MS);
  sensor.poll(started + Config::SCD_WAKE_DELAY_MS + Config::SCD_STOP_DELAY_MS);
}

int main() {
  SensorManager sensor;
  sensor.begin(0);
  finishInitialization(sensor, 0);
  assert(sensor.isReady());
  Measurement original;
  sensor.read(original, 6000);
  assert(original.co2Valid && original.scdSerialNumber == 1);

  // A quick swap can produce no I2C errors: the new sensor acknowledges in idle.
  fakeScd.serial = 2;
  fakeScd.measuring = false;
  Measurement missing;
  sensor.read(missing, 11000);
  assert(!missing.co2Valid);
  sensor.poll(6000 + Config::SCD_MEASUREMENT_TIMEOUT_MS - 1);
  assert(sensor.isReady());
  const uint32_t recovery = 6000 + Config::SCD_MEASUREMENT_TIMEOUT_MS;
  sensor.poll(recovery);
  assert(!sensor.isReady());
  finishInitialization(sensor, recovery);
  Measurement replacement;
  sensor.read(replacement, recovery + 6000);
  assert(replacement.co2Valid && replacement.scdSerialNumber == 2);
  assert(replacement.scdTemperatureOffset == Config::SCD41_TEMPERATURE_OFFSET_C);
  assert(fakeScd.starts == 2);

  // A missing device must not prevent PT100 sampling; retries also find Wire1.
  fakeScd.present = false;
  uint32_t now = recovery + 11000;
  for (int i = 0; i < Config::SCD_MAX_CONSECUTIVE_ERRORS; ++i) {
    Measurement disconnected;
    sensor.read(disconnected, now);
    assert(!disconnected.co2Valid && disconnected.boxTemperatureValid);
    now += 5000;
  }
  assert(!sensor.isReady());
  fakeScd.present = true;
  fakeScd.bus = 1;
  fakeScd.serial = 3;
  fakeScd.measuring = false;
  const uint32_t started = now - 5000;
  finishInitialization(sensor, started);
  finishInitialization(sensor, started + Config::SCD_WAKE_DELAY_MS + Config::SCD_STOP_DELAY_MS);
  Measurement otherBus;
  sensor.read(otherBus, now + 6000);
  assert(otherBus.co2Valid && otherBus.scdSerialNumber == 3);
  return 0;
}
