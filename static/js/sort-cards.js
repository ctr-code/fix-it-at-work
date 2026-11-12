/* jshint esversion: 6 */
// "Sort by" for lists of job cards. A <select data-sort-cards=".job-list"> reorders the cards
// inside every matching list. Each card gives its values as data-title, data-priority (number,
// higher is more urgent), data-due (ISO date) and data-overdue ("1" or "0").
// The choice is remembered on this device, so it's kept when coming back from a job.
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
    const STORE_KEY = "fiaw-job-sort";

    document.querySelectorAll("select[data-sort-cards]").forEach((select) => {
        const lists = document.querySelectorAll(select.dataset.sortCards);
        const status = document.querySelector("[data-sort-status]");
        const bar = select.closest("[data-sort-bar]");
        if (bar) { bar.hidden = false; }

        const apply = (key, announce) => {
            const order = ORDERS[key] || ORDERS.due;
            lists.forEach((list) => {
                const cards = Array.from(list.querySelectorAll(":scope > [data-due]"));
                cards.sort(order.compare).forEach((card) => list.appendChild(card));
            });
            if (announce && status) { status.textContent = "Jobs sorted by " + order.words + "."; }
        };

        let saved = null;
        try { saved = window.localStorage.getItem(STORE_KEY); } catch (e) { /* storage blocked */ }
        if (saved && ORDERS[saved]) {
            select.value = saved;
            apply(saved, false);
        }

        select.addEventListener("change", () => {
            apply(select.value, true);
            try { window.localStorage.setItem(STORE_KEY, select.value); } catch (e) { /* storage blocked */ }
        });
    });
})();
