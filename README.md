# portfolio-chat-rag

The AI assistant on Sonny's portfolio site: a retrieval-augmented chatbot with a
harness, evals and tracing. It answers questions about Sonny's work from a small,
public corpus and cites its sources.

> **Status: phase 1 of 6.** The pipeline chunks the corpus, embeds it, indexes it
> in Qdrant (dense + BM25 hybrid) and scores retrieval on golden questions. The
> service still answers from the profile text; it starts retrieving in phase 2.

## How it fits together

```
Browser ─► Portfolio-Sonny on Vercel ─► /api/chat route (rate limit, CHAT_API_KEY)
                                              │
                                              ▼
                         Cloud Run: backend/  (this repo, FastAPI)
                         guard in → retrieve → generate → guard out
                              │          │          │
                              │          │          └─► OpenAI chat model
                              │          └─► Qdrant Cloud (phase 2)
                              └─► tools: Firestore leads, Pushover alerts

GitHub Actions: pipeline/ builds the index (phase 1) · CI tests · deploy.yml ships images
Terraform: Cloud Run, Artifact Registry, IAM, Secret Manager, Workload Identity
```

## Layout

```
pyproject.toml     uv workspace: backend + pipeline, one uv.lock
backend/app/       the chat API Cloud Run runs
  main.py            /health and /api/chat: bearer key, validation, rate limit
  chat.py            one turn: system prompt, model call, at most 3 tool rounds
  tools.py           the tool registry (only listed tools can run)
  prompts/           every instruction the model gets, versioned, with a CHANGELOG
  config.py          every setting, read once from the environment
pipeline/          corpus -> chunks -> vectors -> Qdrant, and the retrieval eval
  chunker.py         markdown by heading (code blocks dropped), one chunk per project
  embedders.py       OpenAI text-embedding-3-small behind a sha256 SQLite cache
  keywords.py        BM25 terms: Qdrant sparse vectors and the in-memory baseline
  retrieval.py       QdrantRetriever (hybrid, RRF) and MemoryRetriever (numpy + BM25)
  evaluate.py        hit@1, hit@5 and MRR on evals/retrieval/questions.json
corpus/            public, redacted material only, declared in sources.yaml
evals/retrieval/   golden questions and the pinned baseline scores
scripts/           export_projects.mts: the portfolio's projects.ts -> corpus
terraform/         the Google Cloud side
.github/workflows/ ci.yml (ruff, pytest, image smoke test, terraform validate), deploy.yml
```

## Run it locally

```bash
uv sync
cp .env.example .env        # add OPENAI_API_KEY
uv run uvicorn app.main:app --reload --port 8000
uv run pytest               # no API key or network needed
uv run chat-pipeline status # list the corpus
```

## The pipeline

```bash
uv run chat-pipeline chunks              # what each document becomes
uv run chat-pipeline build               # embed (cached) + new Qdrant collection
uv run chat-pipeline eval                # Qdrant and in-memory, per question
uv run chat-pipeline search "What did Sonny do at Foodstuffs?"
uv run chat-pipeline build --promote     # point the live alias at the new build
uv run chat-pipeline eval --save-baseline   # pin today's scores to compare against
```

`build` needs `OPENAI_API_KEY` in `.env` (about a cent for the whole corpus;
unchanged text is never embedded twice). Add `--embedder hash` to try every
command offline: the scores are then meaningless, which is what the tests use.
Without `QDRANT_URL` everything runs against a local store in `data/qdrant/`.

Every build is a new collection, `portfolio-chunks-<time>`. The chatbot reads the
alias `portfolio-chunks`, which only `--promote` moves (from phase 4, only after
the eval gate passes), so a bad build never goes live and rollback is one alias
switch. The newest three builds are kept.

To refresh the projects after editing the portfolio:

```bash
node --experimental-strip-types scripts/export_projects.mts \
  ../Portfolio-Sonny/src/data/projects.ts > corpus/projects/projects.json
```

## First deploy (once)

1. **Infrastructure.** In `terraform/`, copy `terraform.tfvars.example` to
   `terraform.tfvars`, fill it in, then with your own Google login:
   ```bash
   gcloud auth application-default login
   terraform init && terraform apply          # create_service = false
   ```
2. **Secret values,** which Terraform never sees:
   ```bash
   printf '%s' "$OPENAI_API_KEY" | gcloud secrets versions add openai-api-key --data-file=-
   openssl rand -hex 32 | tee /dev/stderr | gcloud secrets versions add chat-api-key --data-file=-
   printf '%s' "$PUSHOVER_TOKEN" | gcloud secrets versions add pushover-token --data-file=-
   printf '%s' "$PUSHOVER_USER"  | gcloud secrets versions add pushover-user --data-file=-
   ```
   Keep the chat key: Vercel needs the same value.
3. **The service.** Set `create_service = true` and `terraform apply` again.
4. **Keyless deploys.** Add the repository variables `GCP_PROJECT_ID`,
   `GCP_REGION`, `GCP_WORKLOAD_IDENTITY_PROVIDER` and `GCP_DEPLOYER_SA` (from
   `terraform output`). From then on every merge to `main` deploys.
5. **Vercel.** Set `CHAT_API_URL` (`terraform output service_url`) and
   `CHAT_API_KEY`. The portfolio's `/api/chat` route arrives in phase 2.

## Plan

| Phase | What |
| --- | --- |
| 0 | This: workspace, ported chat API, CI, Docker, Terraform |
| 1 | Corpus (CV, projects, READMEs, FAQ), chunking, embeddings, 30 golden questions, hit@5 and MRR |
| 2 | Qdrant hybrid retrieval, cited and streamed replies, portfolio `/api/chat` route |
| 3 | Task YAMLs, registries, Langfuse tracing, input and output guards |
| 4 | Full eval gate in CI: faithfulness, adversarial set, PR comments |
| 5 | Cut over from portfolio-backend-sonny |
| 6 | Optional: `score_job` hands a job listing to the CV Guestimator |
