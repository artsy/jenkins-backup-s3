import os
import sys
import datetime

from subprocess import call

import click

import boto
from boto.s3.key import Key

class S3Backups(object):
  KEY_SUFFIX = '__jenkins-backup.tar.gz'

  def __init__(self, bucket, prefix, region):
    self.conn = boto.s3.connect_to_region(region)
    self.bucket = bucket

    b = self.conn.lookup(self.bucket)

    self.__b = self.conn.get_bucket(self.bucket)
    self.__bucket_prefix = prefix

  def __list_backups(self):
    return sorted(map(lambda x: x.key, self.__b.list(prefix=self.__bucket_prefix)), reverse=True)

  def backups(self):
    backups = []
    for k in self.__list_backups():
      if self.KEY_SUFFIX not in k:
        continue
      backups.append(k.replace("%s/" % self.__bucket_prefix, '').replace(self.KEY_SUFFIX, ''))
    return backups

  def latest(self):
    backups = self.backups()
    if len(backups):
      return self.backups()[0]
    return None

  def backup(self, file_path, backup_name):
    k = Key(self.__b)
    k.key = os.path.join(self.__bucket_prefix, backup_name + self.KEY_SUFFIX)
    k.set_contents_from_filename(file_path)
    return os.path.join(self.__bucket_prefix, backup_name)

  def restore(self, backup_name, target):
    k = Key(self.__b)
    k.key = os.path.join(self.__bucket_prefix, backup_name + self.KEY_SUFFIX)
    k.get_contents_to_filename(target)
    return target

  def delete(self, backup_name):
    self.__b.delete_key(os.path.join(self.__bucket_prefix, backup_name + self.KEY_SUFFIX))
    return os.path.join(self.__bucket_prefix, backup_name)

@click.group()
@click.pass_context
@click.option('--bucket', required=True, type=click.STRING, envvar='JENKINS_BACKUP_BUCKET', help='S3 bucket to store backups')
@click.option('--bucket-prefix', type=click.STRING, default='jenkins-backups', envvar='JENKINS_BACKUP_BUCKET_PREFIX', help='S3 bucket prefix : defaults to "jenkins-backups"')
@click.option('--bucket-region', type=click.STRING, default='us-east-1', envvar='JENKINS_BACKUP_BUCKET_REGION', help='S3 bucket region : defaults to "us-east-1')
def cli(ctx, bucket, bucket_prefix, bucket_region):
    """Manage Jenkins backups to S3"""
    ctx.obj['BUCKET'] = bucket
    ctx.obj['BUCKET_PREFIX'] = bucket_prefix
    ctx.obj['BUCKET_REGION'] = bucket_region

@cli.command()
@click.pass_context
@click.option('--jenkins-home', type=click.STRING, default='/var/lib/jenkins', help='Jenkins home directory : defaults to "/var/lib/jenkins"')
@click.option('--tmp', type=click.STRING, default='/tmp/jenkins-backup.tar.gz', help='Temporary tar archive file : defaults to "/tmp/jenkins-backup.tar.gz"')
@click.option('--tar', type=click.STRING, default='/bin/tar', help='tar executable : defaults to "/bin/tar"')
@click.option('--tar-opts', type=click.STRING, default='cvfz', help='tar options : defaults to "cvfz"')
@click.option('--exclude-vcs/--include-vcs', default=True, help='Exclude VCS from the backup : defaults to true')
@click.option('--ignore-fail/--dont-ignore-fail', default=True, help='Tar should ignore failed reads : defaults to true')
@click.option('--exclude-archive/--include-archive', default=True, help='Exclude archive directory from the backup : defaults to true')
@click.option('--exclude-target/--include-target', default=True, help='Exclude target directory from the backup : defaults to true')
@click.option('--exclude-builds/--include-builds', default=True, help='Exclude job builds directories from the backup : defaults to true')
@click.option('--exclude-workspace/--include-workspace', default=True, help='Exclude job workspace directories from the backup : defaults to true')
@click.option('--exclude-maven/--include-maven', default=True, help='Exclude maven repository from the backup : defaults to true')
@click.option('--exclude-logs/--include-logs', default=True, help='Exclude logs from the backup : defaults to true')
@click.option('--exclude', '-e', type=click.STRING, multiple=True, help='Additional direcoties to exclude from the backup')
@click.option('--dry-run', type=click.BOOL, is_flag=True, help='Create tar archive as "tmp" but to do not upload to S3  : defaults to false')
def create(ctx, jenkins_home, tmp, tar, tar_opts, exclude_vcs, ignore_fail, exclude_archive, exclude_target,
            exclude_builds, exclude_workspace, exclude_maven, exclude_logs, exclude, dry_run):
  """Create a backup"""
  print("Backing up %s to %s/%s..." % (jenkins_home, ctx.obj['BUCKET'], ctx.obj['BUCKET_PREFIX']))

  command = [tar, tar_opts, tmp, '-C', jenkins_home]

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

  print("Executing %s" % ' '.join(command))
  retval = call(command)
  if retval >= 2:
    print("Creating tar archive failed with error code %s." % retval)
    os.remove(tmp)
    sys.exit(retval)

  s3 = S3Backups(ctx.obj['BUCKET'], ctx.obj['BUCKET_PREFIX'], ctx.obj['BUCKET_REGION'])
  backup_id = str(datetime.datetime.now()).replace(' ', '_')

  if dry_run:
    print("Would have created backup id %s from %s" % (backup_id, tmp))
  else:
    s3.backup(tmp, backup_id)
    os.remove(tmp)
    print("Created backup id %s" % backup_id)


@cli.command()
@click.pass_context
def list(ctx):
  """List available backups"""
  print("All backups for %s/%s..." % (ctx.obj['BUCKET'], ctx.obj['BUCKET_PREFIX']))

  print("---------------------------")
  print('\n')

  s3 = S3Backups(ctx.obj['BUCKET'], ctx.obj['BUCKET_PREFIX'], ctx.obj['BUCKET_REGION'])
  for backup in s3.backups():
    print backup

  print('\n')

@cli.command()
@click.pass_context
@click.argument('backup-id', required=True, type=click.STRING)
def delete(ctx, backup_id):
  """Delete a backup by {backup-id}"""
  print("Deleting backup %s in %s/%s..." % (backup_id, ctx.obj['BUCKET'], ctx.obj['BUCKET_PREFIX']))

  s3 = S3Backups(ctx.obj['BUCKET'], ctx.obj['BUCKET_PREFIX'], ctx.obj['BUCKET_REGION'])
  s3.delete(backup_id)
  print("Deleted %s" % backup_id)


@cli.command()
@click.pass_context
@click.argument('keep', required=True, type=click.INT)
@click.option('--dry-run', type=click.BOOL, is_flag=True, help='Print backups marked for deletion but do not delete them')
def prune(ctx, keep, dry_run):
  """Delete old up to {keep} number of backups"""
  print("Pruning backups in %s/%s..." % (ctx.obj['BUCKET'], ctx.obj['BUCKET_PREFIX']))
  s3 = S3Backups(ctx.obj['BUCKET'], ctx.obj['BUCKET_PREFIX'], ctx.obj['BUCKET_REGION'])
  for backup_id in s3.backups()[keep:]:
    if dry_run:
      print("Would have deleted %s" % backup_id)
    else:
      s3.delete(backup_id)
      print("Deleted %s" % backup_id)


@cli.command()
@click.pass_context
@click.argument('backup-id', required=True, type=click.STRING)
@click.option('--jenkins-home', type=click.STRING, default='/var/lib/jenkins', help='Jenkins home directory : defaults to "/var/lib/jenkins"')
@click.option('--tmp', type=click.STRING, default='/tmp/jenkins-backup.tar.gz', help='Temporary tar archive file : defaults to "/tmp/jenkins-backup.tar.gz"')
@click.option('--tar', type=click.STRING, default='/bin/tar', help='tar executable : defaults to "/bin/tar"')
@click.option('--tar-opts', type=click.STRING, default='xvzf', help='tar options : defaults to "xvzf"')
@click.option('--dry-run', type=click.BOOL, is_flag=True, help='Download tar archive to "tmp" directory but do not decomress it to "jenkins-home"')
def restore(ctx, jenkins_home, tmp, tar, backup_id, tar_opts, dry_run):
  """Restore a backup by {backup-id} or 'latest'"""
  s3 = S3Backups(ctx.obj['BUCKET'], ctx.obj['BUCKET_PREFIX'], ctx.obj['BUCKET_REGION'])
  if backup_id == 'latest':
    backup_id = s3.latest()
    if backup_id is None:
      print("No backups found.")
      return

  print("Restoring %s from %s/%s/%s..." % (jenkins_home, ctx.obj['BUCKET'], ctx.obj['BUCKET_PREFIX'], backup_id))

  s3.restore(backup_id, tmp)

  if dry_run:
    print('Would have restored %s from %s' % (jenkins_home, tmp))
  else:
    command = [tar, tar_opts, tmp, '-C', jenkins_home]

    print("Executing %s" % ' '.join(command))
    retval = call(command)
    if retval >= 2:
      print("Restoring tar archive failed with error code %s." % retval)
    os.remove(tmp)
    sys.exit(retval)


if __name__ == '__main__':
    cli(obj={})
