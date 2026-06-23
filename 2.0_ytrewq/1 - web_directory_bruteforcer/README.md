# Web Directory Brute-Forcer

Discovers hidden paths on a web server by requesting candidate directories from a
wordlist and interpreting HTTP status codes (200 found / 301 redirect /
403 forbidden). Includes a safe `_simulator` variant.

```bash
pip install requests
python web_directory_bruteforcer.py          # live
python web_directory_bruteforcer_simulator.py # offline demo
```

> Use only against web servers you own or are authorized to test.
