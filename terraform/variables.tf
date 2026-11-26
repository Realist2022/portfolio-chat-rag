variable "project_id" {
  description = "Google Cloud project that runs the chat backend."
  type        = string
}

variable "region" {
  description = "Cloud Run and Artifact Registry region. Sydney is the closest to NZ."
  type        = string
  default     = "australia-southeast1"
}

variable "service_name" {
  type    = string
  default = "portfolio-chat"
}

variable "github_repository" {
  description = "owner/name of the repository allowed to deploy through Workload Identity."
  type        = string
  default     = "Realist2022/portfolio-chat-rag"
}

variable "allowed_origins" {
  description = "Comma-separated browser origins allowed by CORS."
  type        = string
  default     = "http://localhost:3000"
}

variable "firestore_project_id" {
  description = "Project whose Firestore holds leads and unanswered questions. Defaults to project_id."
  type        = string
  default     = ""
}

variable "create_service" {
  description = <<-EOT
    Create the Cloud Run service. Leave false on the first apply: Cloud Run can't
    start until every secret has a value, and Terraform never holds the values.
    Add them (see README.md), then apply again with true.
  EOT
  type        = bool
  default     = false
}

variable "image" {
  description = "Image for the first revision. Later revisions are deployed by CI."
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}
