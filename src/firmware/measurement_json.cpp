#include "firmware/measurement_json.h"

namespace {
String nullableNumber(float value, bool valid) {
  return valid && isfinite(value) ? String(value, 2) : String("null");
}

const char* booleanJson(bool value) {
  return value ? "true" : "false";
}
}  // namespace

void appendMeasurementJson(String& json, const Measurement& measurement,
                           uint32_t bootId) {
  json += "{\"boot_id\":" + String(bootId);
  json += ",\"sequence\":" + String(measurement.sequence);
  json += ",\"uptime_ms\":" + String(measurement.uptimeMs);
  json += ",\"co2\":";
  json += measurement.co2Valid ? String(measurement.co2) : String("null");
  json += ",\"boxtemp\":" +
          nullableNumber(measurement.boxTemperature,
                         measurement.boxTemperatureValid);
  json += ",\"humidity\":" +
          nullableNumber(measurement.humidity, measurement.humidityValid);
  json += ",\"outertemp\":" +
          nullableNumber(measurement.outerTemperature,
                         measurement.outerTemperatureValid);
  json += ",\"valid\":{\"co2\":";
  json += booleanJson(measurement.co2Valid);
  json += ",\"boxtemp\":";
  json += booleanJson(measurement.boxTemperatureValid);
  json += ",\"humidity\":";
  json += booleanJson(measurement.humidityValid);
  json += ",\"outertemp\":";
  json += booleanJson(measurement.outerTemperatureValid);
  json += "},\"faults\":{\"rtd_box\":" + String(measurement.boxFault);
  json += ",\"rtd_outer\":" + String(measurement.outerFault) + "}}";
}
