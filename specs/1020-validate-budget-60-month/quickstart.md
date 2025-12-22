# Quickstart: Validate $60/Month Budget

## Prerequisites

- infracost CLI installed (`brew install infracost` or see [docs](https://www.infracost.io/docs/))
- AWS credentials configured
- Terraform initialized in `infrastructure/terraform/`

## Quick Validation

```bash
# Run cost analysis
make cost

# Expected output shows total monthly cost
# Must be under $60/month per SC-010
```

## Detailed Analysis

```bash
cd infrastructure/terraform

# Generate breakdown JSON
infracost breakdown --path . --format json > /tmp/cost-breakdown.json

# View summary
jq '.totalMonthlyCost' /tmp/cost-breakdown.json

# View by resource type
jq '.projects[].breakdown.resources[] | {name: .name, cost: .monthlyCost}' /tmp/cost-breakdown.json
```

## Verify Budget Compliance

| Check | Command | Expected |
| ----- | ------- | -------- |
| Total cost | `make cost` | Shows breakdown and total |
| Under budget | Visual check | Total < $60/month |
| By category | See detailed analysis | DynamoDB, Lambda, CloudWatch breakdown |

## Troubleshooting

**"infracost not found"**
```bash
brew install infracost
# or
curl -fsSL https://raw.githubusercontent.com/infracost/infracost/master/scripts/install.sh | sh
```

**"Terraform not initialized"**
```bash
cd infrastructure/terraform
terraform init
```

**"No cost data for on-demand resources"**
- Create `infracost-usage.yml` with usage estimates
- See [infracost usage docs](https://www.infracost.io/docs/features/usage_based_resources/)

## Output Location

After running `make cost`, the cost breakdown is documented in:
- Console output (summary)
- `docs/cost-breakdown.md` (detailed breakdown)

## Links

- [Spec](spec.md)
- [Plan](plan.md)
- [Research](research.md)
- [Parent Feature SC-010](../1009-realtime-multi-resolution/spec.md)
