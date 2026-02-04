"""Core business logic for neo-portal."""

import json
import os
import shlex
import socket
import subprocess
import tempfile
import time

DEFAULT_TCP_PORT = 28812


def tcp_address(host: str, port: int = DEFAULT_TCP_PORT) -> str:
    """Return the kitty TCP address for the given host and port."""
    return f"tcp:{host}:{port}"


def is_port_listening(host: str, port: int = DEFAULT_TCP_PORT) -> bool:
    """Return True if a TCP connection to host:port succeeds."""
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def init(
    host: str,
    port: int = DEFAULT_TCP_PORT,
    timeout: float = 10.0,
    poll_interval: float = 0.1,
) -> None:
    """Start kitty with remote control via TCP and wait until the port is listening."""
    addr = tcp_address(host, port)
    proc = subprocess.Popen(
        [
            "kitty",
            "-o",
            "allow_remote_control=yes",
            f"--listen-on={addr}",
            "--name",
            "portal-control",
        ],
    )
    deadline = time.monotonic() + timeout
    while not is_port_listening(host, port):
        ret = proc.poll()
        if ret is not None:
            raise RuntimeError(f"kitty exited early with return code {ret}")
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Timed out waiting for kitty to listen on {addr}")
        time.sleep(poll_interval)


def _find_min_tab_id(addr: str) -> int:
    """Return the minimum tab ID from kitty ls output."""
    ls_result = subprocess.run(
        ["kitty", "@", "--to", addr, "ls"],
        check=True,
        capture_output=True,
        text=True,
    )
    os_windows = json.loads(ls_result.stdout)
    tab_ids = [
        tab["id"] for os_window in os_windows for tab in os_window.get("tabs", [])
    ]
    if not tab_ids:
        raise RuntimeError("No tabs found in kitty ls output")
    return min(tab_ids)


def pick_directory(
    host: str,
    remote_host: str,
    port: int = DEFAULT_TCP_PORT,
    remote_dir: str = "~/dev",
    timeout: float = 120.0,
    poll_interval: float = 0.2,
) -> str:
    """Run fzf in the main kitty tab and return the chosen dir."""
    addr = tcp_address(host, port)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".neo-portal") as f:
        tmp_path = f.name

    try:
        tab_id = _find_min_tab_id(addr)
        subprocess.run(
            [
                "kitty",
                "@",
                "--to",
                addr,
                "focus-window",
                "--match",
                f"id:{tab_id}",
            ],
            check=True,
        )
        fzf_cmd = (
            f"ssh {shlex.quote(remote_host)} "
            f'"find {remote_dir} -maxdepth 2'
            " -not -path '*/.*' -type d\""
            f" | fzf > {shlex.quote(tmp_path)}\r"
        )
        subprocess.run(
            [
                "kitty",
                "@",
                "--to",
                addr,
                "send-text",
                fzf_cmd,
            ],
            check=True,
        )

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with open(tmp_path) as f:
                content = f.read().strip()
            if content:
                return content
            time.sleep(poll_interval)

        raise RuntimeError("Timed out waiting for directory selection")
    finally:
        os.unlink(tmp_path)


def launch_tab(
    directory: str,
    host: str,
    remote_host: str,
    port: int = DEFAULT_TCP_PORT,
) -> None:
    """Launch a new kitty tab that opens nvim in the given directory."""
    addr = tcp_address(host, port)
    subprocess.run(
        [
            "kitty",
            "@",
            "--to",
            addr,
            "launch",
            "--type=tab",
            "ssh",
            "-t",
            remote_host,
            f"zsh -ic {shlex.quote(f'cd {shlex.quote(directory)} && nvim')}",
        ],
        check=True,
    )
