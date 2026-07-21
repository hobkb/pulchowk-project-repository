# STATUS.md

## Implementation Status — Pulchowk Project Repository

**Purpose:** DESIGN.md describes the *finished* product. This file tracks what's *actually built* right now, so that a human or AI agent reading DESIGN.md knows which chapters are safe to build full-stack today, and which ones require mocked data or should be deferred.

**Rule for agents:** Before implementing anything from a DESIGN.md chapter, check its status here.
- 🟢 Build normally, wired to the real API.
- 🟡 Build the UI, but data must come from an explicit mock/fixture clearly marked `// MOCK — see STATUS.md`, not invented as if it were real. Do not write frontend code that assumes an endpoint shape that doesn't exist yet — check `docs/backend/actions.md` first, and if the endpoint isn't documented there, stop and ask rather than guessing the contract.
- 🔴 Do not build. Propose the backend work first, or skip the chapter entirely for this session.

**Last updated:** 2026-07-21

---

## 1. Backend Apps

| App | Models | Migrations | Serializers | Views | URLs | Notes |
|---|---|---|---|---|---|---|
| `accounts` | ✅ | ✅ | ✅ | ✅ | ✅ | Google OAuth, domain-restricted. Custom User model (`email` PK, `role`), plus `Person` model for linking student/faculty academic records. |
| `core` | — | — | — | ✅ | — | Shared response (`responses.py`) and exception (`exceptions.py`) envelopes are fully implemented and registered globally in settings. |
| `repository` | ✅ | ✅ | ✅ | ✅ | ✅ | `Project`, `ProjectSection`, `ProjectPerson`, `Department`, `Campus`, `ResearchGroup`, `Tag` models and migrations implemented. |
| `ingestion` | ✅ | ✅ | ✅ | ✅ | ✅ | `IngestionJob`, `IngestionJobLog` models, modular 7-step extraction pipeline engine, Celery + Redis background task, DRF API endpoints (`/api/ingestion/jobs/`, `/api/ingestion/jobs/{id}/publish/`). |

## 2. Frontend

| Area | Status | Notes |
|---|---|---|
| `AuthContext.jsx` | ✅ | Session/role read from backend session, with developer role switching (`?mockRole=`). |
| `GoogleLoginButton.jsx` | ✅ | |
| `Landing.jsx` | ✅ | |
| `Dashboard.jsx` | 🟢 | Implemented layout shell, role-aware sidebar navigation, and project view dashboard composition. |
| Route guards (`RequireAdmin`, §3.3) | 🟢 | Implemented. |
| Design tokens (§7–10) | 🟢 | Light-theme CSS variables and tokens configured per DESIGN.md specifications. |
| Component library (§13) | 🟢 | `ProjectCard`, `SearchBar`, `Badge`, `Sidebar`, `Navbar`, `StatCard`, etc. built. |

## 3. DESIGN.md Chapter → Status

| Chapter | Depends on | Status | Can an agent build this now? |
|---|---|---|---|
| 1–10 (Philosophy, Identity, Roles, Principles, Visual Language, Color, Type, Grid, Icons) | — | 🟢 active | Applied across light-theme design system tokens and layout components. |
| 11 Layout Architecture | tokens | 🟢 | **Yes — built.** Navbar, role-aware sidebar, and layout shell implemented. |
| 12 Navigation by Role | layout | 🟢 | **Yes — built.** Role-specific navigation arrays for general users and admins. |
| 13 Component Library | tokens | 🟢 | **Yes — built.** `ProjectCard`, `SearchBar`, `Badge`, `StatCard`, `EmptyState`, etc. |
| 14 Dashboard (General) | `repository` API, `role` | 🟢 | **Yes — built.** General dashboard with search, metrics, and project cards. |
| 15 Dashboard (Admin) | `repository`, `ingestion` APIs, `role` | 🟢 | **Yes — built.** Admin dashboard with ingestion job tracking and operations. |
| 16 Browse Projects | `repository` API | 🟢 | **Yes — built.** Browse, category tags, search filters, and detail drawer. |
| 17 Project Details | `repository` API | 🟢 | **Yes — built.** Metadata table, abstract, section structure, and author info. |
| 18 Semantic Search | `repository` API + vector index | 🟡 | Keyword search live; vector embedding indexing in progress. |
| 19 AI Assistant (RAG) | ingestion + vector store + LLM | 🔴 | Next phase. |
| 20 Upload & Ingestion | `ingestion` API | 🟢 | **Yes — backend API & background pipeline complete.** (`/api/ingestion/jobs/`). |
| 21 Pending Approvals / Repo Mgmt | `repository`, `ingestion` APIs | 🟢 | **Yes — built.** Ingestion job review, patching, and publish endpoints live. |
| 22 Authentication | `accounts` | 🟢 | **Yes — built.** |
| 23 Profile & Settings | `accounts`, `role` | 🟡 | Profile display active; settings expansion next. |
| 24 Accessibility | — | 🟢 | Applies to all built components (contrast, Lucide icons, keyboard nav). |
| 25 Responsive Design | — | 🟢 | Applied across layout shell and mobile breakpoints. |
| 26 Motion Guidelines | — | 🟢 | Applied (150-250ms transitions, no heavy blur). |
| 27–29 (Agent Rules, Do's/Don'ts, Future Expansion) | — | 🟢 | Active constraints. |

---

## 4. Maintenance

Update this file whenever:
- A backend app gains models/serializers/views/URLs.
- A frontend chapter moves from mock data to a real API call.
- A new dependency is discovered (e.g., vector DB choice for §18).

Keep this file and DESIGN.md both at the repo root so an agent reads both before touching frontend code.
