# jenkins-backup-s3

A collection of scripts to backup Jenkins configuration to S3, as well as manage and restore those backups

## Setup

### Python (and optionally, virtualenvs)

- Install Python 2.7.x

- http://docs.python-guide.org/en/latest/dev/virtualenvs/

### Install requirements

`pip install -r requirements.txt`

### Configure AWS

Create an S3 bucket to store backups.

Create an IAM user.  The IAM user must have the S3:GetObject, CreateObject, DeleteObject and ListBucket permissions for that bucket.

Configure boto with these IAM credentials.  See: http://boto.cloudhackers.com/en/latest/boto_config_tut.html

## Usage

`python backup.py {OPTIONS} {COMMAND} {COMMAND_OPTIONS}`

Options can be set via either a switch or environment variable.

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

Set the Shell builder to run `python backup.py --bucket={BUCKET_NAME} create`.

Set the build on a daily CRON schedule.
