#!/usr/bin/env bash
set -euo pipefail

refuse() { echo "Candidate build refused: $*" >&2; exit 1; }
[[ ${GITHUB_ACTIONS:-} == true && ${RUNNER_ENVIRONMENT:-} == github-hosted ]] || refuse 'hosted Actions only'
[[ ${RUNNER_OS:-} == Linux && ${RUNNER_ARCH:-} == ARM64 ]] || refuse 'Linux ARM64 only'
[[ ${GITHUB_EVENT_NAME:-} == workflow_dispatch ]] || refuse 'manual dispatch only'
[[ ${GITHUB_REPOSITORY:-} == donvargax/talos-builder && ${GITHUB_REF:-} == refs/heads/main ]] || refuse 'fork main only'
[[ ${GITHUB_SHA:-} =~ ^[0-9a-f]{40}$ ]] || refuse 'missing committed SHA'
[[ ${GITHUB_RUN_ID:-} =~ ^[0-9]+$ && ${GITHUB_RUN_ATTEMPT:-} =~ ^[0-9]+$ ]] || refuse 'missing run identity'
[[ $# == 4 ]] || refuse 'expected registry, namespace, tag and push mode'
[[ $1 == localhost:5000 && $2 == donvargax/talos-builder ]] || refuse 'runner-local registry and fork namespace only'
[[ $3 == candidate-${GITHUB_SHA}-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT} ]] || refuse 'immutable candidate tag only'
[[ $4 == true || $4 == false ]] || refuse 'invalid push mode'
