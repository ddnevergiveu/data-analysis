# 可追溯的数据分析结果

**数据来源：合成演示数据，不能代表真实业务表现。**

问题：总销售额是多少？

规划模式：离线规则演示（没有调用大模型）。

## 数据库实际返回

| order_count | customer_count | total_amount |
| --- | --- | --- |
| 160 | 58 | 47250.74 |

返回 1 行。返回结果未截断。

## 可复核的执行 SQL

```sql
SELECT COUNT(*) AS order_count, COUNT(DISTINCT customer_id) AS customer_count, SUM(amount) AS total_amount FROM orders
```

## 证据与口径

证据 ID：`ev_ba026dd3c1584f491e9c2a14`

数据元信息：

```json
{
  "amount_definition": "gross order amount, not net revenue; one consistent currency required",
  "coverage_note": "Observed dates do not establish complete source coverage.",
  "currency": "unspecified; demo uses synthetic currency units",
  "date_max": "2025-06-29",
  "date_min": "2025-01-01",
  "demo_seed": 42,
  "grain": "one row per order",
  "input_sha256": "4d3aaf5667629123da0d9fc7b25e0d723f1f177d219aa8b494190f979f60a5e7",
  "rows": 160,
  "schema_version": 1,
  "semantic_sha256": "4d3aaf5667629123da0d9fc7b25e0d723f1f177d219aa8b494190f979f60a5e7",
  "source": "synthetic_demo",
  "synthetic": true
}
```

规划说明（不构成事实证明）：按每笔订单仅出现一次的金额汇总，同时给出去重客户和订单数。

- 一行是一笔订单；customer_id 必须是跨订单稳定客户标识。
- amount 为输入约定的订单商品毛额，不含退款核销；所有金额必须使用同一币种。
- 只描述所提供数据的覆盖范围，不能假设样本包含全部历史。

SQL 和数据指纹用于复核计算；它们不能保证模型对问题的理解正确，也不是防篡改签名。
