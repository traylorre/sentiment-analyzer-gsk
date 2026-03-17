/**
 * DynamoDB helper for extracting magic link tokens in E2E tests (Feature 1223, R2).
 *
 * Queries DynamoDB directly for the most recent unused magic link token
 * for a given email address. Used because we don't have MailSlurp yet
 * (see Issue #731 for future email service integration).
 */

import { DynamoDBClient, QueryCommand } from '@aws-sdk/client-dynamodb';
import { unmarshall } from '@aws-sdk/util-dynamodb';

const REGION = process.env.AWS_REGION || 'us-east-1';
const TABLE_NAME = process.env.USERS_TABLE || 'preprod-sentiment-users';

/**
 * Query DynamoDB for the most recent unused magic link token for an email.
 *
 * @param email - The email address to find the token for
 * @returns The token ID (without TOKEN# prefix) or null if not found
 */
export async function getMagicLinkToken(email: string): Promise<string | null> {
  const client = new DynamoDBClient({ region: REGION });

  const command = new QueryCommand({
    TableName: TABLE_NAME,
    IndexName: 'by_email',
    KeyConditionExpression: 'email = :email',
    FilterExpression: 'begins_with(PK, :prefix) AND used = :unused',
    ExpressionAttributeValues: {
      ':email': { S: email },
      ':prefix': { S: 'TOKEN#' },
      ':unused': { BOOL: false },
    },
    ScanIndexForward: false, // Most recent first
    Limit: 1,
  });

  const response = await client.send(command);
  const items = response.Items || [];

  if (items.length === 0) {
    return null;
  }

  const item = unmarshall(items[0]);
  // PK format: TOKEN#{token_id}
  const pk = item.PK as string;
  return pk.startsWith('TOKEN#') ? pk.slice(6) : pk;
}
