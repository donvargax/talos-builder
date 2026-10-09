import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("build_contract", ROOT / "scripts/build_contract.py")
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)


def workflow(heavy=True):
    return json.loads((ROOT / ".github/workflows" / ("build.yaml" if heavy else "ci.yml")).read_text())


class WorkflowTests(unittest.TestCase):
    def test_all_workflows_parse_and_meet_contract(self):
        self.assertEqual({file.name for file in (ROOT / ".github/workflows").iterdir()}, {"ci.yml", "build.yaml"})
        for heavy in (True, False):
            contract.validate_workflow(workflow(heavy), heavy)

    def test_automatic_heavy_triggers_are_refused(self):
        for trigger in ("push", "pull_request", "pull_request_target", "schedule", "workflow_run"):
            with self.subTest(trigger=trigger):
                data = workflow()
                data["on"][trigger] = {}
                with self.assertRaisesRegex(ValueError, "triggers"):
                    contract.validate_workflow(data, True)

    def test_arbitrary_dispatch_inputs_and_refs_are_refused(self):
        data = workflow()
        data["on"]["workflow_dispatch"] = {"inputs": {"ref": {"type": "string"}}}
        with self.assertRaises(ValueError):
            contract.validate_workflow(data, True)
        data = workflow()
        data["jobs"]["candidate"]["steps"][0]["with"]["ref"] = "${{ inputs.ref }}"
        with self.assertRaises(ValueError):
            contract.validate_workflow(data, True)

    def test_write_credentials_and_self_hosted_runner_are_refused(self):
        for field, value in (("permissions", {"contents": "write"}), ("runs-on", "self-hosted"),
                             ("timeout-minutes", 0), ("if", "always()")):
            with self.subTest(field=field):
                data = workflow()
                data["jobs"]["candidate"][field] = value
                with self.assertRaises(ValueError):
                    contract.validate_workflow(data, True)

    def test_publication_and_untrusted_shell_are_refused(self):
        for run in ("gh release create v1.14.2", "crane push installer.tar ghcr.io/siderolabs/installer:latest",
                    "make TALOS_VERSION=${{ inputs.version }} pi5", "docker login ghcr.io", "make pi5"):
            with self.subTest(run=run):
                data = workflow()
                data["jobs"]["candidate"]["steps"].append({"run": run})
                with self.assertRaises(ValueError):
                    contract.validate_workflow(data, True)
        data = workflow(False)
        data["jobs"]["check"]["steps"].append({"run": "bash scripts/candidate.sh build"})
        with self.assertRaises(ValueError):
            contract.validate_workflow(data, False)

    def test_failure_evidence_cannot_be_skipped_or_broad(self):
        for field, value in (("if", "success()"), ("path", "."), ("if-no-files-found", "warn")):
            data = workflow()
            step = data["jobs"]["candidate"]["steps"][-1]
            if field == "if":
                step[field] = value
            else:
                step["with"][field] = value
            with self.assertRaises(ValueError):
                contract.validate_workflow(data, True)

    def test_action_tags_and_builder_connectivity_regressions_are_refused(self):
        data = workflow()
        data["jobs"]["candidate"]["steps"][0]["uses"] = "actions/checkout@v4"
        with self.assertRaises(ValueError):
            contract.validate_workflow(data, True)
        data = workflow()
        step = next(step for step in data["jobs"]["candidate"]["steps"] if step.get("uses", "").startswith("docker/"))
        step["with"]["driver-opts"] = "network=bridge"
        with self.assertRaises(ValueError):
            contract.validate_workflow(data, True)

    def test_empty_buildkit_flags_cannot_enable_action_default_entitlements(self):
        data = workflow()
        step = next(step for step in data["jobs"]["candidate"]["steps"] if step.get("uses", "").startswith("docker/"))
        step["with"]["buildkitd-flags"] = ""
        with self.assertRaisesRegex(ValueError, "entitlements"):
            contract.validate_workflow(data, True)

    def test_shell_and_python_syntax_without_execution(self):
        for file in (ROOT / "scripts").glob("*.sh"):
            subprocess.run(["bash", "-n", str(file)], check=True)
        for file in list((ROOT / "scripts").glob("*.py")) + list((ROOT / "tests").glob("*.py")):
            compile(file.read_text(), str(file), "exec")
        for heavy in (True, False):
            for step in next(iter(workflow(heavy)["jobs"].values()))["steps"]:
                if "run" in step:
                    subprocess.run(["bash", "-n"], input=step["run"], text=True, check=True)

    def test_itos_installer_matches_repository_pin(self):
        config = (ROOT / "itos.yaml").read_text()
        installer = (ROOT / "scripts/install-itos.sh").read_text()
        self.assertIn('version: "6.5.1"', config)
        self.assertIn("version=6.5.1", installer)
        manifest = "1a0ac1e1fdb920668e3cba96cad9ea94d23d2c1b667fe4f60d5d77f1573a8a08"
        self.assertIn(manifest, config)
        self.assertIn("manifest_sha=" + manifest, installer)
        self.assertLess(installer.index('"$manifest_sha" | sha256sum'), installer.index('tar -xzf'))
        self.assertLess(installer.index('sha256sum --check --strict archive.sha256'), installer.index('tar -xzf'))


class HostedGuardTests(unittest.TestCase):
    def setUp(self):
        self.env = dict(os.environ, GITHUB_ACTIONS="true", RUNNER_ENVIRONMENT="github-hosted", RUNNER_OS="Linux",
                        RUNNER_ARCH="ARM64", GITHUB_EVENT_NAME="workflow_dispatch", GITHUB_REPOSITORY=contract.NAMESPACE,
                        GITHUB_REF="refs/heads/main", GITHUB_SHA="a" * 40, GITHUB_RUN_ID="123", GITHUB_RUN_ATTEMPT="1")
        self.args = [contract.REGISTRY, contract.NAMESPACE, "candidate-" + "a" * 40 + "-123-1", "true"]

    def guard(self, env=None, args=None):
        return subprocess.run(["bash", str(ROOT / "scripts/hosted-guard.sh"), *(args or self.args)],
                              env=env or self.env, capture_output=True, text=True)

    def test_exact_hosted_manual_candidate_is_allowed(self):
        self.assertEqual(self.guard().returncode, 0)

    def test_local_pr_wrong_arch_and_wrong_repository_are_refused(self):
        for key, value in (("GITHUB_ACTIONS", "false"), ("RUNNER_ENVIRONMENT", "self-hosted"),
                           ("RUNNER_ARCH", "X64"), ("GITHUB_EVENT_NAME", "pull_request"),
                           ("GITHUB_REPOSITORY", "johnlaur/talos-builder"), ("GITHUB_REF", "refs/tags/v1.14.2"),
                           ("GITHUB_SHA", "main"), ("GITHUB_RUN_ID", ""), ("GITHUB_RUN_ATTEMPT", "$(id)")):
            with self.subTest(key=key):
                env = dict(self.env, **{key: value})
                self.assertNotEqual(self.guard(env=env).returncode, 0)

    def test_remote_registry_upstream_namespace_and_mutable_tags_are_refused(self):
        for index, value in ((0, "ghcr.io"), (1, "siderolabs"), (1, "talos-rpi5"), (2, "latest"),
                             (2, "v1.14.2"), (2, "candidate-" + "b" * 40 + "-123-1"), (3, "yes")):
            with self.subTest(value=value):
                args = self.args.copy()
                args[index] = value
                self.assertNotEqual(self.guard(args=args).returncode, 0)

    def test_make_heavy_targets_refuse_before_docker_or_checkout_deletion(self):
        env = dict(os.environ, GITHUB_ACTIONS="false")
        for target in ("kernel", "overlay", "imager", "installer-base", "initramfs-kernel", "installer", "image", "pi5", "clean"):
            with self.subTest(target=target):
                result = subprocess.run(["make", "--no-print-directory", target], cwd=ROOT, env=env,
                                        capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Candidate build refused", result.stderr)


class PlanAndEvidenceTests(unittest.TestCase):
    def test_failed_phase_preserves_log_and_stops_before_following_phases(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            scripts = root / "scripts"
            scripts.mkdir()
            for name in ("candidate.sh", "hosted-guard.sh"):
                shutil.copyfile(ROOT / "scripts" / name, scripts / name)
            (scripts / "build_contract.py").write_text("# Offline provenance fixture\n")
            dest = root / "_out/candidate"
            (dest / "logs").mkdir(parents=True)
            (dest / "provenance.json").write_text("{}")
            tools = root / "tools"
            tools.mkdir()
            fake_git = tools / "git"
            fake_git.write_text("#!/bin/sh\nif [ \"$1\" = rev-parse ]; then printf '%s\\n' " + "a" * 40 + "; fi\n")
            fake_git.chmod(0o755)
            fake_make = tools / "make"
            fake_make.write_text("#!/bin/sh\necho fixture-phase-$1\nif [ \"$1\" = kernel ]; then echo fixture-error >&2; exit 23; fi\n")
            fake_make.chmod(0o755)
            env = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ["PATH"], GITHUB_ACTIONS="true",
                       RUNNER_ENVIRONMENT="github-hosted", RUNNER_OS="Linux", RUNNER_ARCH="ARM64",
                       GITHUB_EVENT_NAME="workflow_dispatch", GITHUB_REPOSITORY=contract.NAMESPACE,
                       GITHUB_REF="refs/heads/main", GITHUB_SHA="a" * 40, GITHUB_RUN_ID="123", GITHUB_RUN_ATTEMPT="1")
            result = subprocess.run(["bash", str(scripts / "candidate.sh"), "build"], env=env,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 23)
            self.assertIn("fixture-error", (dest / "logs/kernel.log").read_text())
            self.assertTrue((dest / "logs/checkouts.log").is_file())
            self.assertFalse((dest / "logs/initramfs-kernel.log").exists())

    def test_plan_is_offline_and_matches_committed_versions(self):
        with patch.object(contract.subprocess, "run", side_effect=AssertionError("plan must not execute commands")):
            with patch("builtins.print") as output:
                contract.plan()
        text = "\n".join(str(call.args[0]) for call in output.call_args_list)
        self.assertIn("TALOS_VERSION=" + contract.pins()["TALOS_VERSION"], text)
        self.assertIn("no public registry uploads", text)
        self.assertIn("No commands above were executed", text)
        result = subprocess.run(["make", "--no-print-directory", "plan"], cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertIn("make installer", result.stdout)
        dry = subprocess.run(["make", "--no-print-directory", "-n", "plan"], cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual(dry.stdout.strip(), "python3 scripts/build_contract.py plan")
        for target in ("installer", "image"):
            dry = subprocess.run(["make", "--no-print-directory", "-n", target], cwd=ROOT, capture_output=True, text=True, check=True)
            self.assertNotIn("crane", dry.stdout)
            self.assertIn("--network=host", dry.stdout)
            self.assertNotIn("ghcr.io", dry.stdout)
            self.assertIn("localhost:5000/donvargax/talos-builder/", dry.stdout)

    def test_safe_make_defaults_and_serial_pipeline(self):
        makefile = (ROOT / "Makefile").read_text()
        self.assertIn("PUSH ?= false", makefile)
        self.assertNotIn("crane", makefile)
        self.assertNotIn("git reset --hard", makefile)
        self.assertIn("TAG=$(PKGS_TAG)", makefile)
        script = (ROOT / "scripts/candidate.sh").read_text()
        self.assertIn("for target in " + " ".join(contract.PHASES), script)
        self.assertIn("set -euo pipefail", script)
        self.assertIn('test "$(git rev-parse HEAD)" = "$GITHUB_SHA"', script)
        self.assertNotIn("make clean", script)
        self.assertNotIn("env |", script)

    def test_failed_build_retains_metadata_and_success_requires_both_images(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Makefile").write_text((ROOT / "Makefile").read_text())
            (root / "itos.yaml").write_text((ROOT / "itos.yaml").read_text())
            (root / "patches").mkdir()
            (root / "patches/example.patch").write_text("upstream patch origin\n")
            with patch.object(contract, "ROOT", root), patch.object(contract, "command", return_value="offline fixture"):
                contract.collect()
                dest = root / "_out/candidate"
                self.assertTrue((dest / "provenance.json").is_file())
                data = json.loads((dest / "provenance.json").read_text())
                self.assertIn("patches/example.patch", data["input_sha256"])
                with self.assertRaisesRegex(ValueError, "missing installer/raw"):
                    contract.collect(require_images=True)
                images = root / "checkouts/talos/_out"
                images.mkdir(parents=True)
                (images / "installer-arm64.tar").write_bytes(b"fixture installer")
                (images / "metal-arm64.raw.xz").write_bytes(b"fixture raw image")
                (images / "credential.env").write_text("must never be collected")
                contract.collect(require_images=True)
                self.assertFalse((dest / "credential.env").exists())
                for line in (dest / "SHA256SUMS").read_text().splitlines():
                    digest, name = line.split("  ", 1)
                    self.assertEqual(digest, hashlib.sha256((dest / name).read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
