output "cluster_name" {
  value = stackit_ske_cluster.cluster.name
}

output "kubernetes_version_used" {
  value = stackit_ske_cluster.cluster.kubernetes_version_used
}

output "egress_address_ranges" {
  description = "Outbound NAT ranges for the cluster — add these to allowlists on external systems."
  value       = stackit_ske_cluster.cluster.egress_address_ranges
}

output "floating_ip" {
  description = "Reserved Floating IP. Paste into DNS A records for example.com + *.example.com, and into ingress-nginx values-stackit.yaml as loadBalancerIP."
  value       = stackit_public_ip.platform_ingress.ip
}

output "kubeconfig_path" {
  description = "Path to the admin kubeconfig file. Set KUBECONFIG=$(terraform output -raw kubeconfig_absolute_path)."
  value       = local_file.kubeconfig.filename
}

output "kubeconfig_absolute_path" {
  value = abspath(local_file.kubeconfig.filename)
}

output "kubeconfig_expires_at" {
  value = stackit_ske_kubeconfig.admin.expires_at
}
