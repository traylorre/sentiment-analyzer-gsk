# Quickstart: Dynamic Dashboard Link

## Overview

This feature adds a dynamic link from the interview dashboard to the live service dashboard, with environment-aware URLs and last-deployed dates.

## Files to Modify

1. **`interview/index.html`** - Add link element and JavaScript functions
2. **`.github/workflows/deploy.yml`** - Add metadata generation step
3. **`tests/unit/interview/test_interview_html.py`** - Add tests for new elements

## Step-by-Step Implementation

### Step 1: Add HTML Elements (interview/index.html)

Add after the timer/env-toggle section in header (around line 580):

```html
<div style="display: flex; align-items: center; gap: 8px; margin-right: 16px;">
    <a id="live-dashboard-link" href="#" target="_blank" class="btn btn-secondary" style="padding: 6px 12px; font-size: 12px; text-decoration: none;">
        View Live Dashboard
    </a>
    <span id="last-deployed" style="font-size: 11px; color: var(--text-muted);"></span>
</div>
```

### Step 2: Add JavaScript Functions (interview/index.html)

Add after the `ENVIRONMENTS` constant (around line 1500):

```javascript
// Deployment metadata URL (S3 bucket with public read)
const METADATA_URL = 'https://preprod-sentiment-lambda-deployments.s3.amazonaws.com/deployment-metadata.json';

// Cache for deployment metadata
let deploymentMetadata = null;

// Fetch deployment metadata from S3
async function fetchDeploymentMetadata() {
    if (deploymentMetadata) return deploymentMetadata;

    try {
        const response = await fetch(METADATA_URL + '?t=' + Date.now());
        if (!response.ok) throw new Error('Failed to fetch metadata');
        deploymentMetadata = await response.json();
        return deploymentMetadata;
    } catch (error) {
        console.warn('Could not fetch deployment metadata:', error);
        return null;
    }
}

// Update dashboard link and deployment date
function updateDashboardLink(env, metadata) {
    const linkEl = document.getElementById('live-dashboard-link');
    const dateEl = document.getElementById('last-deployed');

    // Always update the link URL
    linkEl.href = ENVIRONMENTS[env];

    if (metadata && metadata[env]) {
        const date = new Date(metadata[env].last_deployed);
        const formatted = date.toISOString().slice(0, 16).replace('T', ' ');
        dateEl.textContent = `Deployed: ${formatted} UTC`;
    } else {
        dateEl.textContent = '';
    }
}
```

### Step 3: Modify initEnvToggle Function

Update the `initEnvToggle` function to call metadata update:

```javascript
function initEnvToggle() {
    // Fetch metadata on initial load
    fetchDeploymentMetadata().then(metadata => {
        updateDashboardLink(currentEnv, metadata);
    });

    document.querySelectorAll('.env-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            document.querySelectorAll('.env-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentEnv = btn.dataset.env;
            showToast(`Switched to ${currentEnv}`, 'success');
            fetchHealthStats();

            // Update dashboard link
            const metadata = await fetchDeploymentMetadata();
            updateDashboardLink(currentEnv, metadata);
        });
    });
}
```

### Step 4: Add Metadata Generation to Deploy Workflow

In `.github/workflows/deploy.yml`, add after the `Get Preprod Outputs` step:

```yaml
- name: Update Deployment Metadata
  run: |
    ENV="${{ matrix.environment || 'preprod' }}"
    BUCKET="preprod-sentiment-lambda-deployments"
    DASHBOARD_URL="${{ steps.outputs.outputs.dashboard_url }}"
    TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    SHA="${GITHUB_SHA:0:7}"

    echo "Updating deployment metadata for ${ENV}..."

    # Download existing metadata or create empty
    aws s3 cp s3://${BUCKET}/deployment-metadata.json /tmp/metadata.json 2>/dev/null || echo '{}' > /tmp/metadata.json

    # Update metadata for this environment
    jq --arg env "$ENV" \
       --arg url "$DASHBOARD_URL" \
       --arg ts "$TIMESTAMP" \
       --arg sha "$SHA" \
       '.[$env] = {"dashboard_url": $url, "last_deployed": $ts, "git_sha": $sha}' \
       /tmp/metadata.json > /tmp/metadata-new.json

    # Upload with public read
    aws s3 cp /tmp/metadata-new.json s3://${BUCKET}/deployment-metadata.json \
      --content-type "application/json"

    echo "Metadata updated: $(cat /tmp/metadata-new.json)"
```

### Step 5: Add Unit Tests

Add to `tests/unit/interview/test_interview_html.py`:

```python
class TestDashboardLink:
    """Tests for live dashboard link feature."""

    def test_dashboard_link_exists(self):
        """Live dashboard link element should exist."""
        content = get_html_content()
        assert 'id="live-dashboard-link"' in content

    def test_last_deployed_element_exists(self):
        """Last deployed date element should exist."""
        content = get_html_content()
        assert 'id="last-deployed"' in content

    def test_fetch_deployment_metadata_function(self):
        """fetchDeploymentMetadata function should be defined."""
        content = get_html_content()
        assert "function fetchDeploymentMetadata" in content

    def test_update_dashboard_link_function(self):
        """updateDashboardLink function should be defined."""
        content = get_html_content()
        assert "function updateDashboardLink" in content

    def test_metadata_url_defined(self):
        """Metadata URL constant should be defined."""
        content = get_html_content()
        assert "METADATA_URL" in content
```

## Testing Locally

1. Open `interview/index.html` in a browser
2. Check that "View Live Dashboard" link appears in header
3. Click toggle between preprod/prod and verify link changes
4. If metadata is available, verify date displays

## Deployment

After merging to main:
1. Deploy workflow runs automatically
2. Metadata JSON is created/updated in S3
3. Interview dashboard fetches metadata on load
4. Users see current deployment info

## Troubleshooting

- **No deployment date shown**: Check S3 bucket has `deployment-metadata.json` with public read
- **CORS error**: Ensure S3 bucket CORS policy allows requests from GitHub Pages domain
- **Link doesn't update**: Check browser console for JavaScript errors
