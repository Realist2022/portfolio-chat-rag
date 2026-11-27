# Sonny Tapara: CV

AI Systems Builder and Full-Stack Engineer. Rewritten from the CV into sections, so
each part can be found on its own. Contact details are left out on purpose: visitors
get in touch through the website.

## Profile

AI Systems Builder and Full-Stack Engineer, based in Auckland, New Zealand. NZ citizen.
GitHub: github.com/Realist2022.

Designs and deploys reliable, production-oriented AI systems and SaaS applications that
automate workflows and solve real-world problems. Experienced in architecting
retrieval-augmented generation (RAG) pipelines, domain-specific small language model
(SLM) fine-tuning, deterministic guardrails, and scalable cloud media and data
workflows. Combines full-stack software engineering (Python, FastAPI, Node.js, React,
AWS/GCP) with a ground-up systems mindset rooted in hardware diagnostics and physical
infrastructure.

## Skills

- AI and LLM systems: RAG pipelines, hybrid search (vector + BM25), LLM evaluation and
  LLM-as-a-judge, AWS Bedrock Guardrails, SLM fine-tuning (LoRA/QLoRA, Unsloth), vLLM,
  Ollama, prompt engineering, Microsoft Presidio (PII redaction), Instructor/Pydantic,
  Google AI Studio, Gemini AI, Claude / Anthropic API, Azure Custom Vision.
- Backend and data: Python, FastAPI, Node.js, Express.js, RESTful APIs, ETL data
  pipelines, BigQuery, MongoDB, MySQL, SQL Server, Power BI.
- Cloud and DevOps: AWS (Lambda, Bedrock, S3, Cognito), Google Cloud Platform (Cloud
  Storage, BigQuery), Terraform, Docker, Kubernetes (kubectl, minikube), CI/CD (GitHub
  Actions, OIDC, Bamboo), Firebase, Git/GitHub.
- Frontend and mobile: React.js, React Native, Next.js, JavaScript (ES6+), HTML5/CSS3,
  Bootstrap, responsive UI.

## Experience: AI Systems Engineer at Seen Ventures

Seen Ventures, 7 September 2026 – 20 November 2026 (10 weeks). Role: AI Systems Engineer.

- Architected and built a proof-of-concept RAG assistant for members of a New Zealand
  carbon certification body (client not named here), to navigate certification
  schemes, ISO 14064-1 definitions and pre-audit readiness, with cited answers from
  official documentation.
- Designed a hybrid retrieval pipeline combining vector embeddings and BM25 with
  authority ranking and document aliases, to prioritise official rules and improve
  search recall.
- Enforced ISO 14065 independence and impartiality by layering AWS Bedrock Guardrails
  with strict prompt rules, systematically testing against both over-blocking and
  under-blocking.
- Engineered an automated evaluation gate of 163 test questions using an LLM judge,
  Mean Reciprocal Rank (MRR) retrieval metrics and a no-regression baseline, required
  before any prompt, document or FAQ change goes live.
- Delivered a human-in-the-loop admin portal for non-technical staff to audit member
  chats and approve answer corrections, with a full audit trail.
- Deployed serverless infrastructure on AWS (Lambda, S3, Cognito) via Terraform and
  GitHub Actions (OIDC), with Python/FastAPI, Next.js and Claude, at an operating cost
  of about US$1.50 a day per 1,000 queries, and handed over complete technical
  documentation.

## Experience: Software Engineer (Data & Integrations) at Foodstuffs

Foodstuffs, July 2025 – October 2025. Role: Software Engineer (Data & Integrations).

- Engineered scalable REST API integrations and containerised ETL data pipelines
  (Node.js, Docker, Kubernetes) to extract, transform and ingest enterprise engineering
  metrics into Google Cloud Storage and BigQuery.
- Automated real-time code health and CI/CD telemetry across SonarQube, Cortex.io
  (scorecards/EDP) and Bamboo build pipelines, with resilient pagination and error
  handling, powering Power BI dashboards.

## Experience: Hiab Operator and Heavy Truck Driver at Crane and Cartage

Crane and Cartage, September 2021 – November 2024. Role: Hiab operator and heavy truck
driver.

Executed high-precision crane lifts and heavy transport logistics in high-pressure
environments, requiring strict safety compliance, spatial planning and real-time
operational coordination.

## Experience: Electronics Repair Technician

Workshop / self-employed, July 2016 – September 2021. Role: Electronics Repair Technician.

- Diagnosed and repaired complex motherboard- and circuit-level faults across gaming
  consoles and consumer electronics, using microsoldering, hot air rework and
  multimeter diagnostics.
- Applied systematic root-cause troubleshooting and hardware modification skills
  (cooling, storage and custom board repairs) while maintaining reliable turnaround for
  a growing client base.

## Key project: CV to Job Guestimator, a self-hosted multi-agent SLM pipeline

Stack: Llama-3.2-3B, Unsloth, vLLM, FastAPI, Modal.

- Fine-tuned a Llama-3.2-3B model using Unsloth (LoRA/QLoRA) and exported quantised
  GGUF weights to Ollama and vLLM, achieving a 95.8% F1 score on technical skill
  extraction against standardised ESCO taxonomies.
- Replaced per-token external API dependencies by running three structured-extraction
  agents on a single self-hosted model served via FastAPI on Modal (L4 GPU).
- Implemented decoupled PII sanitisation boundaries using Microsoft Presidio (NER and
  regex) alongside a deterministic 60/40 weighted scoring engine to evaluate CVs
  against job requirements.

## Key project: My SnapShare, a live event photo and video sharing SaaS

My SnapShare (mysnapshare.com), a live SaaS product Sonny co-founded and built.

- A commercial web application that lets event hosts collect original-quality guest
  photos and videos through instant QR code links, with no app download needed.
- Engineered a high-throughput media ingestion and gallery delivery workflow supporting
  tiered event capacities (up to 15,000 photos and videos and 500 MB video uploads per
  event), live gallery streaming and one-click bulk archive downloads.
- Implemented end-to-end SaaS product infrastructure: self-serve free-trial onboarding,
  tiered NZD one-off event billing with upgrade difference calculation, custom guest
  themes and automated gallery lifecycle retention (12–24 months).

## Key project: Growise, an AI mobile gardening assistant

Stack: React Native, Firebase, Google Gemini AI.

Developed a cross-platform mobile application integrating Google Gemini AI and Firebase
to generate localised planting schedules for crops such as potatoes and kūmara.

## Key project: AI car insurance chatbot and vehicle image classifier

May 2025 and April 2025.

- Built a contextual policy-scanning chatbot using Google AI Studio and multi-step
  prompt engineering to accurately answer customer insurance enquiries from live policy
  URLs.
- Trained a real-time vehicle classification and write-off assessment model with Azure
  Custom Vision, integrated into a React/Express web workflow with Multer file handling
  to reduce manual claims review.

## Education: Mission Ready HQ

New Zealand Diploma in Web Development and Design (Level 5) and Certificate in Applied
Digital Technology Product Solutions (Level 6 micro-credential), Mission Ready HQ,
Nov 2024 – Nov 2025.

Completed an accelerated full-stack software engineering programme incorporating NZQA
Levels 3–6 and specialised micro-credentials in AI development.

References available on request.
