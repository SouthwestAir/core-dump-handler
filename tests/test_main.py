import sys
import os
import unittest
from unittest.mock import patch

from main import i_am_started, i_am_dead, s3_upload_wrapper, my_callback


class TestCoreUploadFile2S3(unittest.TestCase):
    def setUp(self):
        os.environ["BUCKET_NAME"] = "bucket_name_from_env"
        os.mkdir("main_test_files", 0o777)
        with open("main_test_files/upload.test", "w", encoding="utf-8") as core_dump:
            core_dump.write("test\n")

    def tearDown(self):
        os.unsetenv("BUCKET_NAME")
        for file in os.listdir("main_test_files"):
            if os.path.exists(f"main_test_files/{file}"):
                os.remove(f"main_test_files/{file}")
        os.rmdir("main_test_files")

    def test_i_am_started(self):
        """Test i_am_started().

        1. Test writing the file.
        2. Test exception.
        """
        # 1.
        self.assertTrue(i_am_started(file_name="main_test_files/i_am_started_test_1"))
        with open("main_test_files/i_am_started_test_1", "r", encoding="utf-8") as test_file:
            self.assertEqual(test_file.read(), "started\n")
        # 2.
        with self.assertRaises((Exception, SystemExit)) as cm, self.assertLogs(level="ERROR"):
            with patch(
                "os.open",
                autospec=True,
                side_effect=Exception("These are not the droids you are looking for."),
            ) as mock_upload_file:
                i_am_started(file_name="main_test_files/i_am_started_test_2")

    def test_i_am_dead(self):
        """Test i_am_dead().

        1. Test writing the file.
        2. Test exception.
        """
        # 1.
        self.assertTrue(i_am_dead(file_name="main_test_files/i_am_dead_test_1"))
        with open("main_test_files/i_am_dead_test_1", "r", encoding="utf-8") as test_file:
            self.assertEqual(test_file.read(), "dead\n")
        # 2.
        with self.assertRaises((Exception, SystemExit)) as cm, self.assertLogs(level="ERROR"):
            with patch(
                "os.open",
                autospec=True,
                side_effect=Exception("These are not the droids you are looking for."),
            ) as mock_upload_file:
                i_am_dead(file_name="main_test_files/i_am_dead_test_2")

    def test_s3_upload_wrapper(self):
        """Test s3_upload_wrapper().

        1. Test expected outcome.
        2. Test with OS environment variable for bucket name.
        3. Test Exception.
        """
        # 1.
        with self.assertLogs(logger="main", level="DEBUG") as captured_logs:
            with patch(
                "upload_file_2_s3.upload_file", autospec=True, return_value="s3://testbucket/upload.test"
            ) as mock_upload_file:
                self.assertEqual(
                    s3_upload_wrapper(
                        file_name="upload.test", path_to_directory="main_test_files", bucket_name="testbucket"
                    ),
                    "s3://testbucket/upload.test",
                )
            self.assertEqual(
                captured_logs.output,
                [
                    "DEBUG:main:Sending main_test_files/upload.test to S3 bucket testbucket.",
                ],
            )
        # 2.
        with self.assertLogs(logger="main", level="DEBUG") as captured_logs:
            with patch(
                "upload_file_2_s3.upload_file", autospec=True, return_value="s3://bucket_name_from_env/upload.test"
            ) as mock_upload_file:
                self.assertEqual(
                    s3_upload_wrapper(
                        file_name="upload.test",
                        path_to_directory="main_test_files",
                        bucket_name=os.environ.get("BUCKET_NAME"),
                    ),
                    "s3://bucket_name_from_env/upload.test",
                )
            self.assertEqual(
                captured_logs.output,
                [
                    "DEBUG:main:Sending main_test_files/upload.test to S3 bucket bucket_name_from_env.",
                ],
            )
        # 3.
        with self.assertRaises((Exception, SystemExit)) as cm, self.assertLogs(level="ERROR"):
            with patch(
                "upload_file_2_s3.upload_file",
                autospec=True,
                side_effect=Exception("These are not the droids you are looking for."),
            ) as mock_upload_file:
                s3_upload_wrapper(
                    file_name="upload.test", path_to_directory="main_test_files", bucket_name="testbucket"
                )

    def test_my_callback(self):
        """Test my_callback().

        1. Test logger.
        2. Test exception.
        """
        # 1.
        with self.assertLogs(logger="main", level="INFO") as captured_logs:
            self.assertTrue(my_callback(value="These are the memes of production."))
            self.assertEqual(
                captured_logs.output,
                ["INFO:main:These are the memes of production."],
            )
        # 2.
        with self.assertRaises((Exception, SystemExit)) as cm, self.assertLogs(level="ERROR"):
            my_callback(value=False)
