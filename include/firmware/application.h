#pragma once

#include "firmware/firmware_updater.h"
#include "firmware/measurement_controller.h"
#include "firmware/qspi_storage.h"
#include "firmware/sensor_manager.h"
#include "firmware/web_server.h"

class Application {
 public:
  Application();

  void begin();
  void poll();

 private:
  void beginSerial();

  QspiStorage storage_;
  SensorManager sensors_;
  FirmwareUpdater firmwareUpdater_;
  MeasurementController measurements_;
  WebServer webServer_;
};
