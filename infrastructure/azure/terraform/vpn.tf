# ---- Self-signed root CA (used by Azure VPN Gateway to verify clients) ----
#
# Terraform generates a long-lived root cert; the public part is uploaded to
# the gateway, the private key stays in tf state. For a real shared environment
# you'd swap this for a real PKI integration.

resource "tls_private_key" "vpn_root" {
  count     = var.vpn_gateway_enabled ? 1 : 0
  algorithm = "RSA"
  rsa_bits  = 2048
}

resource "tls_self_signed_cert" "vpn_root" {
  count           = var.vpn_gateway_enabled ? 1 : 0
  private_key_pem = tls_private_key.vpn_root[0].private_key_pem

  subject {
    common_name  = "Platform VPN Root CA"
    organization = "Open Data & Analytics Platform"
  }

  is_ca_certificate     = true
  validity_period_hours = 87600 # 10 years

  allowed_uses = [
    "cert_signing",
    "key_encipherment",
    "digital_signature",
  ]
}

# ---- Per-laptop client cert ----
#
# Signed by the root CA above. Get installed in the user's Windows cert store
# (Personal). Azure VPN Gateway then trusts any cert chained to the uploaded
# root CA.

resource "tls_private_key" "vpn_client" {
  count     = var.vpn_gateway_enabled ? 1 : 0
  algorithm = "RSA"
  rsa_bits  = 2048
}

resource "tls_cert_request" "vpn_client" {
  count           = var.vpn_gateway_enabled ? 1 : 0
  private_key_pem = tls_private_key.vpn_client[0].private_key_pem

  subject {
    common_name  = "odap-platform-vpn-client"
    organization = "Open Data & Analytics Platform"
  }
}

resource "tls_locally_signed_cert" "vpn_client" {
  count              = var.vpn_gateway_enabled ? 1 : 0
  cert_request_pem   = tls_cert_request.vpn_client[0].cert_request_pem
  ca_private_key_pem = tls_private_key.vpn_root[0].private_key_pem
  ca_cert_pem        = tls_self_signed_cert.vpn_root[0].cert_pem

  validity_period_hours = 8760 # 1 year

  allowed_uses = [
    "client_auth",
    "digital_signature",
    "key_encipherment",
  ]
}

# Write certs + keys to disk so the user can package them as PFX for Windows.
resource "local_sensitive_file" "vpn_root_cert" {
  count    = var.vpn_gateway_enabled ? 1 : 0
  filename = "${var.vpn_client_cert_export_dir}/root.crt"
  content  = tls_self_signed_cert.vpn_root[0].cert_pem
}

resource "local_sensitive_file" "vpn_root_key" {
  count           = var.vpn_gateway_enabled ? 1 : 0
  filename        = "${var.vpn_client_cert_export_dir}/root.key"
  content         = tls_private_key.vpn_root[0].private_key_pem
  file_permission = "0600"
}

resource "local_sensitive_file" "vpn_client_cert" {
  count    = var.vpn_gateway_enabled ? 1 : 0
  filename = "${var.vpn_client_cert_export_dir}/client.crt"
  content  = tls_locally_signed_cert.vpn_client[0].cert_pem
}

resource "local_sensitive_file" "vpn_client_key" {
  count           = var.vpn_gateway_enabled ? 1 : 0
  filename        = "${var.vpn_client_cert_export_dir}/client.key"
  content         = tls_private_key.vpn_client[0].private_key_pem
  file_permission = "0600"
}

# ---- VPN Gateway public IP ----

resource "azurerm_public_ip" "vpn" {
  count               = var.vpn_gateway_enabled ? 1 : 0
  name                = "${var.cluster_name}-vpn-pip"
  location            = data.azurerm_resource_group.rg.location
  resource_group_name = data.azurerm_resource_group.rg.name
  # Basic Public IP SKU was retired 2025-03; new VPN Gateways require
  # Standard SKU with Static allocation. AZ-SKU VPN Gateways additionally
  # require the Public IP to be zone-redundant (zones 1+2+3).
  allocation_method = "Static"
  sku               = "Standard"
  zones             = ["1", "2", "3"]
  tags              = var.tags
}

# ---- Strip the PEM headers/footers + base64 newlines so the cert PEM
#      becomes the single-line DER-as-base64 that Azure expects in
#      vpn_client_configuration.root_certificate.public_cert_data ----
locals {
  vpn_root_cert_b64 = var.vpn_gateway_enabled ? replace(replace(replace(
    tls_self_signed_cert.vpn_root[0].cert_pem,
    "-----BEGIN CERTIFICATE-----", ""),
    "-----END CERTIFICATE-----", ""),
  "\n", "") : ""

  aks_vnet_address_space = var.vpn_gateway_enabled ? data.azurerm_virtual_network.aks_vnet[0].address_space : []
}

# ---- VPN Gateway ----

resource "azurerm_virtual_network_gateway" "vpn" {
  count               = var.vpn_gateway_enabled ? 1 : 0
  name                = "${var.cluster_name}-vpn-gw"
  location            = data.azurerm_resource_group.rg.location
  resource_group_name = data.azurerm_resource_group.rg.name

  type     = "Vpn"
  vpn_type = "RouteBased"

  active_active = false
  bgp_enabled   = false
  sku           = var.vpn_gateway_sku

  ip_configuration {
    name                          = "vnetGatewayConfig"
    public_ip_address_id          = azurerm_public_ip.vpn[0].id
    private_ip_address_allocation = "Dynamic"
    subnet_id                     = azurerm_subnet.gateway[0].id
  }

  vpn_client_configuration {
    address_space = var.vpn_client_address_pool

    # VpnGw1+ supports OpenVPN/IKEv2/SSTP. We enable IKEv2 + OpenVPN —
    # IKEv2 works with Windows built-in client, OpenVPN works with the
    # Azure VPN Client (Microsoft Store) and any OpenVPN client on macOS/Linux.
    vpn_client_protocols = ["IkeV2", "OpenVPN"]

    root_certificate {
      name             = "odap-platform-vpn-root"
      public_cert_data = local.vpn_root_cert_b64
    }
  }

  tags = var.tags

  # VPN Gateway provisioning is slow (30-45 min). Use longer timeouts.
  timeouts {
    create = "60m"
    update = "60m"
    delete = "30m"
  }
}
