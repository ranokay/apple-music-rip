#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TAG="${WRAPPER_IMAGE_TAG:-wrapper}"
PLATFORM="${DOCKER_PLATFORM:-linux/amd64}"
DATA_VOLUME="${ROOT_DIR}/rootfs/data:/app/rootfs/data"
HOST_VALUE="0.0.0.0"
LOGIN_ARG=""
CONTAINER_NAME="wrapper-runtime"
FORCE_RECREATE=0

usage() {
    cat <<'EOF'
Usage: wrapper-docker.sh <command> [options]

Commands:
  build               Build the Docker image (defaults: tag=wrapper, platform=linux/amd64)
  login -L user:pass  Run interactive login container with provided credentials
  run                 Run server container (ports exposed)

Options:
  -t, --tag <name>        Image tag (default: wrapper or $WRAPPER_IMAGE_TAG)
  -H, --host <addr>       Host binding for wrapper args (default: 0.0.0.0)
  -L, --login user:pass   Credentials for login command (required for login)
  --platform <value>      Docker platform (default: linux/amd64 or $DOCKER_PLATFORM)
  --recreate              Recreate the named container before running

Environment:
  WRAPPER_IMAGE_TAG   Overrides default image tag
  DOCKER_PLATFORM     Overrides default platform
EOF
}

require_docker() {
    if ! command -v docker >/dev/null 2>&1; then
        echo "docker not found in PATH" >&2
        exit 1
    fi
}

container_exists() {
    local name="$1"
    docker ps -a --format '{{.Names}}' --filter "name=^${name}$" | grep -Fxq "${name}"
}

command="${1:-}"
if [[ -z "${command}" ]]; then
    usage
    exit 1
fi
shift

while [[ $# -gt 0 ]]; do
    case "$1" in
        -t|--tag)
            TAG="$2"; shift 2 ;;
        --platform)
            PLATFORM="$2"; shift 2 ;;
        -H|--host)
            HOST_VALUE="$2"; shift 2 ;;
        -L|--login)
            LOGIN_ARG="$2"; shift 2 ;;
        --recreate)
            FORCE_RECREATE=1; shift ;;
        -h|--help)
            usage; exit 0 ;;
        *)
            echo "Unknown option: $1" >&2
            usage
            exit 1 ;;
    esac
done

require_docker

common_env=(-e ANDROID_DATA=/data -e ANDROID_ROOT=/system)
volume_args=(-v "${DATA_VOLUME}")

case "${command}" in
    build)
        docker build --platform="${PLATFORM}" -t "${TAG}" "${ROOT_DIR}"
        ;;
    login)
        if [[ -z "${LOGIN_ARG}" ]]; then
            echo "Login requires -L user:pass" >&2
            exit 1
        fi
        docker run --platform="${PLATFORM}" -it \
            "${volume_args[@]}" \
            "${common_env[@]}" \
            -e args="-L ${LOGIN_ARG} -H ${HOST_VALUE}" \
            "${TAG}"
        ;;
    run)
        if container_exists "${CONTAINER_NAME}"; then
            if [[ ${FORCE_RECREATE} -eq 1 ]]; then
                docker rm -f "${CONTAINER_NAME}" >/dev/null
            fi
        fi

        if ! container_exists "${CONTAINER_NAME}"; then
            docker create \
                --name "${CONTAINER_NAME}" \
                --platform="${PLATFORM}" \
                "${volume_args[@]}" \
                -p 10020:10020 -p 20020:20020 -p 30020:30020 \
                "${common_env[@]}" \
                -e args="-H ${HOST_VALUE}" \
                "${TAG}" >/dev/null
        fi

        docker start -ai "${CONTAINER_NAME}"
        ;;
    *)
        echo "Unknown command: ${command}" >&2
        usage
        exit 1
        ;;
esac
