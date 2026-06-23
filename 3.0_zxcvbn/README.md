# Level 3.0 — `zxcvbn` · Advanced Security + Machine Learning

The bridge into libraries, APIs, and data/ML. 5 projects that move beyond
single-file scripts toward real ecosystems.

> ⚠️ Educational use only. The packet sniffer and vulnerability scanner must only
> be run on networks/hosts you own or are authorized to assess. See
> [`../DISCLAIMER.md`](../DISCLAIMER.md).

## Projects

| # | Project | What it does | Key tech |
|---|---------|--------------|----------|
| 1 | professional_network_packet_sniffer | Captures and parses live network packets | `scapy` |
| 2 | automated_vulnerability_scanner | Checks targets against a CVE database | requests / CVE data |
| 3 | password_vault_api | Vault with separated API and UI layers | API design, SQLite |
| 4 | phishing_detection | Classifies phishing vs. legitimate messages | scikit-learn |
| 5 | network_anomaly_detection | Flags anomalous network behavior | scikit-learn |

## Run

```bash
pip install -r requirements.txt   # where present
# packet sniffer typically needs elevated privileges:
sudo python *.py
```
