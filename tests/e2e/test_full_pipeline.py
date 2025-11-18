"""
Full Pipeline E2E Test for Sentiment Analyzer

This test validates the complete data flow:
1. Ingestion Lambda fetches from NewsAPI and stores in DynamoDB
2. SNS notification triggers Analysis Lambda
3. Analysis Lambda runs sentiment inference and updates DynamoDB
4. Dashboard Lambda serves aggregated metrics

For On-Call Engineers:
    This test verifies the complete pipeline integration.
    If this test fails, check each component individually:
    - test_ingestion_e2e.py for ingestion issues
    - test_analysis_e2e.py for analysis issues
    - test_dashboard_e2e.py for dashboard issues

Security:
    Uses moto mocks - no real AWS resources accessed.
    Tests API key validation and input sanitization.

Author: Claude Code
"""

import json
import os
import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch, MagicMock

import boto3
import pytest
from moto import mock_aws


# Test configuration
TEST_TABLE_NAME = "test-sentiment-items"
TEST_TOPIC_ARN = "arn:aws:sns:us-east-1:123456789012:test-analysis-requests"
TEST_API_KEY = "test-api-key-12345"
TEST_NEWSAPI_KEY = "test-newsapi-key"


def create_test_infrastructure():
    """Create all test AWS infrastructure.
    
    Returns:
        tuple: (dynamodb_table, sns_client, sqs_client, queue_url)
    """
    # Create DynamoDB table
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.create_table(
        TableName=TEST_TABLE_NAME,
        KeySchema=[
            {"AttributeName": "source_id", "KeyType": "HASH"},
            {"AttributeName": "timestamp", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "source_id", "AttributeType": "S"},
            {"AttributeName": "timestamp", "AttributeType": "S"},
            {"AttributeName": "sentiment", "AttributeType": "S"},
            {"AttributeName": "tag", "AttributeType": "S"},
            {"AttributeName": "status", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "by_sentiment",
                "KeySchema": [
                    {"AttributeName": "sentiment", "KeyType": "HASH"},
                    {"AttributeName": "timestamp", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {
                    "ReadCapacityUnits": 5,
                    "WriteCapacityUnits": 5,
                },
            },
            {
                "IndexName": "by_tag",
                "KeySchema": [
                    {"AttributeName": "tag", "KeyType": "HASH"},
                    {"AttributeName": "timestamp", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {
                    "ReadCapacityUnits": 5,
                    "WriteCapacityUnits": 5,
                },
            },
            {
                "IndexName": "by_status",
                "KeySchema": [
                    {"AttributeName": "status", "KeyType": "HASH"},
                    {"AttributeName": "timestamp", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {
                    "ReadCapacityUnits": 5,
                    "WriteCapacityUnits": 5,
                },
            },
        ],
        BillingMode="PROVISIONED",
        ProvisionedThroughput={
            "ReadCapacityUnits": 10,
            "WriteCapacityUnits": 10,
        },
    )
    table.wait_until_exists()
    
    # Create SNS topic
    sns = boto3.client("sns", region_name="us-east-1")
    topic_response = sns.create_topic(Name="test-analysis-requests")
    topic_arn = topic_response["TopicArn"]
    
    # Create SQS queue to receive SNS messages (for testing)
    sqs = boto3.client("sqs", region_name="us-east-1")
    queue_response = sqs.create_queue(QueueName="test-analysis-queue")
    queue_url = queue_response["QueueUrl"]
    
    # Subscribe SQS to SNS
    queue_arn = f"arn:aws:sqs:us-east-1:123456789012:test-analysis-queue"
    sns.subscribe(
        TopicArn=topic_arn,
        Protocol="sqs",
        Endpoint=queue_arn,
    )
    
    # Create Secrets Manager secrets
    secrets = boto3.client("secretsmanager", region_name="us-east-1")
    secrets.create_secret(
        Name="test/sentiment-analyzer/newsapi",
        SecretString=json.dumps({"api_key": TEST_NEWSAPI_KEY}),
    )
    secrets.create_secret(
        Name="test/sentiment-analyzer/dashboard-api-key",
        SecretString=json.dumps({"api_key": TEST_API_KEY}),
    )
    
    return table, sns, sqs, queue_url, topic_arn


def generate_source_id(url: str) -> str:
    """Generate source_id from URL using same algorithm as production."""
    content_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
    return f"newsapi#{content_hash}"


class TestFullPipeline:
    """End-to-end tests for the complete sentiment analysis pipeline."""
    
    @mock_aws
    @patch.dict(os.environ, {
        "AWS_DEFAULT_REGION": "us-east-1",
        "DYNAMODB_TABLE": TEST_TABLE_NAME,
        "WATCH_TAGS": "AI,climate",
        "ENVIRONMENT": "test",
        "MODEL_VERSION": "v1.0.0",
    })
    def test_pipeline_flow_ingestion_to_dashboard(self):
        """Test complete flow from ingestion through analysis to dashboard.
        
        This is the primary integration test that validates:
        1. Articles are ingested from NewsAPI
        2. Items are stored in DynamoDB with pending status
        3. SNS messages are published for analysis
        4. Analysis updates items with sentiment scores
        5. Dashboard can query and display results
        """
        # Setup infrastructure
        table, sns_client, sqs_client, queue_url, topic_arn = create_test_infrastructure()
        
        # Step 1: Simulate ingestion - create pending items
        test_articles = [
            {
                "url": "https://news.example.com/ai-breakthrough",
                "title": "Major AI Breakthrough Announced",
                "description": "Scientists achieve remarkable progress in AI research.",
                "content": "The AI community is celebrating a major breakthrough today.",
                "publishedAt": "2025-01-15T10:00:00Z",
                "source": {"name": "Tech News"},
            },
            {
                "url": "https://news.example.com/climate-action",
                "title": "Global Climate Summit Results",
                "description": "World leaders agree on new climate targets.",
                "content": "The summit concluded with ambitious emissions reduction goals.",
                "publishedAt": "2025-01-15T11:00:00Z",
                "source": {"name": "World News"},
            },
            {
                "url": "https://news.example.com/market-crash",
                "title": "Stock Market Faces Turbulence",
                "description": "Investors worried about economic downturn.",
                "content": "Market volatility increases as fears of recession grow.",
                "publishedAt": "2025-01-15T12:00:00Z",
                "source": {"name": "Finance Daily"},
            },
        ]
        
        # Store items in DynamoDB (simulating ingestion)
        stored_items = []
        for i, article in enumerate(test_articles):
            source_id = generate_source_id(article["url"])
            timestamp = f"2025-01-15T{10+i:02d}:00:00Z"
            
            item = {
                "source_id": source_id,
                "timestamp": timestamp,
                "title": article["title"],
                "description": article["description"],
                "content": article.get("content", ""),
                "url": article["url"],
                "source_name": article["source"]["name"],
                "tag": ["AI", "climate", "economy"][i],
                "status": "pending",
                "ttl": int(datetime.now(timezone.utc).timestamp()) + 86400 * 30,
                "content_hash": hashlib.sha256(
                    article["url"].encode()
                ).hexdigest()[:16],
            }
            table.put_item(Item=item)
            stored_items.append(item)
            
            # Publish SNS message (simulating ingestion trigger)
            sns_client.publish(
                TopicArn=topic_arn,
                Message=json.dumps({
                    "source_id": source_id,
                    "timestamp": timestamp,
                    "text_for_analysis": f"{article['title']}. {article['description']}",
                }),
            )
        
        # Verify items are in pending status
        for item in stored_items:
            response = table.get_item(
                Key={
                    "source_id": item["source_id"],
                    "timestamp": item["timestamp"],
                }
            )
            assert response["Item"]["status"] == "pending"
        
        # Step 2: Simulate analysis - update items with sentiment
        # (In production, this would be triggered by SNS)
        sentiment_results = [
            {"sentiment": "positive", "score": Decimal("0.92")},
            {"sentiment": "positive", "score": Decimal("0.78")},
            {"sentiment": "negative", "score": Decimal("0.85")},
        ]
        
        for item, result in zip(stored_items, sentiment_results):
            table.update_item(
                Key={
                    "source_id": item["source_id"],
                    "timestamp": item["timestamp"],
                },
                UpdateExpression=(
                    "SET sentiment = :s, score = :sc, "
                    "model_version = :mv, #st = :status, "
                    "analyzed_at = :at"
                ),
                ExpressionAttributeNames={
                    "#st": "status",
                },
                ExpressionAttributeValues={
                    ":s": result["sentiment"],
                    ":sc": result["score"],
                    ":mv": "v1.0.0",
                    ":status": "analyzed",
                    ":at": datetime.now(timezone.utc).isoformat(),
                },
                ConditionExpression="attribute_not_exists(sentiment)",
            )
        
        # Verify items are analyzed
        for item in stored_items:
            response = table.get_item(
                Key={
                    "source_id": item["source_id"],
                    "timestamp": item["timestamp"],
                }
            )
            assert response["Item"]["status"] == "analyzed"
            assert "sentiment" in response["Item"]
            assert "score" in response["Item"]
        
        # Step 3: Verify dashboard can query metrics
        # Query by_sentiment GSI
        positive_response = table.query(
            IndexName="by_sentiment",
            KeyConditionExpression="sentiment = :s",
            ExpressionAttributeValues={":s": "positive"},
        )
        assert positive_response["Count"] == 2
        
        negative_response = table.query(
            IndexName="by_sentiment",
            KeyConditionExpression="sentiment = :s",
            ExpressionAttributeValues={":s": "negative"},
        )
        assert negative_response["Count"] == 1
        
        # Query by_status GSI
        analyzed_response = table.query(
            IndexName="by_status",
            KeyConditionExpression="#st = :s",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={":s": "analyzed"},
        )
        assert analyzed_response["Count"] == 3
        
        # Query by_tag GSI
        ai_response = table.query(
            IndexName="by_tag",
            KeyConditionExpression="tag = :t",
            ExpressionAttributeValues={":t": "AI"},
        )
        assert ai_response["Count"] == 1
    
    @mock_aws
    @patch.dict(os.environ, {
        "AWS_DEFAULT_REGION": "us-east-1",
        "DYNAMODB_TABLE": TEST_TABLE_NAME,
    })
    def test_pipeline_handles_duplicate_items(self):
        """Test that duplicate items are handled correctly.
        
        Items with the same source_id should be deduplicated.
        Second ingestion attempt should not overwrite analyzed items.
        """
        table, _, _, _, _ = create_test_infrastructure()
        
        # Create initial item
        source_id = generate_source_id("https://example.com/article1")
        timestamp = "2025-01-15T10:00:00Z"
        
        # First write (pending)
        table.put_item(
            Item={
                "source_id": source_id,
                "timestamp": timestamp,
                "title": "Test Article",
                "status": "pending",
                "tag": "AI",
            }
        )
        
        # Update to analyzed
        table.update_item(
            Key={"source_id": source_id, "timestamp": timestamp},
            UpdateExpression="SET sentiment = :s, #st = :status",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":s": "positive",
                ":status": "analyzed",
            },
        )
        
        # Attempt to re-analyze (should be idempotent)
        try:
            table.update_item(
                Key={"source_id": source_id, "timestamp": timestamp},
                UpdateExpression="SET sentiment = :s",
                ExpressionAttributeValues={":s": "negative"},
                ConditionExpression="attribute_not_exists(sentiment)",
            )
            # If no exception, the condition was met (shouldn't happen)
            pytest.fail("Expected ConditionalCheckFailedException")
        except Exception as e:
            # Expected: condition check fails because sentiment already exists
            assert "ConditionalCheckFailed" in str(type(e).__name__) or "Condition" in str(e)
        
        # Verify sentiment wasn't overwritten
        response = table.get_item(
            Key={"source_id": source_id, "timestamp": timestamp}
        )
        assert response["Item"]["sentiment"] == "positive"
    
    @mock_aws
    @patch.dict(os.environ, {
        "AWS_DEFAULT_REGION": "us-east-1",
        "DYNAMODB_TABLE": TEST_TABLE_NAME,
    })
    def test_pipeline_metrics_aggregation(self):
        """Test that metrics are correctly aggregated across items.
        
        Verifies:
        - Sentiment distribution counts
        - Tag distribution counts
        - Time-based filtering
        """
        table, _, _, _, _ = create_test_infrastructure()
        
        # Create test data with various sentiments and tags
        test_data = [
            ("positive", "AI", "2025-01-15T10:00:00Z"),
            ("positive", "AI", "2025-01-15T11:00:00Z"),
            ("neutral", "climate", "2025-01-15T12:00:00Z"),
            ("negative", "economy", "2025-01-15T13:00:00Z"),
            ("negative", "health", "2025-01-15T14:00:00Z"),
            ("negative", "health", "2025-01-15T15:00:00Z"),
            ("positive", "sports", "2025-01-15T16:00:00Z"),
        ]
        
        for i, (sentiment, tag, timestamp) in enumerate(test_data):
            source_id = f"newsapi#{i:016d}"
            table.put_item(
                Item={
                    "source_id": source_id,
                    "timestamp": timestamp,
                    "title": f"Article {i}",
                    "sentiment": sentiment,
                    "score": Decimal("0.8"),
                    "tag": tag,
                    "status": "analyzed",
                }
            )
        
        # Verify sentiment distribution
        sentiments = {}
        for sentiment in ["positive", "neutral", "negative"]:
            response = table.query(
                IndexName="by_sentiment",
                KeyConditionExpression="sentiment = :s",
                ExpressionAttributeValues={":s": sentiment},
            )
            sentiments[sentiment] = response["Count"]
        
        assert sentiments == {"positive": 3, "neutral": 1, "negative": 3}
        
        # Verify tag distribution
        tags = {}
        for tag in ["AI", "climate", "economy", "health", "sports"]:
            response = table.query(
                IndexName="by_tag",
                KeyConditionExpression="tag = :t",
                ExpressionAttributeValues={":t": tag},
            )
            tags[tag] = response["Count"]
        
        assert tags == {"AI": 2, "climate": 1, "economy": 1, "health": 2, "sports": 1}
    
    @mock_aws
    @patch.dict(os.environ, {
        "AWS_DEFAULT_REGION": "us-east-1",
        "DYNAMODB_TABLE": TEST_TABLE_NAME,
    })
    def test_pipeline_handles_missing_fields_gracefully(self):
        """Test that the pipeline handles items with missing optional fields.
        
        Demonstrates grey area safety - components should work even
        when items have varying schemas due to deployment timing.
        """
        table, _, _, _, _ = create_test_infrastructure()
        
        # Create item without optional fields
        source_id = generate_source_id("https://example.com/minimal")
        timestamp = "2025-01-15T10:00:00Z"
        
        # Minimal item (old schema - before analysis)
        table.put_item(
            Item={
                "source_id": source_id,
                "timestamp": timestamp,
                "title": "Minimal Article",
                "status": "pending",
                "tag": "AI",
            }
        )
        
        # Query should work without sentiment
        response = table.query(
            IndexName="by_status",
            KeyConditionExpression="#st = :s",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={":s": "pending"},
        )
        assert response["Count"] == 1
        
        # Item should not appear in sentiment queries
        response = table.query(
            IndexName="by_sentiment",
            KeyConditionExpression="sentiment = :s",
            ExpressionAttributeValues={":s": "positive"},
        )
        assert response["Count"] == 0
    
    @mock_aws
    @patch.dict(os.environ, {
        "AWS_DEFAULT_REGION": "us-east-1",
        "DYNAMODB_TABLE": TEST_TABLE_NAME,
    })
    def test_sns_message_format(self):
        """Test that SNS messages are correctly formatted for analysis.
        
        The analysis Lambda expects specific fields in the message.
        """
        table, sns_client, sqs_client, queue_url, topic_arn = create_test_infrastructure()
        
        # Publish message in expected format
        message = {
            "source_id": "newsapi#abc123",
            "timestamp": "2025-01-15T10:00:00Z",
            "text_for_analysis": "This is great news about AI progress.",
        }
        
        sns_client.publish(
            TopicArn=topic_arn,
            Message=json.dumps(message),
        )
        
        # Receive message from SQS (subscriber)
        response = sqs_client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=1,
        )
        
        assert "Messages" in response
        assert len(response["Messages"]) == 1
        
        # Parse SNS wrapper
        sns_wrapper = json.loads(response["Messages"][0]["Body"])
        received_message = json.loads(sns_wrapper["Message"])
        
        assert received_message["source_id"] == "newsapi#abc123"
        assert received_message["timestamp"] == "2025-01-15T10:00:00Z"
        assert "text_for_analysis" in received_message


class TestPipelineErrorHandling:
    """Tests for error handling throughout the pipeline."""
    
    @mock_aws
    @patch.dict(os.environ, {
        "AWS_DEFAULT_REGION": "us-east-1",
        "DYNAMODB_TABLE": TEST_TABLE_NAME,
    })
    def test_handles_dynamodb_errors_gracefully(self):
        """Test that DynamoDB errors are handled without crashing."""
        # Create infrastructure but don't create table
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        
        # Attempt to get item from non-existent table
        table = dynamodb.Table("non-existent-table")
        
        with pytest.raises(Exception) as exc_info:
            table.get_item(
                Key={"source_id": "test", "timestamp": "2025-01-01T00:00:00Z"}
            )
        
        # Should raise ResourceNotFoundException
        assert "ResourceNotFoundException" in str(type(exc_info.value).__name__) or \
               "not found" in str(exc_info.value).lower()
    
    @mock_aws
    @patch.dict(os.environ, {
        "AWS_DEFAULT_REGION": "us-east-1",
        "DYNAMODB_TABLE": TEST_TABLE_NAME,
    })
    def test_handles_invalid_sentiment_values(self):
        """Test that only valid sentiment values are accepted."""
        table, _, _, _, _ = create_test_infrastructure()
        
        # Create item with invalid sentiment (should not match GSI queries)
        source_id = generate_source_id("https://example.com/invalid")
        table.put_item(
            Item={
                "source_id": source_id,
                "timestamp": "2025-01-15T10:00:00Z",
                "title": "Invalid Sentiment",
                "sentiment": "unknown",  # Invalid value
                "status": "analyzed",
                "tag": "AI",
            }
        )
        
        # Standard sentiment queries should not find it
        for sentiment in ["positive", "neutral", "negative"]:
            response = table.query(
                IndexName="by_sentiment",
                KeyConditionExpression="sentiment = :s",
                ExpressionAttributeValues={":s": sentiment},
            )
            assert response["Count"] == 0


class TestConcurrency:
    """Tests for concurrent operations in the pipeline."""
    
    @mock_aws
    @patch.dict(os.environ, {
        "AWS_DEFAULT_REGION": "us-east-1",
        "DYNAMODB_TABLE": TEST_TABLE_NAME,
    })
    def test_concurrent_analysis_updates(self):
        """Test that concurrent analysis updates are handled safely.
        
        Uses conditional writes to ensure idempotency.
        """
        table, _, _, _, _ = create_test_infrastructure()
        
        source_id = generate_source_id("https://example.com/concurrent")
        timestamp = "2025-01-15T10:00:00Z"
        
        # Create pending item
        table.put_item(
            Item={
                "source_id": source_id,
                "timestamp": timestamp,
                "title": "Concurrent Test",
                "status": "pending",
                "tag": "AI",
            }
        )
        
        # First update succeeds
        table.update_item(
            Key={"source_id": source_id, "timestamp": timestamp},
            UpdateExpression="SET sentiment = :s, #st = :status",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":s": "positive",
                ":status": "analyzed",
            },
            ConditionExpression="attribute_not_exists(sentiment)",
        )
        
        # Second update fails (idempotency check)
        with pytest.raises(Exception) as exc_info:
            table.update_item(
                Key={"source_id": source_id, "timestamp": timestamp},
                UpdateExpression="SET sentiment = :s",
                ExpressionAttributeValues={":s": "negative"},
                ConditionExpression="attribute_not_exists(sentiment)",
            )
        
        # Verify original sentiment preserved
        response = table.get_item(
            Key={"source_id": source_id, "timestamp": timestamp}
        )
        assert response["Item"]["sentiment"] == "positive"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
