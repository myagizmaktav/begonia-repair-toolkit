#!/usr/bin/env python3
"""Prepare a private, non-flashable begonia repair review bundle. SPDX-License-Identifier: GPL-3.0-only"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
COMMIT = "100e67c2696f6247fef398cf5b46b9cb260e0f93"
SOURCE_BASE = "https://raw.githubusercontent.com/timjosten/mtk_imei/" + COMMIT + "/"
KEYS = {"DEVICE", "ROM_VERSION", "KERNEL_RELEASE", "IMEI_1", "IMEI_2", "CHIP_ID", "WIFI_MAC", "BT_MAC"}
IDENTITY_KEYS = ("IMEI_1", "IMEI_2", "CHIP_ID", "WIFI_MAC", "BT_MAC")
PAYLOADS = {
    "nvram.img": 64 * 1024 * 1024,
    "nvdata.img": 64 * 1024 * 1024,
    "vendor/lib/modules/md_patcher.ko": 11328,
    "vendor/etc/init/md_patcher.rc": 105,
}


class SafeError(Exception):
    """Only fixed, non-sensitive messages may enter this exception."""


def within(path, parent):
    return path == parent or parent in path.parents


def require_private_file(path):
    try:
        info = path.lstat()
    except OSError:
        raise SafeError("Yapılandırma dosyası okunamadı.") from None
    if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
        raise SafeError("Yapılandırma normal bir dosya olmalı; sembolik bağlantı kabul edilmez.")
    if os.name == "posix" and (info.st_uid != os.getuid() or info.st_mode & 0o077):
        raise SafeError("Yapılandırma size ait ve yalnız sizin okuyabildiğiniz bir dosya olmalı (chmod 600).")
    if info.st_size > 8192:
        raise SafeError("Yapılandırma dosyası beklenen boyutu aşıyor.")


def load_env(path):
    """Parse a deliberately small dotenv subset; never source/eval/expand its contents."""
    path = Path(path)
    require_private_file(path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise SafeError("Yapılandırma UTF-8 metin olarak okunamadı.") from None
    values = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise SafeError("Yapılandırma satırı KEY=VALUE biçiminde olmalı.")
        key, value = (part.strip() for part in line.split("=", 1))
        if key not in KEYS:
            raise SafeError("Yapılandırmada tanınmayan anahtar var.")
        if key in values:
            raise SafeError("Yapılandırmada yinelenen anahtar var.")
        if value[:1] in ("'", '"'):
            if len(value) < 2 or value[-1] != value[0]:
                raise SafeError("Yapılandırmada eşleşmeyen tırnak var.")
            value = value[1:-1]
        if any(c in value for c in ("$", "`", "\\", "\x00", "\r", "\n")):
            raise SafeError("Yapılandırmada kabuk ifadesi veya desteklenmeyen kaçış var.")
        values[key] = value
    return validate_values(values)


def valid_imei(value):
    if not re.fullmatch(r"[0-9]{15}", value) or len(set(value)) == 1:
        return False
    digits = [int(n) for n in value]
    return sum((2 * n // 10 + 2 * n % 10) if i % 2 else n for i, n in enumerate(digits)) % 10 == 0


def validate_values(values):
    if set(values) != KEYS or any(not values[k] for k in KEYS):
        raise SafeError("Gerekli yapılandırma alanları eksik veya boş.")
    if values["DEVICE"] != "begonia" or values["ROM_VERSION"] != "V12.5.15.0.RGGEUXM":
        raise SafeError("Bu yardımcı yalnız begonia / EEA V12.5.15.0.RGGEUXM kapsamındadır.")
    if not re.fullmatch(r"4\.14\.186(?:-[A-Za-z0-9._+]+)?", values["KERNEL_RELEASE"]):
        raise SafeError("Çekirdek sürümü bu hazırlama kapsamıyla eşleşmiyor.")
    if not all(valid_imei(values[k]) for k in ("IMEI_1", "IMEI_2")):
        raise SafeError("IMEI biçimi veya Luhn kontrolü geçersiz.")
    if values["IMEI_1"] == values["IMEI_2"]:
        raise SafeError("İki SIM yuvasının özgün IMEI değerleri farklı olmalı.")
    chip = values["CHIP_ID"]
    if not re.fullmatch(r"0x[0-9a-fA-F]{32}", chip) or int(chip[2:], 16) in (0, (1 << 128) - 1):
        raise SafeError("Chip ID biçimi geçersiz.")
    result = dict(values)
    for key in ("WIFI_MAC", "BT_MAC"):
        value = values[key]
        if not re.fullmatch(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", value):
            raise SafeError("MAC adresi biçimi geçersiz.")
        raw = bytes.fromhex(value.replace(":", ""))
        if raw == b"\0" * 6 or raw[0] & 1:
            raise SafeError("MAC adresi sıfır olmayan bir unicast adres olmalı.")
        result[key] = value.upper()
    return result


def manifest():
    try:
        data = json.loads((ROOT / "upstream-manifest.json").read_text())
        if data["commit"] != COMMIT:
            raise ValueError()
        seen = set()
        for item in data["files"]:
            path = PurePosixPath(item["path"])
            if path.is_absolute() or ".." in path.parts or str(path) in seen:
                raise ValueError()
            seen.add(str(path))
            if item["source"] != SOURCE_BASE + str(path):
                raise ValueError()
            if not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) or not 0 < item["bytes"] <= 70 * 1024 * 1024:
                raise ValueError()
        required = {"bin/mtk_imei.php", "data/alias.txt", "data/private_1024.pem", "data/private_2048.pem",
                    "data/begonia/nvram.bin", "data/begonia/md_patcher-4.14.186.ko", "data/begonia/updater-script.txt", "data/patch.zip", "LICENSE", "README.md"}
        if seen != required:
            raise ValueError()
        return data
    except (OSError, ValueError, KeyError, TypeError):
        raise SafeError("Pinli kaynak manifesti geçersiz.") from None


def private_dir(path):
    if path.is_symlink():
        raise SafeError("Çalışma dizininde sembolik bağlantı kabul edilmez.")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.stat()
    if not path.is_dir() or (os.name == "posix" and (info.st_uid != os.getuid() or info.st_mode & 0o077)):
        raise SafeError("Çalışma dizini size ait ve izinleri 700 olmalı.")
    return path


def runtime_dir(value=None):
    raw = Path(value) if value else Path(tempfile.gettempdir()) / ("begonia-review-" + str(os.getuid() if hasattr(os, "getuid") else "local"))
    if not raw.is_absolute() or raw.is_symlink():
        raise SafeError("Geçici çalışma dizini mutlak bir yol olmalı; sembolik bağlantı kabul edilmez.")
    path = raw.resolve()
    if within(path, ROOT):
        raise SafeError("Özel çalışma verileri depo içine yazılamaz.")
    temp_roots = {Path(tempfile.gettempdir()).resolve(), Path("/tmp").resolve()}
    if not any(within(path, parent) and path != parent for parent in temp_roots):
        raise SafeError("Çalışma dizini işletim sisteminin temp dizini altında olmalı.")
    return private_dir(path)


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verified_file(path, item):
    return (not path.is_symlink() and path.is_file() and path.stat().st_size == item["bytes"]
            and sha256_file(path) == item["sha256"])


def cache_file(cache, relative):
    result = cache / relative
    parent = cache
    for segment in PurePosixPath(relative).parts[:-1]:
        parent = private_dir(parent / segment)
    if result.is_symlink():
        raise SafeError("Önbellekte sembolik bağlantı kabul edilmez.")
    return result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise SafeError("Kaynak indirme yönlendirmesi reddedildi.")


def prepare(runtime):
    data = manifest()
    cache = private_dir(runtime / "sources")
    opener = urllib.request.build_opener(NoRedirect())
    for item in data["files"]:
        destination = cache_file(cache, item["path"])
        if verified_file(destination, item):
            continue
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as output:
                temporary = Path(output.name)
                total = 0
                with opener.open(item["source"], timeout=60) as response:
                    while True:
                        chunk = response.read(min(1024 * 1024, item["bytes"] - total + 1))
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > item["bytes"]:
                            raise SafeError("İndirilen kaynak beklenen boyutu aşıyor.")
                        output.write(chunk)
            if not verified_file(temporary, item):
                raise SafeError("İndirilen kaynağın boyut/SHA-256 doğrulaması başarısız.")
            os.replace(temporary, destination)
        except SafeError:
            raise
        except Exception:
            raise SafeError("Kaynak indirilemedi; mevcut önbellek değiştirilmedi.") from None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return cache


def verified_cache(runtime):
    cache = runtime / "sources"
    if cache.is_symlink() or not cache.is_dir():
        raise SafeError("Doğrulanmış kaynak önbelleği yok; önce prepare çalıştırılmalı.")
    data = manifest()
    for item in data["files"]:
        path = cache
        for part in PurePosixPath(item["path"]).parts:
            path = path / part
            if path.is_symlink():
                raise SafeError("Önbellekte sembolik bağlantı kabul edilmez.")
        if not verified_file(path, item):
            raise SafeError("Önbellek doğrulaması başarısız; build durduruldu.")
    return cache, data


def upstream_config(values):
    return {"device": "begonia", "product": "", "kernel": "4.14.186", "patch_cert": 1,
            "chip_id": values["CHIP_ID"], "imei_1": values["IMEI_1"], "imei_2": values["IMEI_2"],
            "wifi_mac": values["WIFI_MAC"], "bt_mac": values["BT_MAC"], "meid": ""}


def checksum8(content):
    """NVRAM record checksum, independently expressed from the pinned format."""
    digest = hashlib.md5(content).digest()
    return bytes(a ^ b for a, b in zip(digest[:8], digest[8:]))


def checksum2(content):
    total = 0
    for index, byte in enumerate(content):
        total = total + byte if index % 2 == 0 else total ^ byte
    return bytes((0xAA, total & 0xFF))


def nvram_checksum(content):
    total = 0
    aligned = len(content) - len(content) % 4
    for index, (word,) in enumerate(struct.iter_unpack("<I", content[:aligned])):
        total = (total ^ word if index % 2 == 0 else total + word) & 0xFFFFFFFF
    remainder = int.from_bytes(content[aligned:], "little")
    return ((total + remainder) & 0xFFFFFFFF) ^ len(content)


def validate_nvram(blob, values):
    """Compare private fields without returning or formatting any identifier."""
    toc_size = 0x20000
    if len(blob) < toc_size:
        raise SafeError("NVRAM üstbilgisi eksik.")
    content_size = struct.unpack_from("<I", blob, 4)[0]
    if not 0 < content_size <= len(blob) - toc_size:
        raise SafeError("NVRAM içerik sınırları geçersiz.")
    expected = struct.unpack_from("<I", blob, 12)[0]
    if nvram_checksum(memoryview(blob)[toc_size:toc_size + content_size]) != expected:
        raise SafeError("NVRAM genel checksum doğrulaması başarısız.")

    def record(path):
        toc = blob[:toc_size]
        exact_path = path + b"\0"
        position = toc.find(exact_path)
        if position < 8 or toc.find(exact_path, position + 1) != -1:
            raise SafeError("NVRAM TOC kaydı bulunamadı veya yineleniyor.")
        offset, size = struct.unpack_from("<II", toc, position - 8)
        if size < 2 or offset + size > content_size:
            raise SafeError("NVRAM kayıt sınırları geçersiz.")
        return blob[toc_size + offset:toc_size + offset + size]

    cssd_record = record(b"/mnt/vendor/nvdata/md/NVRAM/NVD_IMEI/CSSD_000")
    if len(cssd_record) < 64 + 4104:
        raise SafeError("CSSD kayıt uzunluğu geçersiz.")
    cssd = cssd_record[64:64 + 4096]
    if checksum8(cssd) != cssd_record[64 + 4096:64 + 4104]:
        raise SafeError("CSSD checksum doğrulaması başarısız.")
    match = re.search(rb"(?:^|\\n)criticalData:([0-9a-fA-F]+)(?=\\n|\x00)", cssd)
    if not match:
        raise SafeError("CSSD criticalData kaydı okunamadı.")
    try:
        critical = bytes.fromhex(match.group(1).decode("ascii"))
    except ValueError:
        raise SafeError("CSSD criticalData kodlaması geçersiz.") from None
    if critical[:4] != b"\x00\x01\x00\x62":
        raise SafeError("CSSD sürüm başlığı beklenen EEA şablonuyla eşleşmiyor.")
    fields = {}
    offset = 4
    while offset < len(critical):
        if offset + 2 > len(critical):
            raise SafeError("CSSD TLV başlığı kesilmiş.")
        tag, length = critical[offset:offset + 2]
        offset += 2
        if tag in fields or offset + length > len(critical):
            raise SafeError("CSSD TLV alanları geçersiz.")
        fields[tag] = critical[offset:offset + length]
        offset += length
    wanted = {1: values["CHIP_ID"], 2: values["IMEI_1"], 3: values["IMEI_2"],
              5: values["WIFI_MAC"].replace(":", "").upper(), 6: values["BT_MAC"].replace(":", "").upper()}
    if fields != {key: value.encode("ascii") for key, value in wanted.items()}:
        raise SafeError("Üretilen CSSD kimlik alanları özel yapılandırmayla eşleşmiyor.")
    for path, key, start in ((b"/mnt/vendor/nvdata/APCFG/APRDEB/WIFI", "WIFI_MAC", 4),
                             (b"/mnt/vendor/nvdata/APCFG/APRDEB/BT_Addr", "BT_MAC", 0)):
        entry = record(path)
        if entry[start:start + 6] != bytes.fromhex(values[key].replace(":", "")):
            raise SafeError("Üretilen Wi-Fi/BT kaydı özel yapılandırmayla eşleşmiyor.")
        if checksum2(entry[:-2]) != entry[-2:]:
            raise SafeError("Wi-Fi/BT kayıt checksum doğrulaması başarısız.")


def review_bundle(source_zip, output, cache, values):
    """Strip all installer entry points and unrelated executable helpers from the output."""
    digests = {}
    with zipfile.ZipFile(source_zip) as package:
        names = package.namelist()
        if len(names) != len(set(names)):
            raise SafeError("Üretilen ZIP yinelenen dosya içeriyor.")
        if len(names) > 64 or any(item.file_size > 70 * 1024 * 1024 for item in package.infolist()) or sum(item.file_size for item in package.infolist()) > 160 * 1024 * 1024:
            raise SafeError("Üretilen ZIP beklenen boyut sınırlarını aşıyor.")
        if package.testzip() is not None:
            raise SafeError("Üretilen ZIP CRC doğrulaması başarısız.")
        original_patch = zipfile.ZipFile(cache / "data/patch.zip")
        with original_patch:
            trusted_rc = original_patch.read("vendor/etc/init/md_patcher.rc")
            trusted_nvdata = original_patch.read("nvdata.img")
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for name, size in PAYLOADS.items():
                if name not in names or package.getinfo(name).file_size != size:
                    raise SafeError("Üretilen pakette gerekli payload eksik veya boyutu yanlış.")
                content = package.read(name)
                if name == "vendor/lib/modules/md_patcher.ko" and content != (cache / "data/begonia/md_patcher-4.14.186.ko").read_bytes():
                    raise SafeError("Üretilen modül pinli kaynakla eşleşmiyor.")
                if name == "vendor/etc/init/md_patcher.rc" and content != trusted_rc:
                    raise SafeError("Üretilen init dosyası pinli kaynakla eşleşmiyor.")
                if name == "nvdata.img" and content != trusted_nvdata:
                    raise SafeError("Üretilen NVDATA payload pinli kaynakla eşleşmiyor.")
                if name == "nvram.img" and not any(content):
                    raise SafeError("Üretilen NVRAM payload tamamen sıfır; build reddedildi.")
                if name == "nvram.img":
                    validate_nvram(content, values)
                digests[name] = {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
                bundle.writestr(name, content)
            report = {"format": "review-only-not-flashable", "upstream_commit": COMMIT,
                      "device": "begonia", "files": digests,
                      "warning": "Contains private device data. Never publish. No installer included. Kernel ABI is not verified."}
            bundle.writestr("PRIVATE-MANIFEST.json", json.dumps(report, indent=2) + "\n")
    os.chmod(output, 0o600)
    return report


def build(values, runtime, php_path, php_mode="standard"):
    php = Path(php_path) if php_path else Path("")
    if not php.is_absolute() or not php.is_file() or not os.access(php, os.X_OK):
        raise SafeError("Güvendiğiniz PHP CLI için mutlak, çalıştırılabilir dosya yolu verin.")
    if php_mode not in ("standard", "frankenphp"):
        raise SafeError("PHP çalışma modu tanınmıyor.")
    php_command = [str(php)] + (["php-cli"] if php_mode == "frankenphp" else [])
    cache, data = verified_cache(runtime)
    with tempfile.TemporaryDirectory(prefix="build-", dir=runtime) as temporary:
        workspace = Path(temporary)
        for item in data["files"]:
            destination = workspace / item["path"]
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copyfile(cache / item["path"], destination)
            os.chmod(destination, 0o600)
            if not verified_file(destination, item):
                raise SafeError("Build kopyası hash doğrulamasını geçemedi.")
        config = workspace / "config.txt"
        config.write_text(json.dumps(upstream_config(values)), encoding="utf-8")
        os.chmod(config, 0o600)
        (workspace / "out").mkdir(mode=0o700)
        child_env = {"PATH": os.defpath, "LANG": "C", "LC_ALL": "C", "TMPDIR": str(workspace)}
        quiet = "ini_set('log_errors','0');ini_set('display_errors','0');"
        probe = quiet + "exit(extension_loaded('openssl') && class_exists('ZipArchive') && bin2hex(pack('l',1)) === '01000000' ? 0 : 3);"
        try:
            check = subprocess.run(php_command + ["-r", probe], cwd=workspace, env=child_env,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            if check.returncode:
                raise SafeError("PHP OpenSSL/ZipArchive veya little-endian önkoşulu sağlanmıyor.")
            result = subprocess.run(php_command + ["-r", quiet + "require 'bin/mtk_imei.php';"], cwd=workspace, env=child_env,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
        except (OSError, subprocess.TimeoutExpired):
            raise SafeError("PHP çalıştırması tamamlanamadı; özel stdout/stderr yayımlanmadı.") from None
        generated = workspace / "out/imei_repair-begonia-4.14.186.zip"
        if result.returncode or not generated.is_file():
            raise SafeError("Upstream build geçerli çıktı üretmedi; özel stdout/stderr yayımlanmadı.")
        output_dir = Path(tempfile.mkdtemp(prefix="private-output-", dir=runtime))
        output = output_dir / "begonia-repair-review.zip"
        try:
            review_bundle(generated, output, cache, values)
        except Exception:
            shutil.rmtree(output_dir)
            raise
        return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=("validate", "prepare", "build"), default="validate")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--runtime-dir")
    parser.add_argument("--php")
    parser.add_argument("--php-mode", choices=("standard", "frankenphp"), default="standard")
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            prepare(runtime_dir(args.runtime_dir))
            print("Pinli kaynaklar boyut ve SHA-256 ile doğrulandı. Hiçbir kaynak çalıştırılmadı.")
        else:
            values = load_env(args.env_file)
            if args.command == "validate":
                print("Yapılandırma biçimi doğrulandı. Kimlik sahipliği ve çekirdek ABI uyumu bu kontrolle doğrulanamaz.")
            else:
                build(values, runtime_dir(args.runtime_dir), args.php, args.php_mode)
                print("Özel inceleme paketi temp çalışma dizininin private-output-* altına hazırlandı.")
                print("Bu paket flash edilemez; kimlik verileri içerir. Dosya yolunu veya içeriğini yayımlamayın.")
        return 0
    except SafeError as exc:
        print("Hata: " + str(exc), file=sys.stderr)
        return 2
    except Exception:
        print("Hata: İşlem güvenli biçimde durduruldu; özel hata ayrıntıları yayımlanmadı.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
