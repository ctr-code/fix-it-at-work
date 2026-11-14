/* jshint esversion: 6 */
// "Already reported?" on the report form. While someone types the problem and picks a building, this asks
// the server (/report/similar/) for open reports that look the same and lists them, so they can see it's
// already in hand before sending a duplicate. It only informs: they can still send theirs, and a case
// handler checks for duplicates either way.
// <div data-similar data-similar-url="/report/similar/"> holds [data-similar-list]; it's hidden when
// there's nothing to show. Without JavaScript the form works exactly as before.
(() => {
    "use strict";
    const box = document.querySelector("[data-similar]");
    const form = box && box.closest("form");
    if (!form || !window.fetch) { return; }
    const list = box.querySelector("[data-similar-list]");
    const field = (name) => form.querySelector(`[name="${name}"]`);
    const watched = ["title", "description", "building", "location_detail"].map(field).filter(Boolean);
    let timer = null;
    let last = "";
    let request = null;

    const show = (reports) => {
        list.replaceChildren(...reports.map((r) => {
            const item = document.createElement("li");
            item.className = "similar-item";
            const title = document.createElement("strong");
            title.textContent = r.title;
            const where = document.createElement("span");
            where.className = "d-block small";
            where.textContent = r.where;
            const meta = document.createElement("span");
            meta.className = "d-block small text-muted";
            meta.textContent = `${r.reference} · reported ${r.reported} · ${r.status}`;
            item.append(title, where, meta);
            return item;
        }));
        box.hidden = reports.length === 0;
    };

    const look = () => {
        const params = new URLSearchParams();
        watched.forEach((el) => params.set(el.name, el.value.trim()));
        const query = params.toString();
        if (query === last) { return; }
        last = query;
        if (request) { request.abort(); }
        request = new AbortController();
        fetch(`${box.dataset.similarUrl}?${query}`, { signal: request.signal, headers: { Accept: "application/json" } })
            .then((response) => (response.ok ? response.json() : { reports: [] }))
            .then((data) => show(data.reports || []))
            .catch(() => { /* aborted or offline: keep what's shown */ });
    };

    const soon = () => { window.clearTimeout(timer); timer = window.setTimeout(look, 600); };
    watched.forEach((el) => { el.addEventListener("input", soon); el.addEventListener("change", soon); });
    // A restored draft (static/js/draft.js) already has text in it
    look();
})();
