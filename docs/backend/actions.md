### 2026-08-09-repository-Published Projects Read API

Read-only endpoints for verified, published projects. Only ingestion jobs that have been
published (status `VERIFIED`) surface a `Project` row with `status="Published"` — those are
the only rows returned here. General users are served the same lists/details as admins,
except that the full report PDF URL (`pdfUrl`) is only included for staff/admin users.

- `GET /api/repository/projects/`
  - Returns all `Project` rows with `status="Published"`, in a `success_response` envelope (`data` is an array of cards).
  - Filtering (optional):
    - `?q=<text>` — case-insensitive match on title, abstract, author name, or keyword.
    - `?department=<name>` — case-insensitive match on department name.
  - Card fields: `id`, `title`, `authors[{name, rollNumber, email, role, display_order}]`, `supervisor` (joined names), `supervisors[]`, `year` (derived from `batch`, e.g. `"078"` → `"2078"`), `batch`, `department`, `cluster` (from domains / research group, empty currently), `status`, `abstract`, `resultsSummary` (from the Results/Discussion/Conclusion section), `technologies`/`keywords` (project keywords), `coverImage` (always null for now), `pdfUrl` (staff/admin only).

- `GET /api/repository/projects/{project_id}/`
  - Detail for a specific verified project; 404 for unknown or un-published projects.
  - Adds to the card fields: `sections[]` (ordered by `display_order`: `heading`, `canonical_section`, `heading_level`, `content`, `page_start`, `page_end`, `word_count`), `references[]`, `domains[]`, `academic_level`, `project_type`, `language`, `github_url`, `doi_url`, `publication_url`, `demo_url`, `updated_at`.