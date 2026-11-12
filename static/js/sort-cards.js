/* jshint esversion: 6 */
// "Sort by", filters (e.g. "Location", "Priority") and a search box for lists of job cards.
// - <input data-search-cards=".job-list" data-search-key="title"> keeps cards whose data-title contains
//   the typed text, ignoring capitals and accents. It combines with the filters.
// - <select data-sort-cards=".job-list"> reorders the cards in every matching list. Cards give
//   data-title, data-priority (number, higher is more urgent), data-due (ISO date), data-overdue ("1"/"0").
// - <select data-filter-cards=".job-list" data-filter-key="building"> keeps only cards whose
//   data-building matches; "" means any. Filters combine: a card shows only if it matches all of them.
//   Each list's heading count becomes "2 of 5", and a list's [data-filter-empty] message shows when
//   none of its cards match.
// - Any [data-clear-filters] button empties the search and resets the filters (not the sort).
// All choices are remembered on this device, so they're kept when coming back from a job.
(() => {
    "use strict";

    const collator = new Intl.Collator("en-GB", { numeric: true, sensitivity: "base" });
    const due = (card) => Date.parse(card.dataset.due) || Infinity; // no due date goes last
    const byDue = (a, b) => due(a) - due(b);

    // Each order falls back to due date, so ties are still in a sensible order
    const ORDERS = {
        due: { compare: byDue, words: "due date, soonest first" },
        priority: {
            compare: (a, b) => (b.dataset.priority - a.dataset.priority) || byDue(a, b),
            words: "priority, most urgent first",
        },
        overdue: {
            compare: (a, b) => (b.dataset.overdue - a.dataset.overdue) || byDue(a, b),
            words: "overdue first, then due date",
        },
        title: {
            compare: (a, b) => collator.compare(a.dataset.title, b.dataset.title) || byDue(a, b),
            words: "title, A to Z",
        },
    };

    const load = (key) => { try { return window.localStorage.getItem(key); } catch (e) { return null; } };
    const save = (key, value) => { try { window.localStorage.setItem(key, value); } catch (e) { /* blocked */ } };
    const status = document.querySelector("[data-sort-status]");
    const say = (text) => { if (status) { status.textContent = text; } };
    const cardsIn = (list) => Array.from(list.querySelectorAll(":scope > [data-due]"));

    document.querySelectorAll("[data-sort-bar]").forEach((bar) => { bar.hidden = false; });

    // Sorting
    document.querySelectorAll("select[data-sort-cards]").forEach((select) => {
        const lists = document.querySelectorAll(select.dataset.sortCards);
        const STORE = "fiaw-job-sort";
        const apply = (key) => {
            const order = ORDERS[key] || ORDERS.due;
            lists.forEach((list) => {
                const empty = list.querySelector(":scope > [data-filter-empty]");
                cardsIn(list).sort(order.compare).forEach((card) => list.insertBefore(card, empty));
            });
            return order;
        };
        const saved = load(STORE);
        if (saved && ORDERS[saved]) { select.value = saved; apply(saved); }
        select.addEventListener("change", () => {
            const order = apply(select.value);
            save(STORE, select.value);
            say("Jobs sorted by " + order.words + ".");
        });
    });

    // Filtering: every filter list applies at once
    const filters = Array.from(document.querySelectorAll("select[data-filter-cards]"));
    const searches = Array.from(document.querySelectorAll("input[data-search-cards]"));
    const filterLists = new Set();
    filters.forEach((select) => document.querySelectorAll(select.dataset.filterCards).forEach((l) => filterLists.add(l)));
    searches.forEach((input) => document.querySelectorAll(input.dataset.searchCards).forEach((l) => filterLists.add(l)));
    // Search ignores capitals and accents, so "lucia" finds "Lucía"
    const fold = (text) => text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLocaleLowerCase("en-GB").trim();
    const storeKey = (select) => "fiaw-job-filter-" + select.dataset.filterKey;

    const applyFilters = () => {
        const active = filters.filter((s) => s.value);
        const terms = searches.map((i) => ({ key: i.dataset.searchKey, q: fold(i.value) })).filter((t) => t.q);
        const filtering = active.length + terms.length > 0;
        let shown = 0;
        filterLists.forEach((list) => {
            const cards = cardsIn(list);
            let inList = 0;
            cards.forEach((card) => {
                const match = active.every((s) => card.dataset[s.dataset.filterKey] === s.value)
                    && terms.every((t) => fold(card.dataset[t.key] || "").includes(t.q));
                card.hidden = !match;
                inList += match;
            });
            shown += inList;
            const empty = list.querySelector(":scope > [data-filter-empty]");
            if (empty) { empty.hidden = inList > 0 || cards.length === 0; }
            const heading = list.previousElementSibling;
            const count = heading && heading.querySelector("[data-count]");
            if (count) { count.textContent = filtering ? inList + " of " + cards.length : String(cards.length); }
        });
        // The "Clear filters" button in the controls only shows while something is filtered
        document.querySelectorAll("[data-sort-bar] [data-clear-filters]").forEach((b) => { b.hidden = !filtering; });
        // e.g. "Showing 1 job: Main Office, Medium, titles containing "tap"."
        const parts = active.map((s) => s.options[s.selectedIndex].text)
            .concat(terms.map((t) => 'titles containing "' + t.q + '"'));
        return parts.length
            ? "Showing " + shown + (shown === 1 ? " job" : " jobs") + ": " + parts.join(", ") + "."
            : "Showing all jobs.";
    };

    filters.forEach((select) => {
        // Only reuse a saved choice if it's still in the list (e.g. they still have jobs there)
        const saved = load(storeKey(select));
        if (saved && Array.from(select.options).some((o) => o.value === saved)) { select.value = saved; }
        select.addEventListener("change", () => {
            save(storeKey(select), select.value);
            say(applyFilters());
        });
    });

    // Search boxes filter as you type. The text isn't remembered, so a list is never narrowed by an
    // old search; the result is announced once typing pauses rather than on every key.
    let announce;
    searches.forEach((input) => {
        input.addEventListener("input", () => {
            const message = applyFilters();
            clearTimeout(announce);
            announce = setTimeout(() => say(message), 600);
        });
    });
    // "Clear filters": empty the search and set every filter back to "All"; the sort order is kept
    document.querySelectorAll("[data-clear-filters]").forEach((button) => {
        button.addEventListener("click", () => {
            searches.forEach((input) => { input.value = ""; });
            filters.forEach((select) => { select.value = ""; save(storeKey(select), ""); });
            applyFilters();
            say("Filters cleared. Showing all jobs.");
            // The button hides itself, so move focus somewhere sensible
            const next = searches[0] || filters[0];
            if (next) { next.focus(); }
        });
    });

    if (filters.some((s) => s.value) || searches.some((i) => i.value)) { applyFilters(); }
})();
