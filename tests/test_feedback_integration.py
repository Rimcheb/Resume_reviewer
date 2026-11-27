from pathlib import Path
import sqlite3
from contextlib import closing
import unittest
from sqlalchemy import select, func
import test_uploads as fixtures
from backend import database, sqlite_storage
from backend.models import ResumeRevision
from backend.sqlite_upgrade import upgrade_db


class FeedbackIntegrationTests(unittest.TestCase):
    setUp = fixtures.UploadTests.setUp
    post = fixtures.UploadTests.post

    def test_imported_replacement_stays_plain_and_snapshots_only_on_save(self):
        self.app.config['RICH_TEXT_ENABLED'] = True
        with self.app.app_context():
            record = database.create_resume(self.owner['id'], '<p><strong>Original</strong></p>', 'Software engineering', '', 'html')
            original_revision = database.get_current_revision(record['id'])
            comment = database.create_comment(record['id'], self.other['id'], 'About the original', original_revision['id'])
        result = self.post(f'/resumes/{record["id"]}/import', data={'content_format': 'html', 'resume': '<p>Draft</p>'}, payload=fixtures.docx_bytes())
        self.assertEqual(result.status_code, 200)
        self.assertIn('name="content_format" value="plain"', result.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(database.get_current_revision(record['id'])['id'], original_revision['id'])
            self.assertEqual(database.get_resume_by_id(record['id'])['content_format'], 'html')
        saved = self.post(f'/resumes/{record["id"]}/edit', data={'resume': 'Corrected import', 'content_format': 'plain'})
        self.assertEqual(saved.status_code, 303)
        with self.app.app_context():
            updated = database.get_resume_by_id(record['id'])
            self.assertEqual(updated['content_format'], 'plain')
            self.assertEqual(updated['target_field'], 'Software engineering')
            self.assertNotEqual(database.get_current_revision(record['id'])['id'], original_revision['id'])
            self.assertEqual(database.get_comment_by_id(comment['id'])['revision_id'], original_revision['id'])
            self.assertEqual(database.get_revision(record['id'], original_revision['id'])['content_format'], 'html')

    def test_import_failure_preserves_rich_text_draft_format(self):
        result = self.post(data={'content_format': 'html', 'resume': '<p>Keep draft</p>'}, filename='bad.pdf', payload=b'bad')
        self.assertEqual(result.status_code, 400)
        page = result.get_data(as_text=True)
        self.assertIn('name="content_format" value="html"', page)
        self.assertIn('&lt;p&gt;Keep draft&lt;/p&gt;', page)

    def test_complete_v2_upgrade_preserves_accounts_ratings_and_unknown_history(self):
        with closing(sqlite3.connect(self.app.config['DATABASE'])) as connection:
            for table in ('comment_ratings', 'comments', 'resume_revisions', 'resumes', 'users'):
                connection.execute('DROP TABLE '+table)
            connection.executescript('''
                CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL);
                CREATE TABLE resumes (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, target_field TEXT NOT NULL DEFAULT '', feedback_request TEXT NOT NULL DEFAULT '');
                CREATE TABLE comments (id INTEGER PRIMARY KEY, resume_id INTEGER NOT NULL REFERENCES resumes(id), author_id INTEGER NOT NULL REFERENCES users(id),
                    content TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE comment_ratings (id INTEGER PRIMARY KEY, comment_id INTEGER NOT NULL REFERENCES comments(id), rater_id INTEGER NOT NULL REFERENCES users(id), helpful INTEGER NOT NULL, UNIQUE(comment_id,rater_id));
                INSERT INTO users VALUES (1,'one@example.com','hash-one'),(2,'two@example.com','hash-two');
                INSERT INTO resumes (id,user_id,content,target_field) VALUES (1,1,'<b>Literal old text</b>','SWE');
                INSERT INTO comments (id,resume_id,author_id,content) VALUES (1,1,2,'Old feedback');
                INSERT INTO comment_ratings VALUES (1,1,1,1);
                PRAGMA user_version = 2;
            ''')
            connection.commit()
        backup = Path(self.temp.name) / 'v2-backup.sqlite'
        with self.app.app_context():
            self.assertTrue(upgrade_db(backup))
            self.assertTrue(database.is_ready())
            self.assertEqual(database.get_user_by_id(1)['display_name'], 'Reviewer')
            self.assertEqual(database.get_user_by_id(1)['review_fields'], [])
            self.assertEqual(database.get_resume_by_id(1)['content_format'], 'plain')
            self.assertEqual(database.get_resume_by_id(1)['content'], '<b>Literal old text</b>')
            self.assertEqual(len(database.list_resumes(target_field='Software engineering')), 1)
            comment = database.get_comment_by_id(1)
            self.assertIsNone(comment['revision_id'])
            self.assertIsNone(comment['parent_id'])
            self.assertEqual(database.get_reputation(2)['total'], 1)
            self.assertFalse(upgrade_db(Path(self.temp.name) / 'unused.sqlite'))
            self.assertEqual(sqlite_storage.get_db().scalar(select(func.count()).select_from(ResumeRevision)), 1)
