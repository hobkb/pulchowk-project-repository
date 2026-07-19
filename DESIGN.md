# DESIGN.md

## Pulchowk Project Repository — UI/UX Design Specification

**Project:** Pulchowk Project Repository: An AI-Powered Undergraduate Project Discovery and Knowledge Retrieval Platform
**Institution:** Department of Electronics & Computer Engineering, Pulchowk Campus, Institute of Engineering (IOE), Tribhuvan University
**Document status:** Authoritative — single source of truth for frontend implementation
**Audience:** Human developers and AI coding agents (Cursor, Claude Code, Codex, etc.)

> This document defines *how the product looks, is structured, and behaves*. It is not a general product spec. Any AI agent implementing a page must find its layout, components, states, and rules here before inventing anything. If a decision isn't in this document, the agent should default to the most conservative, metadata-first, information-dense interpretation consistent with the principles in Chapter 1 — not to a generic SaaS pattern.

---

## Table of Contents

1. [Design Philosophy](#1-design-philosophy)
2. [Product Identity](#2-product-identity)
3. [User Roles & Permission Model](#3-user-roles--permission-model)
4. [Target Users](#4-target-users)
5. [Design Principles](#5-design-principles)
6. [Visual Language](#6-visual-language)
7. [Color Palette](#7-color-palette)
8. [Typography](#8-typography)
9. [Grid & Spacing](#9-grid--spacing)
10. [Icon System](#10-icon-system)
11. [Layout Architecture](#11-layout-architecture)
12. [Navigation by Role](#12-navigation-by-role)
13. [Component Library](#13-component-library)
14. [Dashboard (General User)](#14-dashboard-general-user)
15. [Dashboard (Administrator)](#15-dashboard-administrator)
16. [Browse Projects](#16-browse-projects)
17. [Project Details](#17-project-details)
18. [Semantic Search](#18-semantic-search)
19. [AI Assistant (RAG Chat)](#19-ai-assistant-rag-chat)
20. [Upload & Ingestion (Admin Only)](#20-upload--ingestion-admin-only)
21. [Pending Approvals / Repository Management (Admin Only)](#21-pending-approvals--repository-management-admin-only)
22. [Authentication](#22-authentication)
23. [Profile & Settings](#23-profile--settings)
24. [Accessibility](#24-accessibility)
25. [Responsive Design](#25-responsive-design)
26. [Motion Guidelines](#26-motion-guidelines)
27. [AI Agent Implementation Rules](#27-ai-agent-implementation-rules)
28. [Do's & Don'ts](#28-dos--donts)
29. [Future Expansion](#29-future-expansion)

---

## 1. Design Philosophy

The Pulchowk Project Repository is an **institutional knowledge system**, not a marketing product and not an admin panel. It exists to make three years of accumulated undergraduate engineering work discoverable, searchable, and reusable.

Every design decision is judged against one question:

> **Does this help someone find, understand, or reuse a project faster — or is it decoration?**

The product should communicate, in this order of priority:

1. **Academic** — this is a Tribhuvan University / IOE Pulchowk Campus institutional system.
2. **Engineering** — built by and for engineers; technical transparency is a virtue, not a bug.
3. **Professional** — trustworthy enough to be cited by a supervisor evaluating novelty.
4. **Modern** — current interaction patterns (command-style search, inline previews, fast navigation), not a legacy library OPAC.
5. **Minimal** — clean typographic hierarchy; no gradients, glows, or illustration-driven marketing sections.

**Functional lineage:** the information architecture (communities → collections → items, search-first browsing, metadata-driven item pages, recent-submissions feed) is adapted from the Kathmandu University Digital Repository (DSpace, [repository.ku.edu.np](https://repository.ku.edu.np/home)). The *visual* execution must not resemble DSpace at all — DSpace is dated, form-heavy, and low-density. This product borrows DSpace's **repository logic**, not its **look**.

**Visual lineage:** GitHub (structure, monospace metadata, clean light canvas), Vercel (typographic restraint, generous but not empty layout), Linear (interaction crispness, keyboard-first affordances), Notion (content-first density without clutter). Interaction lineage: Perplexity AI (search-as-primary-surface, inline citations, conversational retrieval).

The product must never read as a **fintech dashboard**, a **crypto dashboard**, or a **generic SaaS admin panel**. If a screen could be mistaken for a trading terminal or a Stripe billing page, it has failed this specification.

---

## 2. Product Identity

The interface should feel like software an engineering student would trust the way they trust GitHub — not the way they experience a university ERP portal.

| This product should feel like | Not like |
|---|---|
| GitHub repository / code search | Stripe dashboard |
| Linear issue tracker | Dribbble concept shot |
| Vercel deployment dashboard | College ERP / attendance portal |
| Perplexity search results | A PDF viewer bolted onto a form |

The wordmark, chrome, and structural elements should look like they belong to a piece of **engineering infrastructure** maintained by the department — permanent, precise, unglamorous in a good way.

### 2.1 Institutional Identity (Required, Not Optional)

The product must read as **built by IOE Pulchowk / Tribhuvan University**, not as a generic SaaS template that happens to host university data. This is a correction, not a cosmetic add-on: a prior implementation pass leaned too far toward generic, undifferentiated styling and lost the institutional presence entirely.

- **Crest mark:** the official Tribhuvan University / IOE crest (small, monochrome or two-color treatment, never a low-res raster stretched) appears at `24px`–`28px` beside the wordmark in the Top Navbar and, larger (`64px`–`80px`), centered above the card on the `/login` page.
- **Institutional accent (`--accent-gold`, §7.4):** used sparingly and deliberately — crest area, a `2px` underline accent on the login card header, the active-tab indicator on the login/landing hero — never as a general-purpose UI color and never competing with `--accent-primary` or `--accent-violet` in the same component.
- **Full institutional name on record:** the footer (all authenticated pages) and the login page both carry the full line: "Department of Electronics & Computer Engineering · Pulchowk Campus · Institute of Engineering · Tribhuvan University" in `text-micro`, `--text-tertiary`.
- **What this does *not* mean:** no maroon/red bureaucratic color schemes, no Devanagari-heavy decorative headers, no photographic campus imagery as hero backgrounds, no PDF-form aesthetics. The institutional identity is expressed through the crest, the gold accent, and correct naming — not through abandoning the clean, dense, GitHub/Linear-derived visual system in Chapters 6–10. This is still "engineering infrastructure," just infrastructure that is unambiguously *this department's*.
- **Modern-AI signal stays intact:** the `--accent-violet` AI surfaces (Chapter 19, dashboard AI Assistant shortcut) remain the product's forward-looking signal, deliberately distinct from the institutional gold — gold says "this is IOE/TU," violet says "this part is AI-native." The two must never be blended into a single gradient or combined on the same element.

---

## 3. User Roles & Permission Model

This is a **critical, load-bearing requirement**. The platform implements role-based access control (RBAC) with exactly two roles. Every page, component, and navigation item in this document is tagged with which role(s) can see it. AI agents must never render role-gated UI to a user who lacks that role — this is a security and trust requirement, not just a UX preference.

### 3.1 General Users (Students & Faculty)

Default role for any authenticated user. **Cannot** upload, edit, approve, or reject project records.

Permitted actions:
- Browse all **approved** projects
- Keyword search
- Semantic search
- View project metadata (title, authors, supervisor, department, year, technologies)
- Read abstracts, results summaries, and key findings
- View similar-project recommendations
- Use the RAG assistant (grounded in abstracts/metadata/results — never the full report text, see §3.4)
- Request the full report directly from the authors via email
- Manage their own profile and preferences

General users **must never** see ingestion controls, approval queues, processing logs, or any administrative surface — not greyed out, not hidden-but-reachable-by-URL. Route guards must return a standard 403/redirect, not a disabled version of the admin UI.

General users **must never view, preview, or download the full project report PDF** under any circumstance — see §3.4.

### 3.2 Administrators

Everything a general user can do, **plus**:
- Upload new project reports
- Access the document ingestion pipeline
- Review and edit extracted metadata
- Approve or reject submissions
- Trigger vector indexing
- Manage repository records (edit/unpublish/delete)
- View ingestion logs and processing status
- Access administrative statistics
- View and download the **full project report PDF**, for review, quality-control, and ingestion purposes only

### 3.3 Enforcement Rules for Agents

- Role is resolved server-side; the frontend reads role from the authenticated session and renders conditionally, but **never** relies on the frontend as the only gate.
- Every admin-only route must be wrapped in a route guard component (`RequireAdmin`) that redirects non-admins to the general Dashboard.
- Navigation, dashboard modules, and page-level CTAs must branch on role at the layout level, not be patched in per-page.
- Do not build a single "God dashboard" with conditional divs sprayed throughout. Build `GeneralDashboard` and `AdminDashboard` as distinct compositions of shared components (see Chapters 14–15).

### 3.4 Data Governance & Report Access (Critical, Load-Bearing)

The repository holds student work under the department's consent-of-use terms. Those terms permit the department to **index, describe, and surface** each project — they do **not** permit the platform to redistribute the full report PDF to arbitrary logged-in users. This is a data-governance boundary, not a UX preference, and it applies regardless of role-based navigation elsewhere in this document.

- **General users never see the full report PDF**, in any form: no inline viewer, no thumbnail-through-to-full-document flow, no direct or signed download link, and no PDF bytes returned by any general-user-accessible API response. This holds even if a general user knows or guesses a project's URL or ID.
- What general users **may** see on a project's detail page: title, authors, supervisor, department, academic year, technologies, cluster, the **abstract**, and a **results/key-findings summary** (a short structured excerpt — not the full document — populated at ingestion time; see §20.1). A single **first-page image** (thumbnail only, not embedded as a scrollable/paginated viewer) may be shown for visual identification, since a static preview image is not equivalent to distributing the document.
- To obtain the full report, a general user uses a **Request Report** action (§17.1) that composes an email to the listed author(s) — the platform facilitates contact, it does not act as a distribution channel for the file itself. This is a deliberate design choice to keep consent decisions with the author/department, not with the platform.
- The RAG Assistant (Chapter 19) must be grounded only in abstracts, metadata, and the stored results/key-findings summary for general users — it must never quote, reproduce, or paraphrase full report body text to a general user, and must never attach or link the PDF in a response.
- Administrators may view and download the full PDF, but only within admin surfaces (Project Details in admin review mode, Upload/Ingestion, Repository Management) — never through a route or component also reachable by general users.
- If a report has no listed author email, `Request Report` degrades to a routed message through the department administrator rather than failing silently.

---

## 4. Target Users

| User | Primary need | Primary surface |
|---|---|---|
| Student (browsing) | "Has this idea been done before?" / "What did past BCT batches build?" | Semantic Search, Browse Projects |
| Student (researching) | "What did the RAG systems used in prior projects look like?" | AI Assistant, Project Details |
| Faculty / Supervisor | Evaluate novelty, find prior related work, reference past supervision | Browse Projects, Project Details, Similar Projects |
| Department Administrator | Keep the repository accurate and current | Upload, Pending Approvals, Repository Management |

---

## 5. Design Principles

### 5.1 Metadata Over Decoration (Most Important Principle)

Every project surface — card, list row, detail header — must expose, before any decorative imagery:

`title → authors → supervisor → technologies → department → academic year → approval status`

No project card should ever lead with a stock thumbnail or illustration. If a visual is present (e.g., a generated cover), it is secondary and smaller than the metadata block.

### 5.2 Repository-First, Not Upload-First

The majority of users are **consumers**, not contributors. The product's primary call-to-action, hero interaction, and dashboard center of gravity is **Explore / Search**, never **Upload**. Upload and ingestion are specialized administrative tools, visually and structurally separated from the primary experience (see Chapter 20).

### 5.3 Search-First Workflow

Search is not a feature bolted onto a nav bar — it is the primary way both roles enter the system. The dashboard search bar should be large, prominent, and support both keyword and semantic modes.

### 5.4 Information Density Is a Feature

This is an engineering platform for engineering users. Avoid large empty whitespace; fill unused space with real information — statistics, counts, recent activity — never with decorative filler. Density must remain readable: achieved through disciplined typography and spacing, not by shrinking everything.

### 5.5 Technical Transparency

Where the system does something technical (parsing a PDF, generating embeddings, indexing vectors), show it as real inline technical logs, not a generic spinner. This applies **only** to the Upload/Ingestion workflow (admin-only) — general users never see parser internals.

---

## 6. Visual Language

- **Canvas:** clean white background (`--surface-canvas`, `#FFFFFF`) — this is a **knowledge retrieval platform**, and a stark dark UI reads as unwelcoming for that purpose (corrected 2026-07-17; the product previously shipped dark and it didn't fit the brief). Panels sit one step *toward grey* from canvas (`--surface-raised`), established through subtle background-color steps, not shadows.
- **Borders over shadows:** structure is communicated with 1px hairline borders (`--border-subtle` / `--border-default`), matching the GitHub/Linear convention. Shadows are reserved for floating overlays (modals, dropdowns) only.
- **Flat, not glossy:** no gradients, no glassmorphism, no glow effects, no colorful decorative panels.
- **Monospace as a signal:** any identifier a machine cares about — UUIDs, roll numbers (e.g. `PUL080BCT050`), department codes (`BCT`), embedding/model names (`all-MiniLM-L6-v2`), vector dimensions — is rendered in a monospace face at a slightly reduced size, usually inside a subtle pill or inline code style. This is a deliberate signal that the value is technical/exact, not prose.
- **Consistent radius:** one radius scale used everywhere (see §9.4). Never mix sharp and heavily rounded elements on the same screen.
- **Emerald is earned:** the success/emerald accent is reserved exclusively for successful states (approved badge, "indexing complete," success toasts). It is never used decoratively.

---

## 7. Color Palette

**Theme (corrected 2026-07-17):** light, not dark. The product shipped dark in an earlier pass; that read as cold and unwelcoming for a knowledge-retrieval platform meant to invite browsing, not a terminal-style admin tool. All tokens below replace the prior dark set. Every text/icon-on-background pairing listed here has been checked against WCAG 2.1 contrast math (relative luminance), not eyeballed — the ratio is noted next to each so the reasoning is auditable, not just asserted. Recheck with a live contrast tool (e.g. WebAIM) once real components are built, since actual rendered anti-aliasing/font-weight can shift perceived contrast slightly.

All colors are defined as CSS custom properties (design tokens) and consumed via Tailwind config — never hardcoded hex values in components.

### 7.1 Surface

| Token | Value | Usage |
|---|---|---|
| `--surface-canvas` | `#FFFFFF` | App background |
| `--surface-raised` | `#F6F8FA` | Cards, panels |
| `--surface-overlay` | `#FFFFFF` | Modals, dropdowns, popovers — distinguished from canvas by shadow + `--border-default`, not by color, since both are white |
| `--surface-hover` | `#EEF1F4` | Hover state on rows/cards |
| `--surface-sunken` | `#F1F3F5` | Code blocks, log panels, input wells — the one surface that reads as *recessed* rather than *raised* |

### 7.2 Border

| Token | Value | Usage |
|---|---|---|
| `--border-subtle` | `#E4E7EB` | Default dividers, card outlines |
| `--border-default` | `#D0D5DC` | Interactive element borders |
| `--border-strong` | `#7C8695` | Focused/active borders (3.7:1 vs. white — meets the 3:1 non-text UI contrast minimum) |

### 7.3 Text

| Token | Value | Usage |
|---|---|---|
| `--text-primary` | `#14181F` | Headings, primary content (17.8:1 vs. white) |
| `--text-secondary` | `#55606E` | Body copy, metadata labels (6.4:1 vs. white) |
| `--text-tertiary` | `#8A93A1` | Timestamps, placeholders, disabled (3.1:1 vs. white — non-essential text only, never body copy that needs to be read reliably) |
| `--text-inverse` | `#FFFFFF` | Text on dark/filled surfaces (accent buttons, emerald/gold fills) |

### 7.4 Accent

| Token | Value | Usage |
|---|---|---|
| `--accent-primary` | `#1D4ED8` | Links, primary buttons, active nav, focus ring (6.7:1 vs. white) |
| `--accent-primary-hover` | `#1E40AF` | Hover of the above (8.7:1 vs. white) |
| `--accent-violet` | `#7C3AED` | AI Assistant / RAG-related surfaces only (5.7:1 vs. white) |
| `--accent-gold` | `#B08D3E` | Institutional identity accent only (§2.1): crest area, login card underline, footer institutional line hover. Decorative/graphical use only (3.1:1 vs. white — do not use as small body text). Never used for buttons, links, status, or general UI accents. |

**On `--accent-gold`:** reads as brushed brass/bronze against the white canvas rather than a bright warning-adjacent yellow, so it stays visually distinct from `--warning-amber` (§7.5). A component either signals institutional identity (gold) or pending/warning status (amber), never both.

### 7.5 Semantic

| Token | Value | Usage |
|---|---|---|
| `--success-emerald` | `#15803D` | Approved status, success toasts, "complete" pipeline stages **only** (5.0:1 vs. white) |
| `--warning-amber` | `#B45309` | Pending approval, warnings (5.0:1 vs. white) |
| `--error-red` | `#DC2626` | Rejected status, errors, destructive actions (4.8:1 vs. white) |
| `--info-blue` | `#1D4ED8` | Informational badges (shares `--accent-primary`) |

### 7.6 Department Code Colors

Department badges (`BCT`, `BEI`, `BCE`, etc.) use a single neutral monospace pill style (`--surface-sunken` background, `--border-default` outline, `--text-secondary` text) — **not** a rainbow of department colors. Differentiation comes from the text content, not decorative color-coding.

### 7.7 Rules

- Never introduce a new color outside this table without updating this document first.
- Color is never the sole indicator of status — always pair with an icon or text label (see Chapter 24).
- **Do not reintroduce the previous dark palette as a "dark mode" toggle without discussion** — §29's future-expansion note about a parallel light-token set now inverts: if a dark mode is ever wanted again, it would be the *secondary* mode added later, not the default.

---

## 8. Typography

| Role | Font | Notes |
|---|---|---|
| UI / body | **Inter** | Variable weight, used for all prose, labels, nav |
| Monospace | **JetBrains Mono** | UUIDs, roll numbers, department codes, model names, code/log output |
| Headings | Inter (Semibold/Bold) | No display/serif face — this is not editorial content |

### 8.1 Type Scale

| Token | Size / Line-height | Usage |
|---|---|---|
| `text-display` | 32px / 40px, semibold | Page-level H1 (e.g., Project Details title) |
| `text-h1` | 24px / 32px, semibold | Section headers |
| `text-h2` | 18px / 26px, semibold | Card group headers, panel titles |
| `text-h3` | 15px / 22px, semibold | Card titles, table headers |
| `text-body` | 14px / 20px, regular | Default body text |
| `text-body-sm` | 13px / 18px, regular | Secondary metadata, captions |
| `text-mono` | 13px / 18px, mono | IDs, codes, technical values |
| `text-micro` | 11px / 16px, medium, uppercase, letter-spacing 0.04em | Field labels, eyebrow text |

### 8.2 Rules

- Never use font sizes outside this scale.
- Line length for abstract/body text is capped at ~72 characters via `max-w-prose`-equivalent container width for readability.
- Truncate project titles at 2 lines in cards with ellipsis; never truncate on the Project Details page itself.

---

## 9. Grid & Spacing

### 9.1 Spacing Scale

4px base unit: `4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 96` — expressed as Tailwind's default spacing scale (`1` through `24`). No arbitrary pixel values in component code.

### 9.2 Content Grid

- Max content width: `1440px`, centered, with `24px`–`48px` responsive side gutters.
- Browse/Search grids: 12-column grid at desktop (`≥1280px`), collapsing to 8 columns (tablet) and 4 columns (mobile).
- Sidebar (where present) is a fixed `260px` column; main content fills the remainder.

### 9.3 Card Grid

- Project cards: 3-column grid at desktop (`≥1280px`), 2-column at tablet (`768–1279px`), 1-column at mobile (`<768px`).
- Consistent `20px` gutter between cards at all breakpoints.

### 9.4 Radius Scale

| Token | Value | Usage |
|---|---|---|
| `--radius-sm` | 6px | Badges, pills, inline code |
| `--radius-md` | 10px | Buttons, inputs, small cards |
| `--radius-lg` | 14px | Panels, project cards, modals |

No other radius values are permitted.

---

## 10. Icon System

- **Library:** Lucide React exclusively. Never mix in Heroicons, Feather, FontAwesome, or inline custom SVGs for standard UI actions.
- **Sizes:** `16px` (inline with text), `20px` (buttons, nav items), `24px` (empty states, section headers).
- **Stroke width:** `1.75` consistently.
- **Color:** icons inherit `currentColor`; they are never independently colored except semantic status icons (success/warning/error use the matching semantic token).
- **No emoji, anywhere.** Emoji characters (✅ ⏳ ❌ 📁 👤 etc.) must never appear in the rendered product — not in status badges, stat cards, empty states, navigation, log panels, or copy. Every place an emoji might seem like a quick fix (a folder count, a supervisor field, a status pill) uses the matching Lucide component instead: `Folder`/`FolderOpen` for counts of indexed items, `UserCircle` for a person/supervisor reference, `CheckCircle2`/`Clock`/`XCircle` for approved/pending/rejected. This applies retroactively — if emoji exist anywhere in the current implementation, they are a spec violation to be fixed, not a style choice to preserve.

---

## 11. Layout Architecture

Every authenticated page follows the same skeleton:

```
┌─────────────────────────────────────────────┐
│  Top Navbar (logo, global search, role menu) │
├───────────┬───────────────────────────────────┤
│           │  Page Header (title, breadcrumb,  │
│  Sidebar  │  primary action)                  │
│  (role-   ├───────────────────────────────────┤
│  aware    │  Main Content                     │
│  nav)     │  (cards / tables / detail panels) │
│           │                                   │
└───────────┴───────────────────────────────────┘
```

- **Top Navbar** (`64px` height, sticky): crest + repository wordmark (§2.1), global search shortcut (`⌘K` / `Ctrl K`), role-aware nav summary, notification bell (admin only, for pending approvals), `UserMenu` (right-most element).

### 11.1 UserMenu (Navbar, Right-Aligned)

Order, left to right within the trigger: **username** (`text-body`, `--text-primary`, e.g. "Sarthak Bastola") → **email** (`text-body-sm`, `--text-tertiary`, directly beneath or inline-truncated next to the name depending on width, e.g. "sarthak@pcampus.edu.np") → **user icon** (Lucide `UserCircle` or `CircleUserRound`, `20px`, rightmost — the click target that opens the dropdown).

- **No plain-text role pill in the navbar** (e.g. a "STUDENT" label sitting beside the name). Role is not displayed as chrome in the trigger at all — it already governs which nav items and pages exist (§12), which is the correct signal. If a role indicator is ever needed at a glance, it lives inside the opened dropdown (e.g. "General User" / "Administrator", styled per §23's read-only role badge), never as a colored text pill in the persistent navbar.
- On narrow viewports (`<768px`, per §25), the trigger collapses to the icon alone; username/email move inside the opened dropdown.
- The opened dropdown contains: name + email (repeated, full — not truncated), role (read-only text, no edit control), then `Profile`, `Settings`, a divider, `Log out`.
- **Sidebar** (`260px`, collapsible to icon rail at `72px`): primary navigation, role-aware (Chapter 12).
- **Main Content:** page header (title + breadcrumb + primary CTA) followed by content. Content region always fills available width up to the `1440px` max.
- The dashboard must never feel empty: unused space in the main content region is filled with statistics, repository metrics, or recommendation modules — never blank whitespace for its own sake (see §5.4).

---

## 12. Navigation by Role

The navigation set is resolved once, at the layout/shell level, from the authenticated user's role. Do not conditionally hide individual nav items with CSS — compose two distinct nav arrays.

### 12.1 General User Navigation

```
Dashboard
Browse Projects
Semantic Search
AI Assistant
Bookmarks          (future — render as disabled/"Coming soon" entry, see Ch. 29)
Profile
Settings
```

### 12.2 Administrator Navigation

```
Dashboard
Browse Projects
Upload Project
Pending Approvals   (badge with live pending count)
Semantic Search
Repository Management
Profile
Settings
```

### 12.3 Rules

- `Pending Approvals` shows a numeric badge (amber pill) with the live count of items awaiting review. Zero renders as no badge, not a `0`.
- Admin-only items (`Upload Project`, `Pending Approvals`, `Repository Management`) are visually identical in style to general items — no special "admin" color-coding of the nav itself. The role distinction lives in *what exists*, not in a loud visual treatment, reinforcing that this is one coherent product with two permission levels, not two different apps.
- Active route is indicated by a left accent bar (`2px`, `--accent-primary`) plus `--text-primary` label color; inactive items use `--text-secondary`.

---

## 13. Component Library

AI agents must compose pages from these components. Do not recreate any of them from scratch inside a page file.

| Component | Purpose | Key states |
|---|---|---|
| `DashboardLayout` | Top navbar + sidebar + content shell; accepts `role` prop to resolve nav | — |
| `Navbar` | Global top bar | scrolled, search-focused |
| `Sidebar` | Role-aware primary nav | expanded, collapsed (icon rail) |
| `UserMenu` | Navbar-right trigger (username → email → user icon, per §11.1) opening account dropdown | closed, open, mobile-collapsed (icon only) |
| `SearchBar` | Keyword/semantic toggle input | idle, focused, loading, with-results — see §13.1 for size variants |
| `StatCard` | Single metric display (count + label + optional trend) | default, loading skeleton |
| `ProjectCard` | Metadata-first project summary (grid item) | default, hover, approved/pending/rejected badge variants |
| `ProjectRow` | Compact list/table row variant of ProjectCard, used in admin tables | default, hover, selected |
| `MetadataTable` | Key-value technical metadata block (mono values) | default |
| `EmptyState` | No-results / no-data placeholder with icon, message, optional CTA | search-empty, filter-empty, admin-empty |
| `LoadingSkeleton` | Shimmer placeholder matching the shape of the content it replaces | card, row, text-block |
| `ActionBar` | Sticky bar of bulk/contextual actions (admin tables) | default, with-selection |
| `Button` | Primary, secondary, ghost, destructive variants | default, hover, active, disabled, loading |
| `Modal` | Overlay dialog | default, destructive-confirm |
| `Toast` | Transient feedback | success, error, info |
| `Badge` | Status pill (approved/pending/rejected, department code) | success, warning, error, neutral |
| `UploadDropzone` | Dashed-border PDF drop target (admin only) | idle, drag-active, uploading, error |
| `PipelineLog` | Inline scrolling technical log panel (admin ingestion only) | streaming, complete, error |
| `RoleGuard` | Wrapper that redirects non-permitted roles | — |
| `RagChatPanel` | Conversational interface with source citations | idle, streaming, cited-response |
| `SimilarProjectsRail` | Horizontal rail of recommended/related projects | default, loading, empty |
| `CoverPreview` | Static, non-interactive first-page thumbnail image (general-user Project Details) — never a document viewer | default, loading, unavailable |
| `RequestReportModal` | Author contact info + `mailto:`-based "Compose Email" action, replaces Download for general users | default, no-author-email-fallback |
| `PdfViewer` | Embedded, paginated full-document viewer with download — **admin-only**, never imported into any general-user-reachable page | default, loading, error |

### 13.1 SearchBar Sizing (Correction)

A prior implementation pass rendered `SearchBar` too small on its primary surfaces (Dashboard, Search) — undersized relative to §5.3's "search is the primary way both roles enter the system." Two explicit size variants:

| Variant | Height | Font size | Used on |
|---|---|---|---|
| `hero` | `56px` mobile / `64px` desktop | `text-h2` (18px) input text, `text-body` placeholder | Dashboard (§14.1), Semantic Search top input (§18.1) |
| `compact` | `40px` | `text-body` (14px) | Browse Projects toolbar (§16.1), navbar `⌘K` command palette trigger |

- `hero` variant: full content-width up to a `720px` max on Dashboard, centered and full-width on `/search`; generous internal padding (`16px` horizontal minimum), icon and mode-toggle segmented control sized proportionally (`20px` icons, not `16px`).
- Never render the `hero` variant at the same visual weight as a standard form input — it should read as the page's primary interactive surface, closer in presence to a `StatCard` row than to a filter field.

### 13.2 Badge Typography (Correction)

Status badges (`Approved` / `Pending` / `Rejected`, and department-code pills) were previously implemented with emoji glyphs, which violates §10's icon rule. Corrected spec:

- **Text:** `text-micro` (11px, medium weight, uppercase, `0.04em` letter-spacing) — the same eyebrow-text token used for field labels elsewhere in the system, so status pills read as data, not decoration.
- **Icon:** Lucide only, `14px`, `currentColor` inheriting the semantic token — `CheckCircle2` (approved, `--success-emerald`), `Clock` (pending, `--warning-amber`), `XCircle` (rejected, `--error-red`). No emoji character under any circumstance.
- **Layout:** icon then text, `4px` gap, inside a `--radius-sm` pill with a `1px` border in the matching semantic token at reduced opacity (not a solid fill) and text/icon at full semantic color — this keeps a grid with many badges from getting visually loud/tinted.
- Department-code badges (`BEI`, `BCT`, etc., §7.6) never carry a status icon — icon presence is reserved exclusively for approval-status semantics, so the two badge types stay visually distinguishable.

---

## 14. Dashboard (General User)

**Route:** `/dashboard` (default landing page after login for role `general`)

**Primary CTA:** **Explore Projects** — never Upload.

### 14.1 Structure (top to bottom)

1. **Welcome section** — "Welcome back, {first name}" (`text-h1`), one-line repository tagline underneath in `--text-secondary`.
2. **Search** — large `SearchBar` in keyword/semantic toggle mode, full content width, with placeholder text like `Search projects by topic, technology, or keyword...`.
3. **Repository stats strip** — row of `StatCard`s: total approved projects, departments represented, this year's submissions, total supervisors. Read-only, no admin metrics.
4. **Recent Projects** — grid of `ProjectCard` (most recently approved/published), 3-per-row, "View all" link to Browse Projects.
5. **Recommended Projects** — personalized or popularity-based `ProjectCard` grid, with a one-line rationale under the section header (e.g., "Based on your recent views").
6. **Recently Viewed** — compact horizontal rail (only shown once the user has view history).
7. **Popular Technologies** — a row of technology badges (e.g., `Django`, `pgvector`, `React`) sized/weighted by frequency; clicking filters Browse Projects.
8. **AI Assistant shortcut** — a single prominent card inviting the user into `/assistant`, styled with the `--accent-violet` accent used only for AI-assistant-related surfaces.

### 14.2 Explicit Exclusions

The general dashboard must **never** render: pending approval counts, upload buttons, ingestion status, processing queue, or any admin statistic. If a component needs role-conditional content, branch at the dashboard-composition level (`GeneralDashboard` vs `AdminDashboard`), not inside shared components.

---

## 15. Dashboard (Administrator)

**Route:** `/dashboard` (same route, different composition, resolved by role)

Administrators see everything in Chapter 14, **plus** an additional admin operations section inserted after the stats strip and before "Recent Projects":

### 15.1 Additional Modules

- **Pending Approvals** — `StatCard`-style summary with count, linking to `/admin/approvals`; if count > 0, rendered with an amber accent border (status signal, not decoration).
- **Upload Project** — a clearly-labeled secondary action button (not the page's primary CTA — Explore/Search remains primary even for admins) linking to `/admin/upload`.
- **Processing Queue** — compact list of in-flight ingestion jobs (filename, current pipeline stage, elapsed time), each row linking to that job's detail in Repository Management.
- **Repository Health** — small panel: last successful indexing run, embedding model in use (mono badge), database/vector-store status indicators (green/amber/red dot + label, never color alone).
- **Admin Analytics** — condensed chart cluster (Recharts): submissions by department, submissions by academic year, approval turnaround time. Full analytics live in Repository Management; this is a summary only.

### 15.2 Rules

- Admin modules are visually distinguished only by their content and section headers, not by a different color scheme — see §12.3 rationale.
- The admin dashboard must still lead with search and recent/recommended projects above the fold on desktop; admin operations occupy the second viewport, reflecting the "repository-first, not upload-first" principle even for admins.

---

## 16. Browse Projects

**Route:** `/projects` — available to both roles (general users see only approved projects; admins may toggle a status filter to include pending/rejected).

### 16.1 Layout

```
Page header: "Browse Projects" + result count
┌─────────────┬─────────────────────────────┐
│  Filters     │  SearchBar (keyword toggle) │
│  (sidebar,   │  Sort dropdown               │
│  ~260px)     │  Project grid (3-col)        │
│              │  Pagination                  │
└─────────────┴─────────────────────────────┘
```

### 16.2 Filters

Faceted filter sidebar (checkboxes/multi-select, each with a live count):
- Department
- Academic Year
- Cluster (e.g., AIML, as seen on submitted project cover pages)
- Technologies used
- Supervisor
- Status (**admin only**: Approved / Pending / Rejected)

Applied filters render as removable pill chips above the grid.

### 16.3 Sorting

`Most Recent` (default) · `Most Relevant` (only active when a search query is present) · `Alphabetical (A–Z)` · `Most Viewed`

### 16.4 Grid

`ProjectCard` grid per §9.3. Each card shows, top to bottom: department code badge (mono pill, top-left) + status badge (bottom-right, general users only ever see "Approved" so this badge is typically suppressed for them and only meaningful in admin context) → title (2-line clamp) → authors → supervisor → technology badges (max 4, "+N" overflow) → academic year, bottom-right small text.

### 16.5 Empty & Pagination States

- No results: `EmptyState` with a search icon, "No projects match your filters," and a "Clear filters" action.
- Pagination: numbered pagination control at the bottom, `24` items per page default.

---

## 17. Project Details

**Route:** `/projects/:id` — available to both roles.

### 17.1 Layout

```
Breadcrumb: Browse Projects / {Department} / {Title}
┌───────────────────────────────┬───────────────┐
│  Title (text-display)          │  Actions panel │
│  Authors · Supervisor · Year   │  (Request      │
│  Department badge · Status     │   Report,      │
│  badge (bottom-right per       │   Cite, Share) │
│  established rule)             │  admin only:   │
│                                 │   + Download   │
├───────────────────────────────┴───────────────┤
│  Abstract                                      │
├─────────────────────────────────────────────────┤
│  Results / Key Findings summary                │
├─────────────────────────────────────────────────┤
│  Metadata Table (MetadataTable component)      │
│  Technologies · Cluster · Roll numbers (mono)  │
├─────────────────────────────────────────────────┤
│  Cover Preview (static first-page thumbnail     │
│  image only — general users)                    │
│  OR embedded full PDF viewer (admin-only,       │
│  review/ingestion surfaces only)                │
├─────────────────────────────────────────────────┤
│  Similar Projects (SimilarProjectsRail)         │
└─────────────────────────────────────────────────┘
```

### 17.2 Content Rules

- Metadata always appears before the cover preview — never lead with any document-viewer surface.
- Roll numbers (e.g. `PUL080BCT050`) render in monospace inline next to author names.
- The **Results / Key Findings** block is a short structured excerpt captured at ingestion time (§20.1) — a handful of bullet points or a short paragraph, never a rendering of the report body itself. It exists specifically so a general user can evaluate a project's outcome without needing the full document.
- **Full-document access is role-gated, not just UI-hidden.** For general users, the "Cover Preview" is a static image (first page only, no pagination controls, no text layer, non-interactive) — it is not a lightweight version of a PDF viewer, it is a different, non-extractable asset generated at ingestion time. There is no code path, general-user route, or API response that returns the full PDF's bytes.
- The **Request Report** action (§17.1) opens a `Modal` with the listed authors' contact info and a **"Compose Email"** button (`mailto:` link pre-filled with the project title and a short template subject/body); it does not upload or attach the PDF anywhere. See §3.4.
- The **Similar Projects** rail is populated by the Similarity API (project-level embeddings, cosine similarity) and must show at least a loading skeleton while awaiting results — never a layout shift once loaded.
- Admins viewing a pending/rejected project see an additional inline **Review** action bar (Approve / Reject / Edit metadata) — general users never see this bar regardless of the project's status (they cannot access non-approved project detail pages at all; route guard returns 404/redirect rather than a visible-but-disabled review bar).
- Admins reviewing any project (approved, pending, or rejected) see the embedded full PDF viewer and a **Download** action in the Actions panel — this is an admin-only surface, never conditionally rendered inside the general-user Project Details page.

---

## 18. Semantic Search

**Route:** `/search` — available to both roles.

Designed to feel like an **AI-native search experience** (Perplexity-inspired), not a database query form.

### 18.1 Layout

- Large centered search input at the top, with a visible **Keyword / Semantic** mode toggle (segmented control).
- As the user types (semantic mode), show a subtle helper line: "Searching by meaning, not exact words."
- Results render as `ProjectCard`s in a single column (not grid) at this route, each annotated with a small relevance indicator (e.g., a muted percentage or a 1–5 bar strength meter) and, where useful, the specific matched excerpt shown as a 1–2 line highlighted snippet beneath the abstract preview.
- A persistent left rail repeats the Browse Projects filters so users can narrow a semantic query without leaving the page.

### 18.2 States

`idle` (empty state with example queries as clickable chips) → `loading` (skeleton rows + a short inline status like "Embedding query...") → `results` → `no-results` (`EmptyState` suggesting a rephrase or switching to keyword mode).

---

## 19. AI Assistant (RAG Chat)

**Route:** `/assistant` — available to both roles.

- Full-height chat layout: message history, input composer pinned to bottom, "New conversation" action in the header.
- This is the **one screen** in the product permitted to use the `--accent-violet` token prominently (avatar ring, active input border) — signaling "this surface is generative/AI," distinct from the deterministic blue used everywhere else.
- Every assistant response that draws on repository content must render **source reference chips** beneath the message — each chip is a compact `ProjectCard`-lite (title + department + year) linking to that project's detail page. This is non-negotiable: ungrounded responses (no retrieved sources) must be visually flagged with a small "No matching projects found in the repository" note rather than presented as equally authoritative.
- Streaming responses render token-by-token with a subtle blinking caret, no skeleton shimmer once streaming has started.
- Composer supports multi-line input, shows a disabled Send state while a response is in flight, and surfaces retrieval/generation errors as an inline error bubble (not a toast, since it's part of the conversation record).

---

## 20. Upload & Ingestion (Admin Only)

**Route:** `/admin/upload` — `RoleGuard: admin`

This is the one place in the product where **technical pipeline transparency is a feature**, not a distraction, because its audience is the administrator, not a general user.

### 20.1 Layout

1. **UploadDropzone** — dashed-border drop area (per established rule), accepts PDF, shows filename + size once selected.
2. **Metadata Preview panel** — appears once extraction completes; editable fields for title, abstract, **results/key-findings summary** (short, structured — this is what general users will see in place of the full report, so it must be reviewed for accuracy, not just auto-accepted), authors + contact email, roll numbers (mono input), supervisor, department, academic year, technologies, cluster. A static first-page cover image is generated automatically for `CoverPreview` (§17.2). Every extracted field is pre-filled but editable, with a subtle "auto-extracted" tag until the admin touches it.
3. **PipelineLog panel** — a `--surface-sunken` monospace log panel showing real pipeline stages as they occur, e.g.:
   ```
   > PyMuPDF active
   > Regex extraction
   > Chunk generation
   > Sentence Transformer loading (all-MiniLM-L6-v2)
   > pgvector indexing
   ```
   Each line appears with a timestamp prefix and a status icon (running/done/error) at line-start. This log is real, not decorative — it reflects actual backend pipeline events streamed to the client.
4. **Ingestion Summary** — once complete: chunk count, embedding dimensions, processing duration, and a clear "Submit for Review" action that moves the record into the Pending Approvals queue (it is **not** published directly).

### 20.2 Rules

- This page is never reachable by, or visible to, general users.
- Do not reuse `PipelineLog` anywhere outside the ingestion and (optionally) Repository Management contexts — it is an admin-only technical component.

---

## 21. Pending Approvals / Repository Management (Admin Only)

**Routes:** `/admin/approvals`, `/admin/repository` — `RoleGuard: admin`

### 21.1 Pending Approvals

- Table view (`ProjectRow` list) of all submissions awaiting review, sortable by submission date.
- Row actions: **Review** (opens the Project Details page in admin review mode, per §17.2), quick **Approve**/**Reject** icon actions for low-friction triage, with a confirmation `Modal` for Reject (destructive).
- `ActionBar` appears when rows are multi-selected, offering bulk approve/reject.

### 21.2 Repository Management

- Full record management: search/filter across **all** projects regardless of status, inline edit, unpublish, delete (destructive, confirm-gated).
- Full Admin Analytics view: charts for submissions by department/year/cluster, search usage trends, approval turnaround time, storage/index health.
- Ingestion history log (past `PipelineLog` runs, collapsed by default, expandable per record).

---

## 22. Authentication

**Route:** `/login`

- Single method: **Google OAuth**. No username/password form.
- Minimal centered card: repository wordmark, one sentence of context ("Sign in with your Google account to access the Pulchowk Project Repository"), single **Continue with Google** button.
- **Access is restricted to college-domain email addresses** (enforced server-side, per `accounts/authentication.py`). This is an authorization boundary, not just a UI hint — the frontend must not attempt to pre-filter or validate the domain client-side as a substitute for the backend check.
- If a user authenticates with Google using a non-college account, the backend rejects the session; the client shows a distinct **domain-rejected** state on the login card (not a generic error toast): a short, specific message — e.g., "This repository is only available to \[institution] accounts. Please sign in with your college email." — plus the same **Continue with Google** action so the user can retry with the correct account. Do not imply the account was "banned" or "denied" for any reason other than domain eligibility.
- Role is resolved server-side post-authentication; there is no role picker on the client — a user cannot self-elevate to administrator.
- Unauthenticated visitors hitting any protected route are redirected to `/login` with a return-to path preserved.

---

## 23. Profile & Settings

**Routes:** `/profile`, `/settings` — available to both roles, content scoped to the individual user regardless of role.

- **Profile:** name, roll number/faculty ID (mono), department, role badge (read-only, informational — "General User" or "Administrator"), recently viewed projects, (future) bookmarks.
- **Settings:** theme preference (if a light mode is ever introduced — see Chapter 29), notification preferences (e.g., admins: notify on new submission), search default mode (keyword vs semantic).
- No role-management controls exist here for anyone — role changes are an out-of-band administrative/database operation, not a self-service UI feature.

---

## 24. Accessibility

- Minimum contrast ratio **4.5:1** for body text, **3:1** for large text/icons, verified against the light palette in Chapter 7 (each token's ratio against `--surface-canvas` is noted inline in §7).
- Full keyboard navigation: every interactive element reachable via Tab, with a visible focus ring using `--accent-primary` at 2px offset outline — never suppressed.
- Status is never communicated by color alone: `Badge` components always pair color with a Lucide icon (`CheckCircle2`/`Clock`/`XCircle`, never an emoji — see §10, §13.2) and a text label.
- All images/thumbnails require descriptive `alt` text (e.g., "First page preview of {project title}").
- Modal and dropdown components trap focus and are dismissible via `Escape`.
- Form fields (Upload metadata, Settings) always have visible `<label>` elements, not placeholder-only labeling.

---

## 25. Responsive Design

| Breakpoint | Width | Behavior |
|---|---|---|
| Mobile | `<768px` | Sidebar collapses to a bottom sheet / hamburger drawer; 1-column card grid; search bar full-width and sticky under navbar |
| Tablet | `768–1279px` | Sidebar collapses to icon rail (`72px`) by default, expandable; 2-column card grid |
| Desktop | `≥1280px` | Full sidebar (`260px`) + 3-column card grid as specified throughout |

- The admin Processing Queue and PipelineLog panels reflow to full-width single-column stacks on mobile/tablet — they are never the reason a screen requires horizontal scrolling.
- Tables (`ProjectRow` lists in admin views) convert to stacked card-style rows below `768px`.

---

## 26. Motion Guidelines

- Transition duration: **150–250ms**, `ease-out` for entrances, `ease-in` for exits.
- Permitted motion: opacity fades, small translate (≤8px) on hover/entrance, hover background-color shifts, focus-ring appearance.
- **Forbidden:** parallax, glassmorphism blur effects, floating/bobbing decorative elements, large-distance slide-ins, skeleton shimmer that exceeds 1.5s loops without resolving to real content.
- Streaming text (RAG Assistant) is the one exception permitted a continuous, non-decorative animation (blinking caret) for as long as generation is in flight.

---

## 27. AI Agent Implementation Rules

Binding rules for any AI coding agent (Cursor, Claude Code, Codex, etc.) generating frontend code against this specification:

1. **Never hardcode colors.** Always reference the Tailwind tokens defined from Chapter 7's CSS variables.
2. **Never use inline styles.** All styling goes through Tailwind utility classes mapped to this spec's tokens.
3. **Always reuse components from Chapter 13.** Do not recreate `ProjectCard`, `SearchBar`, `Badge`, etc. inside a page file — import and compose.
4. **Never invent a page layout not described in this document.** If a new page is required, extend this document first (propose an addition), then implement.
5. **Always resolve role at the layout/composition level**, not with scattered inline conditionals (`{role === 'admin' && ...}`) spread through shared components. Prefer distinct composed dashboards/pages per §3.3.
6. **Never render admin-only navigation, dashboard modules, or routes to a general user**, even in a disabled state. Absence, not disablement, is the correct treatment.
7. **Never use decorative gradients, glow, or glassmorphism** anywhere in the product.
8. **Never imitate fintech-dashboard conventions** (large colorful KPI tiles with heavy shadows, sparkline-heavy hero sections, colorful donut charts as decoration).
9. **Always prioritize metadata over imagery** on every project-related surface.
10. **Always use monospace styling for machine-meaningful values** (UUIDs, roll numbers, department codes, model names, vector dimensions).
11. **Keep parser/pipeline technical logs confined to admin ingestion and repository-management surfaces only.**
12. **When uncertain, choose the denser, more technical, more metadata-forward option** — this errs correctly for this product's audience.
13. **Never expose full-report PDF content to a general user**, in the frontend or in any API call a general-user session can make — not the file itself, not an embedded viewer, not the RAG assistant quoting report body text. Treat this as a security requirement equivalent to the role-guard rules in §3.3, not a content-design preference. See §3.4.

---

## 28. Do's & Don'ts

**Do:**
- Wrap UUIDs, roll numbers, vectors, and model names in monospace/code style.
- Use emerald only for successful states.
- Maintain the single consistent border-radius scale (§9.4).
- Prefer technical clarity over polish-for-its-own-sake.
- Lead every project surface with metadata.
- Keep Explore/Search as the primary call-to-action for all roles.
- Use Lucide icons for every piece of iconography, including count/stat labels like "Folders Indexed" (`Folder`/`FolderOpen`) and person references like "Supervisor" (`UserCircle`).
- Order the navbar `UserMenu` as username → email → user icon, per §11.1 — no plain-text role pill in the persistent navbar.

**Don't:**
- Use emoji characters anywhere in the product — status badges, stat cards, empty states, log panels, or copy (§10). This includes folder/document counts and person/role references, which must use Lucide icons instead.
- Use glowing cards, colorful decorative panels, or gradients.
- Overuse shadows — prefer hairline borders.
- Leave large empty whitespace; fill it with real repository information.
- Create marketing-style dashboards (large hero illustrations, big colorful CTAs).
- Show any admin control, count, or route to a general user.
- Let Upload become the product's visual or narrative center of gravity.
- Render `PdfViewer`, a Download action, or any full-PDF byte stream on any general-user-reachable page or API response — general users get abstract, results summary, and a static cover image only, per §3.4.

---

## 29. Future Expansion

Reserved, not yet implemented — do not build backing functionality, but reserve UI slots as specified:

- **Bookmarks/Favorites** (general users): nav item and profile section render in a visibly "Coming soon" disabled state rather than being omitted, per §12.1.
- **Dark mode:** light is now the default and only theme (§7). If a dark mode is ever wanted as a secondary, opt-in theme, token structure should be written so a parallel dark-token set can be added without restructuring components — but do not attempt this until explicitly requested.
- **Multi-department expansion:** department badge and filter components are already data-driven (not hardcoded to BCT) to support future rollout beyond the Department of Electronics & Computer Engineering.
- **Citation export** (BibTeX/APA) from Project Details "Cite" action — placeholder action exists in §17.1's Actions panel; wire-up deferred.

---

## Revision History

| Date | Change |
|---|---|
| 2026-07-17 | Added §2.1 Institutional Identity (crest, `--accent-gold`, footer institutional line); added `--accent-gold` token (§7.4); added explicit no-emoji rule (§10, §13.2, §28); added `SearchBar` size variants and `hero` sizing correction (§13.1); added `UserMenu` component + navbar order spec — username → email → user icon, no text role pill (§11.1, §13). These are corrections against an existing implementation, not new-product speculation — see `STATUS.md` for which surfaces still need the fix applied. |
| 2026-07-17 (later same day) | **Flipped the entire theme from dark to light** (§6, §7): white canvas, light grey raised/sunken surfaces, all text/accent/semantic tokens re-derived and checked against WCAG contrast math. This supersedes every dark-theme value in the prior revision — do not mix old dark hex values with the new light table. §29's dark-mode note now describes dark as a possible *future* secondary theme, not the default. |