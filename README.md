# jenkins-backup-s3

A collection of scripts to backup Jenkins configuration to S3, as well as manage and restore those backups

## Setup

### Python

- Install Python 2.7.x

- Optionally: Install [virtualenv](http://docs.python-guide.org/en/latest/dev/virtualenvs/)

### Install requirements

- `pip install -r requirements.txt`

### Configure S3 and IAM

- Create an S3 bucket to store backups.

- Create an IAM user.  The IAM user must have the `GetObject`, `CreateObject`, `DeleteObject` and `ListBucket` S3 permissions for that bucket.

- [Configure boto](http://boto.cloudhackers.com/en/latest/boto_config_tut.html) with these IAM credentials.

```
export AWS_ACCESS_KEY_ID=foo
export AWS_SECRET_ACCESS_KEY=bar
```

## Usage

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
