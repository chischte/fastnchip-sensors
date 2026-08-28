#include <Arduino.h>
#include "BlockDevice.h"
#include "MBRBlockDevice.h"
#include "FATFileSystem.h"

using namespace mbed;

void setup() {
  Serial.begin(115200);
  const uint32_t serialDeadline = millis() + 8000;
  while (!Serial && millis() < serialDeadline) {
    delay(10);
  }

  Serial.println("QSPI_FORMAT_BEGIN");
  BlockDevice *root = BlockDevice::get_default_instance();
  if (!root || root->init() != BD_ERROR_OK) {
    Serial.println("QSPI_FORMAT_ERROR:init");
    return;
  }

  // Restore Arduino's standard Portenta partition map without erasing the
  // contents of the WiFi, OTA, or provisioning partitions.
  if (MBRBlockDevice::partition(root, 1, 0x0B, 0, 1 * 1024 * 1024) != 0 ||
      MBRBlockDevice::partition(root, 2, 0x0B, 1 * 1024 * 1024, 6 * 1024 * 1024) != 0 ||
      MBRBlockDevice::partition(root, 3, 0x0B, 6 * 1024 * 1024, 7 * 1024 * 1024) != 0 ||
      MBRBlockDevice::partition(root, 4, 0x0B, 7 * 1024 * 1024, 14 * 1024 * 1024) != 0) {
    Serial.println("QSPI_FORMAT_ERROR:partition");
    root->deinit();
    return;
  }

  MBRBlockDevice userData(root, 4);
  FATFileSystem userFs("user");
  const int result = userFs.reformat(&userData);
  Serial.print("QSPI_FORMAT_RESULT:");
  Serial.println(result);
  Serial.println(result == 0 ? "QSPI_FORMAT_OK" : "QSPI_FORMAT_ERROR:filesystem");
  root->deinit();
}

void loop() {
  delay(1000);
}
