# Local Docker demo

Start Docker Desktop, then run these commands in this repository.

    docker compose build
    docker compose run --rm web python -m flask --app app init-db
    docker compose up -d

Open http://localhost:5001. Initialize only the first time. If tables already
exist, initialization refuses to overwrite them. Subsequent starts use
`docker compose up -d`. The named volume stores accounts, resumes, and comments.
`docker compose down` stops the app and retains this volume. Adding `-v`
deletes the volume and its data.

The Compose key is for the local demo. On Render, select Docker as the runtime
and set a random SECRET_KEY, COOKIE_SECURE=true, and a persistent Postgres
DATABASE_URL. Initialize an empty hosted database once with init-db before
directing users there. Free Render services cannot persist the local SQLite
file. Existing PythonAnywhere data needs a separate tested transfer.

The Dockerfile uses Render's PORT when provided. Set /ready as the health
check. Link the original GitHub repository and choose the tested branch for
automatic deploys. The full app must be merged into main before selecting
main as production.

This branch builds on feature/vercel-postgres and the working handoff app.
It does not yet include the pending blue UI integration.
