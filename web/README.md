# ytclfr Nexus — 3D Video-Intelligence Console

An immersive 3D UI for the **ytclfr** YouTube video-intelligence pipeline
(`src/ytclfr`). Built with React + TypeScript + Vite + React Three Fiber, in a
**Modern Dark (cinematic)** design language: deep ink, frosted glass, ambient
light, restrained indigo accent, Jost + Fira Code typography.

It is a **frontend-only** layer over the existing FastAPI v3 API — it never
touches the pipeline code.

## Run

```bash
cd web
npm install
npm run dev      # http://localhost:5173  (proxies /api -> :8000)
# or
npm run build && npm run preview
```

## Live only (no mock data)

The console is wired directly to the backend:

- Click **Connect** (top bar) and paste a JWT bearer token.
- Submit a YouTube URL → it `POST /api/v3/jobs` and polls `GET /api/v3/jobs/{id}`
  until the job reaches a terminal state, then loads the full `DEBUG` result.
- With no token the app is offline: submission and search are disabled and the
  UI shows elegant empty states.

## API surface used

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v3/jobs` | Submit URL |
| `GET /api/v3/jobs/{id}` | Poll status |
| `POST /api/v3/jobs/{id}/retry` | Recover failed job |
| `GET /api/v3/jobs/{id}/result?view=DEBUG` | Full structured result (manifest, bundle, evidence, taxonomy) |
| `GET /api/v3/jobs/{id}/search?q=&mode=keyword\|similarity` | Search transcript/OCR (keyword = Postgres FTS + V3 JSON; similarity = pgvector cosine via Ollama embeddings) |

The `/search` route is new (added in this UI work) and lives at
`src/ytclfr/api/v3/search.py`.

## Views (left rail)

| View | 3D visualization | Data |
|------|------------------|------|
| Pipeline | Orbiting stage nodes (A→D) with live status | Job lifecycle |
| Signals | Constellation of Stage A physical signals | `SignalManifest` |
| Timeline | Segments on a 3D time axis, scrubbable playhead | `EvidenceGraph` |
| Evidence | Entity knowledge-graph with temporal edges | entities + conflicts |
| Taxonomy | Classification tree (parent→child→intent→items) | `FinalResponse.taxonomy` |
| OCR | On-screen text bounding boxes in frame space | `ExtractorBundle.ocr_segments` |
| Search | Live keyword / vector search over transcript & OCR | `/search` |

## Notes

- Design system generated via the `ui-ux-pro-max` skill and persisted to
  `design-system/ytclfr-nexus/MASTER.md`.
- The 3D bloom is intentionally restrained; nodes use gentle pulse + slow group
  rotation rather than constant spinning, for a refined rather than toy-like feel.
