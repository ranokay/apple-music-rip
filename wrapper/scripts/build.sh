#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

NDK_PATH="${ANDROID_NDK_PATH:-${ANDROID_NDK_HOME:-${ANDROID_NDK_ROOT:-$HOME/android-ndk-r23b}}}"

if [[ ! -d "${NDK_PATH}" ]]; then
    echo "Android NDK not found at ${NDK_PATH}. Set ANDROID_NDK_PATH/ANDROID_NDK_HOME/ANDROID_NDK_ROOT." >&2
    exit 1
fi

HOST_OS="$(uname -s)"
HOST_ARCH="$(uname -m)"

if [[ "${HOST_OS}" != "Darwin" && "${HOST_OS}" != "Linux" ]]; then
    echo "Unsupported host OS: ${HOST_OS}" >&2
    exit 1
fi

choose_ndk_host_tag() {
    local requested_tag="$1"
    local -a candidates=()

    if [[ -n "${requested_tag}" ]]; then
        candidates+=("${requested_tag}")
    else
        if [[ "${HOST_OS}" == "Darwin" ]]; then
            if [[ "${HOST_ARCH}" == "arm64" || "${HOST_ARCH}" == "aarch64" ]]; then
                candidates=("darwin-arm64" "darwin-x86_64")
            else
                candidates=("darwin-x86_64" "darwin-arm64")
            fi
        else
            if [[ "${HOST_ARCH}" == "arm64" || "${HOST_ARCH}" == "aarch64" ]]; then
                candidates=("linux-aarch64" "linux-x86_64")
            else
                candidates=("linux-x86_64" "linux-aarch64")
            fi
        fi
    fi

    local chosen=""
    for tag in "${candidates[@]}"; do
        if [[ -d "${NDK_PATH}/toolchains/llvm/prebuilt/${tag}" ]]; then
            chosen="${tag}"
            break
        fi
    done

    if [[ -z "${chosen}" ]]; then
        echo "Could not find an NDK toolchain under ${NDK_PATH}/toolchains/llvm/prebuilt (tried: ${candidates[*]})." >&2
        exit 1
    fi

    if [[ -z "${requested_tag}" && "${chosen}" != "${candidates[0]}" ]]; then
        echo "NDK host tag ${candidates[0]} not found, using fallback ${chosen}." >&2
    fi

    echo "${chosen}"
}

NDK_HOST_TAG="$(choose_ndk_host_tag "${ANDROID_NDK_HOST_TAG:-}")"

JOBS="${JOBS:-}"
if [[ -z "${JOBS}" ]]; then
    if command -v sysctl >/dev/null 2>&1; then
        JOBS="$(sysctl -n hw.ncpu)"
    elif command -v nproc >/dev/null 2>&1; then
        JOBS="$(nproc)"
    else
        JOBS="4"
    fi
fi

wrapper_linux_target="${WRAPPER_LINUX_TARGET:-}"
if [[ -z "${wrapper_linux_target}" ]]; then
    case "${ANDROID_ARCH:-x86_64}" in
        aarch64) wrapper_linux_target="aarch64-linux-gnu" ;;
        *) wrapper_linux_target="x86_64-linux-gnu" ;;
    esac
fi

normalize_arch() {
    case "$1" in
        x86_64|amd64) echo "x86_64" ;;
        arm64|aarch64) echo "aarch64" ;;
        *) echo "$1" ;;
    esac
}

host_cpu="$(normalize_arch "${HOST_ARCH}")"
target_cpu="$(normalize_arch "${wrapper_linux_target%%-*}")"

if [[ ( "${HOST_OS}" != "Linux" || "${host_cpu}" != "${target_cpu}" ) && -z "${WRAPPER_CC:-}" ]]; then
    if ! command -v zig >/dev/null 2>&1; then
        echo "zig is required to cross-compile the wrapper binary for ${wrapper_linux_target}. Install zig or set WRAPPER_CC/WRAPPER_CC_FLAGS." >&2
        exit 1
    fi
fi

cmake_args=(
    -S "${ROOT_DIR}"
    -B "${ROOT_DIR}/build"
    -DANDROID_NDK_PATH="${NDK_PATH}"
    -DANDROID_NDK_HOST_TAG="${NDK_HOST_TAG}"
    -DWRAPPER_LINUX_TARGET="${wrapper_linux_target}"
)

if [[ -n "${ANDROID_ARCH:-}" ]]; then
    cmake_args+=(-DANDROID_ARCH="${ANDROID_ARCH}")
fi

if [[ -n "${ANDROID_API:-}" ]]; then
    cmake_args+=(-DANDROID_API="${ANDROID_API}")
fi

if [[ -n "${WRAPPER_CC:-}" ]]; then
    cmake_args+=(-DWRAPPER_CC="${WRAPPER_CC}")
fi

if [[ -n "${WRAPPER_CC_FLAGS:-}" ]]; then
    cmake_args+=(-DWRAPPER_CC_FLAGS="${WRAPPER_CC_FLAGS}")
fi

cmake "${cmake_args[@]}"
cmake --build "${ROOT_DIR}/build" -j"${JOBS}"
