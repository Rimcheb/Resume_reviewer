# Run the Flask foundation

Use Python 3.12. From the project folder:

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m flask --app app run --port 5001
```

macOS/Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m flask --app app run --port 5001
```

Open http://127.0.0.1:5001/health. It returns `{"status":"ok"}` with HTTP 200.
This foundation exposes only the health endpoint; account and resume routes arrive
in the backend feature changes. The root URL returns 404 at this stage.

If port 5001 is already in use, choose another port and use it in the URL too.
