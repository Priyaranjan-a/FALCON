resource "aws_kms_key" "settlement_signing" {
  description              = "Signs daily settlement files"
  customer_master_key_spec = "RSA_2048"
  key_usage                = "SIGN_VERIFY"
  enable_key_rotation      = false
}

resource "aws_kms_key" "receipts_pq" {
  description = "Post-quantum receipt signing (pilot)"
  key_spec    = "ML_DSA_65"
  key_usage   = "SIGN_VERIFY"
}

resource "aws_kms_key" "card_data" {
  description         = "Envelope encryption for tokenised card data"
  enable_key_rotation = true
}

resource "aws_cloudhsm_v2_cluster" "payments" {
  hsm_type   = "hsm1.medium"
  subnet_ids = ["subnet-0a1b2c3d"]
}

resource "azurerm_key_vault_key" "dr_signing" {
  name         = "dr-signing"
  key_vault_id = "kv-payments-dr"
  key_type     = "RSA-HSM"
  key_size     = 3072
  key_opts     = ["sign", "verify"]
}

resource "google_kms_crypto_key" "analytics" {
  name     = "analytics-export"
  key_ring = "payments"
  purpose  = "ASYMMETRIC_SIGN"
  version_template {
    algorithm        = "EC_SIGN_P256_SHA256"
    protection_level = "HSM"
  }
}

resource "aws_lb_listener" "public" {
  load_balancer_arn = "arn:aws:elasticloadbalancing:ap-south-1:123456789012:loadbalancer/app/payments"
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-2016-08"
}
