# mcp2xiaozhi

[English](README.md) | [中文](README_CN.md)

> 将任意 MCP 服务端（stdio / SSE / StreamableHTTP）通过 WebSocket 桥接到 [Xiaozhi](https://github.com/78/xiaozhi-esp32-server) 服务端。

[![PyPI](https://img.shields.io/pypi/v/mcp2xiaozhi.svg)](https://pypi.org/project/mcp2xiaozhi/)
[![Python](https://img.shields.io/pypi/pyversions/mcp2xiaozhi.svg)](https://pypi.org/project/mcp2xiaozhi/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/StanleyChanH/MCP2Xiaozhi/actions/workflows/ci.yml/badge.svg)](https://github.com/StanleyChanH/MCP2Xiaozhi/actions/workflows/ci.yml)
[![Docs](https://img.shields.io/badge/docs-mkdocs__material-blue)](https://stanleychanh.github.io/MCP2Xiaozhi/)

`mcp2xiaozhi` 是一个通用桥接器，把**任意** [模型上下文协议](https://modelcontextprotocol.io/)（MCP）服务端连接到 Xiaozhi 服务端。Xiaozhi 服务端通过 WebSocket 充当 MCP *客户端*：以文本帧发送 JSON-RPC 工具调用，并期望 JSON-RPC 回复。本包接收这些帧，并在**协议层**将它们中继到你的 MCP 服务端——无论它运行在哪里、使用何种传输类型。

```
                 JSON-RPC over WebSocket (text frames)
   ┌──────────────────────┐   wss://…    ┌──────────────────────┐
   │   Xiaozhi 服务端      │ ◄──────────► │   mcp2xiaozhi 桥     │
   │  (充当 MCP 客户端)    │              └──────────┬───────────┘
   └──────────────────────┘                          │  JSON-RPC
                                                     │  over MCP transport
                              ┌──────────────────────┴───────────────┐
                              │   stdio        │   SSE   │   HTTP    │
                              ▼                ▼         ▼           ▼
                           本地进程         远程服务端           远程服务端
```

## 特性

- 🔄 **三种传输，一座桥** — `stdio`、`sse`、`streamablehttp`（`http`），全部原生支持，无需 `mcp-proxy` 子进程。
- 🧱 **协议级中继** — 帧被解析为 `JSONRPCMessage`（封装在 SDK 的 `SessionMessage` 中），校验后重新序列化。畸形帧被记录并丢弃，不会让桥崩溃。
- 🔁 **自动重连** — 任一端断开时使用带抖动的指数退避；区分正常关闭与异常关闭。
- 🗂️ **多服务** — 运行单个桥或配置中的所有服务端；每个服务端有自己的 endpoint。
- ⚙️ **配置驱动** — 与 Xiaozhi 官方 `mcp-calculator` 演示的 `mcp_config.json` 结构完全兼容。
- 🖥️ **跨平台** — Windows 下 UTF-8 控制台处理，优雅的 `SIGINT`/`SIGTERM` 关闭。
- 📦 **正规包** — `pyproject.toml`、src 布局、类型注解、CLI 入口、测试、CI，使用 [uv](https://docs.astral.sh/uv/) 管理。

## 安装

使用 [uv](https://docs.astral.sh/uv/)（推荐）：

```bash
uv tool install mcp2xiaozhi        # 作为工具安装 CLI
# 或在项目中：
uv add mcp2xiaozhi
```

使用 pip：

```bash
pip install mcp2xiaozhi
```

从源码安装（用于开发）：

```bash
git clone https://github.com/StanleyChanH/MCP2Xiaozhi.git
cd mcp2xiaozhi
uv sync --extra dev
```

## 快速开始

1. 创建一个 MCP 服务端（或使用已有的）。一个最小的 stdio 计算器：

   ```python
   # calculator.py
   from mcp.server.fastmcp import FastMCP
   import math

   mcp = FastMCP("Calculator")

   @mcp.tool()
   def calculator(python_expression: str) -> dict:
       """计算一个 Python 数学表达式。"""
       return {"success": True, "result": eval(python_expression, {"math": math})}

   if __name__ == "__main__":
       mcp.run(transport="stdio")
   ```

2. 在 `mcp_config.json` 中描述你的服务端：

   ```json
   {
     "mcpServers": {
       "calculator": {
         "type": "stdio",
         "command": "python",
         "args": ["calculator.py"]
       }
     }
   }
   ```

3. 设置 Xiaozhi WebSocket endpoint 并运行：

   ```bash
   export MCP_ENDPOINT="wss://api.your-xiaozhi-server.example/mcp/<token>"
   mcp2xiaozhi run calculator
   ```

   或一次运行所有已启用的服务端：

   ```bash
   mcp2xiaozhi run            # 所有已启用的服务端
   mcp2xiaozhi list           # 显示已配置的服务端
   mcp2xiaozhi version
   ```

## 配置

配置文件发现顺序：`--config PATH` → `$MCP_CONFIG` → `./mcp_config.json`。

### 结构

```jsonc
{
  "mcpServers": {
    "my-server": {
      "type": "stdio",              // stdio | sse | streamablehttp | http
      "disabled": false,            // 可选；运行全部时跳过

      // 仅 stdio
      "command": "python",
      "args": ["-m", "my_server"],
      "env": { "FOO": "bar" },      // 合并到当前环境

      // 仅 sse / streamablehttp
      "url": "https://example.com/mcp",
      "headers": { "Authorization": "Bearer xxx" },
      "timeout": 5.0,               // 连接超时（秒）
      "sse_read_timeout": 300.0,    // 长连接读超时（秒）

      // 可选：服务端专属的 Xiaozhi endpoint
      "endpoint": "wss://api.example.com/mcp/<token>"
    }
  }
}
```

### Endpoint 解析

每个服务端需要它要连接的 Xiaozhi WebSocket endpoint。按优先级解析：

1. 服务端配置中的 `endpoint` 字段
2. `$MCP_ENDPOINT_<NAME>` 环境变量（名称大写，非字母数字 → `_`）
3. 全局 `$MCP_ENDPOINT`

运行**多个**服务端时，请给每个服务端独立的 endpoint——否则 Xiaozhi 服务端无法将工具调用路由到正确的服务端。当某服务端回退到全局 endpoint 而其他服务端在运行时，桥会发出警告。

## 传输类型

| 类型 | 适用场景 | 说明 |
|------|----------|------|
| `stdio` | MCP 服务端是本地脚本/可执行文件 | 作为子进程启动；env 与当前进程合并。 |
| `sse` | 使用 Server-Sent Events 的旧式远程 MCP 服务端 | GET `/sse` 获取流，POST 发送请求——由 SDK 处理。 |
| `streamablehttp` / `http` | 现代远程 MCP 服务端（推荐） | 生产级 HTTP 传输。`http` 是别名。 |

这三种传输都使用官方 [`mcp` Python SDK](https://github.com/modelcontextprotocol/python-sdk) 的 transport 原语实现，它们 yield 携带 `SessionMessage` 对象的 `(read, write)` 内存流。桥在 WebSocket 和这些流之间泵送消息——绝不启动 `mcp-proxy`。

## 命令行

```
mcp2xiaozhi [--config PATH] [--log-level LEVEL] <command>

commands:
  run [SERVER]       运行单个服务端（省略或 --all 则运行所有已启用的）
  list               列出已配置的服务端
  version            打印版本

options:
  --endpoint URL     覆盖 Xiaozhi endpoint（仅单服务端运行）
  --log-level        DEBUG | INFO | WARNING | ERROR | CRITICAL
```

`python -m mcp2xiaozhi …` 也可以。

## 编程式使用

```python
import asyncio
from mcp2xiaozhi import McpBridge, load_config, resolve_endpoint, get_global_endpoint

async def main():
    config = load_config()
    server = config.require("calculator")
    endpoint = resolve_endpoint(server, global_endpoint=get_global_endpoint())
    bridge = McpBridge(server, endpoint)
    await bridge.run()   # 持续重连直到被取消

asyncio.run(main())
```

用 `ServerManager` 一次运行多个：

```python
from mcp2xiaozhi import ServerManager, load_config

manager = ServerManager.from_config(load_config())
asyncio.run(manager.run())
```

## 部署

桥是一个**长驻中继进程**——运行它的机器必须保持在线，因为 Xiaozhi 服务端不会直接连接你的 MCP 服务端。对于远程 SSE/HTTP MCP 服务端，你可以把桥部署到任意一台 7×24 在线的机器（VPS、NAS、树莓派、容器），然后关掉笔记本。

快速选项：

```bash
# Docker（全平台）—— 仓库自带 Dockerfile + docker-compose.yml
docker compose up -d --build

# Linux systemd —— 开机自启，崩溃重启
sudo systemctl enable --now mcp2xiaozhi

# Windows —— NSSM 把它注册为原生服务
nssm install mcp2xiaozhi mcp2xiaozhi.exe
```

➡️ 完整指南（配置与密钥、多服务、日志、升级）：[部署文档](https://stanleychanh.github.io/MCP2Xiaozhi/deployment/)。

## 开发

```bash
uv sync --extra dev          # 安装开发依赖
uv run ruff check .          # lint
uv run mypy src              # 类型检查
uv run pytest                # 测试
uv build                     # 构建 sdist + wheel
```

详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可证

MIT — 详见 [LICENSE](LICENSE)。
