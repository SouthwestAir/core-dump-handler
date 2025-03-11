# Core Dump Handler

Core Dump Handler, inspired by the IBM Core Dump Handler.

## How it works

The Core Dump handler runs as a Daemonset in Kubernetes. This is required because one process on a server cannot easily watch the filesystem on another server. Every pod in the daemonset acts independently of the others. The application is unaware of any other pods in the cluster.

1. Core Dump Handler starts up by processing the path to the watch directory passed as an arguement. This will be the location where the core dumps are expected to land on disk.
1. Spawn a pool of worker processes.
1. Initialize `inotify` from the Operating System via [inotify_simple](https://inotify-simple.readthedocs.io/en/latest/#introduction) to listen for writes to complete in the watched directory.
1. Startup check file is written indicating to Kubernetes the program is fully up via Kubernetes `startupProbe`.
1. Once a core dump is written to disk with the name that start with `core` a worker in the pool is assigned to upload the file via the `s3_upload_wrapper()` function.
1. The worker then uploads the file to S3 and deletes the file from disk.
1. Because the upload task is async, the main loop continues watching `inotify` for more dumps to assign to more workers.
1. On an exception or shutdown of the program, the pool is closed which allows any running tasks in the worker pool to complete.
1. The startup check file with the word "dead" indicating to the Kubernetes `livenessProbe` the application is no longer running.

## Dump location in S3

Core dumps are located in the S3 Buckets you specify.

The naming pattern we follow for files is `core-%e-%t-%p-%s`.

- %e: Truncated 15char process name.
- %t: Unix time stamp in seconds since 1970.
- %p: PID of dumped process.
- $s: Number of signal causing dump.

For more information about core dump naming, see the [core dump man page](https://man7.org/linux/man-pages/man5/core.5.html).

## Setup

### Amazon Linux 2

Core dumps must be enabled and set to output with a file name beginning with `core`. This is accomplished with the following shell commands:

```bash
cat <<EOF > /etc/security/limits.d/69-core-dump.conf
*               soft    core            unlimited
*               hard    core            unlimited
root            soft    core            unlimited
root            hard    core            unlimited
EOF
cat <<EOF > /etc/sysctl.d/69-core-dump.conf
# Enable compressed Core Dumps
kernel.core_pattern=|/bin/sh -c $@ -- eval exec /usr/bin/pigz > /core_dumps/core-%e-%t-%p-%s.gz
EOF
sysctl --system
```

If you do not want compressed core dumps, set the `core_pattern` to `/core_dumps/core-%e-%t-%p-%s` instead.

For a more detailed description about how this works, see the "Core dumps on Linux without the Core Dump Handler" section of this document.

### AWS Bottlerocket

AWS Bottlerocket is a highly modified version of Amazon Linux designed to only run containers. As a result, there are a lot more quirks to work around.

The basic ingredients are as follows:

1. Create bootstrap container to create the directory on the host filesystem. An Alpine container to run the below script is plenty.

    ```shell
    #!/bin/sh
    set -e

    echo "Creating /core_dumps on Host"
    mkdir -p /.bottlerocket/rootfs/var/core_dumps || {
      echo "Failed to create directory"
      exit 1
    }

    chmod 777 /.bottlerocket/rootfs/var/core_dumps || {
      echo "Failed to set permissions"
      exit 1
    }

    echo "Successfully created and configured /core_dumps directory"
    ```

    - We use `/.bottlerocket/rootfs/var/core_dumps` because the Bottlerocket exposes the root filesystem under `/.bottlerocket/rootfs` to the bootstrap containers. Then because `/var` allows us to write a directory, we place out `core_dumps` directory here. You are able to adjust this to your liking, this was simply chosen due to simplicty through trial and error. Setting the directory to `777` allows anything to write there. Permissions can be tightened up as desired.

1. Add the bootstrap container and `core_pattern` setting to the Bottlerocket TOML. This avoids having to cook up your own AMI with these settings pre-applied.

    ```toml
    [settings.bootstrap-containers.core-dump-init]
    source = "path_to_bottlerocket_core_dump_init"
    mode = "always"
    [settings.kernel.sysctl]
    "kernel.core_pattern" = "/core_dumps/core-%e-%t-%p-%s"
    ```

1. For the container you want to collect dumps from;
    - It must be run as a privileged container in a privileged namespace.
    - Create the volume as type `Directory` with `hostpath` as `/var/core_dumps`.
    - Mount the volume to the container.
    - (See [example Kubernetes manifest](./example/kubernetes_manifest.yaml) for an example)
1. Deploy the Core Dump Handler as a daemonset to Kubernetes. The role used for the service account must have access to the S3 Bucket. See AWS section for instructions.
1. Test a dump

### AWS

1. Create an S3 Bucket.
1. Create an IAM role with `s3:PutObject`, `s3:GetObject`, and `GetObjectAttributes` allow action to your S3 Bucket for [IRSA](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html).
1. Update the [service account manifest](./example/kubernetes_manifest.yaml) to utilize the the new role.
1. Update the [daemonset manifest](./example/kubernetes_manifest.yaml) with the `BUCKET_NAME` variable.

### Kubernetes

1. Deploy the [manifests](./example/kubernetes_manifest.yaml).

### ECS

Coming soon.

## Trigger a Core Dump in Linux

1. From inside a container you have setup for dumps, run the following, then you should see the logs in the core dump handler showing the upload was successful:

    ```bash
    sleep 100 &
    kill -QUIT <pid of sleep>
    ```

    - If that doesn't work, use `kill -11 <pid>`.
1. Validate the dump arrived in the bucket.


## Change location of dump

Temporarily via CLI:

```bash
sysctl -w kernel.core_pattern=/core_dumps/core-%t-%p-%u
```

Your dumps will be located in the directory `/core_dumps`, begin with the string `core` followed by the, "[Time of dump, expressed as seconds since the Epoch, 1970-01-01 00:00:00 +0000 (UTC)](https://man7.org/linux/man-pages/man5/core.5.html)," PID of the dumped process, and UID of dumped process.

### Compress a Dump on Creation

Note: Not available on AWS Bottlerocket.

Core dumps may be extremely large as they contain what was in your program's memory. If your program was using 50gb of memory, the dump will likely be 50gb in size. By compressing the dumps, we can save a lot of file space. In the case of the Core Dump Handler, this will save S3 costs, uploads complete sooner, and the downloads done by the end user will be dramatically quicker. In testing, a 188mb C++ program core dump compresses down to 9.2mb.

`pigz` is used here because it is a multi-threaded version of `gzip`. This will compress faster.

```bash
cat <<EOF > /etc/sysctl.d/69-core-dump.conf
# Enable compressed Core Dumps
kernel.core_pattern=|/bin/sh -c $@ -- eval exec /usr/bin/pigz > /core_dumps/core-%e-%t-%p-%s.gz
EOF
sysctl --system
```

[The shell](https://stackoverflow.com/a/62026684/10195252) must be passed in the core dump pattern otherwise the dumps will not be written to disk.
