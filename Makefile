# Talos v1.14.2 and the inputs it names, pinned to full commits. Evidence for
# each pin and patch disposition: docs/build-evidence.md.
TALOS_VERSION := v1.14.2
TALOS_COMMIT := f513c7358cefc69255e29b517ba96c651e0326ad
# Talos v1.14.2 Makefile: PKGS ?= v1.14.0-37-g6c312e4, on the release-1.14 branch.
PKG_VERSION := release-1.14
PKG_COMMIT := 6c312e4b77817a9c1bd4975a532b3fd23d33430c
TALOS_PKGS_VERSION := v1.14.0-37-g6c312e4
# Talos v1.14.2 Makefile TOOLS and pkgs Pkgfile TOOLS_REV; consumed as the
# ghcr.io/siderolabs/tools image tag, not cloned.
TOOLS_VERSION := v1.14.0-8-g9776960
TOOLS_COMMIT := 9776960bd8b0b0c3b2938e1e4c85c5a5700bb2ab
# siderolabs/overlays v1.14.2 names sbc-raspberrypi v0.2.2 for rpi_5.
SBCOVERLAY_VERSION := v0.2.2
SBCOVERLAY_COMMIT := 7aba05ed529e837959cfd15636d53c4e43fb39f2
# Raspberry Pi vendor kernel and device trees, both from this commit. Its
# archive hashes live in the pkgs and sbc-raspberrypi patches.
RPI_KERNEL_VERSION := stable_20260911
RPI_KERNEL_COMMIT := cff533aec2fa601846766b32ff57204e0a61bed7

PUSH ?= false
REGISTRY ?= localhost:5000
REGISTRY_USERNAME ?= donvargax/talos-builder
TAG ?= candidate-$(shell git rev-parse HEAD)

CONFIG_TXT ?= dtparam=i2c_arm=on

EXTENSIONS ?=
EXTENSION_ARGS := $(foreach ext,$(EXTENSIONS),--system-extension-image $(ext))

EXTRA_KERNEL_ARGS ?=
EXTRA_KERNEL := $(foreach arg,$(EXTRA_KERNEL_ARGS),--extra-kernel-arg $(arg))

PKG_REPOSITORY := https://github.com/siderolabs/pkgs.git
TALOS_REPOSITORY := https://github.com/siderolabs/talos.git
SBCOVERLAY_REPOSITORY := https://github.com/siderolabs/sbc-raspberrypi

CHECKOUTS_DIRECTORY := $(CURDIR)/checkouts
PATCHES_DIRECTORY := $(CURDIR)/patches

PKGS_TAG = $(TAG)
TALOS_TAG = $(TAG)
SBCOVERLAY_TAG = $(TAG)

.DEFAULT_GOAL := help
.PHONY: check plan hosted-guard
check:
	python3 -m unittest discover -s tests -v
	itos config check

plan:
	@python3 scripts/build_contract.py plan

# Never run inherited build/publish recipes outside the controlled hosted job.
hosted-guard:
	@bash scripts/hosted-guard.sh "$(REGISTRY)" "$(REGISTRY_USERNAME)" "$(TAG)" "$(PUSH)"

kernel overlay imager installer-base initramfs-kernel installer image pi5 checkouts-clean: | hosted-guard

#
# Help
#
.PHONY: help
help:
	@echo "check / plan    : Offline checks / print candidate plan (no build)"
	@echo "Build targets are restricted to the manual hosted ARM64 candidate workflow."
	@echo "checkouts        : Clone repositories required for the build"
	@echo "patches          : Apply all patches for Raspberry Pi 5"
	@echo "kernel           : Build kernel"
	@echo "overlay          : Build Raspberry Pi 5 overlay"
	@echo "imager           : Build imager docker image"
	@echo "installer-base   : Build installer-base docker image"
	@echo "initramfs-kernel : Build kernel and initramfs"
	@echo "installer        : Build installer"
	@echo "image            : Build disk image for Raspberry Pi 5"
	@echo "pi5              : Full build pipeline for Raspberry Pi 5"
	@echo "clean            : Clean up any remains"

#
# Checkouts
#
.PHONY: checkouts checkouts-clean
checkouts:
	git clone -c advice.detachedHead=false --single-branch --branch "$(PKG_VERSION)" "$(PKG_REPOSITORY)" "$(CHECKOUTS_DIRECTORY)/pkgs"
	cd "$(CHECKOUTS_DIRECTORY)/pkgs" && git checkout --detach "$(PKG_COMMIT)"
	git clone -c advice.detachedHead=false --single-branch --branch "$(TALOS_VERSION)" "$(TALOS_REPOSITORY)" "$(CHECKOUTS_DIRECTORY)/talos"
	git clone -c advice.detachedHead=false --single-branch --branch "$(SBCOVERLAY_VERSION)" "$(SBCOVERLAY_REPOSITORY)" "$(CHECKOUTS_DIRECTORY)/sbc-raspberrypi"
	python3 scripts/build_contract.py verify-checkouts

checkouts-clean:
	rm -rf "$(CHECKOUTS_DIRECTORY)/pkgs"
	rm -rf "$(CHECKOUTS_DIRECTORY)/talos"
	rm -rf "$(CHECKOUTS_DIRECTORY)/sbc-raspberrypi"

#
# Patches
#
.PHONY: patches-pkgs patches-talos patches-sbc-raspberrypi patches
patches-pkgs:
	cd "$(CHECKOUTS_DIRECTORY)/pkgs" && \
		git am "$(PATCHES_DIRECTORY)/siderolabs/pkgs/0001-Patched-for-Raspberry-Pi-5.patch"

patches-talos:
	cd "$(CHECKOUTS_DIRECTORY)/talos" && \
		git am "$(PATCHES_DIRECTORY)/siderolabs/talos/0001-Patched-for-Raspberry-Pi-5.patch"

patches-sbc-raspberrypi:
	cd "$(CHECKOUTS_DIRECTORY)/sbc-raspberrypi" && \
		git am "$(PATCHES_DIRECTORY)/siderolabs/sbc-raspberrypi/0001-Patched-for-Raspberry-Pi-5.patch"

# pkgs kernel patches the pinned vendor kernel already contains (MACB PCIe
# posted-write flush and EEE) or deliberately reverted in favour of upstream
# TX-timeout recovery (MACB ISR/IMR barrier and stall watchdog). rm without -f
# fails if a pin drifts. The other pkgs kernel patches apply and are kept.
PKGS_KERNEL_PATCHES_IN_VENDOR := \
	0001-net-macb-flush-PCIe-posted-write-after-TSTART-doorbe.patch \
	0002-net-macb-insert-PCIe-read-barrier-before-TX-completi.patch \
	0003-net-macb-add-TX-stall-watchdog-to-recover-from-lost-.patch \
	0008-net-cadence-macb-add-EEE-LPI-statistics-counters.patch \
	0009-net-cadence-macb-implement-EEE-TX-LPI-support.patch \
	0010-net-cadence-macb-add-ethtool-EEE-support.patch \
	0011-net-cadence-macb-enable-EEE-for-Raspberry-Pi-RP1.patch

patches-linux:
	cd "$(CHECKOUTS_DIRECTORY)/pkgs/kernel/build/patches" && rm -v -- $(PKGS_KERNEL_PATCHES_IN_VENDOR)

patches: patches-pkgs patches-talos patches-sbc-raspberrypi patches-linux

.PHONY: kernel
kernel:
	cd "$(CHECKOUTS_DIRECTORY)/pkgs" && \
		$(MAKE) \
			TAG=$(PKGS_TAG) REGISTRY=$(REGISTRY) USERNAME=$(REGISTRY_USERNAME) PUSH=$(PUSH) \
			PLATFORM=linux/arm64 \
			kernel

.PHONY: overlay
overlay:
	@echo SBCOVERLAY_TAG = $(SBCOVERLAY_TAG)
	cd "$(CHECKOUTS_DIRECTORY)/sbc-raspberrypi" && \
		$(MAKE) \
			TAG=$(SBCOVERLAY_TAG) REGISTRY=$(REGISTRY) USERNAME=$(REGISTRY_USERNAME) IMAGE_TAG=$(SBCOVERLAY_TAG) PUSH=$(PUSH) \
			INSTALLER_ARCH=arm64 PLATFORM=linux/arm64 \
			sbc-raspberrypi

.PHONY: imager
imager:
	cd "$(CHECKOUTS_DIRECTORY)/talos" && \
		$(MAKE) \
			TAG=${TALOS_TAG} REGISTRY=$(REGISTRY) USERNAME=$(REGISTRY_USERNAME) PUSH=$(PUSH) \
			PKG_KERNEL=$(REGISTRY)/$(REGISTRY_USERNAME)/kernel:$(PKGS_TAG) \
			INSTALLER_ARCH=arm64 PLATFORM=linux/arm64 \
			imager

.PHONY: installer-base
installer-base:
	cd "$(CHECKOUTS_DIRECTORY)/talos" && \
		$(MAKE) \
			TAG=${TALOS_TAG} REGISTRY=$(REGISTRY) USERNAME=$(REGISTRY_USERNAME) PUSH=$(PUSH) \
			PKG_KERNEL=$(REGISTRY)/$(REGISTRY_USERNAME)/kernel:$(PKGS_TAG) \
			INSTALLER_ARCH=arm64 PLATFORM=linux/arm64 \
			installer-base

.PHONY: initramfs-kernel
initramfs-kernel:
	cd "$(CHECKOUTS_DIRECTORY)/talos" && \
		$(MAKE) \
			TAG=${TALOS_TAG} REGISTRY=$(REGISTRY) USERNAME=$(REGISTRY_USERNAME) \
			PKG_KERNEL=$(REGISTRY)/$(REGISTRY_USERNAME)/kernel:$(PKGS_TAG) \
			INSTALLER_ARCH=arm64 PLATFORM=linux/arm64 \
			initramfs kernel

.PHONY: installer
installer:
	cd "$(CHECKOUTS_DIRECTORY)/talos" && \
		docker \
			run --rm --network=host -v ./_out:/out -v /dev:/dev --privileged $(REGISTRY)/$(REGISTRY_USERNAME)/imager:$(TALOS_TAG) \
			installer \
			--arch arm64 \
			--base-installer-image="$(REGISTRY)/$(REGISTRY_USERNAME)/installer-base:$(TALOS_TAG)" \
			--overlay-name="rpi_5" \
			--overlay-image="$(REGISTRY)/$(REGISTRY_USERNAME)/sbc-raspberrypi:$(SBCOVERLAY_TAG)" \
			--overlay-option="configTxtAppend=$(CONFIG_TXT)" \
			$(EXTENSION_ARGS) \
			$(EXTRA_KERNEL)

.PHONY: image
image:
	cd "$(CHECKOUTS_DIRECTORY)/talos" && \
		docker \
			run --rm --network=host -v ./_out:/out -v /dev:/dev --privileged $(REGISTRY)/$(REGISTRY_USERNAME)/imager:$(TALOS_TAG) \
			metal \
			--arch arm64 \
			--base-installer-image="$(REGISTRY)/$(REGISTRY_USERNAME)/installer-base:$(TALOS_TAG)" \
			--overlay-name="rpi_5" \
			--overlay-image="$(REGISTRY)/$(REGISTRY_USERNAME)/sbc-raspberrypi:$(SBCOVERLAY_TAG)" \
			--overlay-option="configTxtAppend=$(CONFIG_TXT)" \
			$(EXTENSION_ARGS) \
			$(EXTRA_KERNEL)

.PHONY: pi5
pi5:
	bash scripts/candidate.sh build

.PHONY: clean
clean: checkouts-clean
