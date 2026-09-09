#pragma once
#include <stdint.h>
#include <stddef.h>
constexpr int MSBFIRST = 1, SPI_MODE1 = 1;
struct SPISettings { SPISettings(int, int, int) {} };
struct SPIClass {
    uint8_t registers[8] = {};
    bool rejectWrites = false;
    bool commandPending = true;
    bool writing = false;
    uint8_t address = 0;

    void begin() {}
    void beginTransaction(const SPISettings&) { commandPending = true; }
    void endTransaction() {}
    uint8_t transfer(uint8_t value) {
        if (commandPending) {
            commandPending = false;
            writing = (value & 0x80) != 0;
            address = value & 0x7f;
            return 0;
        }
        if (writing) {
            if (!rejectWrites && address < 8) {
                // One-shot and fault-clear bits self-clear on the real converter.
                registers[address] = address == 0 ? value & ~0x22 : value;
            }
            ++address;
            return 0;
        }
        return address < 8 ? registers[address++] : 0xff;
    }
    void transfer(void* data, size_t length) {
        auto* bytes = static_cast<uint8_t*>(data);
        for (size_t index = 0; index < length; ++index) bytes[index] = transfer(bytes[index]);
    }
};
inline SPIClass SPI;
