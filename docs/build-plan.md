# Public Pi 5 candidate build plan

## Approved scope

On 2026-10-08 the user approved this public fork and GitHub-hosted ARM64 builds,
then asked to proceed. Target the latest verified stable Talos **1.14.2**, using
the Raspberry Pi vendor kernel. Prepare a candidate, not a production release.
Do not compile locally or perform any cluster or hardware changes.

The target hardware is a Raspberry Pi 5 Model B Rev 1.0, 8 GB RAM, booting
Talos from a 128 GB SD card through U-Boot 2025.04 and an EFI boot entry. Ethernet
uses `end0` with DHCP. A separate 2 TB My Passport USB disk has an existing XFS
user volume mounted at `/var/mnt/local-path-provisioner`. Retaining that data and
configuration matters for a future migration; this build cannot prove retention.
The current custom node is based on Talos 1.11.1 and Kubernetes 1.34.0.

No current workload selects gVisor, and there are no RuntimeClasses. Do not add
inherited iSCSI, Longhorn, GPU, or other extensions without a demonstrated need.
Keep extension choices documented; no live extension change is authorized.

## Starting point

- Fork: <https://github.com/donvargax/talos-builder>, public.
- Source: <https://github.com/johnlaur/talos-builder>, baseline
  `9e8a06ccfb88da4f93fcc3fa34aebdfdfa53c053`, Talos 1.13.2 and vendor kernel 6.18.29.
- The source had no 1.14 branch or pull request at the 2026-10-08 check.
- Upstream Talos 1.14.2 names pkgs `v1.14.0-37-g6c312e4` and tools
  `v1.14.0-8-g9776960`; resolve and verify the actual source commits before porting.
- Official SBC overlay 0.2.2 publishes `rpi_5`; vendor-kernel builds need matching
  vendor device trees rather than blindly using mainline device-tree patches.
- Source references: <https://github.com/siderolabs/talos>,
  <https://github.com/siderolabs/pkgs>,
  <https://github.com/siderolabs/sbc-raspberrypi>, and
  <https://github.com/raspberrypi/linux>.

## Work order

1. T-1: bootstrap itos and record this scope. No build runs.
2. Hosted trial workflow: add fast offline checks and an explicit manual ARM64
   candidate path. Remove automatic production publication, use commit/run-scoped
   identifiers, retain raw image, installer, hashes, provenance, and failure logs.
   Prefer a runner-local registry; necessary remote intermediates may use only
   immutable candidate tags in this fork's namespace. Enable GitHub CI watching
   once push checks exist. Do not trigger expensive trial builds yet.
3. Port the matched Talos/package/tool/vendor-kernel/overlay inputs to 1.14.2.
   Rebase kernel config, module lists, and device trees. Inspect Ethernet patch
   history for fixes already included or obsolete. Run source/patch preflight and
   offline checks, then dispatch the first hosted build after its pushed CI passes.
4. Iterate on genuine build failures, keeping checks and evidence. Stop if this
   expands into new driver development or requires unapproved operations.
5. Hardware boot, cold restart, Ethernet/etcd traffic, and storage tests are a
   later separately approved stage. A build success does not establish these.

## Test and publication requirements

- Lightweight `make check` runs offline with no Docker or cluster dependency.
- Fast push/PR CI runs those checks, including workflow and task-data validation.
- Expensive jobs run only by explicit manual dispatch on hosted ARM64 runners,
  with a timeout and concurrency limit. No build credentials from a live cluster.
- Source refs and archive hashes are pinned. Kernel and device-tree source match.
- Trial workflow artifacts include raw recovery media, installer archive,
  SHA-256 checksums, input/patch/build metadata, and useful failure logs.
- No production tags, GitHub releases, `latest` pushes, or misleading "tested"
  claims. Never overwrite official or upstream namespaces.
- Verify the pushed commit's actual CI/run; do not infer success from an agent's
  report or artifact filename.

## Migration is separate

Any live upgrade still requires cluster recovery material and etcd snapshots,
configuration and bootloader compatibility checks, and approval. Talos tests
configuration migration between adjacent minors; a 1.14.2 image does not justify
skipping the 1.12 and 1.13 stages. Intermediate Pi-compatible artifacts may need
their own build items. Preserve the old SD boot medium and USB data during any
future hardware test; no flashing or formatting is part of this plan.

## Initial checkpoint

2026-10-08: source cloned, itos 6.5.1 initialized, and the candidate-build scope
recorded. No builder code changed, image compiled, workflow dispatched, or image
published. The inherited workflow only ran for version tags, so bootstrap pushes
have no hosted CI until the workflow task lands.

## Controlled workflow checkpoint (T-2)

The workflow definition now separates fast `ci.yml` push/PR checks from manual
`build.yaml` candidate jobs. itos watches `ci.yml` for the pushed commit. The
candidate job is restricted to this fork's `main` dispatch SHA on the hosted
`ubuntu-24.04-arm` runner, with read-only repository permissions, a 180-minute
timeout and one-at-a-time concurrency. There are no arbitrary version/ref inputs,
automatic build triggers, registry credentials or release steps.

Intermediates use only `localhost:5000/donvargax/talos-builder` on a loopback-bound
runner-local registry. Both native ARM64 BuildKit and imager containers use host
networking; BuildKit permits HTTP for this local address. Candidate tags include
the full SHA, run ID and attempt. No public GHCR upload is needed, and the final
installer archive is retained without an unconditional `crane push`.

Artifacts have 14-day retention and include the installer archive, compressed raw
Pi 5 image, hashes, input/patch/checkouts/tool provenance and phase logs when
available. Failure collection/upload runs with `always()`; early bootstrap or
timeout failures also have GitHub's step logs. Evidence collection is allowlisted,
not a scan of credentials, machine configuration or historical logs.

`make check` is offline and uses stdlib unit tests, strict workflow structure
checks, shell/Python syntax checks and itos data validation. Workflows use JSON,
a YAML subset, to avoid adding a network-installed parser. `make plan` and
`make -n plan` are safe locally. Image-build and checkout-deletion targets refuse
execution outside the controlled hosted job. Sources may still be inspected and
patches preflighted locally without compilation.

The Talos 1.13.2, pkgs and overlay inputs remain inherited and are not evidence of
a 1.14.2 port. No heavy workflow was dispatched as part of T-2. T-3 must verify
the full matched source/tool/archive inputs before the first candidate run. The
old tag/release, local compilation, disk-flashing and upgrade instructions are
not the procedure for this fork. No image build or hardware result is claimed
by this workflow definition.
