/* jshint esversion: 6 */
// Filter table rows with dropdowns and a search box.
// - <select data-filter-rows="#triage tbody" data-filter-key="priority"> keeps rows whose
//   data-priority matches the chosen value ("" means any).
// - <input data-search-rows="#triage tbody" data-search-key="title ref"> keeps rows whose data-title
//   or data-ref contains the typed text, ignoring capitals and accents. List one or more keys.
// Controls pointing at the same table combine: a row shows only if it matches all of them.
// - If the table is in a tab, that tab's count becomes "2 of 6" while filtering.
// - [data-row-filter-empty] in the same tab shows (and the table hides) when no rows match;
//   any [data-clear-row-filter] button there empties the search and sets every dropdown to "All".
// Spoken messages say "cases" and "titles" unless the bar has data-row-noun (e.g. "people") and the
// search box has data-search-label (e.g. "names").
// Dropdown choices are remembered on this device, so they're kept when coming back from a case.
// Search text isn't, so a list is never narrowed by an old search.
(() => {
    "use strict";

    const load = (key) => { try { return window.localStorage.getItem(key); } catch (e) { return null; } };
    const save = (key, value) => { try { window.localStorage.setItem(key, value); } catch (e) { /* blocked */ } };
    const storeKey = (select) => "fiaw-filter-" + select.id;
    // "lucia" finds "Lucía"
    const fold = (text) => text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLocaleLowerCase("en-GB").trim();

    // Group the controls by the table they filter
    const groups = new Map();
    const group = (target) => {
        if (!groups.has(target)) { groups.set(target, { selects: [], searches: [] }); }
        return groups.get(target);
    };
    document.querySelectorAll("select[data-filter-rows]").forEach((s) => group(s.dataset.filterRows).selects.push(s));
    document.querySelectorAll("input[data-search-rows]").forEach((i) => group(i.dataset.searchRows).searches.push(i));

    groups.forEach(({ selects, searches }, target) => {
        const tbody = document.querySelector(target);
        if (!tbody) { return; }
        const controls = [...searches, ...selects];
        const rows = Array.from(tbody.rows).filter((r) => r.querySelector("td:not([colspan])"));
        const scope = controls[0].closest(".tab-pane") || document;
        const wrapper = tbody.closest(".table-responsive");
        const empty = scope.querySelector("[data-row-filter-empty]");
        const tab = scope.id && document.querySelector('[data-bs-target="#' + scope.id + '"] .tab-count');

        const bar = controls[0].closest("[data-row-filter-bar]");
        if (bar) { bar.hidden = false; }
        const noun = (bar && bar.dataset.rowNoun) || "cases";
        const status = document.createElement("p");
        status.className = "visually-hidden";
        status.setAttribute("aria-live", "polite");
        (bar || controls[0]).after(status);

        const apply = () => {
            const active = selects.filter((s) => s.value);
            const terms = searches.map((i) => ({ keys: i.dataset.searchKey.split(/\s+/),
                                                 label: i.dataset.searchLabel || "titles",
                                                 q: fold(i.value) })).filter((t) => t.q);
            const filtering = active.length + terms.length > 0;
            let shown = 0;
            rows.forEach((row) => {
                const match = active.every((s) => row.dataset[s.dataset.filterKey] === s.value)
                    && terms.every((t) => t.keys.some((k) => fold(row.dataset[k] || "").includes(t.q)));
                row.hidden = !match;
                shown += match;
            });
            if (tab) { tab.textContent = filtering ? shown + " of " + rows.length : String(rows.length); }
            if (empty) { empty.hidden = shown > 0; }
            if (wrapper) { wrapper.hidden = shown === 0; }
            // e.g. "Showing 1 of 6 cases: Main Office, High, titles containing "leak"."
            const parts = active.map((s) => s.options[s.selectedIndex].text)
                .concat(terms.map((t) => t.label + ' containing "' + t.q + '"'));
            return parts.length
                ? "Showing " + shown + " of " + rows.length + " " + noun + ": " + parts.join(", ") + "."
                : "Showing all " + rows.length + " " + noun + ".";
        };

        selects.forEach((select) => {
            // Only reuse a saved choice if it's still in the list
            const saved = load(storeKey(select));
            if (saved && Array.from(select.options).some((o) => o.value === saved)) { select.value = saved; }
            select.addEventListener("change", () => {
                save(storeKey(select), select.value);
                status.textContent = apply();
            });
        });

        // Search as you type; announce the result once typing pauses rather than on every key
        let pause;
        searches.forEach((input) => {
            input.addEventListener("input", () => {
                const message = apply();
                clearTimeout(pause);
                pause = setTimeout(() => { status.textContent = message; }, 600);
            });
        });

        // Apply anything restored on load (a saved dropdown, or search text the browser kept), quietly
        if (controls.some((c) => c.value)) { apply(); }

        scope.querySelectorAll("[data-clear-row-filter]").forEach((button) => {
            button.addEventListener("click", () => {
                searches.forEach((i) => { i.value = ""; });
                selects.forEach((s) => { s.value = ""; save(storeKey(s), ""); });
                status.textContent = apply();
                controls[0].focus();
            });
        });
    });
})();
