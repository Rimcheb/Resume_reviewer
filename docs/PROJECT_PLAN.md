# Project Plan and Workflow

This document records what we have done, where we stand, and what we plan to do
before the final submission. It follows the CS162 final project instructions.
Update it in a PR whenever the plan changes.

## Key dates

| Date | Milestone |
|---|---|
| Oct 17 | Project check-in 1 |
| Nov 7 | Project check-in 2 |
| Nov 14 | Tag `mvp-1`: working MVP, connected database, deployed |
| Nov 28 | Tag `mvp-2`: changes based on our LBA results |
| Dec 4 | Project check-in 3: release candidate, all features done |
| Dec 9 | Tag `mvp-3`: final version. Feature freeze. |
| Dec 14 | Final submission (PDF + demo video) |

After **Dec 9** we only fix bugs, polish, and prepare the submission. No new features.

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

## Where we are at check-in 2 (Nov 7)

Our goal for today was **a working MVP with a connected database, deployed**.

- **Written, not yet merged:** the backend is in a stack of PRs (#47 → #56):
  app setup, SQLAlchemy storage, accounts, submission, browsing, comments, owner
  edit/delete, helpfulness ratings, reputation and backups. Frontend work for the
  submission and review pages is in #44 and #46, and also included in #50.
- **Not done yet:** none of this is in `main`, the app is not deployed, there are no
  tests, and `mvp-1` is not tagged.

So we are about one week behind. The plan below catches up by Nov 14 and leaves the
last week free for revision.

## Plan until the final submission

### Week 1: Nov 7–14, finish MVP 1
- [ ] Review and merge #47 → #56 **in order** (each PR builds on the previous one).
- [ ] Decide on overlapping PRs: close #9, #44 and #46 with a link to the PR that includes them.
- [ ] Add tests with Flask's test client: register, log in, submit, comment, owner-only edit.
- [ ] Deploy to a free host and add the steps to the README (see *Deployment* below).
- [ ] Tag `mvp-1` on `main`.

### Week 2: Nov 14–21, UX polish and LBA input
- [ ] Display names instead of "Member 3" for comment authors
- [ ] Readable dates (e.g. "Nov 5, 2026") instead of raw timestamps
- [ ] Styled error and success messages; same input and focus style on every field
- [ ] Confirmation step before deleting a resume or comment
- [ ] Each member turns their LBA findings into GitHub issues for MVP 2

### Week 3: Nov 21–28, MVP 2
- [ ] Build the changes chosen from the LBA results
- [ ] Tag `mvp-2` and write down what changed and why (needed for the demo video)

### Week 4: Nov 28 – Dec 4, release candidate (check-in 3)
- [ ] All features finished and merged; open issues are bugs only
- [ ] Test the deployed app from a fresh machine by following only the README
- [ ] Each member drafts their own architecture diagram (#separationofconcerns, #abstraction)

### Week 5: Dec 4–9, final version
- [ ] Act on check-in 3 feedback
- [ ] Bug fixes only, then tag `mvp-3` (final)

### Week 6: Dec 9–14, submission only
- [ ] Write the demo script and record the video (see *Demo video* below)
- [ ] Each member prepares their PDF (see *Submission checklist* below)
- [ ] Final README check. No new features.

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
5. **Stacked PRs.** If a PR builds on another one, say so in the description,
   merge them in order, and rebase the next PR after each merge.
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
- Secrets: the app must not crash when `SECRET_KEY` is missing. Use a development
  fallback or ship a `.env.example`.
- Use one persistent SQLite file, and back it up before each upgrade (`backup-db`).
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
