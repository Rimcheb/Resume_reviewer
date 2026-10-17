# Resume_reviewer

CS162 assignment: a collaborative resume reviewer.

## Local backend setup

Requires Python 3.9 or newer. Run these commands from the repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m flask --app app run --port 5001
```

Open http://127.0.0.1:5001/health. It should return HTTP 200 with
`{"status":"ok"}`. Stop the server with Ctrl+C.

The health endpoint checks that the server responds. Database access, resume
submission, and frontend routes are not implemented yet. The root URL `/`
currently returns 404.

## Run the test

With the environment activated:

```sh
python -m unittest discover -s tests
```

The test uses Flask's test client, so no running server or database is needed.
