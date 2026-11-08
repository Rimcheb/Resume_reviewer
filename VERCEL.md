# Vercel preview

Import the group repository into Vercel using the Flask preset and repository root.
Use Python 3.12. Select the preview branch for the first deployment.
Configure the Preview environment with a pooled Postgres DATABASE_URL and a stable
random SECRET_KEY. Use a dedicated preview database and keep both values private.

Before the first preview, install requirements.txt locally, export SECRET_KEY
and DATABASE_URL for the empty preview database, and run:

    python -m flask --app app init-db

Initialization refuses existing tables. Run it once, outside the build. Subsequent
deployments reuse the database. The existing PythonAnywhere SQLite records stay
on that host. For production, plan a tested data transfer before switching users.

Open /ready, sign in with two test accounts, submit a sample resume, and comment
from the second account. Push a change to the linked preview branch. Confirm Vercel
deploys the new commit and both users can read the same discussion. After the
team merges the running app into main, set main as the production branch and use
separate Production secrets and a production database.
