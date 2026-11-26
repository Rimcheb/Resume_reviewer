import tempfile
import unittest
from pathlib import Path
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from backend.app import create_app
from backend import database

class StorageTests(unittest.TestCase):
    def test_explicit_initialization_preserves_existing_rows_and_constraints(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'db.sqlite'
            app=create_app({'TESTING':True,'SECRET_KEY':'test-only','DATABASE':str(path)})
            try:
                self.assertFalse(path.exists())
                runner=app.test_cli_runner()
                self.assertEqual(runner.invoke(args=['init-db']).exit_code,0)
                with app.app_context():
                    user=database.create_user('test@example.com','hashed-value')
                    self.assertIsNone(database.create_user('test@example.com','another'))
                    self.assertEqual(database.get_user_by_id(user['id'])['email'],'test@example.com')
                result=runner.invoke(args=['init-db'])
                self.assertNotEqual(result.exit_code,0)
                self.assertIn('Nothing was changed',result.output)
                with app.extensions['database_engine'].begin() as connection:
                    self.assertEqual(
                        set(inspect(connection).get_table_names()),
                        {'users', 'resumes', 'comments', 'comment_ratings'},
                    )
                    self.assertEqual(connection.exec_driver_sql('SELECT count(*) FROM users').scalar(),1)
                    self.assertEqual(connection.exec_driver_sql('PRAGMA foreign_keys').scalar(),1)
                with self.assertRaises(IntegrityError):
                    with app.extensions['database_engine'].begin() as connection:
                        connection.exec_driver_sql("INSERT INTO resumes(user_id,content) VALUES (999,'Invalid owner')")
            finally:
                app.extensions['database_engine'].dispose()
