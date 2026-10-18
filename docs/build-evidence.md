# Talos 1.14.2 Pi 5 candidate build evidence (T-3)

This file records what the T-3 candidate is built from, how each input was
checked, and what the hosted runs produced. A green build here is a compile
result only. It is **not** a hardware boot, an upgrade, an Ethernet-stability
result or a storage-preservation result, and it does not authorize skipping
the Talos 1.12 and 1.13 upgrade stages. No cluster command, disk flash or
firmware change is part of this work.

## Pinned inputs

Every source is pinned to a full commit in the [Makefile](../Makefile).
`make checkouts` runs `scripts/build_contract.py verify-checkouts`, which
refuses a checkout whose `HEAD` is not the pinned commit, and refuses Talos or
pkgs sources that name different pkgs/tools versions. `make check` verifies
offline that the pins are full SHAs and that the kernel and device trees use
the same vendor archive.

| Input | Ref | Full commit | How it was verified |
| --- | --- | --- | --- |
| siderolabs/talos | `v1.14.2` (signed annotated tag `5a2b3063`) | `f513c7358cefc69255e29b517ba96c651e0326ad` | Tag object resolved locally; GitHub reports the tag signature valid. |
| siderolabs/pkgs | `v1.14.0-37-g6c312e4`, branch `release-1.14` | `6c312e4b77817a9c1bd4975a532b3fd23d33430c` | Named by Talos v1.14.2 `Makefile` (`PKGS ?=`); `git describe` of the full SHA gives the same string; GitHub reports the commit signature valid. |
| siderolabs/tools | `v1.14.0-8-g9776960`, branch `release-1.14` | `9776960bd8b0b0c3b2938e1e4c85c5a5700bb2ab` | Named by Talos v1.14.2 `Makefile` (`TOOLS ?=`) and the pkgs `Pkgfile` (`TOOLS_REV`); `git describe` matches; signature valid. The build consumes it as the `ghcr.io/siderolabs/tools` image of that tag. |
| siderolabs/sbc-raspberrypi | `v0.2.2` (signed annotated tag) | `7aba05ed529e837959cfd15636d53c4e43fb39f2` | siderolabs/overlays `v1.14.2` (`internal/overlays/overlays.yaml`) names `sbc-raspberrypi:v0.2.2` for `rpi_5`; tag signature valid. |
| raspberrypi/linux | `stable_20260911` (lightweight tag on `rpi-6.18.y`), Linux 6.18.50 | `cff533aec2fa601846766b32ff57204e0a61bed7` | Tag resolved through the GitHub API; `Makefile` read at the commit; the archive's embedded commit ID matches. The vendor commit is unsigned, as are Raspberry Pi's kernel commits generally. |

GitHub archive digests (SHA-256) of those commits, checked against the git
trees (`git archive` of each commit extracts to identical files, and each
archive's embedded commit ID matches):

| Archive | SHA-256 |
| --- | --- |
| `raspberrypi/linux/archive/cff533aec2fa…tar.gz` | `6c58de91ade97d7cd9176e408f05c9d134cda64dba95a87b7af976bf26c0c0bd` |
| `siderolabs/talos/archive/f513c7358cef…tar.gz` | `85811a8fe16cc2434c023e2d13d5e6fafecaf4e1a21129c06b6fb8e6a46044ff` |
| `siderolabs/pkgs/archive/6c312e4b7781…tar.gz` | `3a36cf4a4d6ba05bb545e5e3ca3270c7cbb353c15741ce138810730eb0bc5395` |
| `siderolabs/tools/archive/9776960bd8b0…tar.gz` | `ff962e56faa4ab3953fa8226de3f7df4d6458844e93ea84039fac558f16d079e` |
| `siderolabs/sbc-raspberrypi/archive/7aba05ed529e…tar.gz` | `51983e51f64b2997ed79dc699fe19a150758ef91ec1c86ba1ec95b8cde2cdc35` |

The vendor archive was downloaded twice with the same digest. Its SHA-256 and
SHA-512 are committed in both the pkgs and sbc-raspberrypi patches, and bldr
checks both during the build. The other repositories are cloned with git and
checked by commit.

### Why stable_20260911

Talos 1.14.2's pkgs builds kernel.org 6.18.54. Raspberry Pi's newest release
tag, `stable_20260911`, is the same 6.18 LTS series (6.18.50), so the pkgs
6.18 configuration applies without a series change. The `rpi-6.18.y` branch
head (6.18.57 on 2026-10-16) is a moving development branch, and no vendor
commit is exactly 6.18.54: the branch merged 6.18.53 and then 6.18.55. A tag
Raspberry Pi published is preferred over an arbitrary branch commit. The same
commit feeds the kernel package and the overlay's device trees.

## Kernel configuration

`kernel/build/config-arm64` in the pkgs patch is the pkgs `6c312e4`
configuration with the Raspberry Pi option delta re-applied. The delta is
computed option by option between pkgs `969f61c` (Talos 1.13.2) and the
inherited 1.13.2 Pi configuration from johnlaur/talos-builder `9e8a06cc`. It
has 295 explicit values after dropping removals that only reflected the old
vendor tree. Then, deliberately:

- `MMC_SDHCI`, `USB_XHCI_HCD`, `USB_XHCI_PCI`, `USB_XHCI_PLATFORM`,
  `USB_STORAGE`, `USB_UAS` and `USB_HID` stay built in, as in the 1.13.2 Pi
  build. pkgs 1.14 turned them into modules, which would have made the SD
  card, USB host and USB storage depend on module loading.
- `ARM64_BTI_KERNEL` is off. Linux 6.18.52 disables it for clang >= 21
  (llvm/llvm-project#215547). The pinned vendor 6.18.50 predates that change,
  and the pkgs toolchain is LLVM 22.1.8.
- `CPU_FREQ_DEFAULT_GOV_ONDEMAND` is unset. The 1.13 file set both ondemand
  and schedutil; schedutil already won as the later entry.
- The 1.13 delta had turned off some Talos defaults with no Pi hardware
  reason. These keep their Talos 1.14.2 values: `DM_AUDIT`, `DM_INTEGRITY`,
  `IPV6_GRE`, `IPV6_MROUTE`, `NFT_CONNLIMIT`, `NET_TC_SKB_EXT`,
  `INFINIBAND_USER_ACCESS`, `INFINIBAND_USER_MAD`, `HID_MULTITOUCH`, `IDPF`
  and `MLX5_SF`. Pi-specific choices stay as the 1.13 delta set them: 16K
  pages, vendor `MFD_RP1` with mainline `MISC_RP1` off, and Panthor/DRM accel,
  PCI Meson, powercap and GPIO fan off.

Checks run locally without compiling:

- The Talos hardening gate (kernel-hardening-checker at the pkgs-pinned
  `1315e5b9`, archive SHA-256 verified, filtered by the pkgs
  `filter-hardened-check.py`) passes for the new configuration.
- An offline Kconfig resolution of the configuration against the patched vendor
  tree (kconfiglib 14.1.0, with canned toolchain answers, no tree scripts run)
  changes only derived values (16K-page shifts, selects), `AQTION`,
  `DRM_VC4` and `HID_LOGITECH` to modules (forced by `MACSEC`/`SND`
  dependencies), and adds vendor-only symbols with their defaults.
- Pi 5 essentials are built in: `MFD_RP1`, `PINCTRL_RP1`, `COMMON_CLK_RP1`,
  `MACB` with `BROADCOM_PHY`, `PCIE_BRCMSTB`, `MMC_SDHCI_BRCMSTB`, `USB_DWC3`,
  xHCI, USB storage/UAS, `XFS_FS` with POSIX ACLs, `RASPBERRYPI_FIRMWARE`,
  `BCM2712_IOMMU`, `RTC_DRV_RPI` and `EFI_ZBOOT`. Lockdown, module signing,
  SquashFS and overlayfs are unchanged from the Talos values.

## Talos module list

Talos stages `hack/modules-arm64.txt` into the rootfs with `install -D`, then
fails on any depmod warning. Every listed module must therefore be built as a
module. The Talos patch keeps the upstream v1.14.2 list in order and only
removes entries. Each entry's Kbuild rule was evaluated against the resolved
configuration: 110 upstream modules are built in on this configuration, and
`drm_gpuvm.ko` is not built because Panthor is off. 216 modules and the three
`modules.*` metadata entries remain. No option that Talos 1.14.2 builds in is
a module here, so a kept module cannot lose a dependency that upstream
provided built in, and the list stays closed under dependencies.

The 1.13.2 builder shipped every module its build produced, including amdgpu,
sound, UVC, USB network adapters, btrfs, nfsd and the Pi SMI driver. None of
those is a Pi 5 boot, network or storage requirement, so they are not carried.

## Device trees and overlay

The overlay is siderolabs/sbc-raspberrypi v0.2.2, which ships U-Boot 2026.01
and the rpi_5 installer. Its patch builds `bcm2712*.dtb` and the overlays from
the same vendor commit as the kernel, fetched by commit with the same archive
hashes. It skips the overlay's ten device-tree patches, which adapt vendor
device trees to mainline drivers (RP1 nexus node, RP1 Ethernet for the mainline
`macb` binding, bcm2712 DMA removal, PCIe range, overlay maps). The vendor
kernel carries the vendor drivers these trees were written for. The patch also
drops `gpu_mem=32` and `hdmi_safe` from the Pi 5 `config.txt`, as the 1.13.2
builder did. The current node boots U-Boot 2025.04, so the bootloader version
changes. That has not been tested.

## Patch dispositions

Vendor history evidence comes from `raspberrypi/linux` commits, all confirmed
ancestors of `cff533aec2fa` through the GitHub compare API. Dry runs used
`patch -p1 --dry-run`, forward and reverse, against the extracted vendor
archive. The kept patches were applied in order with `patch -p1`, as the pkgs
build does, with no fuzz (offsets only).

| Patch | Disposition | Evidence |
| --- | --- | --- |
| pkgs `0001-net-macb-flush-PCIe-posted-write-after-TSTART-doorbe` | Already in vendor; dropped | `a9e13da2dc4c` (flush) and `b1b307c0ab22` (gate behind `MACB_CAPS_PCIE_POSTED_WRITES`, set on `raspberrypi_rp1_config`). The flag and both gated read-backs are present in `macb_main.c`. |
| pkgs `0002-net-macb-insert-PCIe-read-barrier-before-TX-completi` | Reverted in vendor; dropped | Vendor carried the same change as `60fc80b89d13`, then reverted it (`86a1889a9633`) together with its v1 ISR re-check (`ff6914e97386`, reverted by `560624d8e894`). Would apply forward, but that would re-add what Raspberry Pi removed. |
| pkgs `0003-net-macb-add-TX-stall-watchdog-to-recover-from-lost-` | Superseded in vendor; dropped | Vendor reverted the watchdog (`79dc190b12f9` by `7f49766f02bb`) and its follow-up (`b2f7eec2bfff` by `d57db18eddb0`). The kernel now uses upstream `e438ec3e9e95` "add TX stall timeout callback" (`73ad03c8b5d3` and stable `68af74ad696c`; `.ndo_tx_timeout = macb_tx_timeout`). Does not apply. |
| pkgs `0004-PCI-prevent-shrink-bridge-window` | Kept | Not in 6.18.50; applies cleanly. |
| pkgs `0007-tun-dst-unclone` | Kept | Applies cleanly. |
| pkgs `0008`–`0011` macb EEE (LPI counters, TX LPI, ethtool EEE, RP1 enable) | Already in vendor; dropped | `a37e075be788`, `8a15cb90f40e`, `70d75c74a569`, `f6c4ee984e39`. 0008, 0010 and 0011 reverse-apply. 0009 is rebased in pkgs with `MACB_CAPS_EEE` `0x4000`, while vendor uses `0x2000`, and `macb_tx_lpi_*` is present. |
| pkgs `0012`–`0016` libceph aes256k and bounds fix | Kept | Apply in sequence; `CRYPTO_KRB5` is in the configuration. |
| pkgs `0017-security-lockdown-lock-down-the-kernel-in-EFI-Secure-` | Kept | Applies; `LOCK_DOWN_IN_EFI_SECURE_BOOT=y`. |
| pkgs `0018-efistub-x86-Fix-the-size-type-of-the-Apple-propertie` | Kept | Applies; x86-only code, inert on arm64. |
| local `patches/linux/0001-net-macb-gate-PCIe-posted-write-flush` | Already in vendor; removed | Same change as vendor `b1b307c0ab22`; reverse-applies. |
| local `patches/linux/0002-net-macb-drop-destructive-ISR-read` | Reverted in vendor; removed | Vendor `60fc80b89d13`, reverted by `86a1889a9633`; does not apply. |
| local `patches/linux/0003-net-macb-gate-TX-stall-watchdog` | Reverted in vendor; removed | Vendor `b2f7eec2bfff`, reverted by `d57db18eddb0`; does not apply. |
| old pkgs `0005-PCI-fix-premature-removal-realloc-head` (1.13) | Upstream | Dropped by pkgs 1.14 itself; reverse-applies to the vendor tree. |
| `pkgs/0002-Support-alternative-sed-interpreter` | Obsolete; removed | Only let macOS use `gsed`. The hosted Linux runner uses GNU sed. |
| `talos/0002-Makefile` (sed) | Obsolete; removed | Same macOS-only purpose; no longer applies to v1.14.2. |
| `pkgs/0001`, `talos/0001`, `sbc-raspberrypi/0001` "Patched for Raspberry Pi 5" | Ported | Regenerated on the pinned commits as described above; each `git apply --check`s cleanly there. |

The Makefile deletes the seven pkgs kernel patches named above with `rm` and
no `-f`, so a pin change that renames or drops them stops the build.
Kernel driver development was not needed.

## Extensions

No system extensions are built in or added. No current workload uses gVisor,
iSCSI, Longhorn or GPU extensions, and no extension is needed to boot, network
or store data on this node. The inherited iSCSI/util-linux example was removed
from `talos.env.example`. Adding an extension needs a reviewed, pinned input
change with a documented need. No live extension change is authorized.

## Hosted runs

Fast CI (`ci.yml`) runs on every push. The candidate workflow (`build.yaml`)
runs only by manual dispatch of a `main` commit whose fast CI passed.

| Run | Head SHA | Outcome | Notes |
| --- | --- | --- | --- |
| _none yet_ | | | |

## Limitations

- Compile-only evidence: not booted, not upgraded, no Ethernet soak, no
  storage-preservation test. The USB XFS volume and the SD boot medium were not
  touched.
- The vendor kernel is 6.18.50, four stable releases behind the 6.18.54 that
  upstream Talos 1.14.2 ships. Fixes from 6.18.51 to 6.18.54 are absent unless
  Raspberry Pi carried them.
- Device trees come unpatched from the vendor tree, and U-Boot is the overlay's
  2026.01. Neither has been tested on this hardware.
- The configuration review used offline Kconfig resolution with assumed
  compiler capabilities. The hosted build's own `syncconfig` is authoritative.
- The kernel SBOM records the vendor commit as the kernel version string.

## Next action

Dispatch the candidate workflow for the pushed `main` head once its fast CI
passes, then record the run here. Hardware boot, cold restart,
Ethernet/etcd traffic and storage tests are a later, separately approved stage.
A live migration still has to go through the 1.12 and 1.13 stages.
