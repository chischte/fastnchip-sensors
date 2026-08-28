"""
PlatformIO post-build script: firmware.bin -> firmware.ota
Runs automatically after every build.
"""
import os
import sys
import subprocess

Import("env")  # noqa: F821 – PlatformIO provides this


def make_ota(source, target, env):
    build_dir = env.subst("$BUILD_DIR")
    bin_path = os.path.join(build_dir, "firmware.bin")
    lzss_path = os.path.join(build_dir, "firmware.lzss")
    ota_path = os.path.join(build_dir, "firmware.ota")

    tools_dir = os.path.join(env.subst("$PROJECT_DIR"), "tools")
    lzss_tool = os.path.join(tools_dir, "lzss.py")
    bin2ota_tool = os.path.join(tools_dir, "bin2ota.py")

    if not os.path.isfile(bin_path):
        print(f"[OTA] firmware.bin not found at {bin_path}")
        return
    if not os.path.isfile(lzss_tool) or not os.path.isfile(bin2ota_tool):
        print("[OTA] tools/lzss.py or tools/bin2ota.py missing – skipping .ota generation")
        return

    python = sys.executable

    print(f"[OTA] Compressing {bin_path} ...")
    r = subprocess.run([python, lzss_tool, "--encode", bin_path, lzss_path], capture_output=True, text=True)
    if r.returncode != 0:
        print("[OTA] lzss encode failed:", r.stderr)
        return

    print(f"[OTA] Building {ota_path} ...")
    r = subprocess.run([python, bin2ota_tool, "PORTENTA_H7_M7", lzss_path, ota_path], capture_output=True, text=True)
    if r.returncode != 0:
        print("[OTA] bin2ota failed:", r.stderr)
        return

    size_kb = os.path.getsize(ota_path) // 1024
    print(f"[OTA] firmware.ota ready ({size_kb} KB) -> {ota_path}")


env.AddPostAction("$BUILD_DIR/firmware.bin", make_ota)
