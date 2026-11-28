# Database foundation

backend/models.py is the source of truth. schema.sql is historical reference only.
Install requirements.txt, set DATABASE_PATH to a writable SQLite filename, and run
`flask --app app init-db`. Startup does not create tables; init-db refuses an
existing database without changing its rows. Do not run schema.sql manually.

Display names are implemented separately in #112, already merged into the later
backend branch. Keep that migration when integrating the stack; do not duplicate
it in this foundation step.

## Backup and restore

Run this from the project directory with the app's environment. Choose a new filename for each backup.

```sh
python -m flask --app app backup-db --backup manual-backup.sqlite
```

Keep a copy off the host. The backup contains only data saved by the time it was taken.

1. Stop all app processes. Keep the current database and copy the backup to a new file.
2. Set `DATABASE_PATH` to the absolute path of the new file in both the shell and the app.
3. If the restored database needs an upgrade, run `python -m flask --app app upgrade-db --backup before-upgrade.sqlite`
   with a fresh backup filename. If rolling back the app code, use its matching pre-upgrade backup.
4. Restart the app. Check that `/ready` returns HTTP 200 and open a record you expect to find.
