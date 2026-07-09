# Deployment

`mcp2xiaozhi` is a **long-lived relay process** between the Xiaozhi server and
your MCP server(s). This page explains why it must keep running and how to run
it persistently on any platform.

## Why persistence matters

The bridge is the **middle of a three-part connection** — it is *not* a one-shot
tool:

```
Xiaozhi server  ◄── WebSocket ──  mcp2xiaozhi bridge  ─── SSE/HTTP ──►  remote MCP
 (api.xiaozhi.me)                   (your host)                          (modelscope…)
                                          │
                                          └── stdio ──► local MCP (optional)
```

- The bridge **initiates both connections** (it is a client on both sides).
- The Xiaozhi server **never** connects to your MCP server directly — every tool
  call flows through the bridge.
- If the bridge process dies, both connections drop and Xiaozhi tool calls fail
  until it restarts.

So: **the host running `mcp2xiaozhi` must stay online.** If your MCP server is
remote (SSE / StreamableHTTP, like the modelscope calculator), you can run the
bridge on *any* always-on machine — a VPS, a NAS, a Raspberry Pi, a Docker
container — and turn your laptop off. If your MCP server is a **local stdio**
process, the bridge and that process must run on the same host, so that host
must stay up.

The good news: the bridge auto-reconnects with exponential backoff, so
transient network drops heal themselves. You only need something to keep the
**process** alive.

## Options at a glance

| Method | Platform | Boot | Logout | Best for |
|--------|----------|:---:|:---:|----------|
| Foreground | all | ❌ | ❌ | quick testing |
| `nohup` / `tmux` / `screen` | Linux/macOS | ❌ | ✅ | temporary, dev |
| **systemd** | Linux | ✅ | ✅ | **production (Linux)** |
| **Docker Compose** | all | ✅ | ✅ | **production (any)** |
| **NSSM service** | Windows | ✅ | ✅ | **production (Windows)** |

## Configuration & secrets (all methods)

Regardless of how you run the bridge, the inputs are the same:

- `mcp_config.json` — describes your servers (see [Configuration](configuration.md)).
- `MCP_ENDPOINT` (or `MCP_ENDPOINT_<NAME>`) — the Xiaozhi WebSocket URL, which
  contains a token.

!!! warning "Treat the endpoint like a password"
    The `MCP_ENDPOINT` URL contains a JWT token — anyone who has it can consume
    your Xiaozhi MCP quota.

    - Put it in an env file or secret manager — **not** in the config JSON, and
      never commit it to a public repo.
    - `mcp2xiaozhi` redacts it in its own logs (`?<redacted>`), but third-party
      libraries under `--log-level DEBUG` may print the full URL. Use the
      default `INFO` level in production.
    - Rotate the token from the Xiaozhi console if it ever leaks.

## Linux: systemd (recommended)

`systemd` is the native way to run a long-lived service on Linux: it starts on
boot, restarts on crash, and captures logs via journald.

1. Install the package system-wide:

   ```bash
   sudo pipx install mcp2xiaozhi
   # or, if you prefer uv:
   sudo uv tool install mcp2xiaozhi
   ```

   Note the binary path with `which mcp2xiaozhi` (e.g. `/usr/local/bin/mcp2xiaozhi`).

2. Put the config and endpoint where the service can read them:

   ```bash
   sudo install -d -m 0755 /etc/mcp2xiaozhi
   sudo nano /etc/mcp2xiaozhi/mcp_config.json          # paste your config
   sudo nano /etc/mcp2xiaozhi.env                        # MCP_ENDPOINT=wss://api.xiaozhi.me/mcp/?token=...
   sudo chmod 600 /etc/mcp2xiaozhi.env                   # protect the token
   ```

3. Create `/etc/systemd/system/mcp2xiaozhi.service`:

   ```ini
   [Unit]
   Description=mcp2xiaozhi MCP-to-Xiaozhi bridge
   After=network-online.target
   Wants=network-online.target

   [Service]
   Type=simple
   User=mcp2xiaozhi
   WorkingDirectory=/etc/mcp2xiaozhi
   EnvironmentFile=/etc/mcp2xiaozhi.env
   Environment=MCP_CONFIG=/etc/mcp2xiaozhi/mcp_config.json
   ExecStart=/usr/local/bin/mcp2xiaozhi run --all
   Restart=on-failure
   RestartSec=5s

   # Hardening
   NoNewPrivileges=true
   ProtectSystem=strict
   ProtectHome=true
   PrivateTmp=true
   ReadWritePaths=/etc/mcp2xiaozhi

   [Install]
   WantedBy=multi-user.target
   ```

4. Enable and start:

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now mcp2xiaozhi
   sudo systemctl status mcp2xiaozhi        # verify "active (running)"
   sudo journalctl -u mcp2xiaozhi -f         # live logs
   ```

## Docker / Docker Compose (recommended, any platform)

The repo ships a [`Dockerfile`](https://github.com/StanleyChanH/MCP2Xiaozhi/blob/main/Dockerfile)
and [`docker-compose.yml`](https://github.com/StanleyChanH/MCP2Xiaozhi/blob/main/docker-compose.yml)
for one-command persistent deployment on any host with Docker — including a
small VPS.

1. Put `mcp_config.json` and a `.env` file (with `MCP_ENDPOINT=...`) next to
   `docker-compose.yml`.
2. Start:

   ```bash
   docker compose up -d --build
   docker compose logs -f
   ```

`restart: unless-stopped` keeps it alive across crashes and reboots.

For local stdio MCP servers, either run them in linked containers (reference by
service name) or keep them on the host and use `host.docker.internal`.

## Windows: NSSM service (recommended)

[NSSM](https://nssm.cc/) wraps any executable — including `mcp2xiaozhi.exe` —
as a native Windows service that starts on boot and restarts on failure.

```powershell
# Install NSSM (winget or download from nssm.cc)
winget install nssm

# Register the bridge as a service
nssm install mcp2xiaozhi "C:\Path\To\mcp2xiaozhi.exe"
nssm set mcp2xiaozhi AppDirectory      "C:\Path\To\config\dir"
nssm set mcp2xiaozhi AppParameters     "run --all"
nssm set mcp2xiaozhi AppEnvironmentExtra "MCP_ENDPOINT=wss://api.xiaozhi.me/mcp/?token=..."
nssm set mcp2xiaozhi Start             SERVICE_AUTO_START
nssm set mcp2xiaozhi AppStdout         "C:\Path\To\logs\out.log"
nssm set mcp2xiaozhi AppStderr         "C:\Path\To\logs\err.log"
nssm set mcp2xiaozhi AppRotateFiles    1

Start-Service mcp2xiaozhi
```

Manage with `Start-Service` / `Stop-Service` / `Restart-Service`, or via
`services.msc`.

## Temporary / quick runs

=== "nohup (Linux/macOS)"

    ```bash
    export MCP_ENDPOINT='wss://api.xiaozhi.me/mcp/?token=...'
    nohup mcp2xiaozhi run --all > bridge.log 2>&1 &
    ```

    Survives logout. Check with `tail -f bridge.log`. Kill with
    `pkill -f mcp2xiaozhi`.

=== "tmux / screen"

    ```bash
    tmux new -s mcp
    mcp2xiaozhi run --all        # Ctrl-B then D to detach
    tmux attach -t mcp           # reattach later
    ```

=== "foreground"

    ```bash
    mcp2xiaozhi run --all        # Ctrl-C to stop
    ```

    Fine for testing; stops when you close the terminal.

## Operations

### Logs

- **systemd**: `journalctl -u mcp2xiaozhi -f`
- **Docker**: `docker compose logs -f`
- **NSSM**: the log files you configured (`AppStdout` / `AppStderr`)
- Default level is `INFO`. Use `--log-level DEBUG` only when troubleshooting,
  and rotate the token afterwards (third-party libs may print the endpoint).

### Reconnection

The bridge reconnects automatically with exponential backoff on either side
dropping — clean close → short retry; error → growing backoff up to 600 s.
Usually you don't need to intervene.

### Upgrading

```bash
# pip
pip install -U mcp2xiaozhi
# uv tool
uv tool upgrade mcp2xiaozhi
# Docker
docker compose pull && docker compose up -d --build
```

Then restart the service (`systemctl restart mcp2xiaozhi`, etc.).

### Running multiple servers

Give each server its own endpoint (see
[Configuration → Endpoint resolution](configuration.md#endpoint-resolution)).
With `run --all`, the bridge opens one WebSocket per server.

### Health check (optional)

There is no HTTP health endpoint — the bridge is a pure relay. To monitor,
check that the process is running (`systemctl is-active`, `docker inspect`,
`Get-Service`) and that the logs show `WebSocket connected`. The keepalive
ping/pong roughly every 20 s is a good liveness signal.
