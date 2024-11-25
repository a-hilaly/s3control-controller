# Copyright Amazon.com Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You may
# not use this file except in compliance with the License. A copy of the
# License is located at
#
# 	 http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is distributed
# on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied. See the License for the specific language governing
# permissions and limitations under the License.

"""Integration tests for the S3 Control Access Point API.
"""

import pytest
import time
import logging

from acktest.resources import random_suffix_name
from acktest.k8s import resource as k8s
from acktest.aws.identity import get_account_id

from e2e import service_marker, CRD_GROUP, CRD_VERSION, load_s3control_resource
from e2e.replacement_values import REPLACEMENT_VALUES
from e2e.bootstrap_resources import get_bootstrap_resources
from e2e.tests.helper import S3ControlValidator

RESOURCE_PLURAL = "accesspoints"

CREATE_WAIT_AFTER_SECONDS = 10
UPDATE_WAIT_AFTER_SECONDS = 10
DELETE_WAIT_AFTER_SECONDS = 10

@pytest.fixture(scope="module")
def simple_access_point(s3control_client):

    resource_name = random_suffix_name("accesspoint", 24)

    account_id = get_account_id()
    replacements = REPLACEMENT_VALUES.copy()
    replacements["ACCESS_POINT_NAME"] = resource_name
    replacements["ACCOUNT_ID"] = account_id
    replacements["BUCKET_NAME"] = get_bootstrap_resources().Bucket.name

    resource_data = load_s3control_resource(
        "accesspoint",
        additional_replacements=replacements,
    )
    
    logging.debug(resource_data)

    # Create k8s resource
    ref = k8s.CustomResourceReference(
        CRD_GROUP, CRD_VERSION, RESOURCE_PLURAL,
        resource_name, namespace="default",
    )
    k8s.create_custom_resource(ref, resource_data)

    time.sleep(CREATE_WAIT_AFTER_SECONDS)
    cr = k8s.wait_resource_consumed_by_controller(ref)

    assert cr is not None
    assert k8s.get_resource_exists(ref)

    yield (ref, cr, resource_name)

    _, deleted = k8s.delete_custom_resource(
        ref,
        period_length=DELETE_WAIT_AFTER_SECONDS,
    )
    assert deleted

    time.sleep(DELETE_WAIT_AFTER_SECONDS)

    validator = S3ControlValidator(s3control_client)
    assert not validator.access_point_exist(account_id, resource_name)

@service_marker
@pytest.mark.canary
class TestAccessPoint:
    def test_create_delete(self, s3control_client, simple_access_point):
        (ref, _, access_point_name) = simple_access_point
        assert access_point_name is not None
        account_id = get_account_id()

        validator = S3ControlValidator(s3control_client)
        assert validator.access_point_exist(account_id, access_point_name)