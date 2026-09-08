"""Build Arduino's MAX31865 driver with a 50 Hz filter and matching timing."""

from pathlib import Path

Import("env")  # PlatformIO supplies the build environment.

DRIVER_SUFFIX = "Arduino_PortentaMachineControl/src/utility/MAX31865/MAX31865.cpp"


def configure_rtd_driver(env, node):
    original = Path(node.srcnode().get_abspath())
    if not original.as_posix().endswith(DRIVER_SUFFIX):
        return node

    source = original.read_text(encoding="utf-8")
    replacements = {
        '#include "MAX31865.h"': (
            '#include "utility/MAX31865/MAX31865.h"\n\n'
            'namespace {\n'
            'constexpr uint8_t RTD_FILTER_50HZ = 0x01;\n'
            '// The 50 Hz single-shot conversion takes up to 66 ms.\n'
            'constexpr uint32_t RTD_CONVERSION_WAIT_MS = 70;\n'
            'bool filter50Hz = true;\n'
            'uint16_t lastRawCount = 0;\n'
            '}\n'
            'void setRtdFilter50Hz(bool enabled) { filter50Hz = enabled; }\n'
            'uint16_t lastRtdRawCount() { return lastRawCount; }\n'
        ),
        'readByte(MAX31856_CONFIG_REG) & MAX31856_CONFIG_60_50_HZ_FILTER_MASK': (
            '(readByte(MAX31856_CONFIG_REG) & MAX31856_CONFIG_60_50_HZ_FILTER_MASK)'
            ' | RTD_FILTER_50HZ'
        ),
        'delay(65);': 'delay(RTD_CONVERSION_WAIT_MS);',
        'uint32_t MAX31865Class::readRTD() {': (
            'uint32_t MAX31865Class::readRTD() {\n'
            '  writeByte(MAX31856_CONFIG_REG,\n'
            '      (readByte(MAX31856_CONFIG_REG) & MAX31856_CONFIG_60_50_HZ_FILTER_MASK)\n'
            '      | (filter50Hz ? RTD_FILTER_50HZ : 0));'
        ),
        'read = read >>1;': 'read = read >>1;\n  lastRawCount = read;',
    }
    for before, after in replacements.items():
        if source.count(before) != 1:
            raise RuntimeError(f"Unexpected MAX31865 driver source; cannot apply 50 Hz setting: {before}")
        source = source.replace(before, after)

    generated = Path(env.subst("$BUILD_DIR")) / "rtd_driver" / original.name
    generated.parent.mkdir(parents=True, exist_ok=True)
    if not generated.exists() or generated.read_text(encoding="utf-8") != source:
        generated.write_text(source, encoding="utf-8")
    return env.File(str(generated))


env.AddBuildMiddleware(configure_rtd_driver, "*MAX31865.cpp")
