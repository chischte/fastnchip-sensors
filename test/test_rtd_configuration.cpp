#include "utility/MAX31865/MAX31865.h"
#include "firmware/rtd_driver_diagnostics.h"
extern "C" { int _fltused = 0; }
#define CHECK(condition) do { if (!(condition)) return __LINE__; } while (false)
bool resetDuringConversion = false;
void delay(unsigned long milliseconds) {
    if (resetDuringConversion && milliseconds == 70) SPI.registers[0] = 0;
}

int main() {
    MAX31865Class driver;
    driver.begin(THREE_WIRE);
    SPI.registers[1] = 0x46;
    SPI.registers[2] = 0x50; // Raw count 9000, independent of configuration in this fake.
    CHECK(driver.readRTD() == 9000);
    CHECK(lastRtdDiagnostics().configurationValid);
    CHECK(lastRtdDiagnostics().recoveries == 0);

    SPI.registers[0] = 0; // A converter-only reset loses three-wire compensation.
    CHECK(driver.readRTD() == 9000);
    CHECK(lastRtdDiagnostics().configBefore == 0);
    CHECK(lastRtdDiagnostics().configAfter == 0x11);
    CHECK(lastRtdDiagnostics().recoveries == 1);
    CHECK(SPI.registers[0] == 0x11);

    setRtdLeadCompensation(false);
    driver.readRTD();
    CHECK(lastRtdDiagnostics().configAfter == 0x01);
    setRtdLeadCompensation(true);
    setRtdFilter50Hz(false);
    driver.readRTD();
    CHECK(lastRtdDiagnostics().configAfter == 0x10);
    setRtdFilter50Hz(true);

    SPI.registers[0] = 0;
    SPI.rejectWrites = true;
    CHECK(driver.readRTD() == 0);
    CHECK(!lastRtdDiagnostics().configurationValid);
    CHECK(lastRtdRawCount() == 0);
    SPI.rejectWrites = false;
    CHECK(driver.readRTD() == 9000);
    CHECK(lastRtdDiagnostics().configurationValid);
    CHECK(lastRtdDiagnostics().configAfter == 0x11);
    resetDuringConversion = true;
    CHECK(driver.readRTD() == 0);
    CHECK(!lastRtdDiagnostics().configurationValid);
    resetDuringConversion = false;
    CHECK(driver.readRTD() == 9000);
    CHECK(lastRtdDiagnostics().configurationValid);
    return 0;
}
