# 连接 MCP 客户端

本项目使用官方 **MCP Python SDK 2.3.0** 的 `MCPServer`，默认通过 **stdio** 运行。客户端启动一个本地 Python 子进程，通过标准输入输出交换协议消息；这个模式不监听公网端口，也不需要部署 HTTP 服务。

## 1. 安装与准备数据

在 `projects/evidence-data-copilot` 目录按主 README 创建虚拟环境并安装项目，然后先创建演示数据库：

```bash
python -m evidence_copilot demo --db /absolute/path/to/artifacts/demo.duckdb
```

请换成你实际使用的绝对路径；已有目标文件会被拒绝覆盖，可使用新的文件名。下面使用的数据库路径必须指向已经成功创建的 DuckDB 文件，服务器不会在连接时自动创建或修改数据库。

手工检查启动命令：

```bash
python -m evidence_copilot serve --db /absolute/path/to/artifacts/demo.duckdb
```

进程启动后等待 MCP 协议输入属于正常现象，不会显示普通聊天提示。按 `Ctrl+C` 可结束手工检查。实际使用时由 MCP 客户端启动这个进程。

## 2. 客户端配置示例

以下是采用 `mcpServers` 配置格式的客户端的示例。将 `command` 和 `--db` 后的值替换为你机器上的**绝对路径**，不要直接照抄 `/absolute/path`。

```json
{
  "mcpServers": {
    "evidence-data-copilot": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": [
        "-m",
        "evidence_copilot",
        "serve",
        "--db",
        "/absolute/path/to/artifacts/demo.duckdb"
      ]
    }
  }
}
```

Windows 的 Python 路径通常为 `C:\\path\\to\\.venv\\Scripts\\python.exe`。JSON 中反斜线需要写成 `\\`。通过 `pip install -e .` 安装项目后，无需依赖客户端的当前工作目录。

不同客户端的配置文件位置、字段名称及可支持的协议版本可能不同，应以对应客户端文档为准。本仓库通过官方 MCP `Client` 验证了内存连接和真正的 stdio 子进程连接，不声称测试过所有桌面客户端或托管连接器。

## 3. 可发现的接口

| 类型 | 名称 | 用途 |
| --- | --- | --- |
| Tool | `describe_dataset` | 读取字段、数据来源、合成标记、数据指纹和约束 |
| Tool | `run_query` | 执行一条经过检查的 `SELECT`，返回结果和证据标识 |
| Resource | `dataset://orders/schema` | 以 JSON 读取与 `describe_dataset` 相同的数据说明 |

建议给 AI 客户端的提问：

> 先读取数据说明，再计算每个地区的订单数和订单金额。请展示 SQL、数据指纹和 evidence_id，并说明这是否是合成数据。

`run_query` 示例参数：

```json
{
  "sql": "SELECT region, COUNT(*) AS orders, SUM(amount) AS total FROM orders GROUP BY region ORDER BY total DESC"
}
```

结果包含 `columns`、`rows`、`row_count`、`truncated`、`sql`、`dataset`、`evidence_id` 和 `elapsed_ms`。DECIMAL 金额以字符串传输，避免 JSON 浮点转换损失小数精度。`row_count` 表示本次返回的行数，不能在 `truncated=true` 时把它当作全部匹配行数。

## 4. 执行边界

启动命令选定数据库后，模型不能通过工具参数更换文件路径、扩大返回上限或延长执行时限。工具使用每次最多 100 行、3 秒查询时限，复用 CLI 的 SQL 策略和只读连接。读文件、网络访问、写入及管理语句会被拒绝。

`read_only_hint` 等 MCP 注解只是对客户端的描述；真正的限制由查询引擎执行。AST 检查和 DuckDB 设置不等于操作系统沙箱，因此这仍是面向可信本地数据的受限分析项目，不适合直接开放给匿名公网用户执行任意 SQL。

MCP 服务本身不调用语言模型。自然语言理解由连接的 AI 客户端承担；项目 CLI 中可选的 Ollama 规划器是另一条使用入口。

## 5. 验证

```bash
python -m unittest discover -s tests -p test_mcp.py -v
```

测试覆盖工具发现、只读注解、结构化计算结果、证据标识重复性、schema resource、危险 SQL 错误返回，以及真实 stdio 子进程中的发现和查询。

参考：[官方 MCP v2 工具文档](https://py.sdk.modelcontextprotocol.io/servers/tools/)、[官方 Client 测试文档](https://py.sdk.modelcontextprotocol.io/get-started/testing/)。
