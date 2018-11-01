#! /bin/bash

set -e

python setup.py sdist bdist_wheel
twine upload dist/*
rm -rf build/ dist/ jenkins_backup_s3.egg-info/
