#include "firmware/firmware_updater.h"

#include "config.h"

namespace {
constexpr uint8_t OTA_PARTITION = 2;
constexpr size_t OTA_HEADER_BYTES = 8;
constexpr size_t OTA_SIZE_PREFIX_BYTES = 4;
constexpr char OTA_UPLOAD_PATH[] = "/fs/UPDATE.BIN.LZSS";
}  // namespace

FirmwareUpdater::FirmwareUpdater(QspiStorage& storage)
    : storage_(storage), ota_(QSPI_FLASH_FATFS_MBR, OTA_PARTITION) {}

bool FirmwareUpdater::beginUpload() {
  cancelUpload();
  if (!storage_.isOtaReady()) {
    return false;
  }

  uploadFile_ = fopen(OTA_UPLOAD_PATH, "wb");
  expectedFileSize_ = 0;
  writtenBytes_ = 0;
  prefixBytes_ = 0;
  fileSizeKnown_ = false;
  uploadFailed_ = uploadFile_ == nullptr;
  return !uploadFailed_;
}

bool FirmwareUpdater::write(const uint8_t* data, size_t length) {
  if (!uploadFile_ || uploadFailed_) {
    return false;
  }

  readFileSize(data, length);
  if (uploadFailed_) {
    return false;
  }

  const size_t bytesToWrite = writableBytes(length);
  if (bytesToWrite &&
      fwrite(data, 1, bytesToWrite, uploadFile_) != bytesToWrite) {
    uploadFailed_ = true;
    return false;
  }
  writtenBytes_ += bytesToWrite;
  return true;
}

FirmwareUpdateResult FirmwareUpdater::finishAndInstall() {
  closeUpload();
  if (uploadFailed_ || !fileSizeKnown_ ||
      expectedFileSize_ <= OTA_HEADER_BYTES ||
      writtenBytes_ != expectedFileSize_) {
    remove(OTA_UPLOAD_PATH);
    return {400, "Incomplete or invalid OTA upload.", false};
  }

  const int decompressedBytes = ota_.decompress();
  if (decompressedBytes < 0) {
    remove(OTA_UPLOAD_PATH);
    return {422,
            "OTA decompression failed: " + String(decompressedBytes), false};
  }

  const Arduino_Portenta_OTA::Error updateError = ota_.update();
  if (updateError != Arduino_Portenta_OTA::Error::None) {
    return {422,
            "OTA activation failed: " +
                String(static_cast<int>(updateError)),
            false};
  }
  return {200, "OTA verified; restarting.", true};
}

void FirmwareUpdater::cancelUpload() {
  const bool hadUpload = uploadFile_ != nullptr;
  closeUpload();
  if (hadUpload) {
    remove(OTA_UPLOAD_PATH);
  }
}

void FirmwareUpdater::restart() {
  delay(500);
  ota_.reset();
}

void FirmwareUpdater::readFileSize(const uint8_t* data, size_t length) {
  for (size_t index = 0;
       index < length && prefixBytes_ < OTA_SIZE_PREFIX_BYTES; ++index) {
    filePrefix_[prefixBytes_] = data[index];
    ++prefixBytes_;
  }
  if (prefixBytes_ != OTA_SIZE_PREFIX_BYTES || fileSizeKnown_) {
    return;
  }

  const uint32_t payloadBytes =
      static_cast<uint32_t>(filePrefix_[0]) |
      (static_cast<uint32_t>(filePrefix_[1]) << 8) |
      (static_cast<uint32_t>(filePrefix_[2]) << 16) |
      (static_cast<uint32_t>(filePrefix_[3]) << 24);
  fileSizeKnown_ = true;
  if (payloadBytes > Config::OTA_MAX_FILE_BYTES - OTA_HEADER_BYTES) {
    uploadFailed_ = true;
    return;
  }
  expectedFileSize_ = static_cast<size_t>(payloadBytes) + OTA_HEADER_BYTES;
}

size_t FirmwareUpdater::writableBytes(size_t requestedBytes) const {
  if (!fileSizeKnown_) {
    return requestedBytes;
  }
  if (writtenBytes_ >= expectedFileSize_) {
    return 0;
  }
  return min(requestedBytes, expectedFileSize_ - writtenBytes_);
}

void FirmwareUpdater::closeUpload() {
  if (!uploadFile_) {
    return;
  }
  fflush(uploadFile_);
  fclose(uploadFile_);
  uploadFile_ = nullptr;
}
