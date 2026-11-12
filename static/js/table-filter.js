/* jshint esversion: 6 */
// Filter table rows with a dropdown: <select data-filter-rows="#triage tbody" data-filter-key="priority">
// keeps rows whose data-priority matches the chosen value ("" shows all).
// - If the table is in a tab, that tab's count becomes "2 of 6" while filtering.
// - [data-row-filter-empty] in the same tab shows (and the table hides) when no rows match;
//   any [data-clear-row-filter] button there shows all rows again.
// The choice is remembered on this device, so it's kept when coming back from a case.
(() => {
    "use strict";

    const load = (key) => { try { return window.localStorage.getItem(key); } catch (e) { return null; } };
    const save = (key, value) => { try { window.localStorage.setItem(key, value); } catch (e) { /* blocked */ } };

    document.querySelectorAll("select[data-filter-rows]").forEach((select) => {
        const tbody = document.querySelector(select.dataset.filterRows);
        if (!tbody) { return; }
        const key = select.dataset.filterKey;
        const rows = Array.from(tbody.rows).filter((r) => r.dataset[key] !== undefined);
        const scope = select.closest(".tab-pane") || document;
        const wrapper = tbody.closest(".table-responsive");
        const empty = scope.querySelector("[data-row-filter-empty]");
        const tab = scope.id && document.querySelector('[data-bs-target="#' + scope.id + '"] .tab-count');
        const STORE = "fiaw-filter-" + select.id;

        const bar = select.closest("[data-row-filter-bar]");
        if (bar) { bar.hidden = false; }
        const status = document.createElement("p");
        status.className = "visually-hidden";
        status.setAttribute("aria-live", "polite");
        (bar || select).after(status);

        const apply = (value) => {
            let shown = 0;
            rows.forEach((row) => {
                const match = !value || row.dataset[key] === value;
                row.hidden = !match;
                shown += match;
            });
            if (tab) { tab.textContent = value ? shown + " of " + rows.length : String(rows.length); }
            if (empty) { empty.hidden = shown > 0; }
            if (wrapper) { wrapper.hidden = shown === 0; }
            return shown;
        };
        const announce = (shown) => {
            status.textContent = select.value
                ? "Showing " + shown + " of " + rows.length + " cases: " + select.options[select.selectedIndex].text + "."
                : "Showing all " + rows.length + " cases.";
        };

        // Only reuse a saved choice if it's still in the list
        const saved = load(STORE);
        if (saved && Array.from(select.options).some((o) => o.value === saved)) {
            select.value = saved;
            apply(saved);
        }
        select.addEventListener("change", () => {
            save(STORE, select.value);
            announce(apply(select.value));
        });
        scope.querySelectorAll("[data-clear-row-filter]").forEach((button) => {
            button.addEventListener("click", () => {
                select.value = "";
                save(STORE, "");
                announce(apply(""));
                select.focus();
            });
        });
    });
})();
