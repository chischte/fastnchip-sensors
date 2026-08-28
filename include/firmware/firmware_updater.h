#pragma once

#include <Arduino.h>
#include <Arduino_Portenta_OTA.h>
#include <cstdio>

#include "firmware/qspi_storage.h"

struct FirmwareUpdateResult {
  uint16_t httpStatus;
  String message;
  bool restartRequired;
};

class FirmwareUpdater {
 public:
  explicit FirmwareUpdater(QspiStorage& storage);

  bool beginUpload();
  bool write(const uint8_t* data, size_t length);
  FirmwareUpdateResult finishAndInstall();
  void cancelUpload();
  void restart();

 private:
  void readFileSize(const uint8_t* data, size_t length);
  size_t writableBytes(size_t requestedBytes) const;
  void closeUpload();

  QspiStorage& storage_;
  Arduino_Portenta_OTA_QSPI ota_;
  FILE* uploadFile_ = nullptr;
  size_t expectedFileSize_ = 0;
  size_t writtenBytes_ = 0;
  uint8_t filePrefix_[4] = {};
  uint8_t prefixBytes_ = 0;
  bool fileSizeKnown_ = false;
  bool uploadFailed_ = false;
};
