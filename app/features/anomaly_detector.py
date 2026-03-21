import pandas as pd
from sklearn.ensemble import IsolationForest

def detect_anomalies(df):
    # Standardize column names
    df.columns = df.columns.str.lower()

    # --- VALIDATION ---
    if 'amount' not in df.columns:
        raise ValueError("Dataset must contain 'amount' column")

    # If no category, create one
    if 'category' not in df.columns:
        df['category'] = "unknown"

    # --- KEEP ORIGINAL CATEGORY ---
    df['category_original'] = df['category']

    # --- ENCODE CATEGORY FOR MODEL ---
    df['category_encoded'] = df['category'].astype('category').cat.codes

    # --- FEATURES ---
    X = df[['amount', 'category_encoded']]

    # --- MODEL ---
    model = IsolationForest(
        n_estimators=100,
        contamination=0.1,
        random_state=42
    )

    df['anomaly_flag'] = model.fit_predict(X)

    # Convert to readable labels
    df['anomaly'] = df['anomaly_flag'].map({1: "Normal", -1: "Anomaly"})

    # --- ADD SMART REASONING ---
    mean_amount = df['amount'].mean()
    std_amount = df['amount'].std()

    def get_reason(row):
        if row['anomaly'] == "Anomaly":
            if row['amount'] > mean_amount + 2 * std_amount:
                return "Unusually high transaction compared to your spending pattern"
            elif row['amount'] < mean_amount * 0.2:
                return "Unusually low transaction compared to your typical spending"
            else:
                return "Unusual transaction pattern detected"
        return "Normal"

    df['reason'] = df.apply(get_reason, axis=1)

    # --- CLEAN OUTPUT ---
    result = df[[
        'amount',
        'category_original',
        'anomaly',
        'reason'
    ]].rename(columns={
        'category_original': 'category'
    })

    return result