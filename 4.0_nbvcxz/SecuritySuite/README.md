# SecuritySuite — Desktop Security Multi-Tool

A desktop security toolkit that bundles several Python utilities behind a **C#
desktop UI**. This folder contains the Python tools; the C# build artifacts have
been stripped (`.gitignore`) — rebuild the UI from your .NET project to repackage.

## Tools

| Script | Purpose |
|--------|---------|
| `banner_grabber.py` | Reads service banners from open ports |
| `directory_auditor.py` | Audits/enumerates directory contents |
| `packet_sniffer.py` | Captures and inspects network packets |
| `process_monitor.py` | Lists and monitors running processes |

## Run (individual tools)

```bash
cd SecuritySuite
python banner_grabber.py
sudo python packet_sniffer.py     # packet capture needs privileges
```

> ⚠️ Educational/defensive use only. Run these only against systems you own or are
> authorized to test. See [`../../DISCLAIMER.md`](../../DISCLAIMER.md).
