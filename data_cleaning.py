import pandas as pd

def clean_orders(orders):
    orders['order_approved_at'] = orders['order_approved_at'].fillna(orders['order_purchase_timestamp'])
    orders.drop_duplicates(subset='order_id', inplace=True)
    orders['order_purchase_timestamp'] = pd.to_datetime(orders['order_purchase_timestamp'])
    return orders

def merge_data(orders, order_items, products, customers):
    df = orders.merge(order_items, on='order_id', how='left') \
               .merge(products, on='product_id', how='left') \
               .merge(customers, on='customer_id', how='left')
    return df
