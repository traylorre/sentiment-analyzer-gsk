"""Hypothesis strategies for property testing.

Provides reusable composite strategies for generating test data
that matches the sentiment analyzer's data contracts.
"""

from hypothesis import strategies as st


@st.composite
def lambda_response(draw, status_codes=None):
    """Generate valid Lambda proxy integration response.

    Args:
        draw: Hypothesis draw function
        status_codes: Optional list of status codes to sample from

    Returns:
        dict: Valid Lambda proxy response structure
    """
    if status_codes is None:
        status_codes = [200, 201, 400, 403, 404, 500]

    return {
        "statusCode": draw(st.sampled_from(status_codes)),
        "headers": {
            "Content-Type": "application/json",
            "X-Request-ID": draw(st.uuids().map(str)),
        },
        "body": draw(st.text(min_size=0, max_size=1000)),
    }


@st.composite
def sentiment_response(draw):
    """Generate sentiment analysis response with valid score ranges.

    Returns:
        dict: Sentiment response with score in [-1.0, 1.0] and confidence in [0.0, 1.0]
    """
    return {
        "sentiment": draw(st.sampled_from(["positive", "negative", "neutral"])),
        "score": draw(st.floats(min_value=-1.0, max_value=1.0, allow_nan=False)),
        "confidence": draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False)),
    }


@st.composite
def iam_policy_resource_pattern(draw):
    """Generate IAM policy resource ARN patterns.

    Returns:
        str: Valid ARN pattern for IAM policy resources
    """
    service = draw(st.sampled_from(["sqs", "sns", "lambda", "dynamodb", "cloudwatch"]))
    region = draw(st.sampled_from(["us-east-1", "us-west-2", "*"]))
    account = draw(st.sampled_from(["123456789012", "*"]))
    name_pattern = draw(
        st.sampled_from(["*-sentiment-*", "preprod-sentiment-*", "prod-sentiment-*"])
    )

    return f"arn:aws:{service}:{region}:{account}:{name_pattern}"


@st.composite
def alarm_name(draw, environments=None):
    """Generate CloudWatch alarm names following naming convention.

    Args:
        environments: Optional list of environments to sample from

    Returns:
        str: Alarm name following {env}-sentiment-* pattern
    """
    if environments is None:
        environments = ["dev", "preprod", "prod"]

    env = draw(st.sampled_from(environments))
    component = draw(
        st.sampled_from(
            [
                "lambda-errors",
                "dynamodb-throttles",
                "api-latency-high",
                "dlq-depth-exceeded",
            ]
        )
    )

    return f"{env}-sentiment-{component}"


@st.composite
def dynamodb_item(draw):
    """Generate valid DynamoDB item for sentiment-items table.

    Returns:
        dict: Item matching sentiment-items table schema
    """
    return {
        "source_id": draw(
            st.text(
                min_size=1,
                max_size=100,
                alphabet=st.characters(
                    whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_"
                ),
            )
        ),
        "timestamp": draw(st.datetimes().map(lambda dt: dt.isoformat() + "Z")),
        "sentiment": draw(st.sampled_from(["positive", "negative", "neutral"])),
        "score": draw(st.floats(min_value=-1.0, max_value=1.0, allow_nan=False)),
        "confidence": draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False)),
        "status": draw(st.sampled_from(["pending", "analyzed"])),
    }
