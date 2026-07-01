/**
 * Shared edit/delete icon buttons for configuration and legs tables.
 */
(function (global) {
    var EDIT_ICON_SVG =
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
        '<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>' +
        '<path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>' +
        '</svg>';
    var DELETE_ICON_SVG =
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
        '<polyline points="3 6 5 6 21 6"/>' +
        '<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>' +
        '<line x1="10" y1="11" x2="10" y2="17"/>' +
        '<line x1="14" y1="11" x2="14" y2="17"/>' +
        '</svg>';
    var EXPORT_ICON_SVG =
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
        '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>' +
        '<polyline points="7 10 12 15 17 10"/>' +
        '<line x1="12" y1="15" x2="12" y2="3"/>' +
        '</svg>';
    var COPY_ICON_SVG =
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
        '<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-2"/>' +
        '<path d="M15 2H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2z"/>' +
        '</svg>';
    var REVERSE_ICON_SVG =
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
        '<polyline points="17 11 21 7 17 3"/>' +
        '<line x1="21" y1="7" x2="9" y2="7"/>' +
        '<polyline points="7 13 3 17 7 21"/>' +
        '<line x1="3" y1="17" x2="15" y2="17"/>' +
        '</svg>';

    function createIconButton(kind, title, onClick) {
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'course-map-action-btn';
        if (kind === 'copy') {
            btn.className += ' course-map-action-btn--copy';
        } else if (kind === 'reverse') {
            btn.className += ' course-map-action-btn--reverse';
        }
        btn.title = title;
        btn.setAttribute('aria-label', title);
        if (kind === 'delete') btn.innerHTML = DELETE_ICON_SVG;
        else if (kind === 'export') btn.innerHTML = EXPORT_ICON_SVG;
        else if (kind === 'copy') btn.innerHTML = COPY_ICON_SVG;
        else if (kind === 'reverse') btn.innerHTML = REVERSE_ICON_SVG;
        else btn.innerHTML = EDIT_ICON_SVG;
        if (onClick) {
            btn.addEventListener('click', onClick);
        }
        return btn;
    }

  /**
   * Two-step confirm before destructive deletes.
   * @param {{ subject: string, detail?: string }} opts
   */
    function doubleConfirmDelete(opts) {
        opts = opts || {};
        var subject = opts.subject || 'this item';
        var detail = opts.detail ? '\n\n' + opts.detail : '';
        if (
            !window.confirm(
                'Delete ' + subject + '?' + detail + '\n\nThis cannot be undone.'
            )
        ) {
            return false;
        }
        return window.confirm(
            'Are you absolutely sure you want to permanently delete ' +
                subject +
                '?'
        );
    }

    global.TableActions = {
        createIconButton: createIconButton,
        doubleConfirmDelete: doubleConfirmDelete,
    };
})(typeof window !== 'undefined' ? window : this);
