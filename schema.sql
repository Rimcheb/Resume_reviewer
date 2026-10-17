-- SQLite: enable foreign-key checks on every connection, before a transaction.
PRAGMA foreign_keys = ON;

CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE CHECK (length(trim(email)) > 0),
    password_hash TEXT NOT NULL
);

CREATE TABLE resumes (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    content TEXT NOT NULL CHECK (length(trim(content)) > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE comments (
    id INTEGER PRIMARY KEY,
    resume_id INTEGER NOT NULL REFERENCES resumes(id),
    author_id INTEGER NOT NULL REFERENCES users(id),
    content TEXT NOT NULL CHECK (length(trim(content)) > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
