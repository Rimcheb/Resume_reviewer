from io import BytesIO
import json
import subprocess
import unittest
from unittest.mock import Mock, patch
from werkzeug.datastructures import FileStorage
from backend.uploads import extract_upload, UploadError


class UploadIsolationTests(unittest.TestCase):
    def upload(self):
        return FileStorage(stream=BytesIO(b'%PDF-example'), filename='private-name.pdf')

    def test_timeout_kills_and_reaps_worker_then_releases_capacity(self):
        process = Mock()
        process.communicate.side_effect = [subprocess.TimeoutExpired('worker', 10), (b'', b'')]
        with patch('backend.uploads.subprocess.Popen', return_value=process):
            with self.assertRaisesRegex(UploadError, 'too long'):
                extract_upload(self.upload())
        process.kill.assert_called_once()
        self.assertEqual(process.communicate.call_count, 2)
        success = Mock(returncode=0)
        success.communicate.return_value = (b'"Text"', None)
        with patch('backend.uploads.subprocess.Popen', return_value=success):
            self.assertEqual(extract_upload(self.upload()), 'Text')

    def test_worker_has_no_app_credentials_or_original_filename(self):
        process = Mock(returncode=0)
        process.communicate.return_value = (json.dumps('Safe text').encode(), None)
        with patch('backend.uploads.subprocess.Popen', return_value=process) as launch:
            self.assertEqual(extract_upload(self.upload()), 'Safe text')
        args, options = launch.call_args
        self.assertEqual(args[0][-1], '.pdf')
        self.assertNotIn('private-name.pdf', args[0])
        self.assertEqual(set(options['env']), {'PYTHONIOENCODING', 'LANG'})
        self.assertEqual(process.communicate.call_args.kwargs['timeout'], 10)

    def test_worker_crash_bad_output_and_unavailable_worker_are_recoverable(self):
        for code, output in [(1, b''), (0, b'not json'), (0, b'{}'), (0, b'x'*160001)]:
            process = Mock(returncode=code)
            process.communicate.return_value = (output, None)
            with patch('backend.uploads.subprocess.Popen', return_value=process):
                self.assertIsNone(extract_upload(self.upload()))
        with patch('backend.uploads.subprocess.Popen', side_effect=OSError('no process')):
            with self.assertRaises(UploadError) as raised:
                extract_upload(self.upload())
            self.assertEqual(raised.exception.status, 503)

    def test_busy_worker_pool_rejects_without_spawning(self):
        with patch('backend.uploads._PARSER_SLOTS') as slots, patch('backend.uploads.subprocess.Popen') as launch:
            slots.acquire.return_value = False
            with self.assertRaises(UploadError) as raised:
                extract_upload(self.upload())
            self.assertEqual(raised.exception.status, 503)
            launch.assert_not_called()
            slots.release.assert_not_called()

    def test_platform_limits_apply_cpu_and_linux_memory_cap(self):
        import resource
        from backend.upload_parser import apply_limits
        for platform in ('linux', 'darwin'):
            with patch('backend.upload_parser.sys.platform', platform), patch('resource.getrlimit', return_value=(resource.RLIM_INFINITY, resource.RLIM_INFINITY)), patch('resource.setrlimit') as setter:
                apply_limits()
                setter.assert_any_call(resource.RLIMIT_CPU, (5, 5))
                if platform == 'linux':
                    setter.assert_any_call(resource.RLIMIT_AS, (512*1024*1024, 512*1024*1024))
                else:
                    self.assertEqual(setter.call_count, 1)
