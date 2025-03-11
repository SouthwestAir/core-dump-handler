#!/usr/bin/env python3

import logging
import os
import botocore
import boto3
from boto3.s3.transfer import TransferConfig


logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOGLEVEL", "INFO").upper())
formatter = logging.Formatter("%(levelname)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)
logger.propagate = False


def upload_file(file_name: str = "./", bucket: str = "my-bucket", object_name=None) -> bool:
    """Upload a file to an S3 bucket.

    Args:
        file_name (str, optional): File to upload. Defaults to "./".
        bucket (str, optional): Bucket to upload to. Defaults to "my-bucket".
        object_name (optional): S3 object name. If not specified then file_name is used. Defaults to None.

    Returns:
        bool: True if file was uploaded.
    """
    # If S3 object_name was not specified, use file_name
    if object_name is None:
        object_name = os.path.basename(file_name)
    # Set the desired multipart threshold value (1GB)
    config = TransferConfig(multipart_threshold=104857600, max_concurrency=20)
    # Perform the transfer
    try:
        logger.info(f"Uploading {file_name} to s3://{bucket}.")
        s3 = boto3.client("s3", region_name=os.environ.get("REGION"))
        s3.upload_file(file_name, bucket, object_name, ExtraArgs={"StorageClass": "STANDARD_IA"}, Config=config)
        logger.info(f"{object_name} upload done.")
        check_if_exists(bucket=bucket, object_name=object_name)
        os.remove(file_name)
        logger.info(f"Deleted {file_name} from the filesystem.")
    except Exception as e:
        logging.exception(e)
        raise
    else:
        return f"s3://{bucket}/{object_name}"


def check_if_exists(
    bucket: str = "somebucket", object_name: str = "test_file", delay: int = 5, max_attempts: int = 5
) -> bool:
    """Check if object exists in S3.

    Args:
        bucket (str, optional): Bucket name. Defaults to "somebucket".
        object_name (str, optional): Path to object in bucket. Defaults to "test_file".
        delay (int, optional): Seconds between checks. Defaults to 5.
        max_attempts (int, optional): Max checks. Defaults to 5.

    Returns:
        bool: True on success.
    """
    try:
        s3 = boto3.client("s3", region_name=os.environ.get("REGION"))
        waiter = s3.get_waiter("object_exists")
        waiter.wait(Bucket=bucket, Key=object_name, WaiterConfig={"Delay": delay, "MaxAttempts": max_attempts})
    except botocore.exceptions.WaiterError as waiter_exception:
        logger.exception(waiter_exception)
        # Follow on story to add alerting place-holder
        logger.error(f"Alert to hangar alerts goes here if {object_name} does not make it to S3.")
        raise
    except Exception as e:
        logging.exception(e)
        raise
    else:
        return True


if __name__ == "__main__":
    upload_file(file_name="/crash_dump/testfile.dump", bucket="baker-my-bucket")
