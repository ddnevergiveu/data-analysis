import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import matplotlib
matplotlib.use("TkAgg")   # 或者 "Qt5Agg"
from matplotlib import rcParams


from src.data_cleaning import clean_orders, merge_data
from src.feature_engineering import add_total_amount, add_month_feature
from src.analysis import top_customers, repeat_rate, customer_lifetime_analysis
from src.visualization import plot_category_sales, plot_monthly_sales, plot_state_heatmap

# ===============================
# 1️⃣ 数据读取与清洗
# ===============================
base_dir = os.path.dirname(os.path.abspath(__file__))

data_dir = os.path.join(base_dir, "4")

orders_file = os.path.join(data_dir, "olist_orders_dataset.csv")
customers_file = os.path.join(data_dir, "olist_customers_dataset.csv")
order_items_file = os.path.join(data_dir, "olist_order_items_dataset.csv")
products_file = os.path.join(data_dir, "olist_products_dataset.csv")

orders = pd.read_csv(orders_file)
customers = pd.read_csv(customers_file)
order_items = pd.read_csv(order_items_file)
products = pd.read_csv(products_file)

orders = clean_orders(orders)
df = merge_data(orders, order_items, products, customers)
# ===============================
# 2️⃣ 特征工程
# ===============================
df = add_total_amount(df)
df = add_month_feature(df)

# ===============================
# 3️⃣ 基础统计指标 (Numpy)
# ===============================
total_sales = np.sum(df['total_amount'])
avg_sales = np.mean(df['total_amount'])
std_sales = np.std(df['total_amount'])
median_sales = np.median(df['total_amount'])

print(f"总销售额: {total_sales:.2f}, 平均订单额: {avg_sales:.2f}, 标准差: {std_sales:.2f}, 中位数: {median_sales:.2f}")

# ===============================
# 4️⃣ Pandas 高级分析
# ===============================
# 各州销售额
sales_by_state = df.groupby('customer_state')['total_amount'].sum().sort_values(ascending=False)

# 产品类别销售额及销量
from src.visualization import plot_category_sales, plot_monthly_sales, plot_state_heatmap

category_stats = df.groupby("product_category_name")[["order_item_id","total_amount"]].agg(
    order_count=("order_item_id","count"),
    total_sales=("total_amount","sum")
).sort_values(by="total_sales", ascending=False)

# 月度销售趋势
monthly_sales = df.groupby('month')['total_amount'].sum()

# 高价值客户分析
top_customers_list = top_customers(df, percentile=90)

# 客户复购率
rep_rate = repeat_rate(df)

# 客户生命周期
lifetime_stats = customer_lifetime_analysis(df)

# ===============================
# 5️⃣ 可视化
# ===============================
plot_category_sales(category_stats)
plot_monthly_sales(monthly_sales)
plot_state_heatmap(sales_by_state)

# ===============================
# 6️⃣ 分析结论 & 商业洞察
# ===============================
# - 销售额高度集中在少数州
# - Top 产品类别贡献大，优化库存策略
# - 高价值客户和复购客户是核心群体
# - 月度销售趋势有季节性，可优化营销活动
# - 客户生命周期分析为会员策略提供数据依据




