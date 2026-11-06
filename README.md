# Run the Flask foundation

Use Python 3.12. From the project folder:

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m flask --app app init-db
.venv\Scripts\python.exe -m flask --app app run --port 5001
```

macOS/Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m flask --app app init-db
.venv/bin/python -m flask --app app run --port 5001
```

Open http://127.0.0.1:5001/health. It returns `{"status":"ok"}` with HTTP 200.
This foundation exposes only the health endpoint; account and resume routes arrive
in the backend feature changes. The root URL returns 404 at this stage.

Run `init-db` only for a new database. It creates the users, resumes and comments
tables and refuses to initialize a file that already contains tables.
If your database already has these tables, skip initialization.

The default database is `instance/resume_reviewer.sqlite`. For another location,
set `DATABASE_PATH` before running initialization or starting the server:

```powershell
$env:DATABASE_PATH = "C:/absolute/path/to/resume_reviewer.sqlite"
```

```bash
export DATABASE_PATH=/absolute/path/to/resume_reviewer.sqlite
```

Use the same path when restarting so the app opens the same saved records.

If port 5001 is already in use, choose another port and use it in the URL too.
