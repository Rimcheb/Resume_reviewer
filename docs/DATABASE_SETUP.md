# Database foundation

backend/models.py is the source of truth. schema.sql is historical reference only.
Install requirements.txt, set DATABASE_PATH to a writable SQLite filename, and run
`flask --app app init-db`. Startup does not create tables; init-db refuses an
existing database without changing its rows. Do not run schema.sql manually.

Display names are implemented separately in #112, already merged into the later
backend branch. Keep that migration when integrating the stack; do not duplicate
it in this foundation step.
