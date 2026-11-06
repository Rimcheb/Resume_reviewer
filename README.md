# Run Resume Reviewer

Use Python 3.12. Run commands from the project folder.

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:SECRET_KEY = .venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
$env:COOKIE_SECURE = "false"
.venv\Scripts\python.exe -m flask --app app init-db
.venv\Scripts\python.exe -m flask --app app run --port 5001
```

macOS/Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
export SECRET_KEY=$(.venv/bin/python -c "import secrets; print(secrets.token_hex(32))")
export COOKIE_SECURE=false
.venv/bin/python -m flask --app app init-db
.venv/bin/python -m flask --app app run --port 5001
```

Run init-db only for a new database. It refuses existing tables. Keep existing data.
The default file is instance/resume_reviewer.sqlite. To use another file, set
DATABASE_PATH to an absolute filename before initialization and startup. Use the
same path when restarting. Set environment variables in every new terminal.
COOKIE_SECURE=false is for local HTTP; use true and a stable private SECRET_KEY
for HTTPS hosting. Never commit secrets or database files.

Open http://127.0.0.1:5001 and register, then log in. /health returns server status.
If port 5001 is occupied, choose another port and update the URL.
