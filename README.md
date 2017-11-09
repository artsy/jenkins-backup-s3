# jenkins-backup-s3

A collection of scripts to backup Jenkins configuration to S3, as well as manage and restore those backups. By default
runs silently (no output) with proper exit codes. Log Level option enables output.

## Setup

### Python

- Install Python 3.6.x+

- Optionally: Install [virtualenv](http://docs.python-guide.org/en/latest/dev/virtualenvs/)

### Install requirements

- `pip install -r requirements.txt`

### Configure S3 and IAM

- Create an S3 bucket to store backups.

- Create an IAM role with STS:AssumeRole and a trust Service ec2.amazonaws.com.  The IAM role must have the `GetObject`, `CreateObject`, `DeleteObject` and `ListBucket` S3 permissions for that bucket.

## Usage

Setup with cron for ideal usage.

`python backup.py {OPTIONS} {COMMAND} {COMMAND_OPTIONS}`

Options can be set directly or via and environment variable.

The only required option is your S3 bucket:
  - `python backup.py --bucket={BUCKET_NAME}`
  - `JENKINS_BACKUP_BUCKET={BUCKET_NAME} python backup.py`

Other available options are:

Bucket prefix (defaults to "jenkins-backups"):
  - `python backup.py --bucket-prefix={BUCKET_PREFIX}`
  - `JENKINS_BACKUP_BUCKET_PREFIX={BUCKET_PREFIX} python backup.py`

Bucket region (defaults to "us-east-1"):
  - `python backup.py --bucket-region={BUCKET_REGION}`
  - `JENKINS_BACKUP_BUCKET_REGION={BUCKET_REGION} python backup.py`

Available commands:
  - `create`
  - `restore`
  - `list`
  - `delete`
  - `prune`

Run `python backup.py {COMMAND} --help` for command-specific options.

## Running a daily backup on Jenkins

Create a new item in Jenkins and configure a build of this repository.

Set the shell / virtualenv builder (if you have it installed) to run `python backup.py create`.

Set the build on a daily CRON schedule.
