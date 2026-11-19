# Project Plan and Workflow

This document records what we have done, where we stand, and what we plan to do
before the final submission. It follows the CS162 final project instructions.
Update it in a PR whenever the plan changes.

## Key dates

| Date | Milestone |
|---|---|
| Oct 17 | Project check-in 1 |
| Nov 7 | Project check-in 2 |
| Nov 23 | Tag `mvp-1`: accounts, submission, browsing, comments in `main` and deployed |
| Nov 30 | Tag `mvp-2`: changes based on our LBA and survey results |
| Dec 4 | Tag `mvp-3`: third working MVP, all features done, deployed |
| Dec 5 | Project check-in 3 |
| Dec 5–11 | Act on check-in 3 feedback. Bug fixes and polish only. |
| Dec 14 | Final submission (PDF + demo video) |

**Feature freeze is Dec 4.** After `mvp-3` we only fix bugs, polish, and prepare the
submission.

## What we did up to check-in 1 (Oct 17)

- Chose the project and refined it from a resume *builder* into a **resume reviewer**:
  users paste their resume as text and other members leave feedback.
- Set up the repository and our collaboration rules:
  - PR template so every PR has the same format (#3)
  - Contributing guide: branch naming, one approval to merge, re-review after changes,
    address every comment (#4)
- Design system as CSS tokens for colors, type, spacing and accessible input/focus states (#5)
- Initial SQLite schema for users, resumes and comments (#6)
- First frontend page for submitting a resume (#8)

## Where we were at check-in 2 (Nov 7)

Our goal was **a working MVP with a connected database, deployed**. The backend was
written as a stack of PRs (#47 → #56) but none of it was in `main`, the app was not
deployed, and `mvp-1` was not tagged.

## Where we are now (Nov 19)

**In `main`:** the Flask foundation with tests (#47), SQLAlchemy storage (#48), the
submission and review page styling (#44, #46), the hosted demo check (#58), and the
Render start script (#126).

**Not in `main` yet:**
- **Login and registration (#49)** was merged into `feature/database-foundation-pr`
  *after* that branch had already been merged into `main`, so its code is stranded
  on that branch. The same happened to role-alias filtering (#114) on
  `feature/feedback-field-dropdown`. Both need a new PR into `main`.
- The rest of the stack: submission (#50), browsing (#51), comments (#52),
  edit/delete (#53), ratings (#54), reputation (#55). Display names (#112) and the
  LBA features already merged into `feature/release-reputation` (#75, #81, #96)
  arrive with #55.
- Navigation (#113), the accessibility pass (#122), the blue UI redesign (#123),
  Docker (#124), and the LBA feature PRs (#77–#105).

**Deployment:** Render currently serves only the foundation. We have two approaches:
Docker with Waitress (#124) and Render's Python runtime with Gunicorn (#126, merged).
We need to choose one.

So `mvp-1` is about nine days late. The plan below gets three working MVPs tagged
before check-in 3 and keeps the last week for revision only.

## Plan until the final submission

### Nov 19–23: MVP 1 (core app in `main`, deployed)
- [ ] Open a PR from `feature/database-foundation-pr` into `main` to bring in #49
      (login and registration), and one for #114.
- [ ] Merge #122 (accessibility) into `main`.
- [ ] Merge the stack into `main` **in order**: #50 → #51 → #52 → #53 → #54 → #55.
      Before merging each one, change its base to `main` (see *Stacked PRs* below).
- [ ] Choose one deployment approach (Docker #124 or Gunicorn #126) and document it.
- [ ] Set up persistent Postgres on Render and run `init-db` once.
- [ ] Turn on branch protection for `main` (1 approval, dismiss stale approvals).
- [ ] Tag `mvp-1` once the deployed app supports register, log in, submit, browse
      and comment.

### Nov 23–30: MVP 2 (LBA and survey changes)
- [ ] Merge navigation (#113) and the blue UI redesign (#123), rebased so they keep
      display names, Back links and navbar logout.
- [ ] Review and merge the LBA feature PRs (#77–#105). Each one needs a reviewer.
- [ ] Bring the Docker setup (#124) into `main` if we choose Docker.
- [ ] Remaining UX items: safer delete confirmation, selected state on rating buttons.
- [ ] Tag `mvp-2` and write down what changed since `mvp-1` and why (for the demo).

### Nov 30 – Dec 4: MVP 3 (third working MVP, feature freeze)
- [ ] Finish and merge the last features. Open issues after this are bugs only.
- [ ] Test-client tests for the core flows: register, log in, submit, comment,
      owner-only edit/delete.
- [ ] Test the deployed app from a fresh machine by following only the README.
- [ ] Tag `mvp-3` on **Dec 4** and redeploy.
- [ ] Each member drafts their own architecture diagram (#separationofconcerns, #abstraction).

### Dec 5: Project check-in 3
- [ ] Show `mvp-3` running on the hosted URL.

### Dec 5–11: revision only
- [ ] Act on check-in 3 feedback.
- [ ] Bug fixes, accessibility and copy polish. No new features.
- [ ] Write the demo script and assign a section to every member.

### Dec 11–14: submission
- [ ] Record the demo video (see *Demo video* below).
- [ ] Each member prepares their PDF (see *Submission checklist* below).
- [ ] Final README check, then submit on **Dec 14**.

## How we work

We follow [CONTRIBUTING.md](../CONTRIBUTING.md). In short:

1. **One issue, one branch, one PR.** Create the issue on the Project board first and
   assign yourself. Name the branch `feature/…`, `fix/…`, `design/…` or `docs/…`.
2. **Small PRs.** One component per PR, with a clear description, docstrings and/or tests.
   A PR has to be understandable on its own.
3. **Review within 48 hours.** Leave specific, actionable comments. The author must
   answer every comment, human or automated, by changing the code or explaining why not.
4. **Approval before merging.** New commits after approval need a new review.
   Use *Squash and merge* into `main`.
5. **Stacked PRs.** If a PR builds on another one, say so in the description and
   merge them in order. **Before merging, check the PR says "merge into `main`".**
   If its base is another branch that has already been merged, click **Edit** next
   to the title and change the base to `main` first. Otherwise the code lands on a
   branch nobody merges again (this happened to #49 and #114).
6. **Steady pace.** Our grade depends on commits being spread evenly over time and
   across members. Aim for at least one merged PR per member each week, not large
   batches near deadlines.

### Tagging an MVP

When the team agrees `main` is ready:

```bash
git checkout main
git pull
git tag -a mvp-1 -m "MVP 1: accounts, submission, comments, deployed"
git push origin mvp-1
```

## Deployment

The instructions ask for the simplest possible deployment on any common OS.

- The app should start with documented commands only, with no third-party sign-ups.
- **Pick one approach:** Docker (#124) runs the same on Mac, Windows and Linux, which
  fits the instructions best. Render's Python runtime with Gunicorn (#126) does not
  run Gunicorn on Windows.
- **Hosted data must persist:** Render's free tier wipes local files on restart, so the
  hosted app needs Postgres (`DATABASE_URL`). Local runs can keep SQLite in a Docker volume.
- Secrets: never commit a real `SECRET_KEY`. Set it in the host's dashboard, and keep
  `.env.example` up to date for local setup.
- Run `init-db` once on a new database, and back up before upgrades (`backup-db`).
- Document the hosted URL and the local setup in the README.

## Demo video (10–12 minutes, everyone presents a part)

1. Create an account, log in
2. Main features: submit a resume, browse, comment, edit/delete, ratings and reputation
3. Log out
4. Tech stack overview
5. How the app is deployed
6. **3–5 minutes:** how the MVPs progressed and why we changed things (pivots)

## Submission checklist (each member)

- [ ] Links to meaningful PRs I wrote (merged, reviewed, described, with docstrings/tests)
- [ ] Links to PRs I reviewed, where the author has addressed my comments
- [ ] Links to Project board tasks I was in charge of
- [ ] Roles of everyone on the team (see below)
- [ ] My own architecture diagram

Explanations belong in the PRs themselves, not in the PDF.

## Roles

The roles should be divided evenly and match the work we actually do.
**Each member: fill in your row when reviewing this PR.**

| Member | Role | Main areas |
|---|---|---|
| Alua | co-UI/UX designer, co-product manager | Design system, frontend UX, GitHub workflow, planning |
| | | |
| | | |
| | | |
| | | |
| | | |
