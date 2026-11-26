output "service_url" {
  description = "Set this as CHAT_API_URL in Vercel."
  value       = var.create_service ? google_cloud_run_v2_service.chat[0].uri : null
}

output "image_repository" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}

output "workload_identity_provider" {
  description = "GitHub Actions variable GCP_WORKLOAD_IDENTITY_PROVIDER."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "deployer_service_account" {
  description = "GitHub Actions variable GCP_DEPLOYER_SA."
  value       = google_service_account.deployer.email
}

output "secret_ids" {
  description = "Add a value to each with: gcloud secrets versions add <id> --data-file=-"
  value       = [for s in google_secret_manager_secret.secrets : s.secret_id]
}
