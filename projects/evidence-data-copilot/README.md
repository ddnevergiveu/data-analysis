# Evidence Data Copilot

**可追溯的数据分析助手 · MCP v2 + DuckDB 2.0 LTS + 结构化规划 + 自动评测**

输入一个经营问题，得到可执行的 SQL、数据库计算结果和数据指纹。结果可以保存为 JSON/Markdown，也可以重新执行验证。提供 MCP 工具接口，供支持本地 stdio 的 AI 客户端调用。

这个项目独立安装，**不依赖仓库根目录脚本或其他 PR**。默认使用合成数据和明确的规则演示，无需模型或 API 密钥；可选接入你运行的本机 Ollama 服务。

## 项目解决什么问题

自然语言分析容易出现三类问题：模型算错数字、查询口径不清楚、结果无法复核。本项目把职责拆开：规划器提出查询，受限执行层校验并计算，报告层只展示实际结果。运行成功不自动代表模型理解了问题，因此保留完整 SQL 和假设供检查。

| 能力 | 实现 |
| --- | --- |
| 自然语言入口 | 六类离线规则示例；可选 Ollama JSON Schema 规划 |
| MCP 工具 | `describe_dataset`、`run_query`，结构化返回 |
| 分析引擎 | DuckDB 2.0.0，订单金额使用 `DECIMAL(18,2)` |
| 查询约束 | SQLGlot AST、来源/函数允许列表、只读连接、执行预算 |
| 可追溯结果 | 原始输入与规范化数据 SHA256、规范 SQL、结果行、证据 ID |
| 复核 | `verify` 重跑保存的查询，比较数据指纹与结果 |
| 评估 | 手算正确答案、规则规划、已知拒绝用例和真实 MCP 协议测试 |

## 5 分钟运行

需要 **Python 3.11 或 3.12**。以下从仓库根目录进入本项目：

```bash
cd projects/evidence-data-copilot
python -m venv .venv
```

macOS/Linux：`source .venv/bin/activate`。Windows PowerShell：`.venv\Scripts\Activate.ps1`。

```bash
python -m pip install -e .

# 创建明确标记为 synthetic 的新数据库快照
evidence-copilot demo --db artifacts/demo.duckdb

# 问题 → 规则计划 → 查询 → JSON/Markdown 证据
evidence-copilot ask "总销售额是多少？" \
  --db artifacts/demo.duckdb --output artifacts/answer.json

# 重跑 SQL，核对保存的结果
evidence-copilot verify --db artifacts/demo.duckdb --answer artifacts/answer.json

# 执行独立的手算评估集
evidence-copilot evaluate --output artifacts/evaluation.json
```

也可以把所有 `evidence-copilot` 换成 `python -m evidence_copilot`。数据库创建命令拒绝覆盖已有快照；再次创建时请选择新路径。答案输出路径可复用，会更新对应的 `.json` 和 `.md`。

### 默认演示的实际输出

| 订单数 | 去重客户数 | 订单商品金额 |
| ---: | ---: | ---: |
| 160 | 58 | 47,250.74 |

全部来自 `seed=42` 生成的**合成数据**，金额为合成货币单位，不能描述任何真实公司的经营效果。完整示例见 [EXAMPLE.md](docs/EXAMPLE.md)。

## 六类离线问题

```bash
evidence-copilot questions
```

| 问题 | 计算口径 |
| --- | --- |
| 总销售额是多少？ | 订单商品金额求和，附订单数和客户数 |
| 平均客单价是多少？ | 一行一笔订单的金额均值，显示两位小数 |
| 每月销售额是多少？ | 按日历月汇总，不自动将缺失月份补零 |
| 各地区销售额排名 | 按订单所属地区汇总 |
| 客户复购率是多少？ | 至少两笔订单的客户 / 全部客户 |
| 消费金额最高的前10位客户 | 样本内累计金额排名，不是未来价值预测 |

**离线规则不是大模型。** 支持表中的问题及少量显式别名；遇到“2025 年总销售额”等额外条件会拒绝，不会偷偷忽略过滤条件。更多自由表达可通过本机 Ollama 规划，或显式传入 SQL。

## 可选：使用本机 Ollama 进行结构化规划

先运行 Ollama，并通过 `ollama list` 确认已经安装的本地模型名称。将下面 `YOUR_INSTALLED_MODEL` 替换为该名称：

```bash
evidence-copilot ask "2025年第一季度各地区订单金额，按金额降序排列" \
  --db artifacts/demo.duckdb \
  --planner ollama --model YOUR_INSTALLED_MODEL \
  --output artifacts/model-answer.json
```

默认调用 `http://127.0.0.1:11434/api/chat`。适配器使用 Ollama 的 JSON Schema `format` 参数和 Pydantic 验证；模型只提出 SQL，不直接生成报告中的数值。生成的查询仍需通过执行层检查；不支持的表达或字段会明确报错。

本实现只允许 loopback 接口地址，规划请求发送**问题和固定字段说明**，不发送数据库明细。不过本机接口本身不证明模型一定在本地推理，请选择已安装的本地模型；Ollama Cloud 的结构化输出不在本项目支持范围。

本次已测试适配器的请求格式、响应校验、错误处理和模拟模型到真实数据库的完整链路；**没有运行真实 Ollama 模型，也没有测量模型理解问题的准确率**。

## 接入 MCP 客户端

```bash
evidence-copilot serve --db /absolute/path/to/demo.duckdb
```

该命令通过 stdio 等待客户端，不是网页服务。AI 客户端先调用 `describe_dataset`，再调用 `run_query`，拿到实际查询结果、来源和证据 ID。

可复制的客户端配置、绝对路径示例及协议测试见 [MCP.md](docs/MCP.md)。已经用官方 MCP Client 测试内存连接和真实 stdio 子进程；没有声称逐一验证所有第三方客户端。

MCP 会把查询结果返回所连接的客户端。若客户端使用云模型，后续数据流由客户端决定，不能把整个系统解释为“数据绝不离开本地”。

## 导入自己的数据

输入必须为 UTF-8 CSV，且**恰好包含五列**：

```csv
order_id,customer_id,order_date,region,amount
o1,customer_a,2026-01-02,east,100.00
o2,customer_a,2026-02-02,east,200.00
o3,customer_b,2026-02-03,west,80.00
```

以上只是格式示例，全部为虚构记录。一行一笔订单，订单 ID 不重复；`customer_id` 是跨订单稳定客户标识；金额非负、最多两位小数，所有记录使用同一种货币。

```bash
evidence-copilot import-csv --csv data/orders.csv --db artifacts/my-orders.duckdb
evidence-copilot schema --db artifacts/my-orders.duckdb
evidence-copilot query --db artifacts/my-orders.duckdb \
  --sql "SELECT region, SUM(amount) AS total_amount FROM orders GROUP BY region ORDER BY total_amount DESC"
```

**不能直接导入原始 Olist 商品明细。** 需要先按订单汇总，将 `customer_unique_id` 映射为稳定 `customer_id`，明确订单状态/退款口径，再转换成上述格式。导入程序只验证结构与基本数值，无法判断业务方是否正确清洗了源数据。

## 结果与边界

每份答案包括问题、规划模式/模型、SQL、结果列与行、来源、数据指纹、执行耗时、实际依赖版本和限制说明。DECIMAL 金额在 JSON 中以字符串保存，避免二进制浮点舍入。

`verify` 检查相同数据上能否重现 SQL 结果，并比较快照元数据中保存的语义指纹；不会每次重新扫描全表计算指纹。证据 ID 不是数字签名，也不能认证被手工篡改的数据库或保证自然语言问题被正确理解。没有 `ORDER BY` 的多行查询可能重排，复核时请给需要稳定顺序的查询显式排序。

执行层拒绝多条语句、写入、外部文件/网络读取、表函数、系统目录和未知函数；默认最多返回 100 行、256 MB 引擎内存、2 线程，使用 3 秒协作式中断。`LIMIT` 不是计算预算。DuckDB 的设置、AST 检查和超时都不是 OS 沙箱，本项目面向本地可信数据，不提供公开多租户服务。

## 验证与工程结构

```bash
python -m unittest discover -s tests -v
evidence-copilot evaluate --output artifacts/evaluation.json
```

评估包括 **19 个独立手算/规划/拒绝用例**，详见 [EVALUATION.md](docs/EVALUATION.md)。单元与集成测试还覆盖精确金额、时间与数据校验、快照保护、超时、截断、证据重放、Ollama 模拟响应以及真实 MCP stdio 调用。CI 在 Python 3.11/3.12 上运行安装、测试、演示、重放和评估。

| 模块 | 职责 |
| --- | --- |
| `warehouse.py` | 合成数据、标准 CSV 校验、原子生成快照和数据指纹 |
| `planning.py` | 显式规则、Pydantic 计划、本机 Ollama 适配器 |
| `policy.py` / `engine.py` | SQL AST 约束、只读执行、预算和结构化结果 |
| `answers.py` | 结果导出、Markdown 呈现和重放验证 |
| `mcp_server.py` | 官方 MCP v2 工具与资源 |
| `evaluation.py` | 独立手算预期与拒绝用例 |
| `cli.py` | 一致的命令行入口 |

技术版本与官方来源见 [TECHNOLOGY.md](docs/TECHNOLOGY.md)，系统职责和取舍见 [ARCHITECTURE.md](docs/ARCHITECTURE.md)。

作者：姜圣涛 / [ddnevergiveu](https://github.com/ddnevergiveu)
