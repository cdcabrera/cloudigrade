import logging
import re
from functools import wraps

from botocore.exceptions import ClientError
from django.utils.translation import gettext as _

from util.aws.ec2 import SNAPSHOT_ID
from util.exceptions import InvalidArn

logger = logging.getLogger(__name__)


cloudigrade_policy = {
    'Version': '2012-10-17',
    'Statement': [
        {
            'Sid': 'CloudigradePolicy',
            'Effect': 'Allow',
            'Action': [
                'ec2:DescribeImages',
                'ec2:DescribeInstances',
                'ec2:ModifySnapshotAttribute',
                'ec2:DescribeSnapshotAttribute',
                'ec2:ModifyImageAttribute',
                'ec2:DescribeSnapshots'
            ],
            'Resource': '*'
        }
    ]
}


class AwsArn(object):
    """
    Object representing an AWS ARN.

    See also:
        https://docs.aws.amazon.com/general/latest/gr/aws-arns-and-namespaces.html

    General ARN formats:
        arn:partition:service:region:account-id:resource
        arn:partition:service:region:account-id:resourcetype/resource
        arn:partition:service:region:account-id:resourcetype:resource

    Example ARNs:
        <!-- Elastic Beanstalk application version -->
        arn:aws:elasticbeanstalk:us-east-1:123456789012:environment/My App/foo

        <!-- IAM user name -->
        arn:aws:iam::123456789012:user/David

        <!-- Amazon RDS instance used for tagging -->
        arn:aws:rds:eu-west-1:123456789012:db:mysql-db

        <!-- Object in an Amazon S3 bucket -->
        arn:aws:s3:::my_corporate_bucket/exampleobject.png

    """

    arn_regex = re.compile(r'^arn:(?P<partition>\w+):(?P<service>\w+):'
                           r'(?P<region>\w+(?:-\w+)+)?:'
                           r'(?P<account_id>\d{12})?:(?P<resource_type>[^:/]+)'
                           r'(?P<resource_separator>[:/])?(?P<resource>.*)')

    partition = None
    service = None
    region = None
    account_id = None
    resource_type = None
    resource_separator = None
    resource = None

    def __init__(self, arn):
        """
        Parse ARN string into its component pieces.

        Args:
            arn (str): Amazon Resource Name

        """
        self.arn = arn
        match = self.arn_regex.match(arn)

        if not match:
            raise InvalidArn('Invalid ARN: {0}'.format(arn))

        for key, val in match.groupdict().items():
            setattr(self, key, val)

    def __repr__(self):
        """Return the ARN itself."""
        return self.arn


def _handle_dry_run_response_exception(action, e):
    """
    Handle the normal exception that is raised from a dry-run operation.

    This may look weird, but when a boto3 operation is executed with the
    ``DryRun=True`` argument, the typical behavior is for it to raise a
    ``ClientError`` exception with an error code buried within to indicate if
    the operation would have succeeded.

    See also:
        https://botocore.readthedocs.io/en/latest/client_upgrades.html#error-handling

    Args:
        action (str): The action that was attempted
        e (botocore.exceptions.ClientError): The raised exception

    Returns:
        bool: Whether the operation had access verified, or not.

    """
    dry_run_operation = 'DryRunOperation'
    unauthorized_operation = 'UnauthorizedOperation'

    if e.response['Error']['Code'] == dry_run_operation:
        logger.debug(_('Verified access to "{0}"').format(action))
        return True
    elif e.response['Error']['Code'] == unauthorized_operation:
        logger.warning(_('No access to "{0}"').format(action))
        return False
    raise e


def rewrap_aws_errors(original_function):
    """
    Decorate function to except boto AWS ClientError and raise as RuntimeError.

    This is useful when we have boto calls inside of Celery tasks but Celery
    cannot serialize boto AWS ClientError using JSON. If we encounter other
    boto/AWS-specific exceptions that are not serializable, we should add
    support for them here.

    Args:
        original_function: The function to decorate.

    Returns:
        function: The decorated function.

    """
    @wraps(original_function)
    def wrapped(*args, **kwargs):
        try:
            result = original_function(*args, **kwargs)
        except ClientError as e:
            message = _('Unexpected AWS error {0}: {1}').format(type(e), e)
            raise RuntimeError(message)
        return result
    return wrapped


def _verify_policy_action(session, action):
    """
    Check to see if we have access to a specific action.

    Args:
        session (boto3.Session): A temporary session tied to a customer account
        action (str): The policy action to check

    Returns:
        bool: Whether the action is allowed, or not.

    """
    ec2 = session.client('ec2')

    try:
        if action == 'ec2:DescribeImages':
            ec2.describe_images(DryRun=True)
        elif action == 'ec2:DescribeInstances':
            ec2.describe_instances(DryRun=True)
        elif action == 'ec2:DescribeSnapshotAttribute':
            ec2.describe_snapshot_attribute(
                DryRun=True,
                SnapshotId=SNAPSHOT_ID,
                Attribute='productCodes'
            )
        elif action == 'ec2:DescribeSnapshots':
            ec2.describe_snapshots(DryRun=True)
        elif action == 'ec2:ModifySnapshotAttribute':
            ec2.modify_snapshot_attribute(
                SnapshotId=SNAPSHOT_ID,
                DryRun=True,
                Attribute='createVolumePermission',
                OperationType='add',
            )
        elif action == 'ec2:ModifyImageAttribute':
            ec2.modify_image_attribute(
                Attribute='description',
                ImageId='string',
                DryRun=True
            )
        else:
            logger.warning(_('No test case exists for action "{0}"')
                           .format(action))
            return False
    except ClientError as e:
        return _handle_dry_run_response_exception(action, e)


def verify_account_access(session):
    """
    Check role for proper access to AWS APIs.

    Args:
        session (boto3.Session): A temporary session tied to a customer account

    Returns:
        bool: Whether role is verified.

    """
    success = True
    for action in cloudigrade_policy['Statement'][0]['Action']:
        if not _verify_policy_action(session, action):
            # Mark as failure, but keep looping so we can see each specific
            # failure in logs
            success = False
    return success
