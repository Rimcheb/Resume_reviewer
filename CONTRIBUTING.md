# Contributing Guide

This document describes how our team works together in this repository. Please read it before opening your first pull request.

## Branches

- `main` always holds working, reviewed code. Nobody pushes to `main` directly.
- Create a new branch for each piece of work, named by type:
  - `feature/<short-description>` (e.g. `feature/login-page`)
  - `fix/<short-description>` (e.g. `fix/preview-spacing`)
  - `design/<short-description>` (e.g. `design/resume-wireframes`)
  - `docs/<short-description>` (e.g. `docs/setup-instructions`)

## Pull requests

1. Keep each PR small and focused on **one** thing. Smaller PRs get reviewed faster and are easier to understand.
2. Fill in the PR template. Someone who only reads the PR should be able to understand what it does and why.
3. Add docstrings and/or tests where applicable.
4. Request a review from at least **one** teammate.
5. Don't merge your own PR until it has at least one approval.
6. Address every review comment before merging, whether it came from a person or an automated tool. Either make the change, or reply explaining why you're keeping it as it is.
7. Use **Squash and merge** to keep the history of `main` clean.

## Reviewing

A good review is specific and actionable. Instead of "looks good" or "this is wrong", explain *what* to change and *why*. Point to the line, suggest an alternative, and ask questions when something is unclear.

Try to review requested PRs within 48 hours so nobody stays blocked.

## Issues and the project board

- All planned work lives as issues on the GitHub Project board.
- Assign yourself to an issue before you start it, so two people don't do the same work.
- Link your PR to its issue (`Closes #<number>` in the PR description).

## Releases (MVPs)

Each MVP is tagged on `main` (`mvp-1`, `mvp-2`, `mvp-3`) once the team agrees it's ready.
