"""Build the MAX31865 driver with verified wiring mode and 50 Hz timing."""

from pathlib import Path

Import("env")  # PlatformIO supplies the build environment.

DRIVER_SUFFIX = "Arduino_PortentaMachineControl/src/utility/MAX31865/MAX31865.cpp"


def configure_rtd_driver(env, node):
    original = Path(node.srcnode().get_abspath())
    if not original.as_posix().endswith(DRIVER_SUFFIX):
        return node

    source = original.read_text(encoding="utf-8")
    diagnostics_header = (Path(env.subst("$PROJECT_DIR")) / "include/firmware/rtd_driver_diagnostics.h").as_posix()
    replacements = {
        '#include "MAX31865.h"': (
            '#include "utility/MAX31865/MAX31865.h"\n\n'
            f'#include "{diagnostics_header}"\n'
            'namespace {\n'
            'constexpr uint8_t RTD_FILTER_50HZ = 0x01;\n'
            '// The 50 Hz single-shot conversion takes up to 66 ms.\n'
            'constexpr uint32_t RTD_CONVERSION_WAIT_MS = 70;\n'
            'bool filter50Hz = true;\n'
            'uint16_t lastRawCount = 0;\n'
            'uint8_t wireConfiguration = MAX31856_CONFIG_3_WIRE;\n'
            'constexpr uint8_t RTD_PERSISTENT_CONFIG_MASK =\n'
            '    MAX31856_CONFIG_BIAS_ON | MAX31856_CONFIG_CONV_MODE_AUTO |\n'
            '    MAX31856_CONFIG_3_WIRE | RTD_FILTER_50HZ;\n'
            'RtdDriverDiagnostics diagnostics;\n'
            '}\n'
            'void setRtdFilter50Hz(bool enabled) { filter50Hz = enabled; }\n'
            'uint16_t lastRtdRawCount() { return lastRawCount; }\n'
            'void setRtdLeadCompensation(bool enabled) {\n'
            '  wireConfiguration = enabled ? MAX31856_CONFIG_3_WIRE : 0;\n'
            '}\n'
            'RtdDriverDiagnostics lastRtdDiagnostics() { return diagnostics; }\n'
        ),
        'readByte(MAX31856_CONFIG_REG) & MAX31856_CONFIG_60_50_HZ_FILTER_MASK': (
            '(readByte(MAX31856_CONFIG_REG) & MAX31856_CONFIG_60_50_HZ_FILTER_MASK)'
            ' | RTD_FILTER_50HZ'
        ),
        'delay(65);': 'delay(RTD_CONVERSION_WAIT_MS);',
        'uint32_t MAX31865Class::readRTD() {': (
            'uint32_t MAX31865Class::readRTD() {\n'
            '  const uint8_t expected = wireConfiguration | (filter50Hz ? RTD_FILTER_50HZ : 0);\n'
            '  diagnostics.configBefore = readByte(MAX31856_CONFIG_REG);\n'
            '  if ((diagnostics.configBefore & RTD_PERSISTENT_CONFIG_MASK) != expected) {\n'
            '    ++diagnostics.recoveries;\n'
            '  }\n'
            '  // Reassert wire mode after a converter reset, not just the filter bit.\n'
            '  writeByte(MAX31856_CONFIG_REG, expected);\n'
            '  diagnostics.configAfter = readByte(MAX31856_CONFIG_REG);\n'
            '  diagnostics.configurationValid =\n'
            '      (diagnostics.configAfter & RTD_PERSISTENT_CONFIG_MASK) == expected;\n'
            '  if (!diagnostics.configurationValid) { lastRawCount = 0; return 0; }'
        ),
        'bool MAX31865Class::begin(int wires) {': (
            'bool MAX31865Class::begin(int wires) {\n'
            '  setRtdLeadCompensation(wires == THREE_WIRE);'
        ),
        'read = read >>1;': 'read = read >>1;\n  lastRawCount = read;',
        '  return read;\n}\n\nuint8_t MAX31865Class::readByte': (
            '  // Reject a sample if the converter lost configuration during conversion.\n'
            '  diagnostics.configAfter = readByte(MAX31856_CONFIG_REG);\n'
            '  diagnostics.configurationValid =\n'
            '      (diagnostics.configAfter & RTD_PERSISTENT_CONFIG_MASK) == expected;\n'
            '  if (!diagnostics.configurationValid) { lastRawCount = 0; return 0; }\n'
            '  return read;\n}\n\nuint8_t MAX31865Class::readByte'
        ),
    }
    for before, after in replacements.items():
        if source.count(before) != 1:
            raise RuntimeError(f"Unexpected MAX31865 driver source; cannot apply configuration guard: {before}")
        source = source.replace(before, after)

    generated = Path(env.subst("$BUILD_DIR")) / "rtd_driver" / original.name
    generated.parent.mkdir(parents=True, exist_ok=True)
    if not generated.exists() or generated.read_text(encoding="utf-8") != source:
        generated.write_text(source, encoding="utf-8")
    return env.File(str(generated))


env.AddBuildMiddleware(configure_rtd_driver, "*MAX31865.cpp")
