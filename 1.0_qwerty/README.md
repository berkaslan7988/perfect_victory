# Level 1.0 — `qwerty` · Cryptography & Fundamentals

The foundation level: 10 standalone Python scripts that introduce core security
and programming concepts. Procedural and `input()`-driven by design — the goal is
correct logic and clear, teachable code.

> ⚠️ Educational use only. Tools 8–10 touch networking/OSINT — use them only on
> systems you own or are authorized to test. See [`../DISCLAIMER.md`](../DISCLAIMER.md).

## Projects

| # | Project | What it does |
|---|---------|--------------|
| 1 | password_generator | Generates strong random passwords with configurable rules |
| 2 | hash_generator | Produces hashes (MD5/SHA family) for given input |
| 3 | caesar_cipher_&_decrypter | Caesar-cipher encryption and brute-force decryption |
| 4 | brute_force_4_digit_pin_codes | Demonstrates exhaustive search over a 4-digit PIN space |
| 5 | password_manager | Simple local password vault |
| 6 | phishing_email_analyzer | Flags suspicious indicators in email text |
| 7 | log_file_detective_tool | Parses server logs to surface anomalies |
| 8 | mac_address_spoofer_simulator | Simulates MAC-address changing |
| 9 | ip_osint_information_gatherer | Gathers open-source info about an IP |
| 10 | basic_tcp_port_scanner | Scans a host for open TCP ports |

## Run

```bash
cd "1 - password_generator"
python password_generator.py
```
