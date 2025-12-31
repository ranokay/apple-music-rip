import os
import socket
import subprocess
import threading

import yaml
from flask import jsonify, render_template, request

from . import app

# Wrapper runs externally; track reachability only
wrapper_running = False
wrapper_logs = []
downloader_logs = []
download_process = None
download_running = False
SURVEY_REPLACE_FLAG = "-mod=mod -replace=github.com/AlecAivazis/survey/v2=../wrapper/survey_stub"


def stream_download_logs(pipe, target_list):
    """Thread target to read logs from download process and store them."""
    global download_running, download_process

    try:
        for line in iter(pipe.readline, ""):
            line = line.strip()
            if line:
                target_list.append(line)
                print(f"[DOWNLOAD LOG] {line}")  # Debug print

    except Exception as e:
        target_list.append(f"Error reading download logs: {str(e)}")
    finally:
        # Check if process ended
        if download_process and download_process.poll() is not None:
            exit_code = download_process.poll()
            if exit_code == 0:
                target_list.append("✅ Download completed successfully!")
            else:
                target_list.append(f"❌ Download failed with exit code: {exit_code}")
            download_running = False
        pipe.close()


def _script_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _wrapper_host_port():
    """Read wrapper host:port from downloader config (decrypt-m3u8-port)."""
    host, port = "127.0.0.1", 10020
    config_path = os.path.join(_script_root(), "apple-music-downloader", "config.yaml")
    try:
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            val = config.get("decrypt-m3u8-port") or ""
            if isinstance(val, str) and ":" in val:
                h, p = val.split(":", 1)
                host = h or host
                try:
                    port = int(p)
                except ValueError:
                    pass
    except Exception as exc:
        wrapper_logs.append(f"⚠️ Could not read config.yaml for wrapper port: {exc}")
    return host, port


def _check_wrapper_running():
    """Try a TCP connect to the wrapper decrypt port."""
    host, port = _wrapper_host_port()
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def stream_download_logs(pipe, target_list):
    """Thread target to read logs from download process and store them."""
    global download_running, download_process

    try:
        for line in iter(pipe.readline, ""):
            line = line.strip()
            if line:
                target_list.append(line)
                print(f"[DOWNLOAD LOG] {line}")  # Debug print

    except Exception as e:
        target_list.append(f"Error reading download logs: {str(e)}")
    finally:
        if download_process and download_process.poll() is not None:
            exit_code = download_process.poll()
            if exit_code == 0:
                target_list.append("✅ Download completed successfully!")
            else:
                target_list.append(f"❌ Download failed with exit code: {exit_code}")
            download_running = False
        pipe.close()


@app.route("/")
def index():
    global wrapper_running
    wrapper_running = _check_wrapper_running()
    if wrapper_running:
        wrapper_logs.append("✅ Wrapper reachable.")
    else:
        wrapper_logs.append(
            "⚠️ Wrapper not reachable. Ensure it is running and logged in."
        )

    return render_template(
        "index.html",
        wrapper_running=wrapper_running,
    )


@app.route("/download", methods=["POST"])
def download():
    global download_process, download_running, downloader_logs, wrapper_running

    link = request.form.get("link")
    format_choice = request.form.get("format")

    wrapper_running = _check_wrapper_running()
    if not wrapper_running:
        return jsonify({"status": "error", "msg": "Wrapper not reachable"})

    if download_running:
        return jsonify({"status": "error", "msg": "Download already in progress"})

    if not link:
        return jsonify({"status": "error", "msg": "No URL provided"})

    # Determine the command to run
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    amd_dir = os.path.join(script_dir, "apple-music-downloader")
    config_path = os.path.join(amd_dir, "config.yaml")

    # Read config to get folders and update m3u8 mode
    try:
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            # Update config based on format choice
            if format_choice == "hires":
                config["get-m3u8-mode"] = "hires"
            else:
                config["get-m3u8-mode"] = (
                    "web"  # Default for others to avoid unnecessary checks
                )

            # Save updated config
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

            save_folder = ""
            if format_choice == "atmos":
                save_folder = config.get("atmos-save-folder", "AM-DL-Atmos downloads")
            elif format_choice == "aac":
                save_folder = config.get("aac-save-folder", "AM-DL-AAC downloads")
            else:  # lossless and hires
                save_folder = config.get("alac-save-folder", "AM-DL downloads")

            downloader_logs.append(f"💾 Download will be saved to: {save_folder}")
    except Exception as e:
        print(f"Error reading/writing config: {e}")
        downloader_logs.append(f"⚠️ Error updating config: {e}")

    cmd = ["go", "run", "main.go", link]

    if format_choice == "atmos":
        cmd = ["go", "run", "main.go", "--atmos", link]
        downloader_logs.append(f"🎵 Starting ATMOS download: {link}")
    elif format_choice == "aac":
        cmd = ["go", "run", "main.go", "--aac", link]
        downloader_logs.append(f"🎵 Starting AAC download: {link}")
    elif format_choice == "hires":
        downloader_logs.append(f"🎵 Starting Hi-Res Lossless download: {link}")
    else:
        downloader_logs.append(f"🎵 Starting Lossless download: {link}")

    downloader_logs.append(f"📁 Working directory: {amd_dir}")
    downloader_logs.append(f"⚡ Executing: {' '.join(cmd)}")

    env = os.environ.copy()
    goflags = env.get("GOFLAGS", "").strip()
    if SURVEY_REPLACE_FLAG not in goflags:
        env["GOFLAGS"] = (goflags + " " + SURVEY_REPLACE_FLAG).strip()

    try:
        download_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True,
            cwd=amd_dir,  # Run from apple-music-downloader directory
            env=env,
        )

        download_running = True
        threading.Thread(
            target=stream_download_logs,
            args=(download_process.stdout, downloader_logs),
            daemon=True,
        ).start()

        return jsonify({"status": "ok", "msg": "Download started successfully"})

    except Exception as e:
        downloader_logs.append(f"❌ Error starting download: {str(e)}")
        return jsonify(
            {"status": "error", "msg": f"Failed to start download: {str(e)}"}
        )


@app.route("/get_logs")
def get_logs():
    global wrapper_running, download_running, download_process

    wrapper_running = _check_wrapper_running()

    if download_process and download_process.poll() is not None:
        if download_running:
            download_running = False

    return jsonify(
        {
            "wrapper": wrapper_logs[-200:],  # last 200 lines
            "downloader": downloader_logs[-200:],
            "wrapper_running": wrapper_running,
            "download_running": download_running,
        }
    )


@app.route("/settings")
def settings():
    return render_template("settings.html")


@app.route("/get_config")
def get_config():
    try:
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(script_dir, "apple-music-downloader", "config.yaml")

        with open(config_path, "r", encoding="utf-8") as file:
            config = yaml.safe_load(file)
            return jsonify({"status": "ok", "config": config})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)})


@app.route("/save_config", methods=["POST"])
def save_config():
    try:
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(script_dir, "apple-music-downloader", "config.yaml")

        config_data = request.json

        # Define fields that should be integers
        integer_fields = {
            "alac-max",
            "atmos-max",
            "limit-max",
            "max-memory-limit",
            "mv-max",
        }

        # Define fields that should be booleans
        boolean_fields = {
            "embed-lrc",
            "save-lrc-file",
            "save-artist-cover",
            "save-animated-artwork",
            "emby-animated-artwork",
            "embed-cover",
            "get-m3u8-from-device",
            "use-songinfo-for-playlist",
            "dl-albumcover-for-playlist",
            "convert-after-download",
            "convert-keep-original",
            "convert-skip-if-source-matches",
        }

        # Define fields that are folder paths and need Windows to WSL translation
        path_fields = {"alac-save-folder", "atmos-save-folder", "aac-save-folder"}

        def translate_path_to_wsl(path):
            """Translate Windows paths to WSL paths when saving config"""
            if not path:
                return path
            # Check if it's a Windows-style path (e.g., C:/, D:/)
            if len(path) >= 3 and path[1:3] == ":\\":
                # Convert C:\ to /mnt/c/
                drive = path[0].lower()
                rest = path[3:].replace("\\", "/")
                return f"/mnt/{drive}/{rest}"
            elif len(path) >= 3 and path[1:3] == ":/":
                # Convert C:/ to /mnt/c/
                drive = path[0].lower()
                rest = path[3:]
                return f"/mnt/{drive}/{rest}"
            return path

        # Convert data types properly
        for key, value in config_data.items():
            if key in integer_fields:
                try:
                    config_data[key] = int(value) if value else 0
                except (ValueError, TypeError):
                    config_data[key] = 0
            elif key in boolean_fields:
                # Handle boolean conversion
                if isinstance(value, str):
                    config_data[key] = value.lower() in ("true", "1", "yes", "on")
                else:
                    config_data[key] = bool(value)
            elif key in path_fields:
                # Translate Windows paths to WSL format
                config_data[key] = translate_path_to_wsl(str(value))
            # Strings remain as strings (default)

        with open(config_path, "w", encoding="utf-8") as file:
            yaml.dump(config_data, file, default_flow_style=False, allow_unicode=True)

        return jsonify({"status": "ok", "msg": "Configuration saved successfully"})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)})


@app.route("/get_download_folders")
def get_download_folders():
    """Get download folder paths from config with Windows to WSL path translation"""
    try:
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(script_dir, "apple-music-downloader", "config.yaml")

        with open(config_path, "r", encoding="utf-8") as file:
            config = yaml.safe_load(file)

        folders = {
            "alac": config.get("alac-save-folder", "AM-DL downloads"),
            "atmos": config.get("atmos-save-folder", "AM-DL-Atmos downloads"),
            "aac": config.get("aac-save-folder", "AM-DL-AAC downloads"),
        }

        return jsonify({"status": "ok", "folders": folders})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)})
