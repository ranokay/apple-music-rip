import os
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
WRAPPER_DIR = PROJECT_DIR / "apps/wrapper"
AMD_DIR = PROJECT_DIR / "apps/apple-music-downloader"


def setup_wrapper():
    """
    Ensure the wrapper binary and rootfs already exist locally.
    We skip cloning/downloading because the wrapper is managed separately.
    """
    binary = WRAPPER_DIR / "wrapper"
    rootfs = WRAPPER_DIR / "rootfs"

    if binary.exists() and rootfs.exists():
        print("ℹ️ Wrapper already present, skipping download/build")
        return

    print("❌ Wrapper binary/rootfs not found.")
    print(
        "Please build the wrapper in ./wrapper (e.g., ./scripts/build.sh) so main.py can run."
    )
    sys.exit(1)


def clone_amd_repo():
    if AMD_DIR.exists():
        print("ℹ️ Apple Music Downloader already exists, skipping clone")
        return

    print("⬇️ Cloning Apple Music Downloader...")
    try:
        subprocess.run(
            [
                "git",
                "clone",
                "https://github.com/zhaarey/apple-music-downloader",
                str(AMD_DIR),
            ],
            check=True,
        )
        print("✅ Apple Music Downloader cloned inside project folder")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to clone Apple Music Downloader: {e}")
        sys.exit(1)


def start():
    print("🚀 Starting Apple Music Downloader Web UI...")

    # Add Wrapper to PATH
    os.environ["PATH"] = f"{WRAPPER_DIR}:{os.environ['PATH']}"

    # Set executable permissions for the wrapper
    wrapper_path = WRAPPER_DIR / "wrapper"
    if wrapper_path.exists():
        wrapper_path.chmod(0o755)

    # Import and run the Flask app
    try:
        from apps.web import app

        app.run(host="0.0.0.0", port=5000, debug=True)
    except ImportError as e:
        print(f"❌ Failed to import app: {e}")
        print(
            "Ensure required Python packages are installed (pip install -r requirements.txt)."
        )
        sys.exit(1)


if __name__ == "__main__":
    # Ensure Python deps are present (Flask, PyYAML). Skip nix-shell; rely on local env.
    def ensure_python_dependencies():
        missing = []
        try:
            import flask  # noqa: F401
        except ImportError:
            missing.append("flask")
        try:
            import yaml  # noqa: F401
        except ImportError:
            missing.append("pyyaml")

        if missing:
            print(f"❌ Missing Python packages: {', '.join(missing)}")
            print("Install them with: pip install -r requirements.txt")
            sys.exit(1)

    ensure_python_dependencies()

    setup_wrapper()
    clone_amd_repo()

    start()
