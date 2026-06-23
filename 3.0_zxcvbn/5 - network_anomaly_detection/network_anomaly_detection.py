import pandas as pd
from sklearn.ensemble import IsolationForest

def network_anomaly_scanner():
    print("--- AI Cyber Defense : Zero-Day Threat Hunter ---")
    print("[*] Initializing Unsupervised Machine Learning Engine...\n")

    # 1. THE DATASET (Simulated Live Network Traffic Logs)
    # Features : [Packet_Size_KB, Failed_Logins, Session_Duration_Secons]

    data = {
        "Traffic_ID" : ["#001", "#002", "#003", "#004", "#005", "#006", "#007", "#008", "#009", "#010"],
        "Packet_Size_KB" : [50, 45, 60, 55, 40, 15000, 48, 52, 49, 10], # Notice ID #006 (15,000 KB)
        "Failed_Logins" : [0, 1, 0, 0, 2, 0, 1, 0, 88, 0], # Notice ID #009 (88 fails)
        "Session_Duration" : [120, 300, 150, 400, 200, 10, 250, 100, 5, 9600] # Notice ID #010 (9600 secs)

    }

    df = pd.DataFrame(data)
    df.set_index("Traffic_ID", inplace=True)

    print("--- Live Network Traffic Analyzed ---")
    print(df)
    print("-" * 50 + "\n")

    # 2. THE AI MODEL (Isolation Forest)
    # Contamination parameter tells the AI: "We estimate about 30% of this traffic might be malicious."
    model = IsolationForest(contamination=0.3, random_state=42)

    # 3. TRAINING AND PREDICTION (Happens simultaneously)
    print("[*] AI is learning normal network behavior and isolating outliers...")

    # model.fit_predict returns : 1 for NORMAL, -1 for ANOMALY.
    df['Anomaly_Score'] = model.fit_predict(df)

    # Map the numeric scores to human-readable labels
    df['Status'] = df['Anomaly_Score'].apply(lambda x: "CRITICAL ANOMALY" if x == -1 else "NORMAL")

    # 4. REPORTING THE ZERO-DAY THREATS 
    print("\n" + "=" * 50)
    print("--- SOC (SECURITY OPERATIONS CENTER) AI ALERTS ---")
    print("=" * 50)

    anomalies_found = 0
    for index, row in df.iterrows():
        if row['Anomaly_Score'] == -1:
            anomalies_found += 1
            print(f"[{row['Status']}] Detected on Connection {index}:")
            print(f"  -> Packet Size : {row['Packet_Size_KB']} KB")
            print(f"  -> Failed Logins : {row['Failed_Logins']}")
            print(f"  -> Duration : {row['Session_Duration']} sec\n")

    if anomalies_found == 0:
        print("[INFO] Network is secure. No anomalies detected.")

    else:
        print(f"[!] Engine Successfully Isolated {anomalies_found} Distinct Cyber Threats.")

if __name__ == "__main__":
    network_anomaly_scanner()