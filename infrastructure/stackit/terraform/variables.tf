variable "project_id" {
  description = "STACKIT project ID."
  type        = string
  default     = "442855d5-308d-4e93-95ec-e1a959d6846a"
}

variable "region" {
  description = "STACKIT region. Only eu01 is generally available today."
  type        = string
  default     = "eu01"
}

variable "cluster_name" {
  description = "SKE cluster name. Hard 11-character limit imposed by the SKE API."
  type        = string
  default     = "udp-stackit"

  validation {
    condition     = length(var.cluster_name) <= 11
    error_message = "SKE cluster_name must be 11 characters or fewer."
  }
}

variable "kubernetes_version_min" {
  description = "Kubernetes version. SKE accepts specific versions (not floors); check `stackit ske options --project-id <id>` for available. As of 2026-05: 1.33.11, 1.34.7, 1.35.4."
  type        = string
  default     = "1.34.7"
}

variable "node_pool_name" {
  description = "Name of the default node pool."
  type        = string
  default     = "default"
}

variable "node_machine_type" {
  description = "StackIT machine flavor for worker nodes. g2i.8 = 8 vCPU / 32 GB (parity with AKS Standard_D8s_v5)."
  type        = string
  default     = "g2i.8"
}

variable "node_minimum" {
  description = "Minimum nodes in the pool (autoscaler lower bound)."
  type        = number
  default     = 3
}

variable "node_maximum" {
  description = "Maximum nodes in the pool (autoscaler upper bound)."
  type        = number
  default     = 6
}

variable "node_availability_zones" {
  description = "Availability zones for node pool. Single-AZ keeps cost down; use [\"eu01-1\",\"eu01-2\",\"eu01-3\"] for HA."
  type        = list(string)
  default     = ["eu01-3"]
}

variable "node_volume_type" {
  description = "Block storage class for node OS disk. storage_premium_perf6 ~ 16 KIOPS, matches AKS managed-csi-premium."
  type        = string
  default     = "storage_premium_perf6"
}

variable "node_volume_size_gb" {
  description = "OS disk size per node."
  type        = number
  default     = 100
}

variable "kubeconfig_expiration_seconds" {
  description = "Validity of the generated admin kubeconfig. Re-run `terraform apply` to mint a fresh one after expiry."
  type        = number
  default     = 86400
}

variable "kubeconfig_path" {
  description = "Where the kubeconfig file is written, relative to this module."
  type        = string
  default     = "kubeconfig.yaml"
}

variable "labels" {
  description = "Labels applied to created StackIT resources."
  type        = map(string)
  default = {
    project     = "odap-data-platform"
    environment = "dev"
    managed_by  = "terraform"
  }
}
