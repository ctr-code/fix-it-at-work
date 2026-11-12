/* jshint esversion: 6 */
// Filter table rows with dropdowns: <select data-filter-rows="#triage tbody" data-filter-key="priority">
// keeps rows whose data-priority matches the chosen value ("" means any). Dropdowns pointing at the
// same table combine: a row shows only if it matches all of them.
// - If the table is in a tab, that tab's count becomes "2 of 6" while filtering.
// - [data-row-filter-empty] in the same tab shows (and the table hides) when no rows match;
//   any [data-clear-row-filter] button there sets every dropdown back to "All".
// Choices are remembered on this device, so they're kept when coming back from a case.
(() => {
    "use strict";

    const load = (key) => { try { return window.localStorage.getItem(key); } catch (e) { return null; } };
    const save = (key, value) => { try { window.localStorage.setItem(key, value); } catch (e) { /* blocked */ } };
    const storeKey = (select) => "fiaw-filter-" + select.id;

    // Group the dropdowns by the table they filter
    const groups = new Map();
    document.querySelectorAll("select[data-filter-rows]").forEach((select) => {
        const target = select.dataset.filterRows;
        if (!groups.has(target)) { groups.set(target, []); }
        groups.get(target).push(select);
    });

    groups.forEach((selects, target) => {
        const tbody = document.querySelector(target);
        if (!tbody) { return; }
        const rows = Array.from(tbody.rows).filter((r) => r.querySelector("td:not([colspan])"));
        const scope = selects[0].closest(".tab-pane") || document;
        const wrapper = tbody.closest(".table-responsive");
        const empty = scope.querySelector("[data-row-filter-empty]");
        const tab = scope.id && document.querySelector('[data-bs-target="#' + scope.id + '"] .tab-count');

        const bar = selects[0].closest("[data-row-filter-bar]");
        if (bar) { bar.hidden = false; }
        const status = document.createElement("p");
        status.className = "visually-hidden";
        status.setAttribute("aria-live", "polite");
        (bar || selects[0]).after(status);

        const apply = () => {
            const active = selects.filter((s) => s.value);
            let shown = 0;
            rows.forEach((row) => {
                const match = active.every((s) => row.dataset[s.dataset.filterKey] === s.value);
                row.hidden = !match;
                shown += match;
            });
            if (tab) { tab.textContent = active.length ? shown + " of " + rows.length : String(rows.length); }
            if (empty) { empty.hidden = shown > 0; }
            if (wrapper) { wrapper.hidden = shown === 0; }
            // e.g. "Showing 1 of 6 cases: Main Office, High."
            status.textContent = active.length
                ? "Showing " + shown + " of " + rows.length + " cases: "
                    + active.map((s) => s.options[s.selectedIndex].text).join(", ") + "."
                : "Showing all " + rows.length + " cases.";
        };

        selects.forEach((select) => {
            // Only reuse a saved choice if it's still in the list
            const saved = load(storeKey(select));
            if (saved && Array.from(select.options).some((o) => o.value === saved)) { select.value = saved; }
            select.addEventListener("change", () => {
                save(storeKey(select), select.value);
                apply();
            });
        });
        if (selects.some((s) => s.value)) {
            apply();
            status.textContent = "";  // don't announce on page load
        }

        scope.querySelectorAll("[data-clear-row-filter]").forEach((button) => {
            button.addEventListener("click", () => {
                selects.forEach((s) => { s.value = ""; save(storeKey(s), ""); });
                apply();
                selects[0].focus();
            });
        });
    });
})();
