import sys
import os
import unittest
from unittest.mock import patch
from moto import mock_aws
import boto3
import botocore

from upload_file_2_s3 import upload_file, check_if_exists

os.environ["REGION"] = "us-east-1"


@mock_aws
class TestCoreUploadFile2S3(unittest.TestCase):
    def setUp(self):
        mock_s3_client = boto3.client("s3", region_name="us-east-1")
        mock_s3_client.create_bucket(Bucket="mybucket")
        mock_s3_client.create_bucket(Bucket="myotherbucket")
        os.mkdir("core_dumps", 0o777)
        with open("core-test.gz", "w", encoding="utf-8") as core_dump:
            core_dump.write("test\n")
        with open("core_dumps/core-test-2.gz", "w", encoding="utf-8") as core_dump:
            core_dump.write("test\n")
        with open("core_dumps/core-test-3.gz", "w", encoding="utf-8") as core_dump:
            core_dump.write("test\n")
        with open("core_dumps/core-test-4.gz", "w", encoding="utf-8") as core_dump:
            core_dump.write("test\n")
        mock_s3_client.put_object(Bucket="myotherbucket", Body=bytes("test", "utf-8"), Key="core-test-5.gz")

    def tearDown(self):
        for file in os.listdir("core_dumps"):
            if os.path.exists(f"core_dumps/{file}"):
                os.remove(f"core_dumps/{file}")
        os.rmdir("core_dumps")

    def test_upload_file(self):
        """Test upload_file().

        1. Test file no directory, no object name passed.
        2. Test file in a directory, no object name passed.
        3. Test file in a directory, object name passed.
        4. Test exception.
        5. Test upload failed.
        """
        self.maxDiff = None
        mock_s3_client = boto3.client("s3", region_name="us-east-1")
        # 1.
        with self.assertLogs(logger="upload_file_2_s3", level="INFO") as captured_logs:
            self.assertEqual(upload_file(file_name="core-test.gz", bucket="mybucket"), "s3://mybucket/core-test.gz")
            self.assertEqual(mock_s3_client.list_objects_v2(Bucket="mybucket")["Contents"][0]["Key"], "core-test.gz")
            self.assertEqual(
                mock_s3_client.list_objects_v2(Bucket="mybucket")["Contents"][0]["StorageClass"], "STANDARD_IA"
            )
            self.assertEqual(
                captured_logs.output,
                [
                    "INFO:upload_file_2_s3:Uploading core-test.gz to s3://mybucket.",
                    "INFO:upload_file_2_s3:core-test.gz upload done.",
                    "INFO:upload_file_2_s3:Deleted core-test.gz from the filesystem.",
                ],
            )
        mock_s3_client.delete_object(Bucket="mybucket", Key="core-test.gz")
        # 2.
        with self.assertLogs(logger="upload_file_2_s3", level="INFO") as captured_logs:
            self.assertEqual(
                upload_file(file_name="core_dumps/core-test-2.gz", bucket="mybucket"), "s3://mybucket/core-test-2.gz"
            )
            self.assertEqual(mock_s3_client.list_objects_v2(Bucket="mybucket")["Contents"][0]["Key"], "core-test-2.gz")
            self.assertEqual(
                mock_s3_client.list_objects_v2(Bucket="mybucket")["Contents"][0]["StorageClass"], "STANDARD_IA"
            )
            self.assertEqual(
                captured_logs.output,
                [
                    "INFO:upload_file_2_s3:Uploading core_dumps/core-test-2.gz to s3://mybucket.",
                    "INFO:upload_file_2_s3:core-test-2.gz upload done.",
                    "INFO:upload_file_2_s3:Deleted core_dumps/core-test-2.gz from the filesystem.",
                ],
            )
        mock_s3_client.delete_object(Bucket="mybucket", Key="core-test-2.gz")
        # 3.
        with self.assertLogs(logger="upload_file_2_s3", level="INFO") as captured_logs:
            self.assertEqual(
                upload_file(file_name="core_dumps/core-test-3.gz", bucket="mybucket", object_name="core-test-3.gz"),
                "s3://mybucket/core-test-3.gz",
            )
            self.assertEqual(mock_s3_client.list_objects_v2(Bucket="mybucket")["Contents"][0]["Key"], "core-test-3.gz")
            self.assertEqual(
                mock_s3_client.list_objects_v2(Bucket="mybucket")["Contents"][0]["StorageClass"], "STANDARD_IA"
            )
            self.assertEqual(
                captured_logs.output,
                [
                    "INFO:upload_file_2_s3:Uploading core_dumps/core-test-3.gz to s3://mybucket.",
                    "INFO:upload_file_2_s3:core-test-3.gz upload done.",
                    "INFO:upload_file_2_s3:Deleted core_dumps/core-test-3.gz from the filesystem.",
                ],
            )
        mock_s3_client.delete_object(Bucket="mybucket", Key="core-test-3.gz")
        # 4.
        with self.assertRaises((Exception, SystemExit)) as cm, self.assertLogs(level="ERROR"):
            upload_file(file_name="core_dumps/core-test-4.gz", bucket="wrongbucket")
        self.assertEqual(
            str(cm.exception),
            "Failed to upload core_dumps/core-test-4.gz to wrongbucket/core-test-4.gz: An error occurred (NoSuchBucket) when calling the PutObject operation: The specified bucket does not exist",
        )
        mock_s3_client.delete_object(Bucket="mybucket", Key="core-test-4.gz")

    def test_check_if_exists(self):
        """Test check_if_exists().

        0. Setup.
        1. Object exists.
        2. Object does not exist.
        """
        # 0.
        mock_s3_client = boto3.client("s3", region_name="us-east-1")
        # 1.
        self.assertTrue(check_if_exists(bucket="myotherbucket", object_name="core-test-5.gz"))
        # 2.
        with self.assertRaises((botocore.exceptions.WaiterError, SystemExit)) as cm, self.assertLogs(level="ERROR"):
            check_if_exists(bucket="wrongbucket", object_name="core-test-5.gz", delay=1, max_attempts=1)
            self.assertEqual(
                str(cm.exception),
                "Failed to upload core_dumps/core-test-4.gz to wrongbucket/core-test-4.gz: An error occurred (NoSuchBucket) when calling the PutObject operation: The specified bucket does not exist",
            )
