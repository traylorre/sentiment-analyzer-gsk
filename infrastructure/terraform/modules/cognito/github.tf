# GitHub OAuth Identity Provider for Cognito
#
# GitHub uses OIDC (OpenID Connect) integration with Cognito.
#
# Prerequisites:
# 1. Create OAuth App in GitHub Developer Settings
# 2. Store client_id and client_secret in Secrets Manager
# 3. Add callback URL: https://{domain}.auth.{region}.amazoncognito.com/oauth2/idpresponse

resource "aws_cognito_identity_provider" "github" {
  count = var.github_client_id != "" ? 1 : 0

  user_pool_id  = aws_cognito_user_pool.main.id
  provider_name = "GitHub"
  provider_type = "OIDC"

  provider_details = {
    client_id                 = var.github_client_id
    client_secret             = var.github_client_secret
    authorize_scopes          = "openid user:email"
    attributes_request_method = "GET"
    oidc_issuer               = "https://token.actions.githubusercontent.com"
    authorize_url             = "https://github.com/login/oauth/authorize"
    token_url                 = "https://github.com/login/oauth/access_token"
    attributes_url            = "https://api.github.com/user"
    jwks_uri                  = "https://token.actions.githubusercontent.com/.well-known/jwks"
  }

  # Map GitHub attributes to Cognito attributes
  attribute_mapping = {
    email    = "email"
    username = "sub"
  }

  lifecycle {
    # Don't destroy and recreate if only secrets change
    ignore_changes = [provider_details["client_secret"]]
  }
}
