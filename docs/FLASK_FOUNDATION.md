# Run and test the Flask foundation

This foundation PR adds the application factory and read-only health endpoint.
Account, database, résumé and discussion routes arrive in the subsequent backend
PRs. On this branch, /health returns {"status":"ok"} with HTTP 200 and the root
URL has no handler yet. The separately hosted demo may run a later backend version.

Use Python 3.12 or newer. From this project folder:

macOS/Linux:

    python3 -m venv .venv
    .venv/bin/python -m pip install -r requirements.txt
    .venv/bin/python -m unittest discover -s tests -v
    .venv/bin/python -m flask --app app run --port 5001

Windows PowerShell:

    python -m venv .venv
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    .venv\Scripts\python.exe -m unittest discover -s tests -v
    .venv\Scripts\python.exe -m flask --app app run --port 5001

Open http://127.0.0.1:5001/health. Choose another port if 5001 is occupied.
The test client exercises requests without starting a live server.

The four foundation tests cover JSON health/HEAD responses, rejection of POST to
the read-only endpoint, independent app configuration, and serving shared static
assets. Database/authentication/submission/permission tests belong to the feature
PRs that introduce those behaviors. The later integration branch has a combined
suite; these foundation tests are intentionally runnable before those features.

The project overview in README.md and the project plan from main are preserved.
The deployment checker from PR #58 remains a separate read-only tool.

## Render startup

Use the Python runtime with build command `pip install -r requirements.txt`.
Set the service's Start Command to `sh scripts/start_render.sh` and its
Health Check Path to `/health`. Save and redeploy after merging this change.

The script starts Gunicorn using the factory in app.py and Render's assigned
PORT. This verifies the foundation server. The full app routes and persistent
hosted database must be integrated before this service can replace the demo.
