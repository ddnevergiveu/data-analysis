# 技术选型与版本核验

核验日期：**2026-11-14**。下列版本已实际安装并用于本项目的验证，直接依赖固定在 `pyproject.toml` 和 `requirements.txt`；这不是对所有未来版本的兼容承诺。

| 组件 | 实测版本 | 在项目中的用途 | 官方来源 |
| --- | --- | --- | --- |
| MCP Python SDK | 2.3.0 | 标准化工具发现、结构化调用和 stdio 连接 | [发布记录](https://github.com/modelcontextprotocol/python-sdk/releases) |
| DuckDB | 2.0.0 LTS | 本地分析数据库、精确金额、只读执行 | [2026-10-21 官方发布](https://duckdb.org/2026/10/21/announcing-duckdb-200) |
| SQLGlot | 30.31.0 | DuckDB SQL AST 解析、规范化与受限语言检查 | [官方 API](https://sqlglot.com/sqlglot.html)、[PyPI](https://pypi.org/project/sqlglot/30.31.0/) |
| Pydantic | 2.14.3 | 生成规划 JSON Schema、校验响应字段 | [官方文档](https://docs.pydantic.dev/latest/) |
| HTTPX | 0.28.1 | 本机 Ollama HTTP 适配与 MockTransport 测试 | [官方文档](https://www.python-httpx.org/) |

## MCP v2 的实际变化

官方 v2 稳定线使用 `from mcp.server import MCPServer`，旧 v1 的 `mcp.server.fastmcp.FastMCP` 路径已移除。工具注解和响应使用 snake_case 字段，例如 `read_only_hint`、`structured_content`、`is_error`。

本项目实际使用新 API，并通过官方 `Client` 测试，不只是把旧代码的依赖版本改成 2.x。参考 [官方迁移说明](https://py.sdk.modelcontextprotocol.io/migration/) 和 [官方测试指南](https://py.sdk.modelcontextprotocol.io/get-started/testing/)。

## 结构化规划的价值与限制

Ollama 支持把 JSON Schema 传入 `format`。项目仍使用 Pydantic 校验返回内容，再经过 SQL 执行策略。JSON 合法只说明形状正确，不等于业务逻辑、SQL 或模型解释正确。

参考 [Ollama 官方 Structured Outputs](https://docs.ollama.com/capabilities/structured-outputs)。该官方页面说明其云端当前不支持结构化输出，本项目只提供本机服务适配。

## 为什么没有堆更多框架

当前问题是单数据集上的受限分析，用一次规划、一次受检查询即可完成。MCP 解决工具协议，DuckDB 解决计算，Pydantic 解决结构，评估集解决可验证性；无需额外引入向量库、多 Agent 编排或长链自动重试。

MCP 本身不是 Agent。本项目可称“数据分析 Copilot / MCP 数据工具服务”；离线规则演示不冒充语言模型。

## 不能省略的边界

- SQLGlot 官方明确其 parser 是宽松的：解析成功不等于真实引擎可执行，也不等于安全。
- DuckDB 是嵌入式引擎。只读连接和关闭外部访问是纵深约束，无法替代 OS 沙箱。参考 [官方安全说明](https://duckdb.org/docs/2.0/operations_manual/securing_duckdb/overview)。
- 本项目有源码级回归测试和已知拒绝用例，没有声称完成全面安全审计或真实 LLM 准确率评测。
