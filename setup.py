from setuptools import setup, find_packages

setup(
    name='jenkins-backup-s3',
    version='0.1.5',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'backup-jenkins=jenkins_backup_s3.backup:main'
        ]
    },
    install_requires=(
        'boto3==1.4.7',
        'botocore==1.7.19',
        'click==6.7',
        'colorama==0.3.9',
        'docutils==0.14',
        'jmespath==0.9.3',
        'python-dateutil==2.6.1',
        's3transfer==0.1.11',
        'six==1.11.0',
        'termcolor==1.1.0'
    )
)
