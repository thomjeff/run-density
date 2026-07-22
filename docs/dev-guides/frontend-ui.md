# Frontend UI contract (Issue #791 Phase 3)

Short guide so new tables and Results chrome do not fork styling again.

## Stack

- Jinja2 templates in `frontend/templates/`
- Vanilla JS in `frontend/static/js/`
- Shared styles in `frontend/static/css/common.css` (linked from `base.html`)
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

## Results chrome

On Segments / Density / Flow / Locations / Reports (not Runs):

```jinja
{% include "partials/run_context.html" %}
```

Provides Results sub-nav + run banner / empty CTA. Styles: `.rf-results-*` in `common.css`.

## Tabler UI (Issue #796) — third-party admin chrome

**[Tabler](https://tabler.io/)** (`@tabler/core`) is an open-source admin dashboard UI kit (MIT License). Runflow loads it **opt-in only** from the jsDelivr CDN — there is still no npm/webpack step.

### How to enable

Append `?ui=tabler` (or `&ui=tabler`) to any authenticated page URL. Use **Classic UI** in the top bar (or drop `ui=tabler`) to leave the preview. Default chrome is unchanged when the query param is absent.

### What we load

| Asset | Source |
|-------|--------|
| CSS | `https://cdn.jsdelivr.net/npm/@tabler/core@1.4.0/dist/css/tabler.min.css` |
| JS | `https://cdn.jsdelivr.net/npm/@tabler/core@1.4.0/dist/js/tabler.min.js` |
| Runflow overrides | `frontend/static/css/tabler_spike.css` (linked only when `ui=tabler`) |

Wired from `frontend/templates/base.html` when Jinja sets `tabler_ui` from the query string.

### UX model (horizontal light shell)

- Top bar: **Runflow** | **Runs ▾** | Overview · Segments · Density · Flow · Locations · Reports | **Build** | Day (multi-day) | Classic UI | Logout
- **Runs ▾:** up to 10 recent runs (label primary, short id secondary) + **View all runs…** → `/dashboard?ui=tabler`
- Picking a run opens **`/overview?run_id=&day=&ui=tabler`** (Analysis Inputs + Analysis Outputs)
- Context strip: Active run · label · short id · day · **Package**
- Runs catalog under Tabler is history-only
- Build hub uses Tabler **card-header-tabs** for Legs / Courses / Packages
- Nav preserves `ui=tabler` via `updateNavLinks` / Results `resultsHref` / Build handoffs

### Attribution & license

- Project: [tabler/tabler](https://github.com/tabler/tabler) / [tabler.io](https://tabler.io/)
- License: **MIT** — free to use in Runflow; keep copyright notice when redistributing Tabler sources
- We consume the published CDN build; we do not vendor a fork in-repo
- See also [Developer Guide → Frontend Architecture](developer-guide.md#frontend-architecture)

### Guidelines

- Do **not** load Tabler CSS/JS on Classic UI pages
- Prefer Tabler primitives (`navbar`, `card`, `nav-tabs` / `card-header-tabs`, `dropdown`, `btn`) under `html.rf-tabler`, remapped in `tabler_spike.css`
- Keep Classic markup paths working; dual chrome is gated by `{% if tabler_ui %}`
