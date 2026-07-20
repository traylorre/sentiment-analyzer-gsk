# Google OAuth Identity Provider for Cognito
#
# Prerequisites:
# 1. Create OAuth credentials in Google Cloud Console
# 2. Store client_id and client_secret in Secrets Manager
# 3. Add callback URL: https://{domain}.auth.{region}.amazoncognito.com/oauth2/idpresponse

# count gates on the STATIC enabled_identity_providers list (plan-time known).
# It must NOT depend on google_client_id, which is sourced from a Secrets
# Manager data source and is unknown until apply — Terraform forbids
# count/for_each depending on apply-time-unknown values. The client_id value
# still flows into provider_details below, where apply-time-unknown is allowed.
resource "aws_cognito_identity_provider" "google" {
  count = contains([for p in var.enabled_identity_providers : lower(p)], "google") ? 1 : 0

  user_pool_id  = aws_cognito_user_pool.main.id
  provider_name = "Google"
  provider_type = "Google"

  provider_details = {
    client_id        = var.google_client_id
    client_secret    = var.google_client_secret
    authorize_scopes = "email profile openid"
  }

  # Map Google attributes to Cognito attributes
  attribute_mapping = {
    email    = "email"
    username = "sub"
  }

  lifecycle {
    # Don't destroy and recreate if only secrets change
    ignore_changes = [provider_details["client_secret"]]
  }
}
