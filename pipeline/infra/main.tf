resource "google_project_service" "required" {
  for_each = toset([
    "batch.googleapis.com", "compute.googleapis.com", "logging.googleapis.com",
    "artifactregistry.googleapis.com", "iam.googleapis.com", "iamcredentials.googleapis.com",
    "sts.googleapis.com", "storage.googleapis.com"
  ])
  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "future_risk" {
  for_each                    = toset(["experiments", "results"])
  name                        = "${var.bucket_prefix}-${each.value}"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  versioning { enabled = true }
}

resource "google_service_account" "fri" {
  for_each     = toset(["runner", "worker", "publication", "preparation"])
  account_id   = "fri-${each.value}"
  display_name = "Future Risk Index ${each.value}"
}

resource "google_artifact_registry_repository" "fri" {
  location      = var.region
  repository_id = "fri"
  format        = "DOCKER"
  depends_on    = [google_project_service.required]
}

resource "google_project_iam_member" "runtime" {
  for_each = {
    runner_batch = { account = "runner", role = "roles/batch.jobsEditor" }
    worker_batch = { account = "worker", role = "roles/batch.agentReporter" }
    worker_logs  = { account = "worker", role = "roles/logging.logWriter" }
    prep_batch   = { account = "preparation", role = "roles/batch.agentReporter" }
    prep_logs    = { account = "preparation", role = "roles/logging.logWriter" }
  }
  project = var.project
  role    = each.value.role
  member  = "serviceAccount:${google_service_account.fri[each.value.account].email}"
}

resource "google_service_account_iam_member" "submit_as_worker" {
  service_account_id = google_service_account.fri["worker"].name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.fri["runner"].email}"
}

resource "google_service_account_iam_member" "submit_as_preparation" {
  service_account_id = google_service_account.fri["preparation"].name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.fri["runner"].email}"
}

resource "google_artifact_registry_repository_iam_member" "image" {
  for_each   = { runner = "roles/artifactregistry.writer", worker = "roles/artifactregistry.reader", preparation = "roles/artifactregistry.reader" }
  location   = google_artifact_registry_repository.fri.location
  repository = google_artifact_registry_repository.fri.name
  role       = each.value
  member     = "serviceAccount:${google_service_account.fri[each.key].email}"
}

resource "google_storage_bucket_iam_member" "access" {
  for_each = {
    worker_experiments_read  = { account = "worker", bucket = "experiments", role = "roles/storage.objectViewer" }
    worker_experiments_write = { account = "worker", bucket = "experiments", role = "roles/storage.objectCreator" }
    worker_results_read      = { account = "worker", bucket = "results", role = "roles/storage.objectViewer" }
    worker_results_write     = { account = "worker", bucket = "results", role = "roles/storage.objectCreator" }
    prep_experiments_read    = { account = "preparation", bucket = "experiments", role = "roles/storage.objectViewer" }
    prep_experiments_write   = { account = "preparation", bucket = "experiments", role = "roles/storage.objectCreator" }
    prep_results_read        = { account = "preparation", bucket = "results", role = "roles/storage.objectViewer" }
    prep_results_write       = { account = "preparation", bucket = "results", role = "roles/storage.objectCreator" }
    runner_experiments       = { account = "runner", bucket = "experiments", role = "roles/storage.objectViewer" }
    runner_results           = { account = "runner", bucket = "results", role = "roles/storage.objectViewer" }
    publication_results      = { account = "publication", bucket = "results", role = "roles/storage.objectViewer" }
  }
  bucket = google_storage_bucket.future_risk[each.value.bucket].name
  role   = each.value.role
  member = "serviceAccount:${google_service_account.fri[each.value.account].email}"
}

resource "google_storage_bucket_iam_member" "publisher_staging" {
  for_each = toset(["roles/storage.objectUser", "roles/storage.objectViewer"])
  bucket   = var.publisher_staging_bucket
  role     = each.value
  member   = "serviceAccount:${google_service_account.fri["publication"].email}"
  dynamic "condition" {
    for_each = each.value == "roles/storage.objectUser" ? [1] : []
    content {
      title      = "future-risk-index-collection-only"
      expression = "resource.name.startsWith('projects/_/buckets/${var.publisher_staging_bucket}/objects/future-risk-index/')"
    }
  }
}

# Versioned data is create-only; shared Portolan indexes advance between releases.
resource "google_storage_bucket_iam_member" "results_catalog" {
  for_each = toset(["worker", "preparation"])
  bucket   = google_storage_bucket.future_risk["results"].name
  role     = "roles/storage.objectUser"
  member   = "serviceAccount:${google_service_account.fri[each.value].email}"
  condition {
    title      = "future-risk-index-catalogs-only"
    expression = "resource.name == 'projects/_/buckets/${google_storage_bucket.future_risk["results"].name}/objects/catalog.json' || (resource.name.startsWith('projects/_/buckets/${google_storage_bucket.future_risk["results"].name}/objects/future-risk-index/') && resource.name.endsWith('/catalog.json'))"
  }
}

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "fri-github"
  depends_on                = [google_project_service.required]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.workflow"   = "assertion.workflow_ref.endsWith('/update-risk.yml@refs/heads/main') ? 'runner' : 'publication'"
  }
  attribute_condition = "assertion.repository_id == '${var.github_repository_id}' && assertion.repository == '${var.github_repository}' && assertion.ref == 'refs/heads/main' && assertion.workflow_ref in ['${var.github_repository}/.github/workflows/update-risk.yml@refs/heads/main', '${var.github_repository}/.github/workflows/publish-risk.yml@refs/heads/main']"
  oidc { issuer_uri = "https://token.actions.githubusercontent.com" }
}

resource "google_service_account_iam_member" "github" {
  for_each           = toset(["runner", "publication"])
  service_account_id = google_service_account.fri[each.key].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.workflow/${each.key}"
}
