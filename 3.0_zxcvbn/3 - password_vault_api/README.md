# Password Vault (API + UI)

A password vault split into two layers: a backend **API** (`vault_api.py`) and a
separate **UI** client (`vault_ui.py`) that talks to it — an introduction to
client/server separation. The generated `vault.db` is git-ignored.

```bash
pip install flask requests
python vault_api.py    # start the API
python vault_ui.py     # start the UI (separate terminal)
```
