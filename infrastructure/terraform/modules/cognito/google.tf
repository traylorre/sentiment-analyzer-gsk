# Google OAuth Identity Provider for Cognito
#
# Prerequisites:
# 1. Create OAuth credentials in Google Cloud Console
# 2. Store client_id and client_secret in Secrets Manager
# 3. Add callback URL: https://{domain}.auth.{region}.amazoncognito.com/oauth2/idpresponse

resource "aws_cognito_identity_provider" "google" {
  count = var.google_client_id != "" ? 1 : 0

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
