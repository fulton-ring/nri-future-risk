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
variable "bucket_prefix" {
  type    = string
  default = "future-risk-index"
}
variable "publisher_staging_bucket" {
  type        = string
  description = "Existing external publication staging bucket; this module does not create it."
}


variable "network" {
  type        = string
  description = "Existing VPC resource path for private Batch VMs."
}

variable "subnetwork" {
  type        = string
  description = "Existing regional subnet with Private Google Access enabled."
}
