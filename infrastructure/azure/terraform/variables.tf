variable "subscription_id" {
  description = "Azure subscription ID."
  type        = string
}

variable "tenant_id" {
  description = "Azure AD tenant ID."
  type        = string
}

variable "resource_group_name" {
  description = "Existing resource group that will hold the AKS cluster."
  type        = string
  default     = "dev-stackable-rg"
}

variable "location" {
  description = "Azure region. Must match the existing resource group."
  type        = string
  default     = "westeurope"
}

variable "cluster_name" {
  description = "AKS cluster name."
  type        = string
  default     = "odap-platform-aks"
}

variable "dns_prefix" {
  description = "DNS prefix for the AKS API server."
  type        = string
  default     = "odap-platform"
}

variable "node_count" {
  description = "Number of nodes in the default (system) node pool. Burstable B-series is fine here; user workloads run on the 'user' pool."
  type        = number
  default     = 2
}

variable "node_vm_size" {
  description = <<-DESC
    VM size for the default (system) node pool. We use burstable B-series
    by default (~70% cheaper than D-series for dev/test workloads). Override
    to Dsv5/Dsv6 for steady-state production load.
  DESC
  type        = string
  default     = "Standard_B4ms"
}

# ---- User node pool (workloads) ----

variable "user_pool_enabled" {
  description = "Provision a separate 'user' node pool for application workloads (recommended). System pool then only runs kube-system / CoreDNS / metrics-server."
  type        = bool
  default     = true
}

variable "user_pool_vm_size" {
  description = "VM size for the user node pool. B8ms (8 vCPU / 32 GiB) burstable fits the Stackable+OM stack comfortably."
  type        = string
  default     = "Standard_B8ms"
}

variable "user_pool_min_count" {
  description = "Minimum nodes in the user pool (autoscaler floor)."
  type        = number
  default     = 1
}

variable "user_pool_max_count" {
  description = "Maximum nodes in the user pool (autoscaler ceiling)."
  type        = number
  default     = 4
}

# ---- Spot node pool (optional, batch workloads) ----

variable "spot_pool_enabled" {
  description = "Provision a Spot node pool with NoSchedule taint 'workload=batch'. Pods that tolerate it can use cheap (70-90% off) preemptible nodes for Spark executors / dbt runs."
  type        = bool
  default     = false
}

variable "spot_pool_vm_size" {
  description = "VM size for the Spot node pool."
  type        = string
  default     = "Standard_D4s_v5"
}

variable "spot_pool_max_price" {
  description = "Maximum hourly price (USD) for spot nodes. -1 = up to on-demand price (recommended)."
  type        = number
  default     = -1
}

variable "spot_pool_min_count" {
  description = "Minimum nodes in the spot pool."
  type        = number
  default     = 0
}

variable "spot_pool_max_count" {
  description = "Maximum nodes in the spot pool."
  type        = number
  default     = 3
}

variable "node_os_disk_size_gb" {
  description = "OS disk size per node."
  type        = number
  default     = 128
}

variable "kubernetes_version" {
  description = "AKS Kubernetes version. Empty = pick latest GA in the region (default_version)."
  type        = string
  default     = ""
}

variable "sp_client_id" {
  description = "Service principal client ID used as AKS cluster identity."
  type        = string
}

variable "sp_client_secret" {
  description = "Service principal client secret. Pass via TF_VAR_sp_client_secret env var, never commit."
  type        = string
  sensitive   = true
}

variable "tags" {
  description = "Tags applied to all created resources."
  type        = map(string)
  default = {
    project     = "odap-data-platform"
    environment = "dev"
    managed_by  = "terraform"
    purpose     = "reference-implementation"
  }
}

