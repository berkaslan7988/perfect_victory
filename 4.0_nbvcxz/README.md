# Level 4.0 — `nbvcxz` · Full Applications

The peak of the portfolio: four complete, multi-component applications showing a
clear shift from scripts to layered, production-style architecture.

> ⚠️ Some components are security tooling. Use responsibly — see
> [`../DISCLAIMER.md`](../DISCLAIMER.md). Projects requiring API keys ship an
> `.env.example`; copy it to `.env` and add your own keys. **Never commit a real `.env`.**

## Projects

### Zeus AI
A multi-agent autonomous coding agent. Specialized agents — **Planner, Coder,
Researcher, Validator** — coordinate via async orchestration, each with its own
tool subset. Features `litellm` model routing, ChromaDB vector memory, and voice
& screen monitoring. Frontend built with **Tauri + React + Vite**.
→ copy `ZeusAI/.env.example` to `ZeusAI/.env`.

### GhostChat Protocol
End-to-end encrypted messaging with web, mobile, and desktop variants.

### SecuritySuite
A desktop multi-tool combining a **C# UI** with Python security scripts.

### CyberDashboard
A dark-themed security-tools dashboard with Chart.js visualizations and a clean
CSS-variable design system.

## Notes
Build artifacts (`build/`, `target/`, `node_modules/`, `chroma_db/`, compiled
binaries) are intentionally excluded via `.gitignore`. Rebuild locally with the
relevant toolchain (npm / cargo / flutter / pip).
