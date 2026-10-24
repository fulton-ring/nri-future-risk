variable "project" { type = string }
variable "region" {
  type    = string
  default = "us-central1"
}
variable "github_repository" {
  type    = string
  default = "fulton-ring/nri-future-risk"
}
variable "github_repository_id" {
  type        = string
  description = "Numeric GitHub repository ID; protects against name reuse."
}
variable "transform_service_account" {
  type        = string
  description = "Existing HIFLD Next transform/publisher service account email."
}

variable "network" {
  type        = string
  description = "Existing VPC resource path for private Batch VMs."
}

variable "subnetwork" {
  type        = string
  description = "Existing regional subnet with Private Google Access enabled."
}
