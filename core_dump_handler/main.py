#!/usr/bin/env python3
"""
Core Dump Handler
"""

import logging
import os
import multiprocessing
import sys
from inotify_simple import INotify, flags
import upload_file_2_s3


logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOGLEVEL", "INFO").upper())
formatter = logging.Formatter("%(levelname)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)


def i_am_started(file_name: str = "/core_dump_handler/startupcheck") -> bool:
    """Write a file stating the app has started for K8s start up probe.

    Args:
        file_name (str, optional): Where to write the file. Defaults to "/core_dump_handler/startupcheck".

    Returns:
        bool: True when completed.
    """
    with open(file_name, "w", encoding="utf-8") as startupcheck:
        startupcheck.write("started\n")
    return True


def i_am_dead(file_name: str = "/core_dump_handler/startupcheck") -> bool:
    """Overwrite the liveness probe file with "dead".

    Intended to be called in the main functions (watch_directory()) "finally" clause to indicate to K8s the program
    is fully stopped or crashed.

    Args:
        file_name (str, optional): _description_. Defaults to "/core_dump_handler/startupcheck".

    Returns:
        bool: True when completed.
    """
    with open(file_name, "w", encoding="utf-8") as startupcheck:
        startupcheck.write("dead\n")
    return True


def spawn_multiprocessing_pool(processes: int = 4, maxtasksperchild: int = 1) -> object:
    """Spawn multiprocessing pool.

    This is a pool of python processes waiting to be tasked with work. In this program, the workers get tasked with
    uploading core dumps to S3.

    Args:
        processes (int, optional): max number of processes. Defaults to 4 to limit the resources taken by the
        core dump handler.
        maxtasksperchild (int, optional): Maximum amount of times a worker can be distributed work.
        Defaults to 1 to release resources back to the operating system when not in use.

    Returns:
        object: Multiprocessing pool object.
    """
    pool = multiprocessing.Pool(processes=processes, maxtasksperchild=maxtasksperchild)  # pylint: disable=R1732
    logger.debug("pool is type %s", type(pool))
    return pool


def watch_directory(path_to_directory: str = "./"):
    """Watch a directory and upload files that start with `core` to S3.

    How it works:
    1. Spawns a pool of workers.
    2. Initializes `inotify` from the Operating System to listen for writes to complete in the watched directory.
    3. Startup check file is written indicating to Kubernetes the program is fully up.
    4. Once a core dump is written to disk with the name that start with `core`, a worker in the pool
    is assigned to upload the file via the `s3_upload_wrapper()` function.
    5. The worker then uploads the file to S3 and deletes the file from disk.
    6. Because the upload task is async, the main loop continues watching `inotify` for more dumps to assign to
    more workers.
    7. On an exception or shutdown of the program, the pool is closed which allows any running tasks in the
    worker pool to complete.
    8. The program updates the startup check file with the word "dead" indicating to the Kubernetes Liveness check
    the application is no longer running.

    Args:
        path_to_directory (str, optional): Directory to watch. Defaults to "./". Recommended to use the
        full directory path
    """
    try:
        pool = spawn_multiprocessing_pool()
    except Exception as e:
        logger.exception(e)
        raise
    try:  # pylint: disable=R1702
        # Initialize inotify
        inotify = INotify()
        watch_flags = flags.CLOSE_WRITE
        # Add watched directory
        inotify.add_watch(path_to_directory, watch_flags)
        i_am_started()
        while True:
            for event in inotify.read():
                for flag in flags.from_mask(event.mask):
                    # Only work if the inotify signal is CLOSE_WRITE.
                    # This ensures we do not try reading a file that is not finished writing to disk.
                    # https://inotify-simple.readthedocs.io/en/latest/#inotify_simple.flags
                    if str(flag) == "8":
                        file_name = str(event[3])
                        if file_name.startswith("core"):
                            logger.info("Sending %s to S3.", file_name)
                            pool.apply_async(
                                func=s3_upload_wrapper, args=[file_name, path_to_directory], callback=my_callback
                            )
    except Exception as e:
        logger.exception(e)
        raise
    finally:
        pool.close()
        pool.join()
        i_am_dead()


def s3_upload_wrapper(file_name: str, path_to_directory: str, bucket_name: str = os.environ.get("BUCKET_NAME")) -> str:
    """Wrapper for S3 upload function. Compiles the required information to send to S3 upload function.

    Args:
        file_name (str): File name.
        path_to_directory (str): Directory path to file on disk.
        bucket_name (str, optional): S3 Bucket name. Defaults to os.environ.get("BUCKET_NAME").

    Returns:
        str: Path to file in S3.
    """
    file_name_with_path = f"{path_to_directory}/{file_name}"
    logger.debug("Sending %s to S3 bucket %s.", file_name_with_path, bucket_name)
    s3_object = upload_file_2_s3.upload_file(file_name=file_name_with_path, bucket=bucket_name)
    return s3_object


def my_callback(value: str) -> bool:
    """Return callback value from async pool worker upon S3 upload completion.

    Args:
        value (str): Input string.

    Returns:
        bool: True upon completion.
    """
    logger.info(value)
    return True


if __name__ == "__main__":
    # Start up the Core Dump Handler. Uses 1st argument as the directory path.
    logger.debug("main.py starting!")
    dir_path = sys.argv[1]
    logger.debug("ヽ(｀Д´)⊃━☆ﾟ. * ･ ｡ﾟ,")
    logger.info("Watching `%s` for core dumps.", dir_path)
    logger.info("(⌐⊙_⊙)")
    watch_directory(path_to_directory=dir_path)
