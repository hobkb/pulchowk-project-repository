# STATUS.md

## Implementation Status — Pulchowk Project Repository

**Purpose:** DESIGN.md describes the *finished* product. This file tracks what's *actually built* right now, so that a human or AI agent reading DESIGN.md knows which chapters are safe to build full-stack today, and which ones require mocked data or should be deferred.

**Rule for agents:** Before implementing anything from a DESIGN.md chapter, check its status here.
- 🟢 Build normally, wired to the real API.
- 🟡 Build the UI, but data must come from an explicit mock/fixture clearly marked `// MOCK — see STATUS.md`, not invented as if it were real. Do not write frontend code that assumes an endpoint shape that doesn't exist yet — check `docs/backend/actions.md` first, and if the endpoint isn't documented there, stop and ask rather than guessing the contract.
- 🔴 Do not build. Propose the backend work first, or skip the chapter entirely for this session.

**Last updated:** 2026-07-16

---

## 1. Backend Apps

| App | Models | Migrations | Serializers | Views | URLs | Notes |
|---|---|---|---|---|---|---|
| `accounts` | ✅ | ✅ | ✅ | ✅ | ✅ | Google OAuth, domain-restricted. User model has a `role` field with choices: `student`, `faculty`, and `admin` (default: `student`). |
| `core` | — | — | — | ✅ | — | Shared response (`responses.py`) and exception (`exceptions.py`) envelopes are fully implemented and registered globally in settings. |
| `repository` | 🔴 stub | — | ❌ | 🔴 stub | ❌ | No serializers or URLs yet. This backs Browse/Search/Project Details. |
| `ingestion` | 🔴 stub | — | ❌ | 🔴 stub | ❌ | No serializers or URLs yet. This backs Upload/Pipeline/Approvals. |

## 2. Frontend

| Area | Status | Notes |
|---|---|---|
| `AuthContext.jsx` | ✅ | Session/role read from backend session, per §22. |
| `GoogleLoginButton.jsx` | ✅ | |
| `Landing.jsx` | ✅ | |
| `Dashboard.jsx` | 🟡 | Exists but is a placeholder — not yet the role-branched `GeneralDashboard`/`AdminDashboard` split from §3.3, §14–15. |
| Route guards (`RequireAdmin`, §3.3) | 🔴 | Not implemented — layout architecture and routing guards needed (role is available). |
| Design tokens (Tailwind config, §7–10) | 🔴 | No token setup yet — colors/spacing/type scale from DESIGN.md not wired into `index.css`/`tailwind.config`. |
| Component library (§13: `ProjectCard`, `SearchBar`, `Badge`, etc.) | 🔴 | None built yet. |

## 3. DESIGN.md Chapter → Status

| Chapter | Depends on | Status | Can an agent build this now? |
|---|---|---|---|
| 1–10 (Philosophy, Identity, Roles, Principles, Visual Language, Color, Type, Grid, Icons) | — | 🟡 reference only | These are *rules*, not pages — always "in scope" as constraints, but §7–10 tokens should be set up once, early, before any page work (see below). |
| 11 Layout Architecture | tokens | 🔴 | No — needs design tokens and routing setup first (role is available). |
| 12 Navigation by Role | layout | 🔴 | No — needs layout architecture first. |
| 13 Component Library | tokens | 🔴 | No — but this is good next-step work once tokens exist; everything else depends on it. |
| 14 Dashboard (General) | `repository` API, `role` | 🔴 | No — mock data only, clearly marked. |
| 15 Dashboard (Admin) | `repository`, `ingestion` APIs, `role` | 🔴 | No. |
| 16 Browse Projects | `repository` API | 🔴 | No. |
| 17 Project Details | `repository` API | 🔴 | No. |
| 18 Semantic Search | `repository` API + vector index | 🔴 | No. |
| 19 AI Assistant (RAG) | ingestion + vector store + LLM integration | 🔴 | No — largest lift, build last. |
| 20 Upload & Ingestion | `ingestion` API | 🔴 | No. |
| 21 Pending Approvals / Repo Mgmt | `repository`, `ingestion` APIs | 🔴 | No. |
| 22 Authentication | `accounts` | 🟢 | **Yes — already built.** |
| 23 Profile & Settings | `accounts`, `role` | 🟡 | Partially — profile basics could be built against `accounts` now; settings persistence needs more backend. |
| 24 Accessibility | — | 🟢 | Applies to whatever is being built at any time. |
| 25 Responsive Design | — | 🟢 | Same — apply as you go. |
| 26 Motion Guidelines | — | 🟢 | Same. |
| 27–29 (Agent Rules, Do's/Don'ts, Future Expansion) | — | 🟢 | Always active constraints, not features to "build." |

---

## 4. Suggested build order

1. ~~Confirm/add `role` field on `accounts.User` (or equivalent)~~ (Done: `role` field exists in `accounts` User model).
2. Wire Tailwind tokens from §7–10 into `index.css` (Tailwind v4 theme config) — unblocks all visual work.
3. Build `repository` app: models → serializers → views → URLs for read-only project listing/detail (unblocks §16, §17).
4. Build component library (§13) against real token + real `repository` data.
5. Build `GeneralDashboard` (§14), then `AdminDashboard` (§15) once `ingestion` exists.
6. `ingestion` app (§20) and approvals (§21).
7. Semantic search (§18) and RAG assistant (§19) last — highest complexity, most external dependencies (embeddings, vector DB, LLM).

---

## 5. Maintenance

Update this file whenever:
- A backend app gains models/serializers/views/URLs.
- A frontend chapter moves from mock data to a real API call.
- A new dependency is discovered (e.g., vector DB choice for §18).

Keep this file and DESIGN.md both at the repo root so an agent reads both before touching frontend code.

