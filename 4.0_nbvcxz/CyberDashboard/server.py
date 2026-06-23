"""
CyberDashboard — Unified Cybersecurity Tools Dashboard
FastAPI backend serving real-time scan modules over WebSocket.
"""

import asyncio
import json
import os
import socket
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

import psutil
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

# ---------------------------------------------------------------------------
# App & constants
# ---------------------------------------------------------------------------

app = FastAPI(title="CyberDashboard", version="1.0.0")

COMMON_PORTS = [21, 22, 23, 25, 53, 80, 110, 143, 443, 445,
                993, 995, 1433, 3306, 3389, 5432, 8080, 8443, 27017, 6379]

SERVICE_MAP = {
    21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS",
    80: "HTTP", 110: "POP3", 143: "IMAP", 443: "HTTPS", 445: "SMB",
    993: "IMAPS", 995: "POP3S", 1433: "MSSQL", 3306: "MySQL",
    3389: "RDP", 5432: "PostgreSQL", 8080: "HTTP-Alt", 8443: "HTTPS-Alt",
    27017: "MongoDB", 6379: "Redis",
}

HTTP_PORTS = {80, 8080, 443, 8443}

CVE_DB = {
    "OpenSSH 7.4": {
        "cve": "CVE-2017-15906",
        "severity": "HIGH",
        "description": "Read-only bypass via sftp-server",
    },
    "OpenSSH 8.2": {
        "cve": "CVE-2020-15778",
        "severity": "MEDIUM",
        "description": "Command injection via scp",
    },
    "Apache/2.4.41": {
        "cve": "CVE-2020-1927",
        "severity": "MEDIUM",
        "description": "mod_rewrite redirect vulnerability",
    },
    "Apache/2.4.49": {
        "cve": "CVE-2021-41773",
        "severity": "CRITICAL",
        "description": "Path traversal and RCE",
    },
    "nginx/1.14.0": {
        "cve": "CVE-2019-20372",
        "severity": "MEDIUM",
        "description": "HTTP request smuggling",
    },
    "OpenSSH 7.6": {
        "cve": "CVE-2018-15473",
        "severity": "MEDIUM",
        "description": "Username enumeration",
    },
    "vsftpd 2.3.4": {
        "cve": "CVE-2011-2523",
        "severity": "CRITICAL",
        "description": "Backdoor command execution",
    },
    "ProFTPD 1.3.5": {
        "cve": "CVE-2015-3306",
        "severity": "HIGH",
        "description": "Remote code execution via SITE CPFR",
    },
}

DIR_WORDLIST = [
    "admin", "login", "dashboard", "api", "config", "backup", "uploads",
    "secret", "test", "dev", "staging", "db", "database", "phpmyadmin",
    ".env", "wp-admin", "robots.txt", "sitemap.xml", ".git", "server-status",
]

# ---------------------------------------------------------------------------
# HTTP endpoint — serve index.html
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = Path(__file__).parent / "index.html"
    if not index_path.exists():
        return HTMLResponse(
            "<h1>index.html not found</h1><p>Place index.html next to server.py</p>",
            status_code=404,
        )
    return HTMLResponse(index_path.read_text(encoding="utf-8"))

# ---------------------------------------------------------------------------
# Helpers — low-level blocking I/O (run in executor)
# ---------------------------------------------------------------------------

def _scan_port(target: str, port: int, timeout: float = 1.5) -> bool:
    """Return True if *port* is open on *target*."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex((target, port)) == 0
    except Exception:
        return False


def _grab_banner(target: str, port: int, timeout: float = 3.0) -> str:
    """Grab a service banner from an open port."""
    try:
        if port in HTTP_PORTS:
            proto = "https" if port in {443, 8443} else "http"
            url = f"{proto}://{target}:{port}/"
            req = urllib.request.Request(url, method="HEAD",
                                         headers={"User-Agent": "CyberDashboard/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                server = resp.headers.get("Server", "")
                powered = resp.headers.get("X-Powered-By", "")
                parts = [p for p in (server, powered) if p]
                return " | ".join(parts) if parts else f"HTTP {resp.status}"
        else:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                s.connect((target, port))
                try:
                    banner = s.recv(1024).decode("utf-8", errors="replace").strip()
                except socket.timeout:
                    banner = ""
                return banner if banner else ""
    except Exception as exc:
        return f"[error: {exc}]"

# ---------------------------------------------------------------------------
# WebSocket helper — safe JSON sender
# ---------------------------------------------------------------------------

async def _ws_send(ws: WebSocket, module: str, msg_type: str, data: dict):
    """Send a JSON message through the WebSocket, swallowing closed-socket errors."""
    try:
        await ws.send_json({"module": module, "type": msg_type, "data": data})
    except Exception:
        pass  # connection may already be closed

# ---------------------------------------------------------------------------
# Module 1 — Port Scanner
# ---------------------------------------------------------------------------

async def run_port_scanner(ws: WebSocket, target: str):
    module = "port_scanner"
    await _ws_send(ws, module, "status", {"message": f"Starting port scan on {target}…"})

    loop = asyncio.get_event_loop()
    open_ports: list[dict] = []
    total = len(COMMON_PORTS)

    for idx, port in enumerate(COMMON_PORTS, 1):
        is_open = await loop.run_in_executor(None, _scan_port, target, port)
        service = SERVICE_MAP.get(port, "unknown")
        status = "open" if is_open else "closed"

        if is_open:
            open_ports.append({"port": port, "service": service})

        await _ws_send(ws, module, "result", {
            "port": port,
            "service": service,
            "status": status,
            "progress": f"{idx}/{total}",
        })

    await _ws_send(ws, module, "complete", {
        "message": f"Scan complete — {len(open_ports)}/{total} ports open",
        "open_ports": open_ports,
    })

# ---------------------------------------------------------------------------
# Module 2 — Banner Grabber
# ---------------------------------------------------------------------------

async def run_banner_grabber(ws: WebSocket, target: str):
    module = "banner_grabber"
    await _ws_send(ws, module, "status", {"message": f"Discovering open ports on {target}…"})

    loop = asyncio.get_event_loop()

    # Phase 1 – find open ports
    open_ports: list[int] = []
    for port in COMMON_PORTS:
        if await loop.run_in_executor(None, _scan_port, target, port):
            open_ports.append(port)

    if not open_ports:
        await _ws_send(ws, module, "complete", {"message": "No open ports found — nothing to grab."})
        return

    await _ws_send(ws, module, "status", {
        "message": f"Found {len(open_ports)} open port(s). Grabbing banners…"
    })

    # Phase 2 – grab banners
    banners: list[dict] = []
    for port in open_ports:
        banner = await loop.run_in_executor(None, _grab_banner, target, port)
        service = SERVICE_MAP.get(port, "unknown")
        entry = {"port": port, "service": service, "banner": banner}
        banners.append(entry)
        await _ws_send(ws, module, "result", entry)

    await _ws_send(ws, module, "complete", {
        "message": f"Grabbed banners from {len(banners)} port(s)",
        "banners": banners,
    })

# ---------------------------------------------------------------------------
# Module 3 — Directory Auditor
# ---------------------------------------------------------------------------

def _probe_path(base_url: str, path: str) -> dict:
    """Probe a single URL path and return the result dict."""
    url = f"{base_url.rstrip('/')}/{path}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "CyberDashboard/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return {"path": path, "url": url, "status": resp.status, "tag": "found"}
    except urllib.error.HTTPError as exc:
        tag = "restricted" if exc.code == 403 else ("redirect" if exc.code in (301, 302) else "not_found")
        return {"path": path, "url": url, "status": exc.code, "tag": tag}
    except Exception:
        return {"path": path, "url": url, "status": 0, "tag": "error"}


async def run_dir_auditor(ws: WebSocket, target: str):
    module = "dir_auditor"

    base_url = target if target.startswith(("http://", "https://")) else f"http://{target}"

    await _ws_send(ws, module, "status", {
        "message": f"Auditing directories on {base_url}…"
    })

    loop = asyncio.get_event_loop()
    total = len(DIR_WORDLIST)
    findings: list[dict] = []

    for idx, path in enumerate(DIR_WORDLIST, 1):
        result = await loop.run_in_executor(None, _probe_path, base_url, path)
        if result["tag"] in ("found", "redirect", "restricted"):
            findings.append(result)

        await _ws_send(ws, module, "result", {
            **result,
            "progress": f"{idx}/{total}",
        })

    await _ws_send(ws, module, "complete", {
        "message": f"Audit complete — {len(findings)} interesting path(s) found",
        "findings": findings,
    })

# ---------------------------------------------------------------------------
# Module 4 — Process Monitor
# ---------------------------------------------------------------------------

async def run_process_monitor(ws: WebSocket, _target: str):
    module = "process_monitor"
    await _ws_send(ws, module, "status", {"message": "Collecting process information…"})

    try:
        procs: list[dict] = []
        for p in psutil.process_iter(["pid", "name", "memory_info", "cpu_percent"]):
            try:
                info = p.info
                mem_mb = round((info["memory_info"].rss if info["memory_info"] else 0) / (1024 * 1024), 2)
                procs.append({
                    "pid": info["pid"],
                    "name": info["name"] or "unknown",
                    "memory_mb": mem_mb,
                    "cpu_percent": info["cpu_percent"] or 0.0,
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        procs.sort(key=lambda p: p["memory_mb"], reverse=True)
        top25 = procs[:25]

        vm = psutil.virtual_memory()
        system_stats = {
            "cpu_percent": psutil.cpu_percent(interval=0.5),
            "memory_total_mb": round(vm.total / (1024 * 1024), 2),
            "memory_used_mb": round(vm.used / (1024 * 1024), 2),
            "memory_percent": vm.percent,
        }

        for proc in top25:
            await _ws_send(ws, module, "result", proc)

        await _ws_send(ws, module, "complete", {
            "message": f"Top {len(top25)} processes by memory",
            "processes": top25,
            "system_stats": system_stats,
        })

    except Exception as exc:
        await _ws_send(ws, module, "error", {"message": f"Process monitor failed: {exc}"})

# ---------------------------------------------------------------------------
# Module 5 — Vulnerability Scanner
# ---------------------------------------------------------------------------

async def run_vuln_scanner(ws: WebSocket, target: str):
    module = "vuln_scanner"
    await _ws_send(ws, module, "status", {"message": f"Starting vulnerability scan on {target}…"})

    loop = asyncio.get_event_loop()

    # Step 1 — port scan
    await _ws_send(ws, module, "status", {"message": "Step 1/3 — Scanning ports…"})
    open_ports: list[int] = []
    for port in COMMON_PORTS:
        if await loop.run_in_executor(None, _scan_port, target, port):
            open_ports.append(port)

    await _ws_send(ws, module, "status", {
        "message": f"Step 1 complete — {len(open_ports)} open port(s)"
    })

    if not open_ports:
        await _ws_send(ws, module, "complete", {
            "message": "No open ports — no vulnerabilities to assess.",
            "vulnerabilities": [],
        })
        return

    # Step 2 — banner grab
    await _ws_send(ws, module, "status", {"message": "Step 2/3 — Grabbing banners…"})
    port_banners: dict[int, str] = {}
    for port in open_ports:
        banner = await loop.run_in_executor(None, _grab_banner, target, port)
        if banner and not banner.startswith("[error"):
            port_banners[port] = banner

    await _ws_send(ws, module, "status", {
        "message": f"Step 2 complete — {len(port_banners)} banner(s) retrieved"
    })

    # Step 3 — match CVEs
    await _ws_send(ws, module, "status", {"message": "Step 3/3 — Matching against CVE database…"})
    vulns: list[dict] = []
    for port, banner in port_banners.items():
        for sig, cve_info in CVE_DB.items():
            if sig.lower() in banner.lower():
                entry = {
                    "port": port,
                    "service": SERVICE_MAP.get(port, "unknown"),
                    "banner": banner,
                    "cve": cve_info["cve"],
                    "severity": cve_info["severity"],
                    "description": cve_info["description"],
                }
                vulns.append(entry)
                await _ws_send(ws, module, "result", entry)

    severity_counts = {}
    for v in vulns:
        severity_counts[v["severity"]] = severity_counts.get(v["severity"], 0) + 1

    await _ws_send(ws, module, "complete", {
        "message": f"Scan complete — {len(vulns)} vulnerability/ies found",
        "vulnerabilities": vulns,
        "severity_counts": severity_counts,
    })

# ---------------------------------------------------------------------------
# Module 6 — Packet Sniffer
# ---------------------------------------------------------------------------

async def run_packet_sniffer(ws: WebSocket, _target: str):
    module = "packet_sniffer"

    try:
        from scapy.all import sniff, IP, TCP, UDP, Raw  # type: ignore
    except ImportError:
        await _ws_send(ws, module, "error", {
            "message": "scapy is not installed. Install with: pip install scapy"
        })
        return

    await _ws_send(ws, module, "status", {"message": "Capturing packets for 10 seconds…"})

    sensitive_keywords = ["user", "pass", "login", "password", "token", "auth"]

    try:
        loop = asyncio.get_event_loop()
        packets = await loop.run_in_executor(None, lambda: sniff(timeout=10))
    except PermissionError:
        await _ws_send(ws, module, "error", {
            "message": "Administrator/root privileges required for packet capture."
        })
        return
    except Exception as exc:
        await _ws_send(ws, module, "error", {
            "message": f"Packet capture failed: {exc}"
        })
        return

    proto_counts: dict[str, int] = {"TCP": 0, "UDP": 0, "Other": 0}
    alerts: list[dict] = []

    for pkt in packets:
        if pkt.haslayer(TCP):
            proto_counts["TCP"] += 1
        elif pkt.haslayer(UDP):
            proto_counts["UDP"] += 1
        else:
            proto_counts["Other"] += 1

        # DPI — inspect payload for sensitive keywords
        if pkt.haslayer(Raw):
            try:
                payload = pkt[Raw].load.decode("utf-8", errors="replace").lower()
                for kw in sensitive_keywords:
                    if kw in payload:
                        src = pkt[IP].src if pkt.haslayer(IP) else "?"
                        dst = pkt[IP].dst if pkt.haslayer(IP) else "?"
                        alert = {
                            "keyword": kw,
                            "src": src,
                            "dst": dst,
                            "snippet": payload[:120],
                        }
                        alerts.append(alert)
                        await _ws_send(ws, module, "result", {
                            "type": "alert",
                            **alert,
                        })
                        break  # one alert per packet
            except Exception:
                pass

    total_packets = sum(proto_counts.values())
    await _ws_send(ws, module, "complete", {
        "message": f"Capture complete — {total_packets} packets, {len(alerts)} alert(s)",
        "protocol_distribution": proto_counts,
        "alerts": alerts,
        "total_packets": total_packets,
    })

# ---------------------------------------------------------------------------
# Module dispatcher
# ---------------------------------------------------------------------------

MODULE_RUNNERS = {
    "port_scanner": run_port_scanner,
    "banner_grabber": run_banner_grabber,
    "dir_auditor": run_dir_auditor,
    "process_monitor": run_process_monitor,
    "vuln_scanner": run_vuln_scanner,
    "packet_sniffer": run_packet_sniffer,
}

SCAN_ALL_MODULES = [
    "port_scanner",
    "banner_grabber",
    "dir_auditor",
    "process_monitor",
    "vuln_scanner",
]

# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    print(f"[{datetime.now(timezone.utc).isoformat()}] WebSocket connected", flush=True)

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await _ws_send(ws, "system", "error", {"message": "Invalid JSON"})
                continue

            action = msg.get("action", "")
            target = msg.get("target", "")
            module_name = msg.get("module", "")

            if action == "scan":
                if module_name not in MODULE_RUNNERS:
                    await _ws_send(ws, "system", "error", {
                        "message": f"Unknown module: {module_name}"
                    })
                    continue

                # process_monitor doesn't need a target
                if module_name != "process_monitor" and not target:
                    await _ws_send(ws, module_name, "error", {
                        "message": "Target is required for this module"
                    })
                    continue

                try:
                    await MODULE_RUNNERS[module_name](ws, target)
                except Exception as exc:
                    await _ws_send(ws, module_name, "error", {
                        "message": f"Module crashed: {exc}"
                    })

            elif action == "scan_all":
                if not target:
                    await _ws_send(ws, "system", "error", {
                        "message": "Target is required for scan_all"
                    })
                    continue

                await _ws_send(ws, "system", "status", {
                    "message": f"Launching all modules against {target}…"
                })

                tasks = [
                    MODULE_RUNNERS[m](ws, target)
                    for m in SCAN_ALL_MODULES
                ]

                results = await asyncio.gather(*tasks, return_exceptions=True)
                for m, result in zip(SCAN_ALL_MODULES, results):
                    if isinstance(result, Exception):
                        await _ws_send(ws, m, "error", {
                            "message": f"Module crashed: {result}"
                        })

                await _ws_send(ws, "system", "complete", {
                    "message": "All scans finished"
                })

            else:
                await _ws_send(ws, "system", "error", {
                    "message": f"Unknown action: {action}"
                })

    except WebSocketDisconnect:
        print(f"[{datetime.now(timezone.utc).isoformat()}] WebSocket disconnected", flush=True)
    except Exception as exc:
        print(f"[{datetime.now(timezone.utc).isoformat()}] WebSocket error: {exc}", flush=True)

# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    print("\n[+] CyberDashboard Starting...", flush=True)
    print("[+] Open http://127.0.0.1:9000 in your browser", flush=True)
    print("=" * 50, flush=True)
    uvicorn.run("server:app", host="127.0.0.1", port=9000, reload=True)
