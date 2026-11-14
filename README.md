# Olist 电商分析：经营指标、RFM 分群与月度留存

[![Python checks](https://github.com/ddnevergiveu/data-analysis/actions/workflows/ci.yml/badge.svg)](https://github.com/ddnevergiveu/data-analysis/actions/workflows/ci.yml)

一个可离线演示、可复核计算口径的 Python 数据分析作品集。将 Olist 的订单、商品明细、客户和商品表连接起来，输出经营指标、客户分群、月度复购留存，以及可离线查看的 HTML 报告。

**先运行，再接入真实数据。** 内置数据是固定种子生成的合成数据，不包含真实客户，也不代表 Olist 的经营结果。

## 三个可运行场景

| 场景 | 回答的问题 | 主要输出 |
| --- | --- | --- |
| 经营分析 | 商品销售额、订单数、客单价和复购率如何？ | `summary.json`、月度/品类/州统计 |
| [RFM 客户分群](projects/rfm-segmentation/README.md) · 新增 | 哪些客户近期复购，哪些客户值得观察召回？ | `rfm_segments.csv` |
| [月度复购留存](projects/cohort-retention/README.md) · 新增 | 不同首次购买月份的客户后来是否回来？ | 留存人数、比例及热力图 |

## 3 分钟运行

需要 Python 3.11 或更新版本；CI 覆盖 3.11 / 3.12。

```bash
git clone https://github.com/ddnevergiveu/data-analysis.git
cd data-analysis
python -m venv .venv
```

激活环境：macOS / Linux 用 `source .venv/bin/activate`；Windows PowerShell 用 `.venv\Scripts\Activate.ps1`。

```bash
python -m pip install -r requirements.txt
python main.py --demo --output reports/demo
```

用浏览器打开 `reports/demo/index.html`。无需数据库、GUI 后端、Kaggle 账户或网络数据请求。图表使用英文标签避免跨平台中文字体依赖，HTML 说明为中文。

也可安装为命令行工具：

```bash
python -m pip install -e .
olist-analyze --demo --output reports/demo
```

同样支持 `python -m olist_analytics --demo`。导入模块本身不会运行分析或读取数据。

## 可复现的演示结果

默认 `--seed 42`、截止 `2025-01-01`，**合成样本**得到：

| 指标 | 演示值 |
| --- | ---: |
| 已交付订单 | 235 |
| 去重客户 | 79 |
| 商品明细 | 467 |
| 商品金额（模拟 BRL） | 46,409.63 |
| 平均每单商品金额 | 197.49 |
| 复购客户率 | 69.62% |

这些数值仅用于检查运行结果，**不能用于描述真实 Olist 业务**。完整机器可读示例见 [demo_summary.json](docs/demo_summary.json)。

## 接入真实 Olist 数据

从 [Olist 官方数据发布页](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) 下载，并遵守原始数据的使用条款。将以下四个文件放入 `data/raw/`：

| 文件 | 必需字段 |
| --- | --- |
| `olist_orders_dataset.csv` | `order_id`, `customer_id`, `order_status`, `order_purchase_timestamp` |
| `olist_customers_dataset.csv` | `customer_id`, `customer_unique_id`, `customer_state` |
| `olist_order_items_dataset.csv` | `order_id`, `order_item_id`, `product_id`, `price`, `freight_value` |
| `olist_products_dataset.csv` | `product_id`, `product_category_name` |

```bash
python main.py --data-dir data/raw --as-of 2018-09-01 --output reports/olist
```

`--as-of` 表示独占截止时间，上例仅为用法示例，请根据你实际核实的数据覆盖范围调整。若省略，程序取最后订单日期的次日，并在质量报告标记为推断值；缺少订单不能证明某月数据完整。

## 结果文件

| 文件 | 内容 |
| --- | --- |
| `index.html` | 中文报告；图表内嵌，可离线打开 |
| `summary.json` | 数据来源、观察终点、指标口径、核心指标及分群人数 |
| `data_quality.json` | 输入行数、重复行、排除订单、缺失品类和覆盖提示 |
| `orders.csv` | 每单一行，方便复核客单价 |
| `category_sales.csv` / `monthly_sales.csv` / `state_sales.csv` | 维度统计 |
| `rfm_segments.csv` | 每客户的 R、F、M 和分群 |
| `cohort_counts.csv` / `cohort_retention.csv` | 留存人数与比例；空白代表尚未完整观测 |
| `top_customers.csv` / `customer_observed_span.csv` | 高金额客户与已观测购买跨度 |
| `*.png` | 品类、月度、州分布和留存图 |

默认输出目录为 `reports/latest`。原始数据和生成报告均已加入 `.gitignore`。

## 这次修正了什么

- 修正不存在的 `src` 导入、缺失依赖、写死的本地数据目录和 macOS 字体路径。
- 修正 `price * order_item_id`：明细序号不是数量，金额按每行 `price` 累加。
- 使用 `customer_unique_id` 识别跨订单客户，复购不会因不同 `customer_id` 被漏计。
- 先聚合订单再计算客单价；运费单独统计。
- 仅统计快照中最终为 `delivered` 的订单，并公开这一选择。
- 连接前验证唯一键和外键，拒绝冲突重复、负数/无穷金额、坏日期或缺失必要数据。
- 留存只计完整月份，将未观测单元格保留为空。
- 通过自动测试与 GitHub Actions 检查关键计算、数据校验及完整演示。

## 结构与测试

核心代码在 `olist_analytics/`：`data.py` 负责校验和连接，`metrics.py` 定义业务指标，`customers.py` 实现 RFM 与留存，`report.py` 和 `visualization.py` 负责输出，`cli.py` 提供命令行。根目录旧模块保留为兼容导入入口；客户指标统一使用 `customer_unique_id`，购买跨度字段改为 `observed_span_days`。

```bash
python -m unittest discover -s tests -v
```

测试覆盖多商品金额、跨订单客户身份、订单级客单价、取消订单、完全重复/冲突记录、非法金额/日期/时区、观察边界、留存截尾、RFM 同值一致性、CSV 读取和离线 HTML 导出。

完整口径、RFM 规则与限制见 [METHODOLOGY.md](docs/METHODOLOGY.md)。本项目属于事后描述分析：最终交付状态不是历史时点已知状态；商品金额不是扣除退款和费用后的净收入；RFM 规则是待验证的运营假设。

## 相关作品

- [machine-learning-project1](https://github.com/ddnevergiveu/machine-learning-project1)：从历史行为预测未来高价值/复购，关注时间窗口与数据泄漏。
- [stock-da](https://github.com/ddnevergiveu/stock-da)：行情质量检查、SQLite 导入、SQL 分析与交易成本回测。

作者：姜圣涛 / [ddnevergiveu](https://github.com/ddnevergiveu)
