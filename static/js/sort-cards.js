/* jshint esversion: 6 */
// "Sort by" and "Location" for lists of job cards.
// - <select data-sort-cards=".job-list"> reorders the cards in every matching list. Cards give
//   data-title, data-priority (number, higher is more urgent), data-due (ISO date), data-overdue ("1"/"0").
// - <select data-filter-cards=".job-list" data-filter-key="building"> shows only cards whose
//   data-building matches; "" shows all. Each list's heading count becomes "2 of 5", and a list's
//   [data-filter-empty] message shows when none of its cards match.
// Both choices are remembered on this device, so they're kept when coming back from a job.
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

    // Filtering
    document.querySelectorAll("select[data-filter-cards]").forEach((select) => {
        const lists = document.querySelectorAll(select.dataset.filterCards);
        const key = select.dataset.filterKey;
        const STORE = "fiaw-job-filter-" + key;
        const apply = (value) => {
            let shown = 0;
            lists.forEach((list) => {
                const cards = cardsIn(list);
                let inList = 0;
                cards.forEach((card) => {
                    const match = !value || card.dataset[key] === value;
                    card.hidden = !match;
                    inList += match;
                });
                shown += inList;
                const empty = list.querySelector(":scope > [data-filter-empty]");
                if (empty) { empty.hidden = inList > 0 || cards.length === 0; }
                const heading = list.previousElementSibling;
                const count = heading && heading.querySelector("[data-count]");
                if (count) { count.textContent = value ? inList + " of " + cards.length : String(cards.length); }
            });
            return shown;
        };
        const saved = load(STORE);
        // Only reuse a saved location if there are still jobs there
        if (saved && Array.from(select.options).some((o) => o.value === saved)) { select.value = saved; apply(saved); }
        select.addEventListener("change", () => {
            const shown = apply(select.value);
            save(STORE, select.value);
            say(select.value ? "Showing " + shown + (shown === 1 ? " job" : " jobs") + " in " + select.value + "."
                : "Showing jobs in all locations.");
        });
    });
})();
