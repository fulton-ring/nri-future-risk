mock_provider "google" {}

run "public_read_only_results" {
  command = plan

  assert {
    condition     = google_storage_bucket_iam_member.public_results.bucket == google_storage_bucket.future_risk["results"].name && google_storage_bucket_iam_member.public_results.member == "allUsers" && google_storage_bucket_iam_member.public_results.role == "roles/storage.objectViewer"
    error_message = "Anonymous access must be read-only and scoped to the results bucket."
  }
  assert {
    condition     = toset(google_storage_bucket.future_risk["results"].cors[0].method) == toset(["GET", "HEAD"])
    error_message = "Browser clients may only read results."
  }

  assert {
    condition     = google_storage_bucket.future_risk["experiments"].public_access_prevention == "enforced"
    error_message = "The experiments bucket must remain private."
  }
  assert {
    condition     = google_storage_bucket.future_risk["results"].public_access_prevention == "inherited"
    error_message = "The results bucket must permit public read access."
  }
}
