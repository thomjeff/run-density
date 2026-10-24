/* Active Day Plan context for Execute pages (Issue #920). */
(function () {
    "use strict";

    window.runflowExecuteContext = { resolved: false, active: false };

    function apply(ctx) {
        ctx = ctx || { active: false };
        ctx.resolved = true;
        window.runflowExecuteContext = ctx;
        if (ctx.active && ctx.plan_id) {
            window.runflowDay = window.runflowDay || {};
            window.runflowDay.plan_id = ctx.plan_id;
            window.runflowDay.selected = ctx.weekday_code || "";
        }
        var label = document.getElementById("rf-execute-plan-name");
        if (label) {
            if (ctx.active && (ctx.name || ctx.calendar_date)) {
                var parts = [];
                if (ctx.name) parts.push(ctx.name);
                if (ctx.calendar_date) parts.push(ctx.calendar_date);
                label.textContent = parts.join(" · ");
            } else {
                label.textContent = "No plan active";
            }
        }
        document.dispatchEvent(
            new CustomEvent("runflow:execute-context", { detail: ctx })
        );
    }

    function refresh() {
        return fetch("/api/execute/active-context", { credentials: "same-origin" })
            .then(function (resp) {
                return resp.json();
            })
            .then(apply)
            .catch(function () {
                apply({ active: false });
            });
    }

    window.runflowRefreshExecuteContext = refresh;
    refresh();
})();
