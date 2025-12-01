# Feature 010: Dynamic Dashboard Link

## Overview

Add a dynamic "View Live Dashboard" link to the interview dashboard that updates based on the preprod/prod environment toggle. The link should point to the service dashboard for the currently selected environment and display the last deployment date for that environment.

## Clarifications

### Session 2025-11-30
- Q: Which approach for obtaining deployment metadata? → A: CI/CD generated metadata stored in S3 (Option B)

## User Story

As a technical interviewer demonstrating the Sentiment Analyzer,
I want to see a link to the actual live service dashboard that updates when I toggle between preprod/prod environments,
so that I can quickly navigate to the real service and show when it was last deployed.

## Requirements

### Functional Requirements

1. **Dynamic Dashboard Link**
   - Add a clickable link/button labeled "View Live Dashboard" in the interview dashboard header
   - The link URL should change dynamically when the preprod/prod toggle is triggered
   - For preprod: Link should point to the preprod CloudFront/Lambda URL
   - For prod: Link should point to the prod CloudFront/Lambda URL

2. **Last Deployed Date Display**
   - Display the date and time of the last successful deployment for the selected environment
   - Format: "Last deployed: YYYY-MM-DD HH:MM UTC"
   - The date should update when the environment toggle changes

3. **Deployment Information Source**
   - Obtain deployment information from GitHub Actions API using `gh run list`
   - Query the deploy.yml workflow runs for the corresponding environment
   - Extract the completion timestamp from the most recent successful run

4. **Environment-Specific URLs**
   - preprod: Current URL from `ENVIRONMENTS.preprod` constant
   - prod: Current URL from `ENVIRONMENTS.prod` constant (may differ from Lambda URL)

### Non-Functional Requirements

1. **UX**
   - Link should be visually distinct but not distracting
   - Loading state while fetching deployment date (initial load only)
   - Error handling if GitHub API is unavailable (show link without date)

2. **Performance**
   - Cache deployment dates to avoid repeated API calls
   - Only refresh on toggle change or explicit refresh action

## Technical Approach

**Decision: CI/CD Generated Metadata (Option B)**

During the deploy workflow, generate a JSON metadata file with deployment info and store it in S3. The interview dashboard fetches this metadata client-side on load and toggle events.

Rationale:
- Avoids GitHub API rate limits (60 req/hour unauthenticated)
- Provides consistent, structured data format
- Aligns with existing AWS infrastructure patterns
- S3 offers reliable, low-latency access

## Implementation Notes

- The interview dashboard is at `interview/index.html`
- Currently has an environment toggle at lines 585-588 with preprod/prod buttons
- The `initEnvToggle()` function at line 1542 handles toggle events
- Dashboard URLs are in the `ENVIRONMENTS` constant at lines 1500-1503

## Acceptance Criteria

- [ ] Interview dashboard has a "View Live Dashboard" link visible in the header
- [ ] Link URL changes when preprod/prod toggle is clicked
- [ ] Last deployment date is displayed next to the link
- [ ] Date updates when toggle changes environments
- [ ] Link opens in a new tab
- [ ] Graceful degradation if deployment date cannot be fetched
