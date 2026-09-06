from __future__ import annotations

import base64
import json
import os
import secrets
import signal
import socket
import stat
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import typer
from rich import box
from rich.panel import Panel

from . import __version__
from .console import NAVY, badge, console, ok, status_table, title_panel, warn
from .editor import VSCODE_ACP_EXTENSION, ZED_AGENT_CONFIG, load_jsonc_object, vscode_extension_installed, zed_available
from .manifest import FileTouch, Manifest, PackageTouch, now_iso
from .state import config_path, load_config, manifest_path, minidev_dir
from .system import command_status, run_command

DEFAULT_OPENCODE_PORT = 4096
DEFAULT_OLLAMA_PORT = 11434
SHARE_STATE_FILE = "share.json"
REMOTE_CONFIG_FILE = "remote.json"
REMOTE_LAUNCHER = "bin/minidev-opencode-remote"
USERNAME = "opencode"


def run_share(stop: bool = False, port: int = DEFAULT_OPENCODE_PORT, ollama_port: int = DEFAULT_OLLAMA_PORT) -> None:
    if stop:
        stop_share()
        return

    manifest = Manifest(manifest_path())
    state_path = share_state_path()
    state = load_json_object(state_path)
    if share_is_running(state):
        print_existing_share(state)
        return

    require_tool("opencode")
    require_tool("ollama")

    lan_ip = detect_lan_ip()
    if lan_ip in {"0.0.0.0", "127.0.0.1", "localhost"} or lan_ip.startswith("127."):
        raise typer.BadParameter("MiniDev could not find a non-loopback LAN interface to bind.")

    token = secrets.token_urlsafe(32)
    opencode_port = pick_available_port(lan_ip, port)
    ollama_pid = ensure_lan_ollama(lan_ip, ollama_port)
    opencode_pid = start_opencode_server(lan_ip, opencode_port, token, ollama_port)

    state = {
        "active": True,
        "started_at": now_iso(),
        "project": str(Path.cwd()),
        "host": lan_ip,
        "port": opencode_port,
        "url": f"http://{lan_ip}:{opencode_port}",
        "username": USERNAME,
        "token": token,
        "ollama": {
            "host": lan_ip,
            "port": ollama_port,
            "url": f"http://{lan_ip}:{ollama_port}",
            "pid": ollama_pid,
            "started_by_minidev": ollama_pid is not None,
        },
        "opencode": {
            "pid": opencode_pid,
            "started_by_minidev": True,
        },
    }
    save_json_object(state_path, state)
    update_main_config({"lan": {"enabled": True, "host": lan_ip, "port": opencode_port, "url": state["url"]}})
    manifest.record_file(FileTouch(str(state_path), "MiniDev LAN share state and token", "write"))
    manifest.record_file(FileTouch(str(config_path()), "MiniDev LAN share config", "write"))
    manifest.save()

    table = status_table("LAN Share")
    table.add_row(ok("Bind address"), badge(lan_ip))
    table.add_row(ok("OpenCode"), badge(f"{lan_ip}:{opencode_port}"))
    table.add_row(ok("Ollama"), badge(f"{lan_ip}:{ollama_port}"))
    table.add_row(ok("Token"), badge(token, "mini.yellow"))
    console.print(title_panel("Sharing MiniDev on LAN"))
    console.print(table)
    console.print(
        Panel(
            f"[mini.yellow]Second device command[/]\nminidev connect {lan_ip}:{opencode_port} {token}\n\n"
            "[mini.text]Stop sharing with:[/]\nminidev share --stop",
            border_style="mini.box",
            style=f"on {NAVY}",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )


def run_connect(endpoint: str, token: str) -> None:
    manifest = Manifest(manifest_path())
    remote = normalize_endpoint(endpoint, token)
    remote_path = minidev_dir() / REMOTE_CONFIG_FILE
    launcher_path = minidev_dir() / REMOTE_LAUNCHER

    remote_config = {
        "version": __version__,
        "configured_at": now_iso(),
        "remote": {
            "url": remote["public_url"],
            "authenticated_url": remote["auth_url"],
            "username": USERNAME,
            "token": token,
            "launcher": str(launcher_path),
        },
    }
    save_json_object(remote_path, remote_config)
    write_remote_launcher(launcher_path, remote["auth_url"])
    update_main_config({"remote": remote_config["remote"], "lan": {"enabled": False, "connected": True, "url": remote["public_url"]}})
    configure_remote_editor(launcher_path, manifest)

    manifest.record_file(FileTouch(str(remote_path), "MiniDev remote OpenCode connection config", "write"))
    manifest.record_file(FileTouch(str(launcher_path), "MiniDev remote OpenCode launcher", "write"))
    manifest.record_file(FileTouch(str(config_path()), "MiniDev remote connection config", "write"))
    manifest.save()

    table = status_table("LAN Connect")
    table.add_row(ok("Remote OpenCode"), badge(remote["public_url"]))
    table.add_row(ok("Token stored"), badge("YES"))
    table.add_row(ok("Launcher"), badge(str(launcher_path)))
    console.print(title_panel("Connecting MiniDev to LAN host"))
    console.print(table)
    console.print(
        Panel(
            f"[mini.yellow]Terminal chat[/]\n{launcher_path}\n\n"
            "[mini.text]This connects to the shared OpenCode server. Keep the host running until you are done.[/]",
            border_style="mini.box",
            style=f"on {NAVY}",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )


def stop_share() -> None:
    state_path = share_state_path()
    state = load_json_object(state_path)
    console.print(title_panel("Stopping MiniDev LAN share"))

    table = status_table("LAN Share")
    if not state.get("active"):
        table.add_row(warn("Share"), badge("NOT RUNNING", "mini.warn"))
        console.print(table)
        return

    stopped: list[str] = []
    opencode_pid = nested_int(state, ["opencode", "pid"])
    if opencode_pid and terminate_process(opencode_pid):
        stopped.append("OpenCode")
        table.add_row(ok("OpenCode server"), badge("STOPPED"))
    elif opencode_pid:
        table.add_row(warn("OpenCode server"), badge("NOT FOUND", "mini.warn"))

    if nested_bool(state, ["ollama", "started_by_minidev"]):
        ollama_pid = nested_int(state, ["ollama", "pid"])
        if ollama_pid and terminate_process(ollama_pid):
            stopped.append("Ollama")
            table.add_row(ok("Ollama server"), badge("STOPPED"))
        elif ollama_pid:
            table.add_row(warn("Ollama server"), badge("NOT FOUND", "mini.warn"))

    save_json_object(
        state_path,
        {
            **state,
            "active": False,
            "stopped_at": now_iso(),
            "token": None,
            "revoked": True,
            "stopped": stopped,
        },
    )
    update_main_config({"lan": {"enabled": False, "stopped_at": now_iso()}})
    table.add_row(ok("Token"), badge("REVOKED"))
    console.print(table)


def share_state_path() -> Path:
    return minidev_dir() / SHARE_STATE_FILE


def require_tool(command: str) -> None:
    status = command_status(command)
    if not status.working:
        raise typer.BadParameter(f"{command} is not installed or is not working. Run `minidev install` first.")


def detect_lan_ip() -> str:
    override = os.environ.get("MINIDEV_LAN_IP")
    if override:
        return override

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            address = sock.getsockname()[0]
            if is_lan_address(address):
                return address
    except OSError:
        pass

    candidates: list[str] = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = info[4][0]
            if is_lan_address(address):
                candidates.append(address)
    except OSError:
        pass

    if candidates:
        return candidates[0]
    raise typer.BadParameter("MiniDev could not detect a LAN IP address.")


def is_lan_address(address: str) -> bool:
    return not (address == "0.0.0.0" or address.startswith("127.") or address.startswith("169.254."))


def pick_available_port(host: str, preferred: int) -> int:
    if port_available(host, preferred):
        return preferred
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def port_available(host: str, port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
            return True
    except OSError:
        return False


def ensure_lan_ollama(host: str, port: int) -> int | None:
    if http_ok(f"http://{host}:{port}/api/tags"):
        return None
    if not port_available(host, port):
        raise typer.BadParameter(
            f"Ollama port {port} is already in use on {host}, but it is not reachable as a LAN Ollama server."
        )

    env = {**os.environ, "OLLAMA_HOST": f"{host}:{port}"}
    log = log_file("ollama")
    proc = subprocess.Popen(
        ["ollama", "serve"],
        env=env,
        stdout=log.open("ab"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    if not wait_http_ok(f"http://{host}:{port}/api/tags", timeout_seconds=15):
        terminate_process(proc.pid)
        raise typer.BadParameter("MiniDev started Ollama, but the LAN endpoint did not become reachable.")
    return proc.pid


def start_opencode_server(host: str, port: int, token: str, ollama_port: int) -> int:
    env = {
        **os.environ,
        "OPENCODE_SERVER_USERNAME": USERNAME,
        "OPENCODE_SERVER_PASSWORD": token,
        "OLLAMA_HOST": f"http://{host}:{ollama_port}",
    }
    log = log_file("opencode")
    proc = subprocess.Popen(
        ["opencode", "serve", "--hostname", host, "--port", str(port)],
        env=env,
        cwd=Path.cwd(),
        stdout=log.open("ab"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    if not wait_socket(host, port, timeout_seconds=20):
        terminate_process(proc.pid)
        raise typer.BadParameter("MiniDev started OpenCode, but the LAN server did not become reachable.")
    return proc.pid


def log_file(name: str) -> Path:
    path = minidev_dir() / "logs" / f"{name}-share.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def wait_socket(host: str, port: int, timeout_seconds: float) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.25)
    return False


def wait_http_ok(url: str, timeout_seconds: float) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if http_ok(url):
            return True
        time.sleep(0.25)
    return False


def http_ok(url: str, token: str | None = None) -> bool:
    headers = {}
    if token:
        credentials = base64.b64encode(f"{USERNAME}:{token}".encode()).decode()
        headers["Authorization"] = f"Basic {credentials}"
    try:
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=2) as response:
            return 200 <= response.status < 500
    except (OSError, urllib.error.URLError):
        return False


def normalize_endpoint(endpoint: str, token: str) -> dict[str, str]:
    candidate = endpoint if "://" in endpoint else f"http://{endpoint}"
    parsed = urllib.parse.urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or not parsed.port:
        raise typer.BadParameter("Endpoint must look like `192.168.1.20:4096` or `http://192.168.1.20:4096`.")
    if parsed.hostname in {"0.0.0.0", "localhost"} or parsed.hostname.startswith("127."):
        raise typer.BadParameter("Use the host device's LAN IP, not localhost or 0.0.0.0.")

    public = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
    auth = f"{parsed.scheme}://{USERNAME}:{urllib.parse.quote(token)}@{parsed.hostname}:{parsed.port}"
    return {"public_url": public, "auth_url": auth}


def write_remote_launcher(path: Path, authenticated_url: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\nexec opencode attach {authenticated_url!r}\n")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)


def configure_remote_editor(launcher_path: Path, manifest: Manifest) -> None:
    table = status_table("Editor")
    code = command_status("code", ["--version"])
    if code.working:
        if vscode_extension_installed():
            manifest.record_package(PackageTouch(VSCODE_ACP_EXTENSION, "vscode", "present"))
            table.add_row(ok("VS Code ACP extension"), badge("PRESENT"))
        else:
            run_command(["code", "--install-extension", VSCODE_ACP_EXTENSION])
            manifest.record_package(PackageTouch(VSCODE_ACP_EXTENSION, "vscode", "install"))
            table.add_row(ok("VS Code ACP extension"), badge("OK"))
        table.add_row(ok("Remote launcher"), badge(str(launcher_path)))
        console.print(table)
        return

    if zed_available():
        path, existed = write_remote_zed_agent_config(launcher_path)
        manifest.record_file(FileTouch(str(path), "Zed remote OpenCode launcher for MiniDev", "overwrite" if existed else "create"))
        table.add_row(ok("Zed remote agent config"), badge(str(path)))
        console.print(table)
        return

    table.add_row(warn("Editor integration"), badge("MANUAL", "mini.warn"))
    console.print(table)


def write_remote_zed_agent_config(launcher_path: Path) -> tuple[Path, bool]:
    path = minidev_dir().parent / ZED_AGENT_CONFIG
    existed = path.exists()
    content = load_jsonc_object(path)
    agent_servers = content.get("agent_servers") if isinstance(content.get("agent_servers"), dict) else {}
    agent_servers["MiniDev Remote"] = {
        "type": "custom",
        "command": str(launcher_path),
        "args": [],
    }
    content["agent_servers"] = agent_servers
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, indent=2) + "\n")
    return path, existed


def update_main_config(values: dict[str, Any]) -> None:
    current = load_config()
    merged = deep_merge(current, values)
    save_json_object(config_path(), merged)


def deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def save_json_object(path: Path, content: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, indent=2) + "\n")


def share_is_running(state: dict[str, Any]) -> bool:
    if not state.get("active"):
        return False
    pid = nested_int(state, ["opencode", "pid"])
    return bool(pid and process_alive(pid))


def print_existing_share(state: dict[str, Any]) -> None:
    table = status_table("LAN Share")
    table.add_row(ok("Share"), badge("RUNNING"))
    table.add_row(ok("OpenCode"), badge(f"{state.get('host')}:{state.get('port')}"))
    token = state.get("token")
    if isinstance(token, str) and token:
        table.add_row(ok("Token"), badge(token, "mini.yellow"))
    console.print(title_panel("MiniDev LAN share already running"))
    console.print(table)


def process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def terminate_process(pid: int) -> bool:
    if not process_alive(pid):
        return False
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return False
    for _ in range(20):
        if not process_alive(pid):
            return True
        time.sleep(0.1)
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        return False
    return True


def nested_int(data: dict[str, Any], keys: list[str]) -> int | None:
    value: Any = data
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value if isinstance(value, int) else None


def nested_bool(data: dict[str, Any], keys: list[str]) -> bool:
    value: Any = data
    for key in keys:
        if not isinstance(value, dict):
            return False
        value = value.get(key)
    return value is True
