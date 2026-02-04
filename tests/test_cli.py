"""Tests for the neo-portal CLI."""

import json
import os
import shlex
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from neo_portal.cli import cli
from neo_portal.core import (
    DEFAULT_TCP_PORT,
    _find_min_tab_id,
    launch_tab,
    pick_directory,
    tcp_address,
)

TEST_HOST = "1.2.3.4"
TEST_REMOTE = "test.remote.host"
TCP_ADDR = tcp_address(TEST_HOST)
CLI_ARGS = ["--host", TEST_HOST, "--remote-host", TEST_REMOTE]


def _mock_cli_callbacks() -> dict:
    """Return context managers that mock pick_directory and launch_tab."""
    return {
        "pick_directory": patch(
            "neo_portal.cli.pick_directory",
            return_value="/some/dir",
        ),
        "launch_tab": patch("neo_portal.cli.launch_tab"),
    }


def test_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "neo-portal" in result.output


def test_version() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_missing_host_fails() -> None:
    """CLI exits with error when --host is not provided."""
    mocks = _mock_cli_callbacks()
    with (
        patch("neo_portal.cli.is_port_listening", return_value=True),
        mocks["pick_directory"],
        mocks["launch_tab"],
    ):
        runner = CliRunner()
        result = runner.invoke(cli, ["--remote-host", TEST_REMOTE])
        assert result.exit_code != 0


def test_missing_remote_host_fails() -> None:
    """CLI exits with error when --remote-host is not provided."""
    mocks = _mock_cli_callbacks()
    with (
        patch("neo_portal.cli.is_port_listening", return_value=True),
        mocks["pick_directory"],
        mocks["launch_tab"],
    ):
        runner = CliRunner()
        result = runner.invoke(cli, ["--host", TEST_HOST])
        assert result.exit_code != 0


def test_init_called_when_port_not_listening() -> None:
    """init() is called when TCP port is not being listened on."""
    mocks = _mock_cli_callbacks()
    with (
        patch("neo_portal.cli.is_port_listening", return_value=False),
        patch("neo_portal.cli.init") as mock_init,
        mocks["pick_directory"],
        mocks["launch_tab"],
    ):
        runner = CliRunner()
        result = runner.invoke(cli, CLI_ARGS)
        assert result.exit_code == 0
        mock_init.assert_called_once_with(TEST_HOST, DEFAULT_TCP_PORT)


def test_init_not_called_when_port_listening() -> None:
    """init() is NOT called when TCP port is already listening."""
    mocks = _mock_cli_callbacks()
    with (
        patch("neo_portal.cli.is_port_listening", return_value=True),
        patch("neo_portal.cli.init") as mock_init,
        mocks["pick_directory"],
        mocks["launch_tab"],
    ):
        runner = CliRunner()
        result = runner.invoke(cli, CLI_ARGS)
        assert result.exit_code == 0
        mock_init.assert_not_called()


def test_args_passed_through() -> None:
    """--host, --remote-host, and --port are forwarded to core functions."""
    mocks = _mock_cli_callbacks()
    with (
        patch("neo_portal.cli.is_port_listening", return_value=False),
        patch("neo_portal.cli.init") as mock_init,
        mocks["pick_directory"] as mock_pick,
        mocks["launch_tab"] as mock_launch,
    ):
        runner = CliRunner()
        result = runner.invoke(cli, CLI_ARGS)
        assert result.exit_code == 0
        mock_init.assert_called_once_with(TEST_HOST, DEFAULT_TCP_PORT)
        mock_pick.assert_called_once_with(
            TEST_HOST, TEST_REMOTE, DEFAULT_TCP_PORT, remote_dir="~/dev"
        )
        mock_launch.assert_called_once_with(
            "/some/dir", TEST_HOST, TEST_REMOTE, DEFAULT_TCP_PORT
        )


def test_custom_port_passed_through() -> None:
    """--port overrides the default and is forwarded to core functions."""
    mocks = _mock_cli_callbacks()
    with (
        patch("neo_portal.cli.is_port_listening", return_value=False),
        patch("neo_portal.cli.init") as mock_init,
        mocks["pick_directory"] as mock_pick,
        mocks["launch_tab"] as mock_launch,
    ):
        runner = CliRunner()
        result = runner.invoke(cli, [*CLI_ARGS, "--port", "9999"])
        assert result.exit_code == 0
        mock_init.assert_called_once_with(TEST_HOST, 9999)
        mock_pick.assert_called_once_with(
            TEST_HOST, TEST_REMOTE, 9999, remote_dir="~/dev"
        )
        mock_launch.assert_called_once_with("/some/dir", TEST_HOST, TEST_REMOTE, 9999)


def test_custom_remote_dir_passed_through() -> None:
    """--remote-dir is forwarded to pick_directory."""
    mocks = _mock_cli_callbacks()
    with (
        patch("neo_portal.cli.is_port_listening", return_value=True),
        mocks["pick_directory"] as mock_pick,
        mocks["launch_tab"],
    ):
        runner = CliRunner()
        result = runner.invoke(cli, [*CLI_ARGS, "--remote-dir", "~/projects"])
        assert result.exit_code == 0
        mock_pick.assert_called_once_with(
            TEST_HOST, TEST_REMOTE, DEFAULT_TCP_PORT, remote_dir="~/projects"
        )


def test_runtime_error_becomes_click_exception() -> None:
    """RuntimeError from core functions is wrapped as ClickException."""
    with (
        patch("neo_portal.cli.is_port_listening", return_value=True),
        patch(
            "neo_portal.cli.pick_directory",
            side_effect=RuntimeError("something broke"),
        ),
    ):
        runner = CliRunner()
        result = runner.invoke(cli, CLI_ARGS)
        assert result.exit_code == 1
        assert "something broke" in result.output


def test_find_min_tab_id() -> None:
    """_find_min_tab_id() returns the minimum tab id from kitty ls."""
    kitty_ls_output = json.dumps(
        [
            {
                "tabs": [
                    {"id": 10, "windows": [{"id": 1}]},
                    {"id": 5, "windows": [{"id": 2}]},
                ]
            },
            {
                "tabs": [
                    {"id": 20, "windows": [{"id": 3}]},
                ]
            },
        ]
    )
    ls_result = MagicMock()
    ls_result.stdout = kitty_ls_output
    with patch("neo_portal.core.subprocess.run") as mock_run:
        mock_run.return_value = ls_result
        assert _find_min_tab_id(TCP_ADDR) == 5
    mock_run.assert_called_once_with(
        ["kitty", "@", "--to", TCP_ADDR, "ls"],
        check=True,
        capture_output=True,
        text=True,
    )


def test_pick_directory() -> None:
    """pick_directory() sends fzf to kitty, then polls local temp file."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".neo-portal-test") as tmp:
        tmp_path = tmp.name

    try:

        def simulate_fzf_write(*_args, **_kwargs):
            """On the send-text call, write the selection to the file."""
            with open(tmp_path, "w") as f:
                f.write("~/dev/my-project\n")

        call_count = 0

        def mock_subprocess(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # Second kitty call is send-text; simulate fzf output
            if call_count == 2:
                simulate_fzf_write()

        with (
            patch("neo_portal.core._find_min_tab_id", return_value=5),
            patch(
                "neo_portal.core.subprocess.run",
                side_effect=mock_subprocess,
            ) as mock_run,
            patch(
                "neo_portal.core.tempfile.NamedTemporaryFile",
            ) as mock_ntf,
        ):
            mock_ntf.return_value.__enter__ = lambda s: type(
                "F", (), {"name": tmp_path}
            )()
            mock_ntf.return_value.__exit__ = lambda *a: None

            directory = pick_directory(TEST_HOST, TEST_REMOTE)

        assert directory == "~/dev/my-project"
        assert mock_run.call_count == 2
        # First call: focus-window
        mock_run.assert_any_call(
            [
                "kitty",
                "@",
                "--to",
                TCP_ADDR,
                "focus-window",
                "--match",
                "id:5",
            ],
            check=True,
        )
        # Second call: send-text with fzf piped to local file
        send_call = mock_run.call_args_list[1]
        cmd_list = send_call[0][0]
        assert cmd_list[:5] == [
            "kitty",
            "@",
            "--to",
            TCP_ADDR,
            "send-text",
        ]
        assert "fzf" in cmd_list[5]
        assert shlex.quote(TEST_REMOTE) in cmd_list[5]
        assert shlex.quote(tmp_path) in cmd_list[5]
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_pick_directory_timeout() -> None:
    """pick_directory() raises on timeout when temp file stays empty."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".neo-portal-test") as tmp:
        tmp_path = tmp.name

    try:
        with (
            patch("neo_portal.core._find_min_tab_id", return_value=5),
            patch("neo_portal.core.subprocess.run"),
            patch(
                "neo_portal.core.tempfile.NamedTemporaryFile",
            ) as mock_ntf,
        ):
            mock_ntf.return_value.__enter__ = lambda s: type(
                "F", (), {"name": tmp_path}
            )()
            mock_ntf.return_value.__exit__ = lambda *a: None

            with pytest.raises(RuntimeError, match="Timed out"):
                pick_directory(
                    TEST_HOST,
                    TEST_REMOTE,
                    timeout=0.3,
                    poll_interval=0.05,
                )
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_launch_tab_runs_correct_command() -> None:
    """launch_tab() opens a new kitty tab with ssh + cd + nvim."""
    with patch("neo_portal.core.subprocess.run") as mock_run:
        launch_tab(
            "~/dev/conduit/validator-network",
            TEST_HOST,
            TEST_REMOTE,
        )
    mock_run.assert_called_once_with(
        [
            "kitty",
            "@",
            "--to",
            TCP_ADDR,
            "launch",
            "--type=tab",
            "ssh",
            "-t",
            TEST_REMOTE,
            "zsh -ic "
            + shlex.quote(
                f"cd {shlex.quote('~/dev/conduit/validator-network')} && nvim"
            ),
        ],
        check=True,
    )


def test_pick_directory_then_launch_tab() -> None:
    """The CLI pipes pick_directory output into launch_tab."""
    with (
        patch("neo_portal.cli.is_port_listening", return_value=True),
        patch(
            "neo_portal.cli.pick_directory",
            return_value="~/dev/conduit/validator-network",
        ) as mock_pick,
        patch("neo_portal.cli.launch_tab") as mock_launch,
    ):
        runner = CliRunner()
        result = runner.invoke(cli, CLI_ARGS)
        assert result.exit_code == 0
        mock_pick.assert_called_once_with(
            TEST_HOST, TEST_REMOTE, DEFAULT_TCP_PORT, remote_dir="~/dev"
        )
        mock_launch.assert_called_once_with(
            "~/dev/conduit/validator-network",
            TEST_HOST,
            TEST_REMOTE,
            DEFAULT_TCP_PORT,
        )
