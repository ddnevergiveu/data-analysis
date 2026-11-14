# 项目 01：RFM 客户分群

**业务问题：** 哪些客户近期持续购买，哪些老客户已经较久没有回来？

## 运行

在仓库根目录运行：

```bash
python main.py --demo --output reports/rfm-demo
```

打开 `reports/rfm-demo/index.html` 的“客户分群”部分；完整逐客户结果在 `rfm_segments.csv`，字段为 R、F、M、分群和最近购买时间。该统一命令同时生成经营及留存结果，避免维护多份重复清洗代码。

真实数据：

```bash
python main.py --data-dir data/raw --as-of 2018-09-01 --output reports/rfm
```

`--as-of` 应换成你已核实的导出截止日期。输入为四张 Olist CSV，格式见主 README。

## 设计与解释

先按 `customer_unique_id` 识别同一个人、按 `order_id` 汇总金额，再计算 RFM。固定规则保留同分客户的一致性，不通过任意排序制造分层。完整规则见 [指标说明](../../docs/METHODOLOGY.md)。

示例运营动作：对 `at_risk` 组设计召回实验，对 `loyal` 组评估会员权益，对 `new` 组观察第二次购买。分群本身不证明这些动作有效；需要观察后续增量订单与成本。

## 验收

- 同一客户多个订单身份仍合并为一人。
- 多商品订单 F 只计一笔，M 是明细价格之和。
- 相同 RFM 值的客户不会因输入顺序不同被分到不同组。
- 自动测试：`python -m unittest discover -s tests -v`。
