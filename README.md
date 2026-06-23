# Perfect Victory — Cybersecurity & Software Engineering Portfolio

A progressive, self-built learning journey spanning **33 projects across 5 difficulty levels** — from fundamental cryptography scripts to a multi-agent autonomous coding assistant and full-stack web applications.

The levels are named after keyboard rows (`qwerty → ytrewq → zxcvbn → nbvcxz → asdfgh`) and are intentionally ordered so each one is harder than the last. Together they trace a path from single-file procedural scripts to layered, modular, production-style architectures.

> ⚠️ **Educational use only.** Several projects are offensive-security tools (keylogger, backdoor simulator, packet sniffer, brute-forcers). They were written to learn how attacks work so they can be defended against. See [`DISCLAIMER.md`](./DISCLAIMER.md) before running anything. Use them **only** on systems you own or have explicit written permission to test.

---

## Curriculum at a glance

| Level | Theme | Projects | Focus |
|-------|-------|----------|-------|
| [1.0 `qwerty`](./1.0_qwerty) | Cryptography & Fundamentals | 10 | Python basics, hashing, ciphers, OSINT, networking primitives |
| [2.0 `ytrewq`](./2.0_ytrewq) | Reverse Engineering & Pentest | 6 | Sockets, HTTP, process & memory manipulation |
| [3.0 `zxcvbn`](./3.0_zxcvbn) | Advanced Security + Machine Learning | 5 | `scapy`, CVE scanning, APIs, scikit-learn detection models |
| [4.0 `nbvcxz`](./4.0_nbvcxz) | Full Applications | 4 | Multi-agent AI, E2EE messaging, desktop security suites |
| [5.0 `asdfgh`](./5.0_asdfgh) | Web Development | 8 | Static → dynamic, Flask + DB, MVC, auth, e-commerce |

---

## Highlights

- **Zeus AI** — a multi-agent (Planner / Coder / Researcher / Validator) autonomous coding agent with async orchestration, per-agent tool subsets, ChromaDB memory, voice & screen monitoring, and a Tauri + React + Vite desktop frontend.
- **GhostChat Protocol** — end-to-end encrypted messaging with web, mobile, and desktop variants.
- **ML detection models** — phishing and network-anomaly detection built on scikit-learn.
- **Full-stack web suite** — portfolio, blog, landing pages, plus Flask-backed news, e-commerce, job board, and forum apps.

---

## Tech stack

**Languages:** Python, JavaScript, C#, HTML/CSS, Rust (Tauri)
**Security/Networking:** `scapy`, `socket`, `requests`, raw packet analysis, CVE lookups
**ML/Data:** scikit-learn, pandas
**AI:** litellm, multi-agent orchestration, ChromaDB (vector memory)
**Web/App:** Flask, Vite, React, Chart.js
**Desktop:** Tauri, C# UI

---

## Repository structure

```
perfect_victory_portfolio/
├── 1.0_qwerty/     # Cryptography & fundamentals (10 projects)
├── 2.0_ytrewq/     # Reverse engineering & pentest (6 projects)
├── 3.0_zxcvbn/     # Advanced security + ML (5 projects)
├── 4.0_nbvcxz/     # Full applications (Zeus AI, GhostChat, SecuritySuite, ...)
├── 5.0_asdfgh/     # Web development (8 projects)
├── DISCLAIMER.md   # Ethics & responsible-use notice
├── LICENSE         # MIT
└── .gitignore
```

Each level has its own `README.md` with a project-by-project breakdown.

---

## Getting started

Most Level 1–3 projects are standalone Python scripts:

```bash
cd "1.0_qwerty/1 - password_generator"
python password_generator.py
```

Projects that need third-party packages or API keys (Levels 3–4) include a
`requirements.txt` and/or an `.env.example`. Copy `.env.example` to `.env` and
add your own keys — never commit the real `.env`.

---

## License

Released under the [MIT License](./LICENSE).
