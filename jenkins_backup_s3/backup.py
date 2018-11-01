#!/usr/bin/python3

import os
import sys
import datetime
import boto3
import click
import logging
from boto3.exceptions import S3UploadFailedError
from subprocess import call
from colorama import init
from termcolor import colored

init()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

DEFAULT_REGION='us-east-1'

ch = logging.StreamHandler()


class S3Backups(object):
    KEY_SUFFIX = '__jenkins-backup.tar.gz'

    def __init__(self, bucket, prefix, region):
        self.s3 = boto3.resource('s3')
        self.__bucket = bucket
        self.__bucket_prefix = prefix
        self.__bucket_region = region
        logger.debug(colored('Instantiated S3Backups class', 'white'))

    def __list_backups(self):
        logger.debug(colored("Fetching S3 objects from %s..." % self.__bucket, 'white'))

        objects = []
        bucket = self.s3.Bucket(self.__bucket)
        for obj in bucket.objects.all():
            objects.append(obj.key)
        logger.info(colored("Successfully fetched objects from %s" % self.__bucket, 'green'))
        return sorted(objects, reverse=True)

    def backups(self):
        backups = []
        for key in self.__list_backups():
            if self.KEY_SUFFIX not in key:
                continue
            backups.append(key.replace("%s/" % self.__bucket_prefix, '').replace(self.KEY_SUFFIX, ''))
        return backups

    def backup(self, file_path, backup_name):
        key = "%s/%s%s" % (self.__bucket_prefix, backup_name, self.KEY_SUFFIX)
        logger.debug(colored('Attempting to upload object to S3', 'white'))
        try:
            s3_object = self.s3.Object(self.__bucket, key).upload_file(file_path, Callback=logger.info(colored('File uploaded to S3 successfully', 'blue')))
        except S3UploadFailedError as e:
            logger.critical(colored("Error uploading file to S3: %s" % e, 'red'))

    def delete(self, backup_name):
        key = "%s/%s%s" % (self.__bucket_prefix, backup_name, self.KEY_SUFFIX)
        logger.debug(colored('Attempting delete S3 object', 'white'))
        s3_object = self.s3.Object(self.__bucket, key).delete()

    def latest(self):
        backups = self.backups()
        if len(backups):
            return self.backups()[0]
        return None

    def restore(self, backup_name, target):
        key = "%s/%s%s" % (self.__bucket_prefix, backup_name, self.KEY_SUFFIX)

        logger.debug(colored('Attempting to fetch file from s3: %s' % key, 'white'))

        s3_object = self.s3.Object(self.__bucket, key).download_file(target)

        return target


@click.group()
@click.pass_context
@click.option('--bucket', required=True, type=click.STRING, help='S3 bucket to store backups in')
@click.option('--bucket-prefix', type=click.STRING, default='jenkins-backups', help='S3 bucket prefix : defaults to "jenkins-backups"')
@click.option('--bucket-region', type=click.STRING, default=DEFAULT_REGION, help='S3 bucket region : defaults to "%s"' % DEFAULT_REGION)
@click.option('--log-level', type=click.STRING, default='INFO', help='Display colorful status messages')
def cli(ctx, bucket, bucket_prefix, bucket_region, log_level):
    """Manage Jenkins backups to S3"""
    ctx.obj['BUCKET'] = bucket
    ctx.obj['BUCKET_PREFIX'] = bucket_prefix
    ctx.obj['BUCKET_REGION'] = bucket_region

    ch.setLevel(log_level)
    formatter = logging.Formatter('[%(levelname)s]: %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)


@cli.command()
@click.pass_context
@click.option('--jenkins-home', type=click.STRING, default='/var/lib/jenkins', help='Jenkins home directory : defaults to "/var/lib/jenkins"')
@click.option('--tmp', type=click.STRING, default='/tmp/jenkins-backup.tar.gz', help='Jenkins archive name : defaults to "/tmp/jenkins-backup.tar.gz"')
@click.option('--tar', type=click.STRING, default='/bin/tar', help='tar executable : defaults to "/bin/tar"')
@click.option('--tar-opts', type=click.STRING, default='cvfz', help='tar options : defaults to "cvfz"')
@click.option('--exclude-jenkins-war/--include-jenkins-war', default=True, help='Exclude jenkins.war from the backup : defaults to true')
@click.option('--exclude-vcs/--include-vcs', default=True, help='Exclude VCS from the backup : defaults to true')
@click.option('--ignore-fail/--dont-ignore-fail', default=True, help='Tar should ignore failed reads : defaults to true')
@click.option('--exclude-archive/--include-archive', default=True, help='Exclude archive directory from the backup : defaults to true')
@click.option('--exclude-target/--include-target', default=True, help='Exclude target directory from the backup : defaults to true')
@click.option('--exclude-builds/--include-builds', default=True, help='Exclude job builds directories from the backup : defaults to true')
@click.option('--exclude-workspace/--include-workspace', default=True, help='Exclude job workspace directories from the backup : defaults to true')
@click.option('--exclude-maven/--include-maven', default=True, help='Exclude maven repository from the backup : defaults to true')
@click.option('--exclude-logs/--include-logs', default=True, help='Exclude logs from the backup : defaults to true')
@click.option('--exclude', '-e', type=click.STRING, multiple=True, help='Additional directories to exclude from the backup')
@click.option('--dry-run', type=click.BOOL, is_flag=True, help='Create tar archive as "tmp" but do not upload it to S3 : defaults to false')
def create(ctx, jenkins_home, tmp, tar, tar_opts, exclude_jenkins_war, exclude_vcs, ignore_fail, exclude_archive, exclude_target,
            exclude_builds, exclude_workspace, exclude_maven, exclude_logs, exclude, dry_run):
    """Create a backup"""
    logger.info(colored("Backing up %s to %s/%s" % (jenkins_home, ctx.obj['BUCKET'], ctx.obj['BUCKET_PREFIX']), 'blue'))

    command = [tar, tar_opts, tmp, '-C', jenkins_home]

    if exclude_jenkins_war:
        command.append('--exclude=jenkins.war')
    if exclude_vcs:
        command.append('--exclude-vcs')
    if ignore_fail:
        command.append('--ignore-failed-read')
    if exclude_archive:
        command.append('--exclude=archive')
    if exclude_target:
        command.append('--exclude=target')
    if exclude_builds:
        command.append('--exclude=jobs/*/builds/*')
    if exclude_workspace:
        command.append('--exclude=jobs/*/workspace/*')
    if exclude_maven:
        command.append('--exclude=.m2/repository')
    if exclude_logs:
        command.append('--exclude=*.log')
    for e in exclude:
        command.append("--exclude=%s" % e)

    command.append('.')

    logger.info(colored("Executing command \"%s\"" % ' '.join(command), 'blue'))

    retval = call(command)
    if retval >= 2:
        logger.critical(colored("Creating tar archive failed with error code %s." % retval, 'red'))

        os.remove(tmp)
        sys.exit(retval)

    logger.debug(colored("Successfully created tar archive", 'white'))

    s3 = S3Backups(ctx.obj['BUCKET'], ctx.obj['BUCKET_PREFIX'], ctx.obj['BUCKET_REGION'])
    backup_id = str(datetime.datetime.now()).replace(' ', '_')

    if dry_run:
        logger.info(colored("Would have created backup id %s from %s" % (backup_id, tmp), 'green'))
    else:
        s3.backup(tmp, backup_id)
        os.remove(tmp)

        logger.info(colored("Created backup id %s" % backup_id, 'green'))


@cli.command()
@click.pass_context
def list(ctx):
    """List available backups"""
    logger.info(colored("All backups for %s/%s..." % (ctx.obj['BUCKET'], ctx.obj['BUCKET_PREFIX']), 'blue'))
    logger.info(colored("------------------------", 'blue'))

    s3 = S3Backups(ctx.obj['BUCKET'], ctx.obj['BUCKET_PREFIX'], ctx.obj['BUCKET_REGION'])

    for backup in s3.backups():
        logger.info(colored(backup, 'blue'))


def _delete_command(backup_id, bucket, bucket_prefix, bucket_region, dry_run):
    logger.info(colored("Deleting backup %s in %s/%s..." % (backup_id, bucket, bucket_prefix), 'blue'))

    s3 = S3Backups(bucket, bucket_prefix, bucket_region)

    if dry_run:
        logger.info(colored("Would have deleted %s" % backup_id, 'blue'))
    else:
        s3.delete(backup_id)
        logger.info(colored("Deleted %s" % backup_id, 'green'))


@cli.command()
@click.pass_context
@click.argument('backup-id', required=True, type=click.STRING)
@click.option('--dry-run', type=click.BOOL, is_flag=True, help='List delete candidate, do not delete it')
def delete(ctx, backup_id, dry_run):
    """Delete a backup by {backup-id}"""
    _delete_command(backup_id, ctx.obj['BUCKET'], ctx.obj['BUCKET_PREFIX'], ctx.obj['BUCKET_REGION'], dry_run)


@cli.command()
@click.pass_context
@click.argument('keep', required=True, type=click.INT)
@click.option('--dry-run', type=click.BOOL, is_flag=True, help='List delete candidates, do not delete them')
def prune(ctx, keep, dry_run):
    """Delete any backups older than the latest {keep} number of backups"""
    logger.info(colored("Pruning backups in %s/%s..." % (ctx.obj['BUCKET'], ctx.obj['BUCKET_PREFIX']), 'blue'))

    s3 = S3Backups(ctx.obj['BUCKET'], ctx.obj['BUCKET_PREFIX'], ctx.obj['BUCKET_REGION'])
    for backup_id in s3.backups()[keep:]:
        _delete_command(backup_id, ctx.obj['BUCKET'], ctx.obj['BUCKET_PREFIX'], ctx.obj['BUCKET_REGION'], dry_run)


@cli.command()
@click.pass_context
@click.argument('backup-id', required=True, type=click.STRING)
@click.option('--jenkins-home', type=click.STRING, default='/var/lib/jenkins', help='Jenkins home directory : defaults to "/var/lib/jenkins"')
@click.option('--tmp', type=click.STRING, default='/tmp/jenkins-backup.tar.gz', help='Temporary tar archive file : defaults to "/tmp/jenkins-backup.tar.gz"')
@click.option('--tar', type=click.STRING, default='tar', help='tar executable : defaults to "tar"')
@click.option('--tar-opts', type=click.STRING, default='xzf', help='tar options : defaults to "xzf"')
@click.option('--dry-run', type=click.BOOL, is_flag=True, help='Download tar archive to "tmp" directory but do not decomress it to "jenkins-home"')
def restore(ctx, backup_id, jenkins_home, tmp, tar, tar_opts, dry_run):
    """Restore a backup by {backup-id} or 'latest'"""
    logger.info(colored("Attempting to restore backup by criteria '%s'..." % backup_id, 'blue'))
    s3 = S3Backups(ctx.obj['BUCKET'], ctx.obj['BUCKET_PREFIX'], ctx.obj['BUCKET_REGION'])
    if backup_id == 'latest':
        backup_id = s3.latest()
        if backup_id is None:
            logger.info(colored("No backups found.", 'blue'))
            return

    logger.info(colored("Restoring %s from %s/%s/%s..." % (jenkins_home, ctx.obj['BUCKET'], ctx.obj['BUCKET_PREFIX'], backup_id), 'blue'))

    s3.restore(backup_id, tmp)

    if dry_run:
        logger.info(colored("Would have restored %s from %s" % (jenkins_home, tmp), 'blue'))
    else:
        command = [tar, tar_opts, tmp, '-C', jenkins_home]

        logger.info(colored("Executing %s" % ' '.join(command), 'blue'))

        retval = call(command)
        if retval >= 2:
            logger.critical(colored("Restoring tar archive failed with error code %s." % retval, 'red'))
        os.remove(tmp)
        sys.exit(retval)


def main():
    cli(obj={})


if __name__ == '__main__':
    main()
