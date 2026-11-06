# Run the Flask foundation

Use Python 3.12. From the project folder:

```bash
python -m venv .venv
```

Activate it with `.venv\Scripts\Activate.ps1` in PowerShell, or
`source .venv/bin/activate` on macOS/Linux. Then run:

```bash
python -m pip install -r requirements.txt
python -m flask --app app run --port 5001
```

Open http://127.0.0.1:5001/health. It returns `{"status":"ok"}` with HTTP 200.
This foundation exposes only the health endpoint; account and resume routes arrive
in the backend feature changes. The root URL returns 404 at this stage.
