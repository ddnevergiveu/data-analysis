🛒 Olist 电商数据分析项目
📌 项目简介

本项目基于 巴西电商 Olist 数据集，使用 Python（Pandas / NumPy / Matplotlib / Seaborn / Plotly） 对用户、订单、商品和销量进行全面分析。
通过数据清洗、特征工程和可视化，帮助理解电商业务的 客户行为、商品类别表现、销售趋势 等
🛍️ 电商行业业务分析参考

📂 项目结构
data-analysis/
│
├── data/                          # 原始数据集 (Olist)
│   ├── olist_orders_dataset.csv
│   ├── olist_customers_dataset.csv
│   ├── olist_order_items_dataset.csv
│   └── olist_products_dataset.csv
│
├── src/                           # 核心功能模块
│   ├── data_cleaning.py           # 数据清洗
│   ├── feature_engineering.py     # 特征工程
│   ├── analysis.py                # 数据分析逻辑
│   └── visualization.py           # 数据可视化
│
├── main.py                        # 主程序入口
├── requirements.txt               # 依赖库
└── README.md                      # 项目说明

⚙️ 环境配置
1. 克隆项目
git clone https://github.com/ddnevergiveu/data-analysis.git
cd data-analysis

2. 创建虚拟环境并安装依赖
python3 -m venv venv
source venv/bin/activate   # Mac/Linux
venv\Scripts\activate      # Windows

pip install -r requirements.txt

3. 运行项目
python main.py

📊 分析内容

数据清洗：处理缺失值、时间字段、异常数据

特征工程：新增订单总金额、订单月份等特征

核心分析

🧑‍🤝‍🧑 用户分布 & 客户生命周期

📦 商品类别销售额排行

📈 月度销售趋势

🌍 按州的销量热力图

🖼️ 可视化结果示例
<img width="1200" height="600" alt="Figure_1" src="https://github.com/user-attachments/assets/2ac9867b-f49c-4282-bf52-8fc48e515cbc" />

<img width="1200" height="600" alt="Figure_1" src=
"https://github.com/user-attachments/assets/08822e10-b7c9-4200-91f0-74758c046313" />
<img width="1200" height="600" alt="Figure_2" src="https://github.com/user-attachments/assets/46443faf-ec9a-4ae7-949b-548476cbbebd" />


🔮 下一步改进

引入机器学习模型，预测客户流失

使用聚类分析客户分群

构建交互式 Dashboard（Streamlit / Dash）

📝 作者![Uploading Figure_1.png…]()


👤 姜圣涛 / ddnevergiveu

📧 Email: 1544209178@qq.com

🌐 Blog / LinkedIn: （可选）
