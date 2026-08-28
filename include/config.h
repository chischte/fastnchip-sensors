#pragma once

// Hardware mapping
constexpr uint8_t RTD_BOX_CHANNEL = 1;
constexpr uint8_t RTD_OUTER_CHANNEL = 0;
constexpr float RTD_REFERENCE_OHMS = 400.0f;
constexpr float RTD_NOMINAL_OHMS = 100.0f;

// Acquisition and recovery
constexpr uint32_t MEASUREMENT_INTERVAL_MS = 5000;
constexpr uint32_t SENSOR_RETRY_INTERVAL_MS = 30000;
constexpr uint32_t WIFI_RECONNECT_INTERVAL_MS = 10000;
constexpr uint32_t WIFI_CONNECT_SLICE_MS = 250;
constexpr uint8_t HISTORY_SIZE = 240;

// SCD41 installation settings. Adjust after calibration in the final enclosure.
constexpr float SCD41_TEMPERATURE_OFFSET_C = 4.0f;
constexpr uint16_t SCD41_ALTITUDE_M = 450; // Site altitude; pressure input would override this.
// Closed chambers normally do not see fresh 400 ppm air regularly, so ASC is disabled.
constexpr bool SCD41_ASC_ENABLED = false;

// QSPI append-only recovery buffer. The older file is retained across one rotation.
constexpr size_t PERSISTENT_LOG_MAX_BYTES = 4U * 1024U * 1024U;
constexpr const char* FIRMWARE_VERSION = "2.0.0";
