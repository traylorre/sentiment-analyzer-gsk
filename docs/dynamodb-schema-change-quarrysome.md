# DynamoDB subscription schema change: adjacency-list pattern for streaming consumers

> **QUARRYSOME**: unaudited; verify against code before trusting.

Ingested design proposal, operator-supplied, adjudicated as current pending work: not
implemented, and nothing in the live path supersedes it. It targets the many-to-many problem of
streaming consumers subscribed to multiple tags and is expected to change the DynamoDB table
schema, the caching strategy, and the routes. Connection tracking is in-memory in the SSE
streaming Lambda today and no per-topic subscription rows exist. SSE implementation work is
deferred by standing owner constraint; building this needs that constraint lifted and owner
sign-off for the GSI.

## The problem

One connection subscribes to multiple tags (conn_123 wants AAPL, TSLA, GOOG) and one tag has
thousands of connected clients. Storing tags as a List attribute inside a single connection item
cannot be queried through an index; every "who subscribes to AAPL" lookup becomes a full table
Scan, which is slow, expensive, and fails at scale.

## The design: one item per subscription, plus a GSI

Base table: partition key `PK` (string), sort key `SK` (string).
GSI1: partition key `GSI1PK` (string), sort key `GSI1SK` (string).

Client conn_123 subscribes to AAPL and TSLA; conn_456 subscribes to AAPL:

| PK | SK | GSI1PK | GSI1SK | Attributes |
|---|---|---|---|---|
| CONN#conn_123 | METADATA | USER#user_abc | CONN#conn_123 | connected_at |
| CONN#conn_123 | SUB#AAPL | TOPIC#AAPL | CONN#conn_123 | subscribed_at |
| CONN#conn_123 | SUB#TSLA | TOPIC#TSLA | CONN#conn_123 | subscribed_at |
| CONN#conn_456 | METADATA | USER#user_xyz | CONN#conn_456 | connected_at |
| CONN#conn_456 | SUB#AAPL | TOPIC#AAPL | CONN#conn_456 | subscribed_at |

## Access pattern 1: an update for AAPL arrives; who receives it?

Query GSI1 where `GSI1PK = TOPIC#AAPL`. DynamoDB returns only the matching subscription rows
(`CONN#conn_123`, `CONN#conn_456`). The publisher iterates those connection ids and pushes to
each target connection.

## Access pattern 2: conn_123 disconnected; clean up its state

Query the base table where `PK = CONN#conn_123`. DynamoDB returns every row for that connection
(METADATA plus each SUB#) in one query, without knowing the topics in advance. Delete them all
with a single BatchWriteItem.

## Why this shape

Decoupling connections into individual subscription records behind a GSI avoids scans, prevents
hot partitions, and serves both primary workflows (push by topic, clean up on disconnect) as
single Query operations.

## Build preconditions

- Compare against the live SSE path before implementing: connection tracking is currently
  in-memory in the SSE streaming Lambda, and no per-topic subscription rows exist. Establish
  what the live fan-out actually does and where it breaks under multiple consumers with
  overlapping tag sets.
- Decide the blast radius: table schema (new PK/SK shapes and GSI), caching (what per-topic
  lookups make cacheable or redundant), and routes (subscribe/unsubscribe surface).
- No new AWS resources without owner sign-off; a GSI on an existing table needs that
  conversation.
