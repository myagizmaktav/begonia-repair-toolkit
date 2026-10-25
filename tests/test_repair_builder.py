"""No real identifiers, network, PHP or phone access. SPDX-License-Identifier: GPL-3.0-only"""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import struct
import tempfile
import unittest
from unittest import mock
import zipfile

import repair_builder as tool


def synthetic_imei(label):
    body = "35" + str(int.from_bytes(hashlib.sha256(label.encode()).digest()[:6], "big")).zfill(12)[-12:]
    for digit in "0123456789":
        candidate = body + digit
        if tool.valid_imei(candidate):
            return candidate
    raise AssertionError("Synthetic check digit construction failed")


def values():
    def mac(label):
        return ":".join("%02X" % n for n in b"\x02" + hashlib.sha256(label.encode()).digest()[:5])
    return {"DEVICE": "begonia", "ROM_VERSION": "V12.5.15.0.RGGEUXM", "KERNEL_RELEASE": "4.14.186-test",
            "IMEI_1": synthetic_imei("test-slot-one"), "IMEI_2": synthetic_imei("test-slot-two"),
            "CHIP_ID": "0x" + hashlib.sha256(b"synthetic-chip").hexdigest()[:32],
            "WIFI_MAC": mac("test-wifi"), "BT_MAC": mac("test-bt")}


def synthetic_nvram(config):
    toc = bytearray(0x20000)
    content = bytearray()
    critical = b"\x00\x01\x00\x62"
    for tag, key in ((1, "CHIP_ID"), (2, "IMEI_1"), (3, "IMEI_2"), (5, "WIFI_MAC"), (6, "BT_MAC")):
        field = config[key].replace(":", "").encode("ascii")
        critical += bytes((tag, len(field))) + field
    cssd = (b"criticalData:" + critical.hex().encode() + b"\\ncrticalDataSign:test").ljust(4096, b"\0")
    cssd = b"\0" * 64 + cssd + tool.checksum8(cssd)
    wifi = b"\0" * 4 + bytes.fromhex(config["WIFI_MAC"].replace(":", "")) + b"\0" * 20
    bt = bytes.fromhex(config["BT_MAC"].replace(":", "")) + b"\0" * 8
    records = [(b"/mnt/vendor/nvdata/md/NVRAM/NVD_IMEI/CSSD_000", cssd),
               (b"/mnt/vendor/nvdata/APCFG/APRDEB/WIFI", wifi + tool.checksum2(wifi)),
               (b"/mnt/vendor/nvdata/APCFG/APRDEB/BT_Addr", bt + tool.checksum2(bt))]
    for index, (name, record) in enumerate(records):
        at = 256 + index * 128
        struct.pack_into("<II", toc, at - 8, len(content), len(record))
        toc[at:at + len(name)] = name
        content += record
    struct.pack_into("<I", toc, 4, len(content))
    struct.pack_into("<I", toc, 12, tool.nvram_checksum(content))
    return bytes(toc + content)


class EnvSecurityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.env = Path(self.directory.name) / "device.env"
        self.data = values()

    def write_env(self, data=None):
        data = self.data if data is None else data
        self.env.write_text("\n".join(k + "=" + v for k, v in data.items()) + "\n")
        self.env.chmod(0o600)

    def test_default_only_validates_and_never_prints_identifiers(self):
        self.write_env()
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output), \
                mock.patch.object(tool.urllib.request, "build_opener", side_effect=AssertionError("network called")), \
                mock.patch.object(tool.subprocess, "run", side_effect=AssertionError("subprocess called")):
            result = tool.main(["--env-file", str(self.env)])
        self.assertEqual(result, 0)
        for key in tool.IDENTITY_KEYS:
            self.assertNotIn(self.data[key], output.getvalue())
        self.assertNotIn(str(self.env), output.getvalue())

    def test_rejects_shell_expression_without_echo(self):
        self.write_env()
        with self.env.open("a") as handle:
            handle.write("UNEXPECTED=$(sensitive-content)\n")
        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            self.assertEqual(tool.main(["validate", "--env-file", str(self.env)]), 2)
        self.assertNotIn("sensitive-content", output.getvalue())

    def test_symlink_and_world_readable_env_rejected(self):
        self.write_env()
        link = self.env.with_name("link.env")
        link.symlink_to(self.env)
        with self.assertRaises(tool.SafeError):
            tool.load_env(link)
        self.env.chmod(0o644)
        with self.assertRaises(tool.SafeError):
            tool.load_env(self.env)

    def test_duplicate_and_empty_fields_rejected(self):
        self.write_env()
        with self.env.open("a") as handle:
            handle.write("DEVICE=begonia\n")
        with self.assertRaises(tool.SafeError):
            tool.load_env(self.env)
        bad = dict(self.data, CHIP_ID="")
        with self.assertRaises(tool.SafeError):
            tool.validate_values(bad)

    def test_local_unicast_mac_allowed_but_multicast_rejected(self):
        self.assertEqual(tool.validate_values(self.data)["WIFI_MAC"], self.data["WIFI_MAC"])
        bad = dict(self.data, WIFI_MAC="03" + self.data["WIFI_MAC"][2:])
        with self.assertRaises(tool.SafeError):
            tool.validate_values(bad)

    def test_wrong_luhn_and_duplicate_imei_rejected(self):
        bad = dict(self.data, IMEI_2=self.data["IMEI_1"])
        with self.assertRaises(tool.SafeError):
            tool.validate_values(bad)
        broken = self.data["IMEI_1"][:-1] + str((int(self.data["IMEI_1"][-1]) + 1) % 10)
        with self.assertRaises(tool.SafeError):
            tool.validate_values(dict(self.data, IMEI_1=broken))

    def test_repo_runtime_rejected(self):
        with self.assertRaises(tool.SafeError):
            tool.runtime_dir(str(tool.ROOT / "private-runtime"))
        self.assertFalse((tool.ROOT / "private-runtime").exists())


class PayloadTests(unittest.TestCase):
    def test_independent_checksum_vectors(self):
        self.assertEqual(tool.checksum2(bytes((1, 2, 3))), bytes((0xAA, 6)))
        self.assertEqual(tool.checksum2(bytes((255, 255, 255, 1))), bytes((0xAA, 254)))
        self.assertEqual(tool.checksum8(b""), bytes.fromhex("3d9d854163f8f07a"))
        self.assertEqual(tool.nvram_checksum(struct.pack("<II", 1, 2)), 11)
        self.assertEqual(tool.nvram_checksum(struct.pack("<III", 1, 2, 3)), 12)
        self.assertEqual(tool.nvram_checksum(bytes((1, 2, 3))), 0x030202)

    def test_valid_payload_and_private_identity_mismatch(self):
        config = values()
        blob = synthetic_nvram(config)
        tool.validate_nvram(blob, config)
        with self.assertRaisesRegex(tool.SafeError, "kimlik alanları"):
            tool.validate_nvram(blob, dict(config, IMEI_1=synthetic_imei("different-test-slot")))

    def test_corruption_and_toc_boundary_rejected(self):
        blob = bytearray(synthetic_nvram(values()))
        blob[-1] ^= 1
        with self.assertRaisesRegex(tool.SafeError, "genel checksum"):
            tool.validate_nvram(bytes(blob), values())
        blob = bytearray(synthetic_nvram(values()))
        struct.pack_into("<I", blob, 256 - 8, len(blob))
        with self.assertRaisesRegex(tool.SafeError, "kayıt sınırları"):
            tool.validate_nvram(bytes(blob), values())

    def test_wifi_prefix_neighbor_is_not_duplicate(self):
        blob = bytearray(synthetic_nvram(values()))
        neighbor = b"/mnt/vendor/nvdata/APCFG/APRDEB/WIFI_CUSTOM\0"
        blob[1024:1024 + len(neighbor)] = neighbor
        tool.validate_nvram(bytes(blob), values())
        exact_duplicate = b"/mnt/vendor/nvdata/APCFG/APRDEB/WIFI\0"
        blob[1536:1536 + len(exact_duplicate)] = exact_duplicate
        with self.assertRaisesRegex(tool.SafeError, "yineleniyor"):
            tool.validate_nvram(bytes(blob), values())

    def test_manifest_is_pinned(self):
        source = tool.manifest()
        self.assertEqual(source["commit"], tool.COMMIT)
        self.assertEqual(len(source["files"]), 10)
        self.assertTrue(all(item["source"].startswith(tool.SOURCE_BASE) for item in source["files"]))

    def test_tampered_cache_rejected_before_php(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp)
            (runtime / "sources").mkdir()
            with mock.patch.object(tool.subprocess, "run", side_effect=AssertionError("PHP called")):
                with self.assertRaises(tool.SafeError):
                    tool.verified_cache(runtime)

    def test_review_bundle_excludes_installers(self):
        config = values()
        payload = synthetic_nvram(config)
        fixture = {"nvram.img": payload, "nvdata.img": b"test-nvdata", "vendor/lib/modules/md_patcher.ko": b"test-module",
                   "vendor/etc/init/md_patcher.rc": b"test-init"}
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "data/begonia").mkdir(parents=True)
            (directory / "data/begonia/md_patcher-4.14.186.ko").write_bytes(fixture["vendor/lib/modules/md_patcher.ko"])
            with zipfile.ZipFile(directory / "data/patch.zip", "w") as package:
                package.writestr("vendor/etc/init/md_patcher.rc", fixture["vendor/etc/init/md_patcher.rc"])
                package.writestr("nvdata.img", fixture["nvdata.img"])
            source = directory / "upstream.zip"
            with zipfile.ZipFile(source, "w") as package:
                for name, content in fixture.items():
                    package.writestr(name, content)
                package.writestr("META-INF/com/google/android/update-binary", "must not propagate")
            output = directory / "review.zip"
            with mock.patch.object(tool, "PAYLOADS", {name: len(content) for name, content in fixture.items()}):
                tool.review_bundle(source, output, directory, config)
            with zipfile.ZipFile(output) as package:
                self.assertEqual(set(package.namelist()), set(fixture) | {"PRIVATE-MANIFEST.json"})
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
