"""Exercise the patched production MAX31865 driver with register-level SPI fakes."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RtdConfigurationTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32" and shutil.which("clang++"),
                         "Requires Windows with Clang and LLD")
    def test_converter_reset_and_failed_configuration_write(self):
        driver = ROOT / ".pio/build/portenta_h7_m7/rtd_driver/MAX31865.cpp"
        self.assertTrue(driver.exists(), "Run pio run -e portenta_h7_m7 first")
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "rtd_configuration.exe"
            command = [
                "clang++", "-std=c++17", "-O2", "-fno-math-errno", "-ffreestanding", "-fno-exceptions",
                "-fno-rtti", "-fno-stack-protector", "-fuse-ld=lld", "-nostdlib",
                "-Itest/rtd_fakes", "-Iinclude",
                "-I.pio/libdeps/portenta_h7_m7/Arduino_PortentaMachineControl/src",
                "test/test_rtd_configuration.cpp", str(driver),
                "-Wl,/entry:main,/subsystem:console", "-o", str(executable),
            ]
            build = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            result = subprocess.run([str(executable)], timeout=10)
            self.assertEqual(result.returncode, 0,
                             f"RTD configuration check failed at C++ line {result.returncode}")
