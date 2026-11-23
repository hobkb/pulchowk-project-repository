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
### 2026-08-23-repository-Keyword Search, Facets and Nested Sections

Search, filtering and the published section hierarchy. No schema change; all of this is
serializer/view level.

- `GET /api/repository/projects/` — search and filtering are now entirely server-side.
  - `?q=<text>` — keyword search. The query is split on whitespace and **every term must
    match at least one** of: title, abstract, batch, department name, author/supervisor
    name, keyword, domain. (Previously a single `icontains` over the whole string, so
    `"solar tracker"` only matched that exact adjacent phrase.) This is plain substring
    matching — there is no ranking model and no semantic component, and the UI must not
    describe it as anything else.
  - `?department=<name>` — now an **exact** (case-insensitive) match, not `icontains`.
  - `?academic_level=<UG|Masters|PhD|Faculty>` and `?batch=<code>` — new exact filters.
  - Results are de-duplicated and ordered newest-published-first.

- `GET /api/repository/projects/facets/` — **new**. The filter values that actually occur
  among published projects, with counts: `{ total, departments[{name, count}],
  academic_levels[{name, count}], batches[{name, count}] }`. Lets a client build filters
  from real data instead of offering choices that match nothing.

- `GET /api/repository/projects/{id}/` — `sections[]` is now a **nested tree**. Each node
  carries `children[]` (recursively), plus `id` alongside the existing fields. The tree is
  rebuilt from the flat `ProjectSection` rows using document order + `heading_level`; a
  level that would leave an impossible gap is clamped rather than dropped, so no section
  can disappear.

Two publish-path fixes stand behind that:

- `ProjectSection.display_order` is now a single document-wide pre-order sequence. The
  ingestion tree numbers each node **within its own parent**, so `"1.1"` and
  `"2 Literature Review"` both arrived as `display_order=1`; writing those through collided
  on a model ordered by `display_order`, and published sections read back interleaved.
- Section headings are no longer passed through `normalize_person_name` on publish, which
  stripped the dots out of numbering (`"1.1 Background"` → `"11 Background"`).
  `normalize_section_title` now preserves a leading numbering prefix and in-word
  punctuation; `normalize_canonical_section` keeps the old bare-alphanumeric behaviour,
  since it is a lookup key rather than display text.

### 2026-08-23-notifications-Notification API

Persistent, per-user notifications raised by real ingestion lifecycle events. All endpoints
require authentication and are scoped to `request.user`.

- `GET /api/notifications/` — paginated (`page`, `page_size`, max 100), newest first.
  Fields: `id`, `notification_type`, `message`, `job`, `project`, `is_read`, `created_at`.
- `GET /api/notifications/unread-count/` → `{ "count": n }`.
- `POST /api/notifications/{id}/read/` — 404 for another user's notification.
- `POST /api/notifications/read-all/` → `{ "updated": n }`.

Types and their triggers: `JOB_READY_FOR_REVIEW` and `JOB_AWAITING_ADMIN` (pipeline reaches
EXTRACTED — the first to the uploader, the second fanned out to admins and active
department admins), `JOB_FAILED` (pipeline raised), `JOB_PUBLISHED` (publish view).
Notifications are only ever created by `notifications.services.NotificationService`, never
through the API.

### 2026-08-23-accounts-Current User Profile Block

- `GET /api/accounts/me/` gains a read-only `profile` object — the linked `Person`, or
  `null` before onboarding. Always includes `full_name`, `email`, `department`, `kind`;
  `kind="student"` adds `roll_number` and `academic_level`, `kind="faculty"` adds `title`,
  `designation`, `research_group`. Previously only the person's **id** was exposed, so a
  client had no way to display which department or roll number an account belonged to
  without fetching every user and guessing. Every field on the serializer remains
  read-only: there is still no self-service account editing endpoint.

### 2026-08-23-ingestion-reprocess_people management command

`python manage.py reprocess_people` re-runs people extraction against the **original PDF**
of published projects and adds only the people currently missing — principally supervisors
dropped by the older extraction logic.

Strictly additive: it never edits, re-roles or deletes an existing `ProjectPerson`, never
touches project fields or sections, and resolves an existing `Faculty` without
`update_or_create` (which would overwrite a hand-corrected designation with an empty
string). Flags: `--dry-run`, `--include-authors`, `--project-id N`, `--all-projects`
(default is to skip projects that already have a supervisor).

### 2026-08-23-repository-Report body is confidential

The extracted report body is student work and is now served ONLY to
reviewers (staff, superusers, `role="admin"`, or an active `DepartmentAdmin`).
Enforced in the serializer, not the interface: it was previously returned to
every caller including anonymous ones, so the full extracted text of every
report was readable straight from the public API.

- `GET /api/repository/projects/{id}/` — `sections` and `references` are `[]`
  for an unprivileged caller, and a new boolean `sections_restricted` says so
  explicitly, so a client can state the restriction rather than render an
  empty document and imply the report has no content.
- `GET /api/repository/projects/` — `resultsSummary` previously returned the
  raw text of the Results (or Conclusion) section to anyone listing projects.
  It is now `""` unless the caller is a reviewer.
- `pdfUrl` was already reviewer-only and is unchanged.

The abstract deliberately stays public: it is the readable academic summary
the catalogue is built on.

Also fixed here: `get_supervisors` reached `person.faculty` through
`getattr(..., None)`. Person→Faculty is multi-table inheritance, so that
accessor raises `Faculty.DoesNotExist` (not `AttributeError`) for a
non-faculty person — a plain `Person` recorded as an Industry Mentor would
have crashed the whole response. It now catches `ObjectDoesNotExist`.

### 2026-08-23-repository-Bookmarks API

The `Bookmark` model already existed with no endpoints, so a "Saved" entry in
the navigation could only have been decorative. All endpoints require
authentication and are scoped to `request.user`.

- `GET /api/repository/bookmarks/` — the user's saved projects, serialised as
  catalogue cards. Projects that are no longer `Published` are omitted.
- `POST /api/repository/bookmarks/` `{"project": id}` — idempotent; 404 for a
  project that is not published.
- `GET /api/repository/bookmarks/{project_id}/` → `{"bookmarked": bool}`.
- `DELETE /api/repository/bookmarks/{project_id}/`.
