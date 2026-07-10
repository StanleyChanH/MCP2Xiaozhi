# mcp2xiaozhi 中文文档

> 将任意 MCP 服务端（stdio / SSE / StreamableHTTP）通过 WebSocket 桥接到 [Xiaozhi](https://github.com/78/xiaozhi-esp32-server) 服务端。

Xiaozhi 服务端通过 WebSocket 充当 MCP *客户端*：以文本帧发送 JSON-RPC 工具调用，并期望 JSON-RPC 回复。本包接收这些帧，并在**协议层**将它们中继到你的 MCP 服务端——无论它运行在哪里、使用何种传输类型。

## 特性

- 🔄 **三种传输，一座桥** — `stdio`、`sse`、`streamablehttp`（`http`），全部原生支持，无需 `mcp-proxy` 子进程。
- 🧱 **协议级中继** — 帧被解析为 `JSONRPCMessage`（封装在 SDK 的 `SessionMessage` 中），校验后重新序列化。畸形帧被丢弃，不会让桥崩溃。
- 🔁 **自动重连** — 指数退避带抖动；区分正常关闭与异常关闭。
- 🗂️ **多服务** — 运行单个桥或配置中的所有服务端；每个服务端有自己的 endpoint。
- 🖥️ **跨平台** — Windows 下 UTF-8 控制台处理，优雅的 `SIGINT`/`SIGTERM` 关闭。
- 📦 **正规包** — PyPI、CLI、类型注解、42 个测试、CI、uv 管理。

## 安装

=== "uv（推荐）"

    ```bash
    uv tool install mcp2xiaozhi
    # 或在项目中：
    uv add mcp2xiaozhi
    ```

=== "pip"

    ```bash
    pip install mcp2xiaozhi
    ```

## 快速开始

1. 创建一个 MCP 服务端（计算器示例）：

   ```python title="calculator.py"
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

2. 描述你的服务端（`mcp_config.json`）：

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

3. 设置 endpoint 并运行：

   ```bash
   export MCP_ENDPOINT="wss://api.your-xiaozhi-server.example/mcp/<token>"
   mcp2xiaozhi run calculator
   ```

## 配置

配置文件发现顺序：`--config PATH` → `$MCP_CONFIG` → `./mcp_config.json`。

```jsonc
{
  "mcpServers": {
    "my-server": {
      "type": "stdio",              // stdio | sse | streamablehttp | http
      "disabled": false,
      "command": "python",
      "args": ["-m", "my_server"],
      "env": { "FOO": "bar" },
      "url": "https://example.com/mcp",        // 仅 sse / streamablehttp
      "headers": { "Authorization": "Bearer xxx" },
      "endpoint": "wss://api.example.com/mcp/<token>"  // 可选：服务端专属 endpoint
    }
  }
}
```

### Endpoint 解析

每个服务端需要它要连接的 Xiaozhi WebSocket endpoint。按优先级解析：

1. 服务端配置中的 `endpoint` 字段
2. `$MCP_ENDPOINT_<NAME>` 环境变量（名称大写，非字母数字 → `_`）
3. 全局 `$MCP_ENDPOINT`

!!! warning
    运行**多个**服务端时，请给每个服务端独立的 endpoint，否则 Xiaozhi 服务端无法路由工具调用。当某服务端回退到全局 endpoint 时桥会发出警告。

## 传输类型

| 类型 | 适用场景 | 说明 |
|------|----------|------|
| `stdio` | 本地脚本/可执行文件 | 子进程启动；env 与当前进程合并。 |
| `sse` | 旧式 SSE 远程服务端 | 由 SDK 处理 GET 流 / POST 请求。 |
| `streamablehttp` / `http` | 现代远程服务端（推荐） | 生产级 HTTP 传输。`http` 是别名。 |

## 命令行

```
mcp2xiaozhi [--config PATH] [--log-level LEVEL] <command>

commands:
  run [SERVER]       运行单个服务端（省略或 --all 则运行所有已启用的）
  list               列出已配置的服务端
  version            打印版本
```

## 许可证

MIT — 详见 [LICENSE](https://github.com/StanleyChanH/MCP2Xiaozhi/blob/main/LICENSE)。

---

📖 完整英文文档见左侧导航。源码：[GitHub](https://github.com/StanleyChanH/MCP2Xiaozhi) · 包：[PyPI](https://pypi.org/project/mcp2xiaozhi/)
