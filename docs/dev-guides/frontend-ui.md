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

## Tabler / admin template (deferred)

**Selected for a future spike:** [Tabler](https://github.com/tabler/tabler) (MIT, Bootstrap 5). AdminLTE 4 remains the fallback.

**Not adopted in Phase 3.** Loading Bootstrap/Tabler beside today’s hand-rolled `base.html` + `common.css` risks cascade collisions. Revisit only after this SSOT is stable, ideally as an isolated chrome spike (one Build page + one Results page) behind an explicit decision.
