"""Create the two DynamoDB tables (and indexes) the application needs.

Run once, from the project root, AFTER your AWS credentials are available
(for example `aws configure` on your laptop, or the EC2 IAM role):

    python scripts/create_aws_tables.py

Billing mode is on-demand (PAY_PER_REQUEST), so you pay per request and there
is no capacity to size. Running it twice is safe: existing tables are skipped.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import boto3  # noqa: E402

from app.config import Config  # noqa: E402
from app.services.dynamodb_service import (  # noqa: E402
    INDEX_ALL, INDEX_CATEGORY, INDEX_SUBJECT, INDEX_UPLOADER,
)


def _gsi(index_name, partition_attr):
    return {
        "IndexName": index_name,
        "KeySchema": [
            {"AttributeName": partition_attr, "KeyType": "HASH"},
            {"AttributeName": "uploaded_at", "KeyType": "RANGE"},
        ],
        "Projection": {"ProjectionType": "ALL"},
    }


def _create(client, **table_definition):
    name = table_definition["TableName"]
    try:
        client.create_table(BillingMode="PAY_PER_REQUEST", **table_definition)
        print(f"Creating table {name} ...")
        client.get_waiter("table_exists").wait(TableName=name)
        print(f"  {name} is ACTIVE")
    except client.exceptions.ResourceInUseException:
        print(f"Table {name} already exists - skipped")


def main():
    client = boto3.client("dynamodb", region_name=Config.AWS_REGION)
    print(f"Region: {Config.AWS_REGION}")

    _create(
        client,
        TableName=Config.DYNAMODB_USERS_TABLE,
        AttributeDefinitions=[{"AttributeName": "email", "AttributeType": "S"}],
        KeySchema=[{"AttributeName": "email", "KeyType": "HASH"}],
    )

    _create(
        client,
        TableName=Config.DYNAMODB_RESOURCES_TABLE,
        AttributeDefinitions=[
            {"AttributeName": "resource_id", "AttributeType": "S"},
            {"AttributeName": "gsi_all", "AttributeType": "S"},
            {"AttributeName": "subject_key", "AttributeType": "S"},
            {"AttributeName": "category", "AttributeType": "S"},
            {"AttributeName": "uploader_id", "AttributeType": "S"},
            {"AttributeName": "uploaded_at", "AttributeType": "S"},
        ],
        KeySchema=[{"AttributeName": "resource_id", "KeyType": "HASH"}],
        GlobalSecondaryIndexes=[
            _gsi(INDEX_ALL, "gsi_all"),
            _gsi(INDEX_SUBJECT, "subject_key"),
            _gsi(INDEX_CATEGORY, "category"),
            _gsi(INDEX_UPLOADER, "uploader_id"),
        ],
    )


if __name__ == "__main__":
    main()
