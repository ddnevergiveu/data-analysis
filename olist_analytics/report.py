"""Export auditable tables, metadata and a self-contained HTML report."""

import base64
import html
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .customers import cohort_retention, rfm_segments
from .metrics import customer_lifetime_analysis, order_summary, sales_summary, sales_tables, top_customers
from .visualization import plot_category_sales, plot_monthly_sales, plot_retention, plot_state_heatmap


def _json_default(value):
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, (pd.Timestamp, pd.Period)):
        return str(value)
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


def write_report(items, quality, observation_end, output_dir, source):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    summary = sales_summary(items)
    category, monthly, state = sales_tables(items)
    rfm = rfm_segments(items, observation_end)
    counts, retention = cohort_retention(items, observation_end)
    summary = {
        "source": source,
        "synthetic": source == "synthetic_demo",
        "observation_end_exclusive": observation_end.isoformat(),
        "order_status": "delivered",
        "currency": "BRL",
        "amount_definition": "sum of item prices; excludes freight, refunds and platform fees",
        "customer_key": "customer_unique_id",
        "metrics": summary,
        "segments": {str(key): int(value) for key, value in rfm["segment"].value_counts().items()},
        "cohort_last_complete_month": str(observation_end.to_period("M") - 1),
    }
    for filename, content in [("summary.json", summary), ("data_quality.json", quality)]:
        (output / filename).write_text(json.dumps(content, ensure_ascii=False, indent=2, default=_json_default, allow_nan=False) + "\n", encoding="utf-8")
    tables = {
        "orders": order_summary(items).set_index("order_id"),
        "category_sales": category,
        "monthly_sales": monthly,
        "state_sales": state,
        "rfm_segments": rfm,
        "cohort_counts": counts,
        "cohort_retention": retention,
        "top_customers": top_customers(items),
        "customer_observed_span": customer_lifetime_analysis(items),
    }
    for name, table in tables.items():
        table.to_csv(output / f"{name}.csv", encoding="utf-8", float_format="%.6f")
    charts = [
        ("category_sales.png", lambda path: plot_category_sales(category, path)),
        ("monthly_sales.png", lambda path: plot_monthly_sales(monthly, path)),
        ("state_sales.png", lambda path: plot_state_heatmap(state, path)),
        ("cohort_retention.png", lambda path: plot_retention(retention, path)),
    ]
    image_tags = []
    for filename, render in charts:
        path = render(output / filename)
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        image_tags.append(f'<img alt="{html.escape(filename)}" src="data:image/png;base64,{encoded}">')
    metrics = summary["metrics"]
    cards = [("商品销售额 · BRL", f'{metrics["merchandise_value"]:,.2f}'),
             ("已交付订单", f'{metrics["orders"]:,}'),
             ("平均订单商品金额 · BRL", f'{metrics["average_order_value"]:,.2f}'),
             ("客户复购率", f'{metrics["repeat_customer_rate"]:.1%}')]
    card_html = "".join(f'<div class="card"><span>{label}</span><strong>{value}</strong></div>' for label, value in cards)
    segment_table = rfm.groupby("segment").agg(customers=("frequency", "size"), merchandise_value=("monetary", "sum"))
    downloads = " · ".join(f'<a href="{name}.csv">{name}.csv</a>' for name in tables)
    badge = "合成演示数据 · 不能代表 Olist 实际经营结果" if summary["synthetic"] else "用户提供的 Olist 数据快照"
    document = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Olist · 电商经营与客户分析</title><style>
body{{margin:0;background:#f1f4f3;color:#172c30;font:16px/1.6 system-ui,sans-serif}}main{{max-width:1120px;margin:auto;padding:36px 24px}}h1{{font-size:34px;line-height:1.3}}h2{{margin-top:36px}}.badge{{background:#d7e9e4;padding:8px 14px;border-radius:6px;display:inline-block}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:16px;margin:24px 0}}.card,section{{background:white;border:1px solid #d7e1de;border-radius:10px;padding:20px}}.card span{{display:block;font-size:13px;color:#596f72}}.card strong{{display:block;font-size:28px;margin-top:12px}}img{{width:100%;height:auto}}.charts{{display:grid;gap:20px;grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}}table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{padding:9px;text-align:right;border-bottom:1px solid #e1e8e6}}th{{background:#edf4f1}}.scroll{{overflow:auto}}a{{color:#126d70}}pre{{white-space:pre-wrap;font-size:12px}}footer{{margin:32px 0;color:#596f72}}section{{margin-bottom:20px}}
</style></head><body><main>
<span class="badge">{badge}</span><h1>电商经营与客户分析</h1>
<p>观察截止时间（不含）：{html.escape(observation_end.isoformat())}。按最终状态为 delivered 的订单统计；商品金额不含运费、退款核销与平台费用，不能当作净收入。</p>
<div class="cards">{card_html}</div><div class="charts">{''.join(image_tags)}</div>
<h2>客户分群 · RFM</h2><section class="scroll">{segment_table.to_html(border=0, float_format=lambda x: f'{x:,.2f}')}
<p>分群采用可解释的固定规则，不以任意排序拆散同分客户。规则属于演示运营策略，需结合真实业务验证。</p></section>
<h2>首次观测购买月份 · 复购留存</h2><section class="scroll">{retention.to_html(border=0, na_rep='—', float_format=lambda x: f'{x:.1%}')}
<p>分母为首次观测购买月的客户数。仅纳入已结束的完整月份；“—”表示尚未完整观测，0% 才表示完整月份无复购。首次观测不保证是客户的历史首次购买。</p></section>
<h2>月度经营数据</h2><section class="scroll">{monthly.to_html(border=0, float_format=lambda x: f'{x:,.2f}')}<p>最新月份可能不完整，不能直接据此断言增长或下滑。</p></section>
<h2>数据质量与复核</h2><section><pre>{html.escape(json.dumps(quality, ensure_ascii=False, indent=2))}</pre><p>{downloads}</p><p><a href="summary.json">指标和口径 JSON</a> · <a href="data_quality.json">数据质量 JSON</a></p></section>
<footer>所有结果由当前输入计算。图表随 HTML 内嵌，离线可查看；CSV 和 JSON 下载链接需要保留同目录文件。</footer>
</main></body></html>'''
    (output / "index.html").write_text(document, encoding="utf-8")
    return summary
