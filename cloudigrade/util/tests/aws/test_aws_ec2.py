"""Collection of tests for ``util.aws.ec2`` module."""
import random
import uuid
from unittest.mock import patch

from django.test import TestCase

from util.aws import ec2, get_session
from util.tests import helper


class UtilAwsEc2Test(TestCase):
    """AWS EC2 utility functions test case."""


    def test_get_regions_with_no_args(self):
        """Assert get_regions with no args returns expected regions."""
        mock_regions = [
            f'region-{uuid.uuid4()}',
            f'region-{uuid.uuid4()}',
        ]

        with patch.object(ec2, 'boto3') as mock_boto3:
            mock_session = mock_boto3.Session.return_value
            mock_session.get_available_regions.return_value = mock_regions
            actual_regions = ec2.get_regions(mock_session)
            self.assertTrue(mock_session.get_available_regions.called)
            mock_session.get_available_regions.assert_called_with('ec2')
        self.assertListEqual(mock_regions, actual_regions)

    def test_get_regions_with_custom_service(self):
        """Assert get_regions with service name returns expected regions."""
        mock_regions = [
            f'region-{uuid.uuid4()}',
            f'region-{uuid.uuid4()}',
        ]

        with patch.object(ec2, 'boto3') as mock_boto3:
            mock_session = mock_boto3.Session.return_value
            mock_session.get_available_regions.return_value = mock_regions
            actual_regions = ec2.get_regions(mock_session, 'tng')
            self.assertTrue(mock_session.get_available_regions.called)
            mock_session.get_available_regions.assert_called_with('tng')
        self.assertListEqual(mock_regions, actual_regions)

    def test_get_running_instances(self):
        """Assert we get expected instances in a dict keyed by regions."""
        mock_arn = helper.generate_dummy_arn()
        mock_regions = [f'region-{uuid.uuid4()}']
        mock_role = helper.generate_dummy_role()
        mock_running_instance = helper.generate_dummy_describe_instance(
            state=ec2.InstanceState.running
        )
        mock_stopped_instance = helper.generate_dummy_describe_instance(
            state=ec2.InstanceState.stopped
        )
        mock_described = {
            'Reservations': [
                {
                    'Instances': [
                        mock_running_instance,
                        mock_stopped_instance,
                    ],
                },
            ],
        }
        expected_found = {
            mock_regions[0]: [mock_running_instance]
        }

        with patch.object(ec2, 'get_regions') as mock_get_regions, \
                patch.object(ec2, 'boto3') as mock_boto3:
            mock_assume_role = mock_boto3.client.return_value.assume_role
            mock_assume_role.return_value = mock_role
            mock_get_regions.return_value = mock_regions
            mock_client = mock_boto3.Session.return_value.client.return_value
            mock_client.describe_instances.return_value = mock_described

            actual_found = ec2.get_running_instances(get_session(mock_arn))

        self.assertDictEqual(expected_found, actual_found)

    def test_get_ec2_instance(self):
        """Assert that get_ec2_instance returns an instance object."""
        mock_arn = helper.generate_dummy_arn()
        mock_instance_id = helper.generate_dummy_instance_id()

        mock_instance = helper.generate_mock_ec2_instance(mock_instance_id)

        with patch.object(ec2, 'boto3') as mock_boto3:
            mock_session = mock_boto3.Session.return_value
            resource = mock_session.resource.return_value
            resource.Instance.return_value = mock_instance
            actual_instance = ec2.get_ec2_instance(get_session(mock_arn),
                                                   mock_instance_id)

        self.assertEqual(actual_instance, mock_instance)

    def test_get_ami(self):
        """Assert that get_ami returns an Image object."""
        mock_arn = helper.generate_dummy_arn()
        mock_region = random.choice(helper.SOME_AWS_REGIONS)
        mock_image_id = helper.generate_dummy_image_id()
        mock_image = helper.generate_mock_image(mock_image_id)

        with patch.object(ec2, 'boto3') as mock_boto3:
            mock_session = mock_boto3.Session.return_value
            resource = mock_session.resource.return_value
            resource.Image.return_value = mock_image
            actual_image = ec2.get_ami(
                get_session(mock_arn),
                mock_image_id,
                mock_region
            )

        self.assertEqual(actual_image, mock_image)

    def test_get_ami_snapshot_id(self):
        """Assert that an AMI returns a snapshot id."""
        mock_image_id = helper.generate_dummy_image_id()
        mock_image = helper.generate_mock_image(mock_image_id)

        expected_id = mock_image.block_device_mappings[0]['Ebs']['SnapshotId']
        actual_id = ec2.get_ami_snapshot_id(mock_image)
        self.assertEqual(expected_id, actual_id)

    def test_get_snapshot(self):
        """Assert that a snapshot is returned."""
        mock_arn = helper.generate_dummy_arn()
        mock_region = random.choice(helper.SOME_AWS_REGIONS)
        mock_snapshot_id = helper.generate_dummy_snapshot_id()
        mock_snapshot = helper.generate_mock_snapshot(mock_snapshot_id)

        with patch.object(ec2, 'boto3') as mock_boto3:
            mock_session = mock_boto3.Session.return_value
            resource = mock_session.resource.return_value
            resource.Snapshot.return_value = mock_snapshot
            actual_snapshot = ec2.get_snapshot(
                get_session(mock_arn),
                mock_snapshot_id,
                mock_region
            )

        self.assertEqual(actual_snapshot, mock_snapshot)
