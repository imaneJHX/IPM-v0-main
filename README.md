# IPM — Innovation Progress Model

IPM is an AI-assisted innovation intake and qualification workspace. A user submits a business need, the platform classifies and enriches it, searches the DXC catalog, scores candidate solutions, guides selection through stage gates, and produces delivery-ready recommendations and exportable documents.

The current implementation is a single-role experience for **CLIENT DXC**. There is no authentication or RBAC in this version.

## Product Flow

The workflow bar is sticky across the app and mirrors the operational path:

```text
Sourcing → SG-1 → Discovery → SG-2 → Evaluation → Selection → SG-3 → Recos → SG-4 → Done
```

### Route Map

| Route | Step | What happens |
|---|---|---|
| `/sourcing` | Business Need | Capture pitch and horizon, classify with LLM, validate SG-1 |
| `/discovery` | Discovery | Search DXC catalog, run gap analysis, inspect tech signals, validate SG-2 |
| `/evaluation` | Evaluation | Read selected discovery solutions and auto-score them from gap analysis |
| `/selection` | Selection | Choose the solutions that move to delivery, validate SG-3 |
| `/recos` | Recos | Generate technical, organizational, and KPI recommendations, validate SG-4, export PDF/DOCX |
| `/dashboard` | Dashboard | View the current IPM list and status |

State is passed primarily through:
- `?id=` URL parameter for the current business need
- `localStorage` for selection and evaluation handoff data

Key localStorage keys:
- `ipm_selected_solutions` — selected solutions from Discovery
- `ipm_sg2_state` — SG-2 discovery validation state
- `ipm_evaluation_state` — ranked evaluation snapshot
- `ipm_delivery_solutions` — final delivery selections for Recos

## What The App Does

### Sourcing
- Creates a business need
- Calls AI tagging to derive `objectif`, `domaine`, `impact`, and `origine`
- Detects duplicate needs via vector similarity
- Passes the need through SG-1

### Discovery
- Searches the seeded DXC catalog in ChromaDB
- Performs gap analysis for each selected solution
- Surfaces tech signals with Tavily + Groq enrichment
- Persists selected solutions for downstream qualification
- Passes the need through SG-2

### Evaluation
- Reads the Discovery selection snapshot
- Uses gap-analysis output to automatically score each solution on:
  - Fit
  - Feasibility
  - Cost
  - Innovation
- Produces a ranked evaluation snapshot for Selection

### Selection
- Lets the user choose the final delivery candidates
- Opens SG-3 only after the user confirms the chosen solution(s)
- Advances the workflow to the delivery phase

### Recos
- Generates one recommendation bundle per selected solution
- Includes:
  - Technical recommendations
  - Organizational recommendations
  - Target KPIs and measurable criteria
- Unlocks SG-4 before export
- Generates download-ready PDF and DOCX documents

## Backend Capabilities

The main API lives in [backend/app/api/v1/needs.py](backend/app/api/v1/needs.py).

Important endpoints:
- `POST /api/v1/needs/analyze` — classify a pitch
- `POST /api/v1/needs` — create a business need
- `PATCH /api/v1/needs/{id}/status` — advance workflow state
- `POST /api/v1/needs/{id}/catalog-search` — search the DXC catalog
- `POST /api/v1/needs/{id}/gap-analysis` — analyze a selected solution against a need
- `POST /api/v1/needs/{id}/tech-signals` — fetch Tavily-based tech signals
- `POST /api/v1/needs/{id}/recommendations` — generate delivery recommendations per selected solution
- `POST /api/v1/needs/{id}/export/pdf` — generate a PDF report
- `POST /api/v1/needs/{id}/export/docx` — generate a DOCX proposal

Workflow transitions are enforced server-side.

## LLM And Data Sources

- Groq is the default LLM provider
- Azure OpenAI is supported as an alternative
- Local embeddings default to `BAAI/bge-small-en-v1.5`
- ChromaDB is used for catalog retrieval and vector operations
- Tavily powers tech signals search and is enriched by the LLM layer

## Document Exports

Recos now produces real exports rather than placeholder buttons.

Generated artifacts are designed to be minimalist and professional:
- clean typography
- structured sections
- compact tables
- concise recommendation blocks
- KPI targets and measurement criteria

Both exports are generated from the same recommendation payload:
- PDF via `reportlab`
- DOCX via `python-docx`

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 App Router, React 18, TypeScript, Framer Motion |
| Backend | FastAPI, SQLAlchemy async, Pydantic v2 |
| Database | PostgreSQL 15 |
| Vector DB | ChromaDB |
| Embeddings | Local BGE or OpenAI |
| LLM | Groq or Azure OpenAI |
| Observability | Langfuse |
| Export | ReportLab, python-docx |
| Storage | MinIO |
| Infra | Docker Compose |

## Run With Docker

```bash
docker compose up --build
```

Then open:
- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs
- MinIO UI: http://localhost:9001
- ChromaDB: http://localhost:8001

To stop the stack:

```bash
docker compose down
```

## Local Development

### Backend

```bash
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Environment Variables

The backend reads its settings from `.env`.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `CHROMA_HOST` | ChromaDB host |
| `CHROMA_PORT` | ChromaDB port |
| `MINIO_ENDPOINT` | MinIO endpoint |
| `MINIO_ACCESS_KEY` | MinIO access key |
| `MINIO_SECRET_KEY` | MinIO secret key |
| `LLM_PROVIDER` | `groq` or `azure` |
| `GROQ_API_KEY` | Groq API key |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI key |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint |
| `AZURE_OPENAI_DEPLOYMENT` | Azure deployment name |
| `AZURE_OPENAI_API_VERSION` | Azure API version |
| `EMBEDDING_PROVIDER` | `local` or `openai` |
| `OPENAI_API_KEY` | Required for OpenAI embeddings |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key |
| `LANGFUSE_HOST` | Langfuse host |
| `TAVILY_API_KEY` | Tech signals search API key |
| `NEXT_PUBLIC_API_URL` | Frontend API base URL |

## Key Files

| Area | File |
|---|---|
| API routes | [backend/app/api/v1/needs.py](backend/app/api/v1/needs.py) |
| Workflow state machine | [backend/app/api/v1/needs.py](backend/app/api/v1/needs.py) |
| LLM provider wrapper | [backend/app/core/llm_client.py](backend/app/core/llm_client.py) |
| Runtime config | [backend/app/core/config.py](backend/app/core/config.py) |
| Export generation | [backend/app/services/export_service.py](backend/app/services/export_service.py) |
| Pydantic schemas | [backend/app/schemas/business_need.py](backend/app/schemas/business_need.py) |
| Frontend API client | [frontend/src/lib/api.ts](frontend/src/lib/api.ts) |
| Frontend types | [frontend/src/lib/types.ts](frontend/src/lib/types.ts) |
| Discovery page | [frontend/src/app/discovery/page.tsx](frontend/src/app/discovery/page.tsx) |
| Evaluation page | [frontend/src/app/evaluation/page.tsx](frontend/src/app/evaluation/page.tsx) |
| Selection page | [frontend/src/app/selection/page.tsx](frontend/src/app/selection/page.tsx) |
| Recos page | [frontend/src/app/recos/page.tsx](frontend/src/app/recos/page.tsx) |
| Workflow bar | [frontend/src/components/layout/WorkflowBar.tsx](frontend/src/components/layout/WorkflowBar.tsx) |
| SG-1 panel | [frontend/src/components/sourcing/Sg1ValidationPanel.tsx](frontend/src/components/sourcing/Sg1ValidationPanel.tsx) |
| SG-2 panel | [frontend/src/components/sourcing/Sg2ValidationPanel.tsx](frontend/src/components/sourcing/Sg2ValidationPanel.tsx) |
| SG-3 panel | [frontend/src/components/sourcing/Sg3ValidationPanel.tsx](frontend/src/components/sourcing/Sg3ValidationPanel.tsx) |
| SG-4 panel | [frontend/src/components/sourcing/Sg4ValidationPanel.tsx](frontend/src/components/sourcing/Sg4ValidationPanel.tsx) |

## Notes

- The first Docker build can take a while because the backend installs PyTorch and warms the local embedding model.
- If you change the DXC catalog data or embedding model, re-seed ChromaDB so the catalog vectors stay aligned.
