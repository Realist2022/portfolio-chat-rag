terraform {
  required_version = ">= 1.6"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  # State stays local until there is a reason to share it. To keep it in GCS:
  # backend "gcs" { bucket = "<project>-tfstate", prefix = "portfolio-chat-rag" }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
