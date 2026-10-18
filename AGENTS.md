# Talos Pi 5 builder guidance

## Scope and safety

- This is the public `donvargax/talos-builder` fork of `johnlaur/talos-builder`.
  Read `docs/build-plan.md` and `itos work show <item>` before implementation.
- The current goal is a Talos 1.14.2 vendor-kernel build candidate, not a live
  cluster upgrade. Do not run cluster commands, boot images, flash disks, change
  firmware, or access the private infrastructure repository's credentials.
- Compile real images on GitHub-hosted `ubuntu-24.04-arm` runners, not locally
  and not on cluster/self-hosted runners. Local source inspection, dependency
  downloads, patch preflight, and lightweight offline tests are permitted.
- Preserve the Raspberry Pi vendor-kernel approach and matching device trees.
  An official or community image label is not evidence of Ethernet stability.
- Builds are candidates until separately tested. Do not create production
  release tags, GitHub releases, or `latest` images. Prefer a runner-local
  registry for intermediate images; any required public registry uploads must
  use this fork's namespace and immutable candidate tags only.
- Never print, stage, or publish credentials or runtime machine configuration.
  Stage explicit paths. Inspect build recipes before running them: inherited
  targets push images, use privileged containers, and delete checkouts.
- Preserve upstream licenses and authorship. Pin source/tool inputs and record
  patch origins; verify checksums rather than carrying stale tags blindly.

## Work coordination

- Use the itos release `itos.yaml` pins for specs, claims, commits, pushes, and
  closure. One implementing agent holds the checkout at a time; no coordinator staging while it runs.
- Initial bootstrap has no hosted CI run. The hosted-workflow task adds fast
  push/PR checks and GitHub CI monitoring before image-porting work starts.
- `make check` must remain lightweight, offline, and independent of Docker or
  cluster access. Expensive builds are explicit manual workflow runs.
- Report the actual pushed SHA and CI/build run URLs. A green compile is not a
  successful boot, upgrade, Ethernet soak, or storage-preservation test.
- Fix ordinary lint/test failures in the work. Stop for new scope, missing
  authorization, or a genuinely incorrect gate; never weaken a gate to pass.

<!-- itos:begin -->

## itos

Start with `itos go` unless your brief names another guide.

Stage only your own files, by explicit path: untracked files you did not make are someone else's work in progress.

<!-- itos:end -->
