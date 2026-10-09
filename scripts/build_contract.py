#!/usr/bin/env python3
"""Offline plan/contracts and allowlisted candidate evidence, stdlib only.

Workflows use JSON, a strict YAML subset. This permits full parsing without
installing a YAML package or confusing the GitHub `on` key with a boolean.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent.parent
NAMESPACE = "donvargax/talos-builder"
REGISTRY = "localhost:5000"
PHASES = "checkouts patches kernel initramfs-kernel installer-base imager overlay installer image".split()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_workflow(workflow, heavy):
    triggers = {"workflow_dispatch"} if heavy else {"push", "pull_request"}
    require(set(workflow["on"]) == triggers, "unsafe workflow triggers")
    require(all(value == {} for value in workflow["on"].values()), "unexpected trigger filters/inputs")
    require(workflow["permissions"] == {"contents": "read"}, "write permissions forbidden")
    require("concurrency" in workflow, "missing concurrency limit")
    require(workflow["concurrency"]["cancel-in-progress"] is (not heavy), "unsafe cancellation")
    require(len(workflow["jobs"]) == 1, "unexpected job")
    job = next(iter(workflow["jobs"].values()))
    require(job["runs-on"] == ("ubuntu-24.04-arm" if heavy else "ubuntu-24.04"), "unexpected runner")
    require(0 < job["timeout-minutes"] <= (180 if heavy else 10), "missing/broad timeout")
    require("permissions" not in job, "job permission override forbidden")
    for step in job["steps"]:
        require("permissions" not in step, "step permission override")
        require(not step.get("continue-on-error", False), "hidden failure")
        if "uses" in step:
            action, _, commit = step["uses"].partition("@")
            require(action in {"actions/checkout", "actions/upload-artifact", "docker/setup-buildx-action"}, "unexpected action")
            require(re.fullmatch(r"[0-9a-f]{40}", commit), "action must be commit-pinned")
        if "run" in step:
            require("${{" not in step["run"], "workflow interpolation in shell forbidden")
    checkout = job["steps"][0]
    require(checkout["uses"].startswith("actions/checkout@"), "checkout first")
    require(checkout["with"]["persist-credentials"] is False, "persisted credentials")
    require(checkout["with"]["fetch-depth"] == 0, "history required for itos")
    text = json.dumps(workflow)
    for forbidden in ("secrets.", "packages", "release create", "login-action", "pull_request_target", "self-hosted", ":latest"):
        require(forbidden not in text, f"forbidden workflow token: {forbidden}")
    runs = [step.get("run", "") for step in job["steps"]]
    allowed_runs = {"bash scripts/install-itos.sh", "make check", "bash scripts/candidate.sh prepare",
                    "bash scripts/candidate.sh build", "python3 scripts/build_contract.py collect"} if heavy else {
                        "bash scripts/install-itos.sh", "make check plan",
                        "itos verify 9e8a06ccfb88da4f93fcc3fa34aebdfdfa53c053 HEAD"}
    require(all(run in allowed_runs for run in runs if run), "unexpected shell command")
    require("bash scripts/install-itos.sh" in runs, "verified itos bootstrap missing")
    if heavy:
        require(job["if"] == "github.repository == 'donvargax/talos-builder' && github.ref == 'refs/heads/main'", "unsafe dispatch ref/repository")
        require(checkout["with"]["ref"] == "${{ github.sha }}", "checkout must use dispatch SHA")
        require("bash scripts/candidate.sh prepare" in runs and "bash scripts/candidate.sh build" in runs, "missing controlled build")
        require(runs.index("bash scripts/candidate.sh prepare") < runs.index("bash scripts/candidate.sh build"), "prepare before build")
        collect = next(step for step in job["steps"] if step.get("run") == "python3 scripts/build_contract.py collect")
        require(collect["if"] == "always()", "failure diagnostics must be retained")
        upload = next(step for step in job["steps"] if step.get("uses", "").startswith("actions/upload-artifact@"))
        require(upload["if"] == "always()", "failure artifact upload missing")
        require(upload["with"]["path"] == "_out/candidate/", "artifact path must be allowlisted")
        require(upload["with"]["if-no-files-found"] == "error", "missing evidence must fail")
        require(upload["with"]["retention-days"] == 14, "unexpected retention")
        require(upload["with"]["name"] == "pi5-candidate-${{ github.sha }}-${{ github.run_id }}-${{ github.run_attempt }}", "artifact identity missing")
        buildx = next(step for step in job["steps"] if step.get("uses", "").startswith("docker/setup-buildx-action@"))["with"]
        require(buildx["version"] == "v0.28.0", "unpinned buildx")
        require(buildx["driver"] == "docker-container", "unexpected builder driver")
        require("network=host" in buildx["driver-opts"], "builder cannot reach local registry")
        require(re.search(r"image=moby/buildkit:v[0-9.]+@sha256:[0-9a-f]{64}", buildx["driver-opts"]), "unpinned BuildKit")
        require(buildx["buildkitd-config-inline"] == '[registry."localhost:5000"]\n  http = true\n', "local registry HTTP config missing")
        # An empty action input silently enables security.insecure/network.host.
        # A nonempty neutral flag replaces those action defaults completely.
        require(buildx["buildkitd-flags"] == "--debug=false", "unneeded default entitlements")
    else:
        require("make check plan" in runs, "offline checks missing")
        require("itos verify 9e8a06ccfb88da4f93fcc3fa34aebdfdfa53c053 HEAD" in runs, "commit verification missing")
        require(all(not any(word in run for word in ("candidate.sh", "docker", "crane", "make pi5")) for run in runs), "heavy command in fast CI")


def pins():
    # Only literal committed assignments, never evaluate Make or arbitrary input.
    result = {}
    for line in (ROOT / "Makefile").read_text().splitlines():
        match = re.fullmatch(r"([A-Z_]+)\s*:=\s*(\S+)", line)
        if match and ("VERSION" in match[1] or "COMMIT" in match[1] or "REPOSITORY" in match[1]):
            result[match[1]] = match[2]
    return result


def plan():
    print("Manual hosted ARM64 candidate only; NOT a verified boot or upgrade.")
    print("Committed inputs (T-3 must port/verify these before dispatch):")
    for key, value in sorted(pins().items()):
        print(f"  {key}={value}")
    print(f"Intermediates: {REGISTRY}/{NAMESPACE}; no public registry uploads.")
    print("Tag: candidate-<committed SHA>-<run ID>-<attempt>; no release/latest tags.")
    print("Native ubuntu-24.04-arm; BuildKit and imager use host network.")
    for phase in PHASES:
        print(f"  make {phase}")
    print("Evidence: installer-arm64.tar, metal-arm64-rpi5.raw.xz, SHA256SUMS,")
    print("          provenance.json, committed input/patch hashes, phase/failure logs.")
    print("No commands above were executed. No extensions selected by default.")


def command(args):
    try:
        result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=20)
        if result.returncode != 0:
            return f"unavailable (exit {result.returncode})"
        output = result.stdout
        if args[:2] == ["docker", "logs"]:
            output += result.stderr
        return output.strip()
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def provenance():
    dest = ROOT / "_out/candidate"
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / "provenance.json"
    data = json.loads(path.read_text()) if path.exists() else {}
    files = [ROOT / "Makefile", ROOT / "itos.yaml"]
    files += sorted((ROOT / "patches").rglob("*.patch"))
    files += sorted((ROOT / "scripts").glob("*.*"))
    files += sorted((ROOT / ".github/workflows").glob("*"))
    data.update({
        "repository": NAMESPACE,
        "commit": command(["git", "rev-parse", "HEAD"]),
        "pins": pins(),
        "input_sha256": {str(file.relative_to(ROOT)): sha256(file) for file in files},
        "run": {key: os.environ.get(key, "") for key in (
            "GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "RUNNER_OS", "RUNNER_ARCH", "RUNNER_ENVIRONMENT")},
        "run_url": f"https://github.com/{NAMESPACE}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}",
        "registry": REGISTRY,
        "extensions": [],
        "limitations": "Candidate only: no boot, upgrade, Ethernet soak or storage-preservation test.",
    })
    sources = {}
    for name in ("pkgs", "talos", "sbc-raspberrypi"):
        checkout = ROOT / "checkouts" / name
        if (checkout / ".git").exists():
            sources[name] = {
                "head": command(["git", "-C", str(checkout), "rev-parse", "HEAD"]),
                "recent_commits": command(["git", "-C", str(checkout), "log", "-4", "--format=%H %s"]),
                "input_sha256": {str(file.relative_to(checkout)): sha256(file) for file in (
                    checkout / "Makefile", checkout / "Pkgfile", checkout / "vars.yaml") if file.is_file()},
            }
    data.setdefault("source_snapshots", []).append(sources)
    data["tools"] = {"docker": command(["docker", "version", "--format", "{{.Client.Version}}/{{.Server.Version}}"]),
                     "buildx": command(["docker", "buildx", "version"]), "itos": command(["itos", "--version"])}
    path.write_text(json.dumps(data, indent=2) + "\n")


def collect(require_images=False):
    provenance()
    dest = ROOT / "_out/candidate"
    logs = dest / "logs"
    logs.mkdir(exist_ok=True)
    # Only logs from containers this workflow creates, never global Docker or
    # historical Actions logs. No environment dump or credential-bearing config.
    (logs / "registry.log").write_text(command(["docker", "logs", "candidate-registry"]))
    (logs / "buildx.txt").write_text(command(["docker", "buildx", "ls"]))
    expected = {"installer-arm64.tar": "installer-arm64.tar", "metal-arm64.raw.xz": "metal-arm64-rpi5.raw.xz"}
    for source, target in expected.items():
        file = ROOT / "checkouts/talos/_out" / source
        if file.is_file() and file.stat().st_size:
            shutil.copyfile(file, dest / target)
    files = sorted(file for file in dest.rglob("*") if file.is_file() and file.name != "SHA256SUMS")
    (dest / "SHA256SUMS").write_text("".join(f"{sha256(file)}  {file.relative_to(dest)}\n" for file in files))
    if require_images:
        require(all((dest / name).is_file() and (dest / name).stat().st_size for name in expected.values()), "successful build missing installer/raw image")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "provenance", "collect"))
    parser.add_argument("--require-images", action="store_true")
    args = parser.parse_args()
    if args.command == "plan":
        plan()
    elif args.command == "provenance":
        provenance()
    else:
        collect(args.require_images)
