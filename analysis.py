import numpy as np

def top_customers(df, percentile=90):
    customer_sales = df.groupby('customer_id')['total_amount'].sum()
    threshold = np.percentile(customer_sales, percentile)
    return customer_sales[customer_sales >= threshold]

def repeat_rate(df):
    customer_orders = df.groupby('customer_id')['order_id'].nunique()
    return (customer_orders > 1).sum() / customer_orders.shape[0]

def customer_lifetime_analysis(df):
    customer_time = df.groupby('customer_id')['order_purchase_timestamp'].agg(['min','max'])
    customer_time['lifetime_days'] = (customer_time['max'] - customer_time['min']).dt.days
    return customer_time
