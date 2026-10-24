resource "google_project_service" "required" {
  for_each = toset([
    "batch.googleapis.com", "compute.googleapis.com", "logging.googleapis.com",
    "artifactregistry.googleapis.com", "iam.googleapis.com", "iamcredentials.googleapis.com",
    "sts.googleapis.com", "storage.googleapis.com"
  ])
  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "fri" {
  for_each                    = toset(["inputs", "candidates", "staging", "receipts"])
  name                        = "${var.project}-fri-${each.value}"
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
    worker_inputs      = { account = "worker", bucket = "inputs", role = "roles/storage.objectViewer" }
    prep_inputs_read   = { account = "preparation", bucket = "inputs", role = "roles/storage.objectViewer" }
    prep_inputs_create = { account = "preparation", bucket = "inputs", role = "roles/storage.objectCreator" }
    worker_output      = { account = "worker", bucket = "candidates", role = "roles/storage.objectCreator" }
    worker_output_read = { account = "worker", bucket = "candidates", role = "roles/storage.objectViewer" }
    runner_output      = { account = "runner", bucket = "candidates", role = "roles/storage.objectViewer" }
    approval_output    = { account = "publication", bucket = "candidates", role = "roles/storage.objectViewer" }
    approval_staging   = { account = "publication", bucket = "staging", role = "roles/storage.objectCreator" }
    approval_retry     = { account = "publication", bucket = "staging", role = "roles/storage.objectViewer" }
    approval_receipts  = { account = "publication", bucket = "receipts", role = "roles/storage.objectViewer" }
  }
  bucket = google_storage_bucket.fri[each.value.bucket].name
  role   = each.value.role
  member = "serviceAccount:${google_service_account.fri[each.value.account].email}"
}

resource "google_storage_bucket_iam_member" "transform" {
  for_each = {
    staged_sources = { bucket = "staging", role = "roles/storage.objectViewer" }
    receipt_writer = { bucket = "receipts", role = "roles/storage.objectCreator" }
    receipt_retry  = { bucket = "receipts", role = "roles/storage.objectViewer" }
  }
  bucket = google_storage_bucket.fri[each.value.bucket].name
  role   = each.value.role
  member = "serviceAccount:${var.transform_service_account}"
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
