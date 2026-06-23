# Level 2.0 — `ytrewq` · Reverse Engineering & Pentest

Intermediate level introducing sockets, HTTP requests, and process/memory
manipulation. 6 projects.

> ⚠️ Educational use only. This level contains offensive tooling (keylogger,
> backdoor simulator, brute-forcer). Use **only** on systems you own or are
> explicitly authorized to test. See [`../DISCLAIMER.md`](../DISCLAIMER.md).

## Projects

| # | Project | What it does |
|---|---------|--------------|
| 1 | web_directory_bruteforcer | Discovers hidden web paths; interprets 200/301/403 status codes |
| 2 | banner_grabbing | Reads service banners from open ports |
| 3 | backdoor_simulator | Client/server remote-command demo (lab only) |
| 4 | keylogger | Captures keystrokes (lab only) |
| 5 | live_process_monitor | Lists and monitors running processes in real time |
| 6 | memory_hack_simulation | Demonstrates reading/writing process memory |

## Run

Most scripts need third-party packages (e.g. `requests`):

```bash
pip install requests
cd "1 - web_directory_bruteforcer"
python *.py
```
