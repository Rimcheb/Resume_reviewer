This is for CS162's final assignment.

# Resume Reviewer

Get honest, specific feedback on your résumé from peers who know your field, and give feedback in return.

[Live app](https://resumereviewer.pythonanywhere.com/)


[Write up and Analysis](https://docs.google.com/document/d/1GaK4-kPtZVnA47MxypeM9CTyszr_W4Uas1ApG-ajEgU/edit?tab=t.0#heading=h.qcmfzo2b1jwy)


[Survey](https://docs.google.com/forms/d/e/1FAIpQLSe4nhDJyu0zrM4oAXz20m8BwBwyqJhztEwccmk8yEmvaTgelQ/viewform?usp=publish-editor)

## What it does

Resume Reviewer is a free peer-review site. You post your résumé, say which field you're
targeting and what you want feedback on, and other members review it.

- **Submit** your résumé text with a target field and an optional feedback request.
- **Browse** other members' résumés, newest first, and filter by field.
- **Review** a résumé by leaving comments. Owners can reply with follow-ups.
- **Rate** feedback on your own résumé as helpful or not helpful.
- **Reputation:** each reviewer has a page showing how often their feedback was rated helpful.
- **Edit or delete** your own résumés and comments at any time.

## Flask foundation setup

See [the foundation setup and test guide](docs/FLASK_FOUNDATION.md) for local
commands and the scope of the first backend PR. The hosted demo may run a later
backend version than this foundation branch.

## Accounts branch setup

Install requirements.txt, then set a generated secret once in your shell:

```sh
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export COOKIE_SECURE=false  # local HTTP only
flask --app app init-db  # new database only
flask --app app run
```

See .env.example for configuration names; it is a reference, not an automatically
loaded configuration file. Production must supply a stable secret through the host
environment and use secure cookies over HTTPS. See docs/DATABASE_SETUP.md for
initialization safeguards. Account routes are /register, /login and /account.

## Submission branch

After signing in, visit /resumes/new to submit résumé text, a target field and an
optional feedback request. Submissions are visible to signed-in members. Existing
databases require `flask --app app upgrade-db --backup /path/to/new-backup.sqlite`
before using this branch. Never initialize over existing data. Browsing and posting
comments arrive in #51/#52; display names are implemented separately in #112.
