output "github_variables" {
  value = {
    FRI_GCP_PROJECT                 = var.project
    FRI_GCP_REGION                  = var.region
    FRI_NETWORK                     = var.network
    FRI_SUBNETWORK                  = var.subnetwork
    FRI_IMAGE_REPOSITORY            = "${var.region}-docker.pkg.dev/${var.project}/fri/worker"
    FRI_BATCH_SERVICE_ACCOUNT       = google_service_account.fri["worker"].email
    FRI_PREPARATION_SERVICE_ACCOUNT = google_service_account.fri["preparation"].email
    FRI_RUNNER_SERVICE_ACCOUNT      = google_service_account.fri["runner"].email
    FRI_PUBLISHER_SERVICE_ACCOUNT   = google_service_account.fri["publication"].email
    FRI_WORKLOAD_IDENTITY_PROVIDER  = google_iam_workload_identity_pool_provider.github.name
    FRI_EXPERIMENTS_BUCKET          = google_storage_bucket.future_risk["experiments"].name
    FRI_RESULTS_BUCKET              = google_storage_bucket.future_risk["results"].name
    FRI_PUBLISHER_STAGING_BUCKET    = var.publisher_staging_bucket
  }
}

output "results_catalog_url" {
  description = "Anonymous HTTPS entry point for reviewing the results catalog."
  value       = "https://storage.googleapis.com/${google_storage_bucket.future_risk["results"].name}/catalog.json"
}
