locals {
  firestore_project = var.firestore_project_id != "" ? var.firestore_project_id : var.project_id

  # Secret Manager entries the service reads as environment variables.
  # Terraform creates the secrets; their values are added by hand and never
  # appear in configuration or state.
  secrets = {
    OPENAI_API_KEY = "openai-api-key"
    CHAT_API_KEY   = "chat-api-key"
    PUSHOVER_TOKEN = "pushover-token"
    PUSHOVER_USER  = "pushover-user"
    QDRANT_API_KEY = "qdrant-api-key"
  }
}

resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

# ── Images ──────────────────────────────────────────────────────────────────
resource "google_artifact_registry_repository" "images" {
  repository_id = var.service_name
  format        = "DOCKER"
  location      = var.region

  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions {
      keep_count = 10
    }
  }

  depends_on = [google_project_service.apis]
}

# ── Secrets (no values) ─────────────────────────────────────────────────────
resource "google_secret_manager_secret" "secrets" {
  for_each  = local.secrets
  secret_id = each.value

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

# ── Runtime identity: only what the service needs ───────────────────────────
resource "google_service_account" "runtime" {
  account_id   = "${var.service_name}-run"
  display_name = "Portfolio chat backend (Cloud Run runtime)"
}

resource "google_secret_manager_secret_iam_member" "runtime_reads_secrets" {
  for_each  = google_secret_manager_secret.secrets
  secret_id = each.value.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "runtime_firestore" {
  project = local.firestore_project
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

# ── The service ─────────────────────────────────────────────────────────────
resource "google_cloud_run_v2_service" "chat" {
  count    = var.create_service ? 1 : 0
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.runtime.email

    scaling {
      min_instance_count = 0
      max_instance_count = 3 # caps the worst-case bill
    }

    containers {
      image = var.image

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle = true
      }

      env {
        name  = "ALLOWED_ORIGINS"
        value = var.allowed_origins
      }

      env {
        name  = "QDRANT_URL"
        value = var.qdrant_url
      }

      dynamic "env" {
        for_each = local.secrets
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.secrets[env.key].secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }

  # CI deploys new images; Terraform owns everything else.
  lifecycle {
    ignore_changes = [template[0].containers[0].image, client, client_version]
  }

  depends_on = [google_secret_manager_secret_iam_member.runtime_reads_secrets]
}

# The portfolio calls this server to server with CHAT_API_KEY, so Cloud Run
# itself is public and the app checks the bearer key on every chat request.
resource "google_cloud_run_v2_service_iam_member" "public" {
  count    = var.create_service ? 1 : 0
  name     = google_cloud_run_v2_service.chat[0].name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ── Keyless deploys from GitHub Actions ─────────────────────────────────────
resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github"
  display_name              = "GitHub Actions"
  depends_on                = [google_project_service.apis]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-oidc"
  display_name                       = "GitHub OIDC"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }
  # Only this repository can use the pool at all.
  attribute_condition = "assertion.repository == \"${var.github_repository}\""

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account" "deployer" {
  account_id   = "${var.service_name}-deploy"
  display_name = "Portfolio chat deployer (GitHub Actions)"
}

resource "google_service_account_iam_member" "github_impersonates_deployer" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}

resource "google_artifact_registry_repository_iam_member" "deployer_pushes" {
  repository = google_artifact_registry_repository.images.name
  location   = var.region
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_project_iam_member" "deployer_deploys" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

# Deploying a revision that runs as the runtime account needs actAs on it, and only it.
resource "google_service_account_iam_member" "deployer_acts_as_runtime" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer.email}"
}
