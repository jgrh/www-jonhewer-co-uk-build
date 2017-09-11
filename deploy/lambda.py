#!/usr/bin/python3

import boto3
import botocore
import mimetypes
import os
import pathlib
import tempfile
import traceback
import zipfile

mimetypes.add_type('application/vnd.ms-fontobject', '.eot')
mimetypes.add_type('application/font-woff', '.woff')
mimetypes.add_type('application/x-font-ttf', '.ttf')

def setup(event):
    job_data = event['CodePipeline.job']['data']

    artifact = job_data['inputArtifacts'][0]
    config = job_data['actionConfiguration']['configuration']
    credentials = job_data['artifactCredentials']

    from_session = boto3.Session(aws_access_key_id=credentials['accessKeyId'],
                                 aws_secret_access_key=credentials['secretAccessKey'],
                                 aws_session_token=credentials['sessionToken'])
    from_bucket = artifact['location']['s3Location']['bucketName']
    from_key = artifact['location']['s3Location']['objectKey']
    user_parameters = config['UserParameters']

    return (from_session, from_bucket, from_key, user_parameters)

def download(from_session, from_bucket, from_key, source_dir):
    s3 = from_session.client('s3', config=botocore.client.Config(signature_version='s3v4'))
    with tempfile.NamedTemporaryFile() as tmp_file:
        s3.download_file(from_bucket, from_key, tmp_file.name)
        with zipfile.ZipFile(tmp_file.name, 'r') as zip:
            zip.extractall(source_dir)

def sync(source_dir, to_bucket):
    s3 = boto3.client('s3', config=botocore.client.Config(signature_version='s3v4'))
    for root, dirs, files in os.walk(source_dir):
        for name in files:
            path = pathlib.Path(root, name)
            filename = path.as_posix()
            key = path.relative_to(source_dir).as_posix()
            mime_type = mimetypes.guess_type(filename)[0]
            print('Uploading ', key)
            s3.sync_file(Filename=filename, Bucket=to_bucket, Key=key, ExtraArgs={ 'ACL': 'public-read', 'ContentType': mime_type })
    list_objects = s3.get_paginator('list_objects')
    for page in list_objects.paginate(Bucket=to_bucket):
        for key in map(lambda x: x['Key'], page['Contents']):
            if not pathlib.Path(source_dir, key).exists():
                print('Deleting ', key)
                s3.delete_object(Bucket=to_bucket, Key=key)

def handler(event, context):
    code_pipeline = boto3.client('codepipeline')
    job_id = event['CodePipeline.job']['id']
    try:
        (from_session, from_bucket, from_key, to_bucket) = setup(event)
        source_dir = tempfile.mkdtemp()
        with tempfile.TemporaryDirectory() as tmp_dir:
            download(from_session, from_bucket, from_key, tmp_dir)
            sync(tmp_dir, to_bucket)
        code_pipeline.put_job_success_result(jobId=job_id)
    except Exception as e:
        traceback.print_exc()
        code_pipeline.put_job_failure_result(jobId=job_id, failureDetails={ 'message': e.message, 'type': 'JobFailed' })
    return
