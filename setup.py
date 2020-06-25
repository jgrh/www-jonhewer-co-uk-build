#!/usr/bin/env python3

import argparse
import boto3
import botocore
import subprocess
import tempfile
import zipfile

cf = boto3.client('cloudformation')
s3 = boto3.client('s3')

def create_or_update(stack_name, template, parameters, capabilities=[]):
    def stack_exists(stack_name):
        return any(stack['StackName'] == stack_name and stack['StackStatus'] != 'DELETE_COMPLETE' for stack in cf.list_stacks()['StackSummaries'])

    def parse_template(template):
        with open(template) as template_file:
            template_data = template_file.read()
        cf.validate_template(TemplateBody=template_data)
        return template_data

    try:
        if stack_exists(stack_name):
            print('Updating stack:', stack_name)
            stack_result = cf.update_stack(StackName=stack_name,
                                           TemplateBody=parse_template(template),
                                           Parameters=parameters,
                                           Capabilities=capabilities)
            waiter = cf.get_waiter('stack_update_complete')
            print('Waiting for stack to be ready...')
            waiter.wait(StackName=stack_name)
            print('Stack updated')
        else:
            print('Creating stack', stack_name)
            stack_result = cf.create_stack(StackName=stack_name,
                                           TemplateBody=parse_template(template),
                                           Parameters=parameters,
                                           Capabilities=capabilities)
            waiter = cf.get_waiter('stack_create_complete')
            print('Waiting for stack to be ready...')
            waiter.wait(StackName=stack_name)
            print('Stack created')
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Message'] == 'No updates are to be performed.':
            print('No updates to stack performed')
        else:
            raise

def get_stack_outputs(stack_name):
    def describe_stack(stack_name):
        return cf.describe_stacks(StackName=stack_name)['Stacks'][0]
    return { output['OutputKey']: output['OutputValue'] for output in describe_stack(stack_name)['Outputs'] }

def upload_lambda(name, bucket):
    with tempfile.NamedTemporaryFile() as tmp_file:
        with zipfile.ZipFile(tmp_file.name, 'w') as zip:
            zip.write('lambda/' + name + '.py', arcname=name + '.py')
        print('Uploading lambda:', name)
        s3.upload_file(Filename=tmp_file.name, Bucket=bucket, Key=name + '.zip')

def build_and_push_docker_image(dockerfile, image_uri):
    print('Building Docker image:', image_uri)
    build_result = subprocess.run(['docker', 'build', '-f', 'dockerfiles/' + dockerfile, '-t', image_uri + ':latest', '.'], check=True)
    print('Logging into ECR')
    login = subprocess.Popen(['aws', 'ecr', 'get-login-password', '--region', 'eu-west-1'], stdout=subprocess.PIPE)
    login_result = subprocess.run(['docker', 'login', '--username', 'AWS', '--password-stdin', image_uri], stdin=login.stdout, check=True)
    login.wait()
    print('Pushing docker image:', image_uri)
    push_result = subprocess.run(['docker', 'push', image_uri + ':latest'], check=True)

def setup(github_token, service_name, website_hostname):
    create_or_update(service_name + '-pipeline-dependencies', 'pipeline-dependencies.yml',
                     [{ 'ParameterKey': 'ServiceName', 'ParameterValue': service_name }])

    outputs = get_stack_outputs(service_name + '-pipeline-dependencies')

    upload_lambda('deploy', outputs['PipelineLambdaBucketName'])

    build_and_push_docker_image('Dockerfile', outputs['BuildImageContainerRepositoryUri'])

    create_or_update(service_name + '-pipeline', 'pipeline.yml',
                     [
                         { 'ParameterKey': 'GitHubToken', 'ParameterValue': github_token },
                         { 'ParameterKey': 'ServiceName', 'ParameterValue': service_name },
                         { 'ParameterKey': 'WebsiteHostname', 'ParameterValue': website_hostname }
                     ],
                     capabilities=['CAPABILITY_IAM'])

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create service cloudformation stack')
    parser.add_argument('--github-token', required=True)
    parser.add_argument('--service-name', required=True)
    parser.add_argument('--website-hostname', required=True)
    args = parser.parse_args()
    setup(args.github_token, args.service_name, args.website_hostname)
