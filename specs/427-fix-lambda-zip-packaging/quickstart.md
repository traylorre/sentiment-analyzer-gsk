# Quickstart: Fix Lambda ZIP Packaging Structure

**Feature**: 427-fix-lambda-zip-packaging
**Date**: 2025-12-18

## Overview

Fix the Lambda ZIP packaging in `.github/workflows/deploy.yml` to preserve the `src/lambdas/<name>/` directory structure required by absolute imports.

## Prerequisites

- Access to sentiment-analyzer-gsk repository
- On branch `427-fix-lambda-zip-packaging`
- Docker-import validator available in terraform-gsk-template

## Fix Pattern

For each affected Lambda, update the copy command:

```yaml
# BEFORE (broken - flat copy)
cp -r src/lambdas/<name>/* packages/<name>-build/

# AFTER (fixed - structured copy)
mkdir -p packages/<name>-build/src/lambdas/<name>
cp -r src/lambdas/<name>/* packages/<name>-build/src/lambdas/<name>/
```

## Affected Lambdas

| Lambda | Line | Fix Required |
|--------|------|--------------|
| ingestion | 157 | YES |
| analysis | ~270 | CHECK |
| metrics | ~310 | CHECK |
| notification | ~360 | CHECK |
| dashboard | ~225 | NO (correct) |

## Implementation Steps

1. **Edit deploy.yml**: Apply fix pattern to each affected Lambda
2. **Validate locally**: Run docker-import validator
3. **Commit and push**: Create PR with fix
4. **Monitor pipeline**: Watch for deployment success
5. **Test Lambda**: Invoke each Lambda to verify no import errors

## Validation Commands

```bash
# Run docker-import validator (from terraform-gsk-template)
python3 -c "
from pathlib import Path
from src.validators.docker_import import DockerImportValidator
validator = DockerImportValidator()
result = validator.validate(Path('/home/traylorre/projects/sentiment-analyzer-gsk'))
lpk_findings = [f for f in result.findings if f.id.startswith('LPK-')]
print(f'LPK findings: {len(lpk_findings)}')
for f in lpk_findings[:5]:
    print(f'  [{f.id}] {f.file}:{f.line}')
"

# Test Lambda invocation (after deployment)
aws lambda invoke --function-name preprod-sentiment-ingestion /tmp/response.json
cat /tmp/response.json
```

## Success Criteria

1. Docker-import validator reports 0 LPK-003 findings
2. All Lambdas invoke without ImportModuleError
3. E2E tests pass in preprod
