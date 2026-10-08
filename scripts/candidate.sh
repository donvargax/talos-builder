#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
tag="candidate-${GITHUB_SHA:-missing}-${GITHUB_RUN_ID:-missing}-${GITHUB_RUN_ATTEMPT:-missing}"
bash scripts/hosted-guard.sh localhost:5000 donvargax/talos-builder "$tag" true
export REGISTRY=localhost:5000 REGISTRY_USERNAME=donvargax/talos-builder TAG="$tag" PUSH=true
export BUILDKIT_PROGRESS=plain

case ${1:-} in
    prepare)
        test "$(git rev-parse HEAD)" = "$GITHUB_SHA"
        test -z "$(git status --porcelain --untracked-files=normal)"
        mkdir -p _out/candidate/logs
        python3 scripts/build_contract.py provenance
        make plan | tee _out/candidate/plan.txt
        # Registry is bound only to loopback. BuildKit and imager use host
        # networking so localhost means this same ephemeral runner everywhere.
        docker run -d --name candidate-registry -p 127.0.0.1:5000:5000 \
            registry:2.8.3@sha256:a3d8aaa63ed8681a604f1dea0aa03f100d5895b6a58ace528858a7b332415373
        ;;
    build)
        test "$(git rev-parse HEAD)" = "$GITHUB_SHA"
        test -f _out/candidate/provenance.json
        # Sequential phases avoid make prerequisite races and preserve each
        # failed phase's complete log. No clean target or registry login needed.
        for target in checkouts patches kernel initramfs-kernel installer-base imager overlay installer image; do
            make "$target" 2>&1 | tee "_out/candidate/logs/${target}.log"
            if [[ $target == checkouts ]]; then
                for repository in pkgs talos sbc-raspberrypi; do
                    git -C "checkouts/$repository" config user.name 'Candidate builder'
                    git -C "checkouts/$repository" config user.email 'candidate@talos-builder.invalid'
                done
            fi
            if [[ $target == checkouts || $target == patches ]]; then
                python3 scripts/build_contract.py provenance
            fi
        done
        python3 scripts/build_contract.py collect --require-images
        ;;
    *) echo 'Usage: candidate.sh prepare|build' >&2; exit 2 ;;
esac
