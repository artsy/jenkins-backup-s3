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

`python backup.py {OPTIONS} {SUBCOMMAND} {SUBCOMMAND_OPTIONS}`

The only required option is your S3 bucket: `--bucket={BUCKET_NAME}`

Available subcommands:
  - `create`
  - `restore`
  - `list`
  - `delete`
  - `prune`

See `python backup.py --help`

## Running a daily backup on Jenkins

Create a new item in Jenkins and configure a build of this repository.

Set the Shell builder to run `python backup.py --bucket={BUCKET_NAME} create`.

Set the build on a daily CRON schedule.

That's it!
