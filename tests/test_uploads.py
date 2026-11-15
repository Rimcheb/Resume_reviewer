from io import BytesIO
import re
import tempfile
import unittest
import zipfile
from pathlib import Path
from docx import Document
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
from backend.app import create_app
from backend import database, sqlite_storage


def docx_bytes():
    document = Document()
    document.add_paragraph('Alex Example')
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = 'Python'
    table.cell(0, 1).text = 'Calculator project'
    document.add_paragraph('Education')
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def pdf_bytes(text='Alex Example Python projects', pages=1, encrypted=False):
    writer = PdfWriter()
    for _ in range(pages):
        page = writer.add_blank_page(width=612, height=792)
        if text:
            font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
            page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
            stream = DecodedStreamObject()
            stream.set_data(('BT /F1 12 Tf 72 720 Td ('+text+') Tj ET').encode())
            page[NameObject('/Contents')] = writer._add_object(stream)
    if encrypted:
        writer.encrypt('secret-password')
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


class UploadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = create_app({'TESTING': True, 'SECRET_KEY': 'test',
            'DATABASE': str(Path(self.temp.name) / 'test.sqlite'), 'SESSION_COOKIE_SECURE': False})
        self.addCleanup(self.app.extensions['database_engine'].dispose)
        with self.app.app_context():
            sqlite_storage.init_db()
            self.owner = database.create_user('one@example.com', 'unused')
            self.other = database.create_user('two@example.com', 'unused')
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session['user_id'] = self.owner['id']

    def post(self, path='/resumes/import', data=None, filename='resume.docx', payload=None):
        page = self.client.get('/resumes/new').get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        values = {'csrf_token': token, 'target_field': 'Software', 'feedback_request': 'Review projects', 'resume': 'Existing draft'}
        values.update(data or {})
        if payload is not None:
            values['resume_file'] = (BytesIO(payload), filename)
        response = self.client.post(path, data=values)
        response.request.close()
        response.request.environ["wsgi.input"].close()
        return response

    def test_docx_tables_import_in_order_without_publishing(self):
        result = self.post(payload=docx_bytes())
        self.assertEqual(result.status_code, 200)
        page = result.get_data(as_text=True)
        self.assertLess(page.index('Alex Example'), page.index('Calculator project'))
        self.assertLess(page.index('Calculator project'), page.index('Education'))
        self.assertIn('Nothing has been saved yet', page)
        self.assertIn('Review projects', page)
        with self.app.app_context():
            self.assertEqual(database.list_resumes(), [])

    def test_pdf_import_then_reviewed_text_is_saved(self):
        result = self.post(filename='resume.PDF', payload=pdf_bytes())
        self.assertEqual(result.status_code, 200)
        self.assertIn('Alex Example Python projects', result.get_data(as_text=True))
        saved = self.post('/resumes', data={'resume': 'Corrected extracted text'})
        self.assertEqual(saved.status_code, 303)
        with self.app.app_context():
            record = database.list_resumes()[0]
            self.assertEqual(record['content'], 'Corrected extracted text')
            self.assertEqual(record['user_id'], self.owner['id'])

    def test_file_on_submit_also_requires_review(self):
        result = self.post('/resumes', payload=docx_bytes())
        self.assertEqual(result.status_code, 200)
        with self.app.app_context():
            self.assertEqual(database.list_resumes(), [])

    def test_unreadable_unsupported_encrypted_and_blank_files_preserve_draft(self):
        for name, payload in [('fake.pdf', b'%PDF-broken'), ('wrong.pdf', docx_bytes()),
             ('resume.txt', b'Plain text'), ('broken.docx', b'bad zip'),
             ('encrypted.pdf', pdf_bytes(encrypted=True)), ('scan.pdf', pdf_bytes(text='')),
             ('many.pdf', pdf_bytes(pages=11))]:
            with self.subTest(filename=name):
                result = self.post(filename=name, payload=payload)
                self.assertEqual(result.status_code, 400)
                self.assertIn('Existing draft', result.get_data(as_text=True))
                self.assertIn('Review projects', result.get_data(as_text=True))
        self.assertEqual(self.post().status_code, 400)

    def test_oversize_file_and_extracted_text_rejected(self):
        result = self.post(filename='large.pdf', payload=b'%PDF-'+b'x'*(2*1024*1024))
        self.assertEqual(result.status_code, 400)
        self.assertEqual(self.post(filename='large.pdf', payload=b'x'*(3*1024*1024)).status_code, 413)
        document = Document()
        document.add_paragraph('x'*20001)
        output = BytesIO()
        document.save(output)
        result = self.post(payload=output.getvalue())
        self.assertEqual(result.status_code, 400)
        self.assertIn('exceeds 20,000', result.get_data(as_text=True))

    def test_compressed_docx_expansion_is_bounded(self):
        output = BytesIO()
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('word/document.xml', b'x' * (10 * 1024 * 1024 + 1))
        self.assertLess(len(output.getvalue()), 2 * 1024 * 1024)
        self.assertEqual(self.post(payload=output.getvalue()).status_code, 400)

    def test_import_edit_requires_owner_and_does_not_update_until_save(self):
        with self.app.app_context():
            record = database.create_resume(self.owner['id'], 'Original text', 'Software', '')
        result = self.post(f'/resumes/{record["id"]}/import', payload=docx_bytes())
        self.assertEqual(result.status_code, 200)
        with self.app.app_context():
            self.assertEqual(database.get_resume_by_id(record['id'])['content'], 'Original text')
        with self.client.session_transaction() as session:
            session['user_id'] = self.other['id']
        self.assertEqual(self.post(f'/resumes/{record["id"]}/import', payload=docx_bytes()).status_code, 403)
        self.assertEqual(self.app.test_client().get('/resumes/new').status_code, 302)
        self.assertEqual(self.client.post('/resumes/import', data={'resume_file': (BytesIO(docx_bytes()), 'resume.docx')}).status_code, 400)
