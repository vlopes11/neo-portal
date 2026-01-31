"""CLI entry point for neo-portal."""

import click

from neo_portal import __version__
from neo_portal.core import (
    DEFAULT_TCP_PORT,
    init,
    is_port_listening,
    launch_tab,
    pick_directory,
)


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="neo-portal")
@click.option(
    "--host",
    required=True,
    help="TCP host for kitty remote control.",
)
@click.option(
    "--remote-host",
    required=True,
    help="SSH remote host to browse directories on.",
)
@click.option(
    "--port",
    default=DEFAULT_TCP_PORT,
    show_default=True,
    type=int,
    help="TCP port for kitty remote control.",
)
def cli(host: str, remote_host: str, port: int) -> None:
    """neo-portal: a CLI application."""
    if not is_port_listening(host, port):
        init(host, port)
    directory = pick_directory(host, remote_host, port)
    launch_tab(directory, host, remote_host, port)
