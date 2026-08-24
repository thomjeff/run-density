# Frontend UI contract (Issue #791 Phase 3)

Short guide so new tables and Plan chrome do not fork styling again.

## Stack

- Jinja2 templates in `frontend/templates/`
- Vanilla JS in `frontend/static/js/`
- Shared styles in `frontend/static/css/common.css` (linked from `base.html`)
- **Tabler** `@tabler/core@1.4.0` admin chrome (always on via `base.html` / `html.rf-tabler`) + `tabler_spike.css`
- Leaflet for maps
- **No** Tailwind, React, or npm build step

## Tables (one primitive)

```html
<div class="scrollable-table-container">
  <table class="table-sticky-header">
    <thead>
      <tr>
        <th class="table-sortable" data-sort="name">
          Name <span class="table-sortable-indicator">↕</span>
        </th>
        <th class="course-map-action-cell">Actions</th>
      </tr>
    </thead>
    <tbody>…</tbody>
  </table>
</div>
```

| Piece | Class | Notes |
|-------|--------|--------|
| Scroll + sticky area | `.scrollable-table-container` | Required for sticky headers |
| Table | `table.table-sticky-header` | Sticky `thead` |
| Sortable header | `.table-sortable` | Cursor + hover |
| Sort glyph | `.table-sortable-indicator` | Update text to `▲` / `▼` / `↕` in JS |
| Actions cell | `.course-map-action-cell` or `.rf-table-actions` | Centered icon buttons |

**Do not** add page-local `#my-table th { padding… }` or a third sort contract (`::after`, `.sortable` / `.sort-indicator` forks). Override only when Build map tables need denser layout (`course_mapping_styles.html`).

## Action buttons

Use `frontend/static/js/table_actions.js` (`TableActions.createIconButton`). Buttons get `.course-map-action-btn` (and optional `--copy` / `--reverse`). Styles live in `common.css`.

## Plan chrome

On Plan analysis pages (Overview, Density, Flow, Junctions, Motion, Progression, Locations — not the Runs catalog):

```jinja
{% include "partials/run_context.html" %}
```

Provides Plan sub-nav + run banner / empty CTA. Styles: `.rf-results-*` in `common.css`.

Retired destinations (Issue #888 / #891): `GET /segments` redirects to Density; `GET /reports` redirects to Overview. Do not add those items back to Plan nav. Segment APIs and report artifacts remain.

**Density Segment Analysis** uses `.rf-density-analysis-scroll` (`max-height: 25vh`) so the course map and selected-segment tile stay on screen. Do not restore the global `50vh` table height on that table.

## Tabler UI (Issue #798 Phase 7) — sole admin chrome

**[Tabler](https://tabler.io/)** (`@tabler/core`) is an open-source admin dashboard UI kit (MIT License). Runflow loads it **always** from the jsDelivr CDN on pages that extend `base.html` — there is still no npm/webpack step. Classic dual-chrome was removed in Issue #798 Phase 7; `?ui=tabler` is not required and should not be reintroduced as a chrome gate.

### What we load

| Asset | Source |
|-------|--------|
| CSS | `https://cdn.jsdelivr.net/npm/@tabler/core@1.4.0/dist/css/tabler.min.css` |
| JS | `https://cdn.jsdelivr.net/npm/@tabler/core@1.4.0/dist/js/tabler.min.js` |
| Shared styles | `frontend/static/css/common.css` |
| Runflow overrides | `frontend/static/css/tabler_spike.css` |

Wired unconditionally from `frontend/templates/base.html` (`html.rf-tabler`).

### UX model (horizontal light shell)

- Top bar (Plan): **Runflow** | **Plan ▾** | **Runs ▾** | Overview · Density · Flow · Junctions · Motion · Progression · Locations | Logout
- Top bar (Build): **Runflow** | **Build ▾** | Legs · Courses · Runners · Packages | Logout
- Top bar (Execute): **Runflow** | **Execute ▾** | Reopen | Logout (Issue #900); no Locations item
- Workspace control switches Build ↔ Plan ↔ Execute (mutually exclusive chrome; Issue #878, formerly Results/Build in #842)
- **Runs ▾:** up to 10 recent runs (label primary, short id secondary) + **View all runs…** → `/dashboard` (Plan only)
- Picking a run opens **`/overview?run_id=`** (day is derived from the run — Issue #841; no day dropdown)
- Context strip: run ID / description / date / day; **Exports** jumps to Overview `#rf-overview-exports`; **Package** is on Overview Analysis Inputs (name links to Build → that package)
- Overview **Exports** (Issue #891): `Reports (.zip)` and `Data Files (.zip)` for the selected run/day via `/api/reports/export.zip`
- Density (Issue #888) is the segment workspace (course map + Segment Analysis + selected-segment assessment). Segments is not a Plan destination.
- Last Plan route/run, last Build route, and last Execute route are restored when switching workspaces
- Runs catalog is history-only
- Build hub page still has Legs / Courses / Runners / Packages panels; top nav mirrors hub views
- **Build → Runners** is the org runner-dataset library (`runflow/org/runners/{dataset_id}/`). Datasets are immutable; a Package assigns a compatible dataset and freeze-copies required `{event}_runners.csv` files (Issue #879)
- Package header owns **Analysis readiness**; **Run analysis** / start times are on **Plan → Overview** (Issue #904). Assign courses keeps **Build race exports**
- **Build → Legs** **Edit Locations** is the bulk ops editor; package combined-course tables are inspect-only
- Historical multi-day analysis trees are not browsed in product chrome; archive offline if needed

### Attribution & license

- Project: [tabler/tabler](https://github.com/tabler/tabler) / [tabler.io](https://tabler.io/)
- License: **MIT** — free to use in Runflow; keep copyright notice when redistributing Tabler sources
- We consume the published CDN build; we do not vendor a fork in-repo
- See also [Developer Guide → Frontend Architecture](developer-guide.md#frontend-architecture)

### Guidelines

- Prefer Tabler primitives (`navbar`, `card`, `nav-tabs` / `card-header-tabs`, `dropdown`, `btn`) under `html.rf-tabler`, remapped in `tabler_spike.css`
- Do not reintroduce a parallel classic header/nav/footer branch in `base.html`
