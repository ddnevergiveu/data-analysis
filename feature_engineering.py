def add_total_amount(df):
    df['total_amount'] = df['price'] * df['order_item_id']
    df['total_amount'] = df['total_amount'].fillna(0)
    return df

def add_month_feature(df):
    df['month'] = df['order_purchase_timestamp'].dt.to_period('M')
    return df
