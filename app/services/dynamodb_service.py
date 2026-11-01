"""DynamoDB repositories (used when DB_BACKEND=dynamodb).

TABLES
  users      : partition key  email
  resources  : partition key  resource_id
               + 4 global secondary indexes (GSIs), all sorted by uploaded_at
                 so a Query returns newest items first:
                   all-uploaded-index       key gsi_all      (whole library)
                   subject-uploaded-index   key subject_key  (filter by subject)
                   category-uploaded-index  key category      (filter by category)
                   uploader-uploaded-index  key uploader_id   ("my uploads")

We only ever use get_item, put_item, delete_item and Query. There are no Scans.
Title search runs in Python on the (already narrowed) Query result, because
DynamoDB is not a full-text search engine.
"""
import logging
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import BotoCoreError, ClientError

from .common import ALL_PARTITION_VALUE, DatabaseError, title_matches, unique_subjects

logger = logging.getLogger(__name__)

INDEX_ALL = "all-uploaded-index"
INDEX_SUBJECT = "subject-uploaded-index"
INDEX_CATEGORY = "category-uploaded-index"
INDEX_UPLOADER = "uploader-uploaded-index"

MAX_ITEMS_PER_QUERY = 500  # safety cap for a small college project


def _to_plain(value):
    """DynamoDB returns numbers as Decimal; convert them for JSON/templates."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {k: _to_plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_plain(v) for v in value]
    return value


def _dynamodb_resource(region):
    return boto3.resource("dynamodb", region_name=region)


class DynamoUserRepository:
    def __init__(self, table_name, region):
        self.table = _dynamodb_resource(region).Table(table_name)

    def create(self, user):
        """Returns False if the email already exists (atomic conditional write)."""
        try:
            self.table.put_item(Item=user, ConditionExpression="attribute_not_exists(email)")
            return True
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            logger.exception("DynamoDB user create failed")
            raise DatabaseError("Could not create the account.") from exc
        except BotoCoreError as exc:
            logger.exception("DynamoDB user create failed")
            raise DatabaseError("Could not reach the database.") from exc

    def get_by_email(self, email):
        try:
            response = self.table.get_item(Key={"email": email.strip().lower()})
        except (BotoCoreError, ClientError) as exc:
            logger.exception("DynamoDB user lookup failed")
            raise DatabaseError("Could not read from the database.") from exc
        item = response.get("Item")
        return _to_plain(item) if item else None


class DynamoResourceRepository:
    def __init__(self, table_name, region):
        self.table = _dynamodb_resource(region).Table(table_name)

    def create(self, item):
        try:
            self.table.put_item(Item=item, ConditionExpression="attribute_not_exists(resource_id)")
        except (BotoCoreError, ClientError) as exc:
            logger.exception("DynamoDB resource create failed")
            raise DatabaseError("Could not save the resource details.") from exc

    def get(self, resource_id):
        try:
            response = self.table.get_item(Key={"resource_id": resource_id})
        except (BotoCoreError, ClientError) as exc:
            logger.exception("DynamoDB resource lookup failed")
            raise DatabaseError("Could not read from the database.") from exc
        item = response.get("Item")
        return _to_plain(item) if item else None

    def delete(self, resource_id):
        try:
            self.table.delete_item(Key={"resource_id": resource_id})
        except (BotoCoreError, ClientError) as exc:
            logger.exception("DynamoDB resource delete failed")
            raise DatabaseError("Could not delete the resource record.") from exc

    def _query(self, index_name, key_name, key_value, category=None,
               projection=None, names=None):
        """Query one index, newest first, following pagination up to a safety cap."""
        kwargs = {
            "IndexName": index_name,
            "KeyConditionExpression": Key(key_name).eq(key_value),
            "ScanIndexForward": False,  # newest first
        }
        if category:
            kwargs["FilterExpression"] = Attr("category").eq(category)
        if projection:
            kwargs["ProjectionExpression"] = projection
            kwargs["ExpressionAttributeNames"] = names
        items = []
        try:
            while True:
                response = self.table.query(**kwargs)
                items.extend(response.get("Items", []))
                if len(items) >= MAX_ITEMS_PER_QUERY or "LastEvaluatedKey" not in response:
                    break
                kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
        except (BotoCoreError, ClientError) as exc:
            logger.exception("DynamoDB query failed")
            raise DatabaseError("Could not read from the database.") from exc
        return [_to_plain(i) for i in items[:MAX_ITEMS_PER_QUERY]]

    def search(self, query=None, subject=None, category=None, limit=100):
        # Pick the most selective index, then refine the rest in memory.
        if subject:
            items = self._query(INDEX_SUBJECT, "subject_key", subject.strip().lower(),
                                category=category)
        elif category:
            items = self._query(INDEX_CATEGORY, "category", category)
        else:
            items = self._query(INDEX_ALL, "gsi_all", ALL_PARTITION_VALUE)
        return [i for i in items if title_matches(i, query)][:limit]

    def list_by_uploader(self, uploader_id, limit=100):
        return self._query(INDEX_UPLOADER, "uploader_id", uploader_id)[:limit]

    def list_subjects(self):
        items = self._query(INDEX_ALL, "gsi_all", ALL_PARTITION_VALUE,
                            projection="#s, #k",
                            names={"#s": "subject", "#k": "subject_key"})
        return unique_subjects(items)
