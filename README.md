# begonia-repair-toolkit

A tool for preparing a private repair package on your computer, with documentation of an EEA ROM and NV repair on the Redmi Note 8 Pro **begonia**. Its scope is **MIUI EEA V12.5.15.0.RGGEUXM / Android 11** and the **4.14.186** kernel family. It does not target the Redmi 7 or other devices.

This tool prepares restoration of the target phone's own original IMEIs. It does not generate IMEIs, copy another device's identity, or register a phone in Türkiye. Preparing a repair package does not change the phone's registration status. The Python tool never accesses a phone through ADB, fastboot, or USB.

## Findings from this repair

- The EEA ROM was installed. The inspected NVRAM partition contained only zeros; the initial backup preserved that state and was not a valid factory calibration backup.
- Four files had incorrect SELinux labels: `nvdata/fstab.mt6785`, `nvdata/md/NVRAM/NVD_CORE/MTCR_000`, `nvdata/media/Audio_ver1_Vol_custom`, and `protect_s/md/NA77_006`.
- Stock labels were applied without changing file content hashes. The subsequent recovery log contained `--show_bad_nv`, confirming that NV validation was preventing normal boot. Correcting labels alone does not restore original NV contents.
- Android booted after repair using verified partition backups, pinned sources, and separately checked writes. The user **confirmed that calls and mobile data worked**. Diagnosis of the YouTube/speaker audio issue remains incomplete; this is not a claim that every device function has been restored.

These findings describe one device. Similar symptoms can have different causes on other phones. This repository contains no personal device identifiers, logs, backups, or firmware.

## Three commands

Python 3.9+ is required. `build` additionally requires a trusted PHP CLI with OpenSSL, ZipArchive, and a little-endian runtime. `prepare` downloads sources; `build` runs the pinned upstream PHP code on your computer. Installing PHP is outside this tool's scope.

Create a private configuration in a temporary directory:

```sh
TASK_WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/begonia-private.XXXXXX")"
PRIVATE_ENV="$TASK_WORKDIR/device.env"
cp .env.example "$PRIVATE_ENV"
chmod 600 "$PRIVATE_ENV"
```

Fill in `PRIVATE_ENV` using a local editor. Do not put IMEIs in terminal commands, screenshots, issues, or the README. Use only this phone's own original IMEIs and verified chip/MAC information for the device. Do not fill unknown fields with values copied from another phone or the internet. The tool does not generate missing identifiers or MAC addresses. MAC validation checks only for a nonzero unicast address; it does not prove that an address is the factory value or belongs to the device.

```sh
# validate is also the default: no downloads or PHP execution.
python3 repair_builder.py validate --env-file "$PRIVATE_ENV"

# Download pinned sources into temp and verify their hashes; do not execute them.
python3 repair_builder.py prepare --runtime-dir "$TASK_WORKDIR/runtime"

# Run the pinned upstream code with the supplied PHP executable; do not access the phone.
python3 repair_builder.py build --env-file "$PRIVATE_ENV" \
  --runtime-dir "$TASK_WORKDIR/runtime" --php /absolute/path/to/php
```

For FrankenPHP, use:

```sh
python3 repair_builder.py build --env-file "$PRIVATE_ENV" \
  --runtime-dir "$TASK_WORKDIR/runtime" \
  --php /absolute/path/to/frankenphp --php-mode frankenphp
```

The tool adds the `php-cli` subcommand automatically. Set `--php` to the absolute path of an executable you trust.

Configuration uses plain `KEY=VALUE` text and is never evaluated as shell code. `export`, variable expansion, command execution, escape sequences, and inline comments are unsupported. The file must belong to you and have POSIX permissions of `600`. Error messages do not print field values, upstream stdout/stderr, or private file paths.

## Output and limitations

Output is written to `$TASK_WORKDIR/runtime/private-output-*/begonia-repair-review.zip`. **This file contains device identifiers, must remain private, and cannot be flashed directly in recovery.** It contains only `nvram.img`, `nvdata.img`, the vendor module, its init file, and a private hash manifest. Upstream installer entry points and other executable helpers are excluded. The temporary original flashable ZIP and `config.txt` are removed after the build.

Validation covers IMEI format/Luhn checks, chip and MAC formats, pinned source sizes/SHA-256 hashes, ZIP CRCs, NVRAM TOC bounds and its overall checksum, CSSD checksum and TLV matches for both IMEIs/chip/MACs, Wi-Fi/BT records and their checksums, and module/init/NVDATA matches against the pinned sources. These checks do not establish ownership, carrier registration, factory calibration, or RF quality. The template does not recover original calibrations.

The pinned module's vermagic is `4.14.186-g215472d`; the stock kernel in this case was `4.14.186-g4e5507d5edae`. Matching version prefixes do not guarantee ABI compatibility. The upstream init file attempts a normal module load followed by a forced load. If the first succeeds, an “already exists” result from the second is not itself a failure. Module loading and modem behavior require separate verification.

## Applying the repair to a phone

Installation is manual. Preparing a review package does not write anything to the device. **Keep the bootloader unlocked; do not relock it.** Verify actual partition names, mount points, backup restoration options, and vendor writes before writing payloads. The sequence used in this case is documented in the [recovery procedure](docs/recovery-checklist.md). Those notes contain no personal identifiers or device serial numbers.

The upstream installer is excluded because its fixed `/nvdata` mount point may differ from the actual `/mnt/vendor/nvdata` mount, vendor write results are not asserted, and detecting `standalone` in the recovery shell can cause the non-Magisk path to return success without writing anything. In edify, `run_program(...) && ...` does not test success the way a shell does. The review package does not include this installer.

## Privacy and testing

`.gitignore` excludes private env files, configurations, backups, firmware, binaries, and logs. It is not a security boundary and does not remove files already tracked by Git. Inspect staged files before publishing. Hashes and generated packages can also be associated with a device; do not attach them to issues or releases. Deleting temporary files is not a guarantee of secure disk erasure. Keep restoration backups until the procedure and hardware tests are complete.

```sh
python3 -m unittest discover -s tests -v
git diff --cached --stat
git diff --cached --check
```

Tests use synthetic values, do not access a phone, and require neither network access nor PHP. Full build verification requires a suitable PHP runtime and the pinned source cache. Source attribution and licensing details are in [THIRD_PARTY.md](THIRD_PARTY.md) and [LICENSE](LICENSE).

Verified ROM/recovery download sources and runtime details are listed on the [sources page](docs/sources.md).
