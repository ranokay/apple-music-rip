# wrapper

A tool to decrypt Apple Music songs. An active subscription is still needed.

Supports only x86_64 and arm64 Linux.

## Installation

Installation methods:

- [Docker](#docker) (recommended)
- Prebuilt binaries (from [releases](https://github.com/WorldObservationLog/wrapper/releases) or [actions](https://github.com/WorldObservationLog/wrapper/actions))
- [Build from source](#build-from-source)

### Docker

Available for x86_64 and arm64. Need to download prebuilt version from releases or actions.

1. Build image:

```
docker build --platform=linux/amd64 --tag wrapper .
```

1. Login:

```
docker run -it -v ./rootfs/data:/app/rootfs/data -e args='-L username:password -H 0.0.0.0' wrapper
```

1. Run:

```
docker run -v ./rootfs/data:/app/rootfs/data -p 10020:10020 -p 20020:20020 -p 30020:30020 -e args="-H 0.0.0.0" wrapper
```

The image expects the locally built `wrapper` binary in the repo root and `/system/bin/main` under `rootfs` (produced by `./scripts/build.sh`). The bundled rootfs is x86_64, so keep `--platform=linux/amd64` when building/running on Apple Silicon.

### Build from source

1. Install dependencies:

- Build tools:

  ```
  sudo apt install build-essential cmake wget unzip git
  ```

- LLVM:

  ```
  sudo bash -c "$(wget -O - https://apt.llvm.org/llvm.sh)"
  ```

- Android NDK r23b:

  ```
  wget -O android-ndk-r23b-linux.zip https://dl.google.com/android/repository/android-ndk-r23b-linux.zip
  unzip -q -d ~ android-ndk-r23b-linux.zip
  ```

1. Build:

```
git clone https://github.com/WorldObservationLog/wrapper
cd wrapper
mkdir build
cd build
cmake ..
make -j$(nproc)
```

### Build from source (macOS aarch64)

1. Install dependencies (Homebrew examples):

- Build tools:

  ```
  brew install cmake git
  ```

- Android NDK r23b (darwin):

  ```
  curl -L -o android-ndk-r23b-darwin.zip https://dl.google.com/android/repository/android-ndk-r23b-darwin.zip
  unzip -q -d ~ android-ndk-r23b-darwin.zip
  export ANDROID_NDK_HOME="$HOME/android-ndk-r23b"
  ```

- Linux cross-compiler for the wrapper binary (one option):

  ```
  brew install zig
  ```

1. Build:

```
git clone https://github.com/WorldObservationLog/wrapper
cd wrapper
export ANDROID_NDK_PATH="$ANDROID_NDK_HOME"
export ANDROID_ARCH=x86_64
export WRAPPER_LINUX_TARGET=x86_64-linux-gnu
./scripts/build.sh
```

By default `./scripts/build.sh` will fall back to the `darwin-x86_64` NDK toolchain if an `arm64` prebuilt is not present (NDK r23b ships only `darwin-x86_64`), so Rosetta 2 must be available.

## Usage

```
Usage: wrapper [OPTION]...

  -h, --help              Print help and exit
  -V, --version           Print version and exit
  -H, --host=STRING         (default=`127.0.0.1')
  -D, --decrypt-port=INT    (default=`10020')
  -M, --m3u8-port=INT       (default=`20020')
  -A, --account-port=INT    (default=`30020')
  -P, --proxy=STRING        (default=`')
  -L, --login=STRING        (username:password)
  -F, --code-from-file      (default=off)
```

## Special thanks

- Anonymous, for providing the original version of this project and the legacy Frida decryption method.
- chocomint, for providing support for arm64 arch.
