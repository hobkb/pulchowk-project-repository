### 2026-07-12-core-Standardized API Response Architecture

A centralised response architecture using a shared success response helper function and a global DRF exception handler. A consistent API response for all APIViews across all apps can be achieved.

### 2026-07-12-accounts-Email-Based Identity Model

User an email-based user model aligned with Google OAuth. Used email as login identifier and Google's sub identifier as the identity to uniquely identify users in database.


### 2026-07-12-accounts-JWT Cookie Authentication Strategy

Used HttpOnly cookie-based JWT authentication, for that a custom authentication class is written on accounts/authentication.py. So, client side JS cannot access the cookies.

### 2026-08-23-frontend-Redesign and new routes

The interface was rebuilt on a new design system ("The Register", see `src/index.css`):
Source Serif 4 for the record and Public Sans for the interface apparatus (IBM Plex is gone
entirely, as is the monospace family — identifiers use the `.numeric` utility), a warm paper
ground, a single institutional crimson, square-ish geometry with no radius above 4px, and
structure carried by hairline rules rather than cards. The old `src/components/ui/*`
primitives were replaced by `src/components/ui/primitives.jsx` + `Dialog.jsx`, re-exported
through `src/components/ui.jsx`. `Card`, `StatusTag` and `Modal` remain as compatibility
aliases for the admin ingestion pages, but nothing of their old appearance survives.

New routes (all previously listed in the sidebar but unrouted, so they fell through to the
catch-all and silently redirected to the landing page):

- `/projects` — the catalogue. Debounced backend keyword search, department/level/batch
  facets built from `/projects/facets/`, all state in the URL, one in-flight request at a
  time via `AbortController`. No client-side filtering.
- `/notifications` — the full notice list, paginated by following the API's own `next`.
- `/settings` — read-only account details, from `/accounts/me/`'s new `profile` block.
- `/assistant` — an honest placeholder; there is no assistant implementation, so the page
  contains no chat UI of any kind.
- `*` — a real 404 page. Unknown addresses are no longer redirected.

`/admin/repository` and `/bookmarks` were removed from the navigation: neither has a backend
or a page behind it.

### 2026-08-23-frontend-Repository redesign (second pass)

Rebuilt on a new design system after the previous one read as editorial
rather than institutional. Reference points: the UI/UX patterns of mature
academic repositories (white content surface, thin institutional accent rule,
light breadcrumb band, flat solid buttons at ~3px radius, plain bordered
panels without shadows, dense result rows, restrained status colours), with
Pulchowk's own identity supplying the palette — deep navy for structure and
action, TU-crest ochre as the identity rule and current-position marker.

- **One typeface**: Source Sans 3 for the entire interface. The previous
  serif + sans pairing and the monospace family are both gone; numerals use a
  `.tnum` tabular-figures utility rather than a second font.
- **Sentence case throughout.** `text-transform` appears nowhere in
  `index.css`; the tracked-out uppercase micro-label utility was removed and
  all-caps literals ("SUBMISSION #1", "Skip Section Editing") were rewritten.
- **No sidebar.** Top-level sections moved into the header so the catalogue
  gets full width; below `xl` they collapse into a drawer with the same
  labels. `Sidebar.jsx` was deleted.
- **Project detail shows the abstract only.** Report sections are neither
  rendered nor fetched. The full report appears as a locked preview whose
  blurred "page" is a drawn placeholder of grey bars — no report text is
  present in the DOM, so nothing is recoverable by removing the CSS filter.
  "Request report" opens a real prefilled `mailto:` to the recorded authors.
  `DocumentSections.jsx` (the public section renderer) was deleted.
- **Admin section hierarchy fixed in the editor.** New `normalizeSectionTree`
  in `IngestionWorkflow.jsx`: payloads that already nest are used as-is;
  payloads stored **before** the pipeline emitted `children` are flat lists
  carrying only `heading_level`, and are rebuilt into a tree with the same
  open-section stack the backend uses. That flat-payload case is why
  "Introduction", "1.1 Background" and "1.2 Problem Statement" appeared as
  three unrelated top-level sections. Sections are now collapsible, indented,
  and joined by a rule down the subtree, with a subsection count on each
  parent; a heading that already carries its own number does not get a second
  one printed beside it.
- **Supervisors** are shown wherever the data has them and stated as
  "Not available" when it does not — never hidden, never invented.
- `/bookmarks` is now a real page backed by the new bookmarks API.
