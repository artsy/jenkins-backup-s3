import os
import datetime

from subprocess import call, CalledProcessError

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
@click.option('--bucket', required=True, type=click.STRING)
@click.option('--bucket-prefix', type=click.STRING, default='backups')
@click.option('--bucket-region', type=click.STRING, default='us-east-1')
@click.option('--jenkins-home', type=click.STRING, default='/var/lib/jenkins')
@click.option('--tmp', type=click.STRING, default='/tmp/jenkins-backup.tar.gz')
@click.option('--tar', type=click.STRING, default='/bin/tar')
@click.option('--dry-run', type=click.BOOL, is_flag=True)
def cli(ctx, bucket, bucket_prefix, bucket_region, jenkins_home, tmp, tar, dry_run):
    """Manage Jenkins backups to S3"""
    ctx.obj['BUCKET'] = bucket
    ctx.obj['BUCKET_PREFIX'] = bucket_prefix
    ctx.obj['BUCKET_REGION'] = bucket_region
    ctx.obj['JENKINS_HOME'] = jenkins_home
    ctx.obj['TMP'] = tmp
    ctx.obj['TAR'] = tar
    ctx.obj['DRY_RUN'] = dry_run

@cli.command()
@click.pass_context
@click.option('--tar-opts', type=click.STRING, default='cvfz')
@click.option('--exclude-vcs/--include-vcs', default=True)
@click.option('--exclude-archive/--include-archive', default=True)
@click.option('--exclude-target/--include-target', default=True)
@click.option('--exclude-builds/--include-builds', default=True)
@click.option('--exclude-workspace/--include-workspace', default=True)
@click.option('--exclude-maven/--include-maven', default=True)
@click.option('--exclude-logs/--include-logs', default=True)
@click.option('--exclude', '-e', type=click.STRING, multiple=True)
def create(ctx, tar_opts, exclude_vcs, exclude_archive, exclude_target, exclude_builds, exclude_workspace, exclude_maven, exclude_logs, exclude):
  """Create a backup"""
  print("Backing up %s to %s/%s..." % (ctx.obj['JENKINS_HOME'], ctx.obj['BUCKET'], ctx.obj['BUCKET_PREFIX']))

  command = [ctx.obj['TAR'], tar_opts, ctx.obj['TMP']]

  if exclude_vcs:
    command.append('--exclude-vcs')
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

  command.append(ctx.obj['JENKINS_HOME'])

  try:
    call(command)
  except CalledProcessError, err:
    print("Creating tar archive failed with error %s" % repr(e))
    os.remove(ctx.obj['TMP'])
    return

  s3 = S3Backups(ctx.obj['BUCKET'], ctx.obj['BUCKET_PREFIX'], ctx.obj['BUCKET_REGION'])
  backup_id = str(datetime.datetime.now()).replace(' ', '_')

  if ctx.obj['DRY_RUN']:
    print("Would have created backup id %s from %s" % (backup_id, ctx.obj['TMP']))
  else:
    s3.backup(ctx.obj['TMP'], backup_id)
    os.remove(ctx.obj['TMP'])
    print("Created backup id %s" % backup_id)

  print('Done.')

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
  """Delete a backup by id"""
  print("Deleting backup %s in %s/%s..." % (backup_id, ctx.obj['BUCKET'], ctx.obj['BUCKET_PREFIX']))

  s3 = S3Backups(ctx.obj['BUCKET'], ctx.obj['BUCKET_PREFIX'], ctx.obj['BUCKET_REGION'])
  if ctx.obj['DRY_RUN']:
    print("Would have deleted %s" % backup_id)
  else:
    s3.delete(backup_id)
    print("Deleted %s" % backup_id)

  print('Done.')

@cli.command()
@click.pass_context
@click.argument('keep', required=True, type=click.INT)
def prune(ctx, keep):
  """Delete any backups older than the latest {keep} number of backups"""
  print("Pruning backups in %s/%s..." % (ctx.obj['BUCKET'], ctx.obj['BUCKET_PREFIX']))
  s3 = S3Backups(ctx.obj['BUCKET'], ctx.obj['BUCKET_PREFIX'], ctx.obj['BUCKET_REGION'])
  for backup_id in s3.backups()[keep:]:
    if ctx.obj['DRY_RUN']:
      print("Would have deleted %s" % backup_id)
    else:
      s3.delete(backup_id)
      print("Deleted %s" % backup_id)

  print('Done.')

@cli.command()
@click.pass_context
@click.argument('backup-id', required=True, type=click.STRING)
@click.option('--tar-opts', type=click.STRING, default='xzf')
def restore(ctx, backup_id, tar_opts):
  """Restore a backup from a given id"""
  print("Restoring %s from %s/%s..." % (ctx.obj['JENKINS_HOME'], ctx.obj['BUCKET'], ctx.obj['BUCKET_PREFIX']))
  s3 = S3Backups(ctx.obj['BUCKET'], ctx.obj['BUCKET_PREFIX'], ctx.obj['BUCKET_REGION'])
  s3.restore(backup_id, ctx.obj['TMP'])

  if ctx.obj['DRY_RUN']:
    print('Would have restored %s from %s' % (ctx.obj['JENKINS_HOME'], ctx.obj['TMP']))
  else:
    command = [ctx.obj['TAR'], tar_opts, ctx.obj['TMP'], '-C', ctx.obj['JENKINS_HOME']]

    try:
      call(command)
    except CalledProcessError, err:
      print("Restoring tar archive failed with error %s" % repr(e))
    finally:
      os.remove(ctx.obj['TMP'])

  print('Done.')

if __name__ == '__main__':
    cli(obj={})
