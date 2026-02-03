# neo-portal

A neovim remote SSH launcher, powered by [kitty](https://sw.kovidgoyal.net/kitty/).

neo-portal opens an interactive [fzf](https://github.com/junegunn/fzf) picker
inside a kitty terminal, lets you choose a project directory on a remote host,
and launches neovim there in a new tab -- all with a single command.

## How it works

```
neo-portal
```

1. If kitty isn't already running with remote control enabled, neo-portal starts
   it and waits for the TCP listener to be ready.
2. Focuses the main kitty tab and sends an SSH + fzf pipeline that streams
   directories from the remote host and presents them locally via fzf.
3. Once you pick a directory, neo-portal opens a new kitty tab that SSHs into
   the host and starts `nvim` in the selected directory.

## Requirements

- Python 3.13+
- [kitty](https://sw.kovidgoyal.net/kitty/) terminal emulator
- [fzf](https://github.com/junegunn/fzf) installed locally
- SSH access to the configured remote host

## Setup

```sh
uv sync
```

## Usage

```sh
neo-portal --host 192.168.1.37 --remote-host some.host.org

# Search a different remote directory
neo-portal --host 192.168.1.37 --remote-host some.host.org --remote-dir ~/projects
```

### Options

| Flag             | Required | Default | Description                          |
| ---------------- | -------- | ------- | ------------------------------------ |
| `--host`         | yes      |         | TCP host for kitty remote control    |
| `--remote-host`  | yes      |         | SSH remote host to browse dirs on    |
| `--port`         | no       | 28812   | TCP port for kitty remote control    |
| `--remote-dir`   | no       | ~/dev   | Remote directory to search for projects |

## Development

Run the full check suite:

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest tests/ -v
```

## License

MIT
