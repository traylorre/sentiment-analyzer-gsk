# Research: Dynamic Dashboard Link Implementation

**Feature**: 010-dynamic-dashboard-link
**Date**: 2025-11-30

## Problem Statement

The interview dashboard needs to display:
1. A link to the live service dashboard that changes based on preprod/prod toggle
2. The last deployment date for the selected environment

Since the interview dashboard is a static HTML file hosted on GitHub Pages, we need a way to get dynamic deployment information.

## Options Evaluated

### Option 1: Hardcoded URLs Only (No Deployment Date)

**Approach**: Simply use the existing `ENVIRONMENTS` constant for links, skip deployment dates.

**Pros**:
- Simplest implementation
- No external dependencies
- Works offline

**Cons**:
- No deployment date shown
- User doesn't know how fresh the environment is

**Decision**: REJECTED - Missing key requirement (deployment date)

### Option 2: GitHub Actions API (Client-Side)

**Approach**: Use client-side JavaScript to fetch deployment info from GitHub API.

```javascript
// Example API call
fetch('https://api.github.com/repos/traylorre/sentiment-analyzer-gsk/actions/runs?workflow=deploy.yml&status=success&per_page=1')
```

**Pros**:
- Real-time data
- No CI/CD changes needed

**Cons**:
- GitHub API rate limits (60 req/hour unauthenticated)
- CORS issues possible
- Requires parsing workflow run data
- Can't distinguish preprod vs prod from workflow runs easily

**Decision**: REJECTED - Rate limits and complexity

### Option 3: CI/CD Generated Metadata (SELECTED)

**Approach**: During deploy workflow, generate a JSON file with deployment metadata and upload to S3.

```json
{
  "preprod": {
    "dashboard_url": "https://...",
    "last_deployed": "2025-11-30T14:30:00Z",
    "git_sha": "abc1234"
  },
  "prod": {
    "dashboard_url": "https://...",
    "last_deployed": "2025-11-30T15:45:00Z",
    "git_sha": "def5678"
  }
}
```

**Pros**:
- No API rate limits
- Clean separation of concerns
- Can include any metadata needed
- Fast client-side fetch

**Cons**:
- Requires S3 bucket with public read
- Adds step to deploy workflow

**Decision**: SELECTED - Best balance of reliability and features

### Option 4: Embed in HTML During CI

**Approach**: Modify `interview/index.html` during deploy to inject deployment dates.

**Pros**:
- No runtime fetch needed
- Works offline

**Cons**:
- Modifies source file in CI
- Complex merge if running parallel deploys
- HTML would show stale data until next deploy

**Decision**: REJECTED - Complexity and staleness issues

## Implementation Details for Selected Option

### S3 Bucket

- Use existing `preprod-sentiment-lambda-deployments` bucket
- Create `deployment-metadata.json` at bucket root
- Enable public read via bucket policy

### Deploy Workflow Changes

Add step after successful deployment:

```yaml
- name: Update Deployment Metadata
  run: |
    TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

    # Download existing metadata or create new
    aws s3 cp s3://${BUCKET}/deployment-metadata.json /tmp/metadata.json 2>/dev/null || echo '{}' > /tmp/metadata.json

    # Update for this environment
    jq --arg env "$ENV" \
       --arg url "$DASHBOARD_URL" \
       --arg ts "$TIMESTAMP" \
       --arg sha "$GITHUB_SHA" \
       '.[$env] = {"dashboard_url": $url, "last_deployed": $ts, "git_sha": $sha}' \
       /tmp/metadata.json > /tmp/metadata-new.json

    aws s3 cp /tmp/metadata-new.json s3://${BUCKET}/deployment-metadata.json \
      --content-type "application/json" \
      --acl public-read
```

### Interview Dashboard Changes

```javascript
const METADATA_URL = 'https://preprod-sentiment-lambda-deployments.s3.amazonaws.com/deployment-metadata.json';

async function fetchDeploymentMetadata() {
  try {
    const response = await fetch(METADATA_URL);
    return await response.json();
  } catch (error) {
    console.warn('Could not fetch deployment metadata:', error);
    return null;
  }
}

function updateDashboardLink(env, metadata) {
  const linkEl = document.getElementById('live-dashboard-link');
  const dateEl = document.getElementById('last-deployed');

  linkEl.href = ENVIRONMENTS[env];
  linkEl.target = '_blank';

  if (metadata && metadata[env]) {
    const date = new Date(metadata[env].last_deployed);
    dateEl.textContent = `Last deployed: ${date.toISOString().slice(0, 16).replace('T', ' ')} UTC`;
  } else {
    dateEl.textContent = '';
  }
}
```

## Alternatives Considered But Not Selected

### Use GitHub Pages Hosted JSON

Could host metadata as a JSON file in the repo's GitHub Pages. However, this would require updating the main branch with deployment info, creating a chicken-and-egg problem.

### Use Lambda Function URL

Could create a small Lambda that returns deployment metadata. However, this adds complexity for a simple use case.

## Conclusion

CI/CD generated metadata stored in S3 provides the best solution:
- Reliable and fast
- No rate limits
- Clean architecture
- Minimal changes to existing code
