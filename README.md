# Raspberry Pi 5 Talos builder

This public fork of [johnlaur/talos-builder](https://github.com/johnlaur/talos-builder)
prepares custom Talos Linux candidates for Raspberry Pi 5 using the
[Raspberry Pi vendor kernel](https://github.com/raspberrypi/linux) and matching
device trees. The committed inputs target Talos **1.14.2**: Talos, pkgs, tools
and the `sbc-raspberrypi` v0.2.2 overlay are pinned to full commits, and the
kernel and Pi 5 device trees both come from Raspberry Pi's `stable_20260911`
vendor kernel (Linux 6.18.50). [Build evidence](docs/build-evidence.md) records
how each pin was verified, what happened to each carried patch, and every
hosted candidate run.

No candidate has been hardware-tested. A green offline check or a successful
hosted compile does not establish boot compatibility, upgrade safety, Ethernet
stability or preservation of data, and does not authorize skipping the 1.12
and 1.13 upgrade stages. See [the approved build plan](docs/build-plan.md) for
scope and work order.

## Safe local checks

With Python 3, Bash, GNU Make, Git and the repository-pinned itos 6.5.1 installed:

```bash
make check
make plan
make -n plan
```

`make check` runs stdlib `unittest` contract tests, parses workflows, checks shell
and Python syntax, and validates itos configuration/task data. It does not build,
download dependencies, invoke Docker, or contact a cluster. `make plan` prints
the committed inputs and phases without executing them. `make check` also
verifies that every source pin is a full commit and that the kernel and device
trees share one vendor archive. `make checkouts` refuses checkouts that are not
those commits. Build targets refuse execution outside the controlled hosted
ARM64 job.

Pushes and pull requests run only these fast checks and managed-commit
verification in [ci.yml](.github/workflows/ci.yml). CI installs itos 6.5.1 only
after checking its release checksum manifest against the committed hash and
verifying the platform archive. No PR write permissions or registry credentials
are used. itos watches this workflow for the exact pushed SHA.

## Manual hosted candidate pipeline

[build.yaml](.github/workflows/build.yaml) accepts only `workflow_dispatch`, with
no version/ref inputs. Once a pushed `main` commit's fast CI passes, an
authorized maintainer may select the workflow's **Run workflow** action on
`main`. The job checks out the dispatch SHA, runs on GitHub-hosted
`ubuntu-24.04-arm`, and has a 180-minute timeout and one-at-a-time concurrency.
Tags and ordinary pushes never start image builds.

Kernel, overlay, installer-base and imager intermediates stay in a registry bound
to the ephemeral runner's loopback address. Native ARM64 BuildKit and the imager
use host networking to reach `localhost:5000`; BuildKit explicitly allows HTTP
only for this local registry. A nonempty neutral daemon flag disables the
Buildx action's default insecure entitlements. The namespace is
`donvargax/talos-builder`, and
tags include the full commit SHA, run ID and attempt. `PUSH=true` in this job means
push to that local registry, **not GHCR**. No public image uploads, GitHub releases,
production tags or `latest` tags are created. Checkout does not retain its token;
the job has only `contents: read`. The privileged imager container is confined
to the disposable hosted runner, not a local or cluster machine.

The job uploads `pi5-candidate-<SHA>-<run ID>-<attempt>` evidence for 14 days,
including on failure. A successful build must include:

- `metal-arm64-rpi5.raw.xz`, the compressed raw Pi 5 recovery image;
- `installer-arm64.tar`, the installer container archive, without publication;
- `SHA256SUMS` for the captured files;
- `provenance.json`, recording committed pins, input/patch hashes, resolved
  checkout commits before/after patches, runner identity and tool versions;
- the printed plan and phase logs, plus bounded local registry/builder diagnostics.

Failure evidence can contain metadata/logs without either image. GitHub's step
logs remain the source for checkout or tool-bootstrap failures and runner timeout
diagnostics. Always verify the run's SHA and step outcomes; artifact names alone
do not prove success. No runtime machine configuration, credential files, full
environment dumps, or historical Actions logs are collected.

Workflows are written as JSON, a valid YAML subset, so offline checks can parse
their full structure with Python's standard library. Regression tests reject
automatic build triggers, arbitrary inputs, write credentials, public publication,
unsafe namespaces/tags and missing failure-artifact handling. Action commits,
Buildx version, BuildKit image digest and registry image digest are pinned.

## Extensions and hardware scope

No system extensions are selected by default. No current workload needs
gVisor, iSCSI, Longhorn or GPU extensions, and the inherited iSCSI/util-linux
example is gone. Add an extension only through a reviewed, pinned input change
with a documented need; no live extension change is authorized.

The kernel keeps the Pi 5 RP1 Ethernet, SD, USB host and storage, and XFS
support built in, with the Talos hardening gate passing. Carried MACB/Ethernet
patches that the vendor kernel already contains, or that Raspberry Pi reverted,
are no longer applied; see [build evidence](docs/build-evidence.md#patch-dispositions).

Upstream reported tests on the following hardware for earlier builds. These are
upstream historical reports, not verification of a candidate from this fork:

| Hardware reported by upstream |
| --- |
| Raspberry Pi Compute Module 5 on Compute Module 5 IO Board |
| Raspberry Pi Compute Module 5 Lite on [DeskPi Super6C](https://wiki.deskpi.com/super6c/) |
| Raspberry Pi 5b with [RS-P11 for RS-P22 RPi5](https://wiki.52pi.com/index.php?title=EP-0234) |

Upstream also reported that USB is available after Linux starts, but not in
U-Boot. This fork has not re-tested that limitation. Booting images, flashing
disks, changing firmware and cluster upgrades require separate approval; they
are not part of the candidate-build pipeline.

## Attribution and license

The original builder, carried patches and their authorship remain attributed to
[johnlaur/talos-builder](https://github.com/johnlaur/talos-builder). Preserve patch
origin headers when porting. See [LICENSE](LICENSE).
