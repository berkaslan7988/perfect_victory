# Backdoor Simulator (lab only)

A client/server pair demonstrating how a remote-command channel works: the
server issues commands, the client executes them and returns output. Built to
understand C2 mechanics from a defensive perspective.

```bash
python server.py     # attacker side (your machine)
python client.py     # victim side (your test VM)
```

> ⚠️ Lab/educational use ONLY. Never deploy on systems you don't own. See ../../DISCLAIMER.md.
