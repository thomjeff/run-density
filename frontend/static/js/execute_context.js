/* Active Day Plan context for Execute pages (Issue #920). */
(function () {
    "use strict";

    window.runflowExecuteContext = { resolved: false, active: false };

    function apply(ctx) {
        ctx = ctx || { active: false };
        ctx.resolved = true;
        window.runflowExecuteContext = ctx;
        if (ctx.active && ctx.run_id) {
            window.runflowDay = window.runflowDay || {};
            window.runflowDay.run_id = ctx.run_id;
            window.runflowDay.selected = ctx.weekday_code || "";
            try {
                localStorage.setItem("selected_run_id", ctx.run_id);
                if (ctx.weekday_code) {
                    localStorage.setItem("selected_day", ctx.weekday_code);
                }
            } catch (err) {}
        }
        document.dispatchEvent(
            new CustomEvent("runflow:execute-context", { detail: ctx })
        );
    }

    fetch("/api/execute/active-context", { credentials: "same-origin" })
        .then(function (resp) {
            return resp.json();
        })
        .then(apply)
        .catch(function () {
            apply({ active: false });
        });
})();
