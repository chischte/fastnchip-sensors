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
  json += ",\"scdtemp\":" + nullableNumber(measurement.scdTemperature,
                                              measurement.co2Valid);
  json += ",\"scd_offset\":" + nullableNumber(measurement.scdTemperatureOffset,
                                                 measurement.co2Valid);
  json += ",\"scd_serial\":";
  if (measurement.co2Valid) {
    char serial[13];
    snprintf(serial, sizeof(serial), "%04lX%08lX",
             static_cast<unsigned long>(measurement.scdSerialNumber >> 32),
             static_cast<unsigned long>(measurement.scdSerialNumber & 0xFFFFFFFF));
    json += "\"" + String(serial) + "\"";
  } else {
    json += "null";
  }
  json += ",\"rtd_box_raw\":" + String(measurement.boxRaw);
  json += ",\"rtd_outer_raw\":" + String(measurement.outerRaw);
  if (measurement.rtdComparison) {
    json += ",\"rtd_comparison\":{\"box_60hz\":" +
        nullableNumber(measurement.boxTemperature60Hz, !measurement.boxFault60Hz);
    json += ",\"outer_60hz\":" +
        nullableNumber(measurement.outerTemperature60Hz, !measurement.outerFault60Hz);
    json += ",\"box_raw_60hz\":" + String(measurement.boxRaw60Hz);
    json += ",\"outer_raw_60hz\":" + String(measurement.outerRaw60Hz);
    json += ",\"box_fault_60hz\":" + String(measurement.boxFault60Hz);
    json += ",\"outer_fault_60hz\":" + String(measurement.outerFault60Hz) + "}";
  }
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

void appendHistoryMeasurementJson(String& json,
                                  const Measurement& measurement) {
  json += "{\"uptime_ms\":" + String(measurement.uptimeMs);
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
  json += '}';
}
