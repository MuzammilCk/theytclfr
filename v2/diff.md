# diff.md — ytclfr V2 Change Log

## How to Use

After each micro-task, append an entry below using this format:

```
### [TASK-ID] — [Title]
**Date:** YYYY-MM-DD
**Files:**
- `path/to/file.py` — [created | modified | deleted]
**Summary:** One sentence describing what changed and why.
```

Keep entries in chronological order. Never edit a past entry.

---

## V1 → V2 Architectural Summary

| Component | V1 | V2 | Status |
|---|---|---|---|
| `contracts/router.py` | `RouterDecisionModel` — single early label | DEPRECATED | Pending deletion after A-1 |
| `contracts/manifest.py` | Does not exist | `SignalManifest` — multi-signal evidence object | Pending A-1 |
| `router/classifier.py` | Heuristic keyword guesser | DEPRECATED | Pending deletion after A-7 |
| `tasks/route.py` | Fires all extractors blindly | Gutted: only triggers Stage A | Pending W-1 |
| `tasks/stage_a.py` | Does not exist | Signal Census orchestrator | Pending A-7 |
| `tasks/stage_b.py` | Does not exist | Dynamic extraction group builder | Pending B-6 |
| `tasks/stage_c.py` | Does not exist | Evidence fusion + Groq reasoner | Pending C-6 |
| `tasks/stage_d.py` | Does not exist | Taxonomy + intent mapper | Pending D-5 |
| `tasks/align.py` | Basic interval merge | Merged into Stage C fusion | Pending C-6 |
| `probing/audio_checker.py` | Reads codec metadata only | VAD + music detection | Pending A-4 |
| `probing/frame_sampler.py` | Pulls 5 static frames | Motion score + face + text density | Pending A-5 |
| `probing/metadata_probe.py` | Does not exist | yt-dlp metadata + subtitle track parser | Pending A-6 |
| `storage/output_store.py` | Hardcoded `content_type_map` | Removed map, accepts rich `FinalOutput` | Pending D-6 |
| `contracts/output.py` | `content_type: str` field | Full taxonomy + evidence + provenance | Pending D-1 |
| `alignment/engine.py` | Basic timestamp math | V2 temporal alignment with confidence | Pending C-3 |
| `fusion/` directory | Does not exist | Evidence fusion layer | Pending C-4/C-5 |
| `taxonomy/` directory | Does not exist | Taxonomy + intent mapping layer | Pending D-3/D-4 |

---

## Change Entries

<!-- Append entries below this line after each micro-task -->