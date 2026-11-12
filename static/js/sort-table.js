/* jshint esversion: 6 */
// Click a column heading in a .table-sortable table to sort its rows; click again to reverse.
// Each heading says how to compare (data-sort="text|number|date|priority") and may name the
// two directions for screen readers (data-sort-asc / data-sort-desc). Cells can give a
// data-sort-value when the text shown isn't what should be compared (e.g. "3 hours ago").
// Blank values always go to the end. Sorting only reorders rows already on the page.
(() => {
    "use strict";

    // Which way each kind of column sorts on the first click
    const FIRST = { text: "ascending", number: "ascending", date: "ascending", priority: "descending" };
    const WORDS = {
        text: { ascending: "A to Z", descending: "Z to A" },
        number: { ascending: "lowest first", descending: "highest first" },
        date: { ascending: "earliest first", descending: "latest first" },
        priority: { ascending: "least urgent first", descending: "most urgent first" },
    };
    const collator = new Intl.Collator("en-GB", { numeric: true, sensitivity: "base" });

    document.querySelectorAll("table.table-sortable").forEach((table) => {
        const tbody = table.tBodies[0];
        const headings = Array.from(table.tHead.rows[0].cells);

        // Announces the new order to screen readers
        const status = document.createElement("p");
        status.className = "visually-hidden";
        status.setAttribute("aria-live", "polite");
        table.closest(".table-responsive").after(status);

        const readValue = (row, index, type) => {
            const cell = row.cells[index];
            const raw = (cell.dataset.sortValue !== undefined ? cell.dataset.sortValue : cell.textContent).trim();
            if (raw === "") { return null; }
            if (type === "text") { return raw; }
            const n = type === "date" ? Date.parse(raw) : parseFloat(raw);
            return Number.isNaN(n) ? null : n;
        };

        headings.forEach((th, index) => {
            const button = th.querySelector(".sort-btn");
            if (!button) { return; }
            const type = th.dataset.sort || "text";

            button.addEventListener("click", () => {
                const rows = Array.from(tbody.rows);
                // A table showing only its "nothing here" row (one cell across the table) has nothing to sort.
                // Other rows may still use colspan, e.g. "Manager (you)" on the People page.
                if (rows.every((r) => r.cells.length === 1)) { return; }

                const current = th.getAttribute("aria-sort");
                const dir = current === "ascending" ? "descending"
                    : current === "descending" ? "ascending"
                    : FIRST[type];
                const sign = dir === "ascending" ? 1 : -1;

                // Stable sort: rows that compare equal keep their current order
                const keyed = rows.map((row, i) => ({ row, i, v: readValue(row, index, type) }));
                keyed.sort((a, b) => {
                    if (a.v === null || b.v === null) {
                        return (a.v === null) - (b.v === null) || a.i - b.i;
                    }
                    const diff = type === "text" ? collator.compare(a.v, b.v) : a.v - b.v;
                    return diff * sign || a.i - b.i;
                });
                keyed.forEach(({ row }) => tbody.appendChild(row));

                headings.forEach((h) => h.removeAttribute("aria-sort"));
                th.setAttribute("aria-sort", dir);
                const label = button.textContent.trim();
                const words = th.dataset[dir === "ascending" ? "sortAsc" : "sortDesc"] || WORDS[type][dir];
                status.textContent = "Sorted by " + label + ", " + words + ".";
            });
        });
    });
})();
