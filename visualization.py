import os
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib import font_manager as fm


# ---------------- 中文字体 ----------------
def get_chinese_font():
    candidate_fonts = [
        "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/3419f2a427639ad8c8e139149a287865a90fa17e.asset/AssetData/PingFang.ttc",
        "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/62032b9b64a0e3a9121c50aeb2ed794e3e2c201f.asset/AssetData/Hei.ttf",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
    ]
    for path in candidate_fonts:
        if os.path.exists(path):
            return fm.FontProperties(fname=path)
    raise RuntimeError("未找到可用中文字体")


my_font = get_chinese_font()


# ---------------- 绘图函数 ----------------
def plot_category_sales(category_stats, save_path=None):
    plt.figure(figsize=(12, 6))
    top10 = category_stats.sort_values(by='total_sales', ascending=False).head(10).reset_index()
    sns.barplot(x='product_category_name', y='total_sales', hue='product_category_name',
                data=top10, dodge=False, palette="viridis", legend=False)

    plt.title("商品类别销售额", fontproperties=my_font)
    plt.xlabel("类别", fontproperties=my_font)
    plt.ylabel("总销售额", fontproperties=my_font)
    plt.xticks(rotation=45, fontproperties=my_font)
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path)
    plt.show()


def plot_monthly_sales(df, save_path=None):
    if 'order_month' not in df.columns:
        df['order_month'] = pd.to_datetime(df['order_purchase_timestamp']).dt.to_period('M').astype(str)
    monthly = df.groupby('order_month')['total_amount'].sum().reset_index()

    plt.figure(figsize=(12, 6))
    sns.lineplot(x='order_month', y='total_amount', data=monthly, marker='o')

    plt.title("每月销售额趋势", fontproperties=my_font)
    plt.xlabel("月份", fontproperties=my_font)
    plt.ylabel("总销售额", fontproperties=my_font)
    plt.xticks(rotation=45, fontproperties=my_font)
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path)
    plt.show()


def plot_state_heatmap(df, save_path=None):
    state_sales = df.groupby('customer_state')['total_amount'].sum().reset_index()
    plt.figure(figsize=(12, 6))
    sns.barplot(x='customer_state', y='total_amount', data=state_sales, palette="magma")

    plt.title("各州销售额热力图（示意）", fontproperties=my_font)
    plt.xlabel("州", fontproperties=my_font)
    plt.ylabel("总销售额", fontproperties=my_font)
    plt.xticks(rotation=90, fontproperties=my_font)
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path)
    plt.show()


