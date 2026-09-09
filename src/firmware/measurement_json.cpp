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
  json += ",\"rtd_box_config_before\":" + String(measurement.boxDiagnostics.configBefore);
  json += ",\"rtd_box_config_after\":" + String(measurement.boxDiagnostics.configAfter);
  json += ",\"rtd_outer_config_before\":" + String(measurement.outerDiagnostics.configBefore);
  json += ",\"rtd_outer_config_after\":" + String(measurement.outerDiagnostics.configAfter);
  json += ",\"rtd_config_recoveries\":" + String(measurement.outerDiagnostics.recoveries);
  if (measurement.rtdComparison) {
    const String suffix = measurement.rtdComparisonTwoWire ? "_2wire" : "_60hz";
    json += ",\"rtd_comparison\":{\"box" + suffix + "\":" +
        nullableNumber(measurement.boxComparisonTemperature, !measurement.boxComparisonFault);
    json += ",\"outer" + suffix + "\":" +
        nullableNumber(measurement.outerComparisonTemperature, !measurement.outerComparisonFault);
    json += ",\"box_raw" + suffix + "\":" + String(measurement.boxComparisonRaw);
    json += ",\"outer_raw" + suffix + "\":" + String(measurement.outerComparisonRaw);
    json += ",\"box_fault" + suffix + "\":" + String(measurement.boxComparisonFault);
    json += ",\"outer_fault" + suffix + "\":" + String(measurement.outerComparisonFault) + "}";
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
