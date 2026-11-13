/* jshint esversion: 6 */
// Weekly "reported vs resolved" column chart on the manager dashboard.
// Reads {weeks: [{label, reported, resolved, partial}]} from <script id="trend-data" type="application/json">
// and draws an SVG into [data-trend-chart]. The same numbers are in the table under the chart, so the
// chart adds a picture and a hover readout but never holds data the page doesn't also show.
// Marks follow the dashboard chart rules: columns at most 24px wide with a 2px gap between the pair,
// 4px rounded tops and square bottoms, 1px solid gridlines, and text in text colours, never series colours.
(() => {
    "use strict";

    const holder = document.querySelector("[data-trend-chart]");
    const source = document.getElementById("trend-data");
    if (!holder || !source) { return; }
    const weeks = JSON.parse(source.textContent).weeks;
    const SERIES = [
        { key: "reported", name: "Reported", cls: "series-reported" },
        { key: "resolved", name: "Resolved", cls: "series-resolved" },
    ];
    const NS = "http://www.w3.org/2000/svg";
    const el = (name, attrs, parent) => {
        const node = document.createElementNS(NS, name);
        Object.entries(attrs || {}).forEach(([k, v]) => node.setAttribute(k, v));
        if (parent) { parent.appendChild(node); }
        return node;
    };

    // Clean axis steps: 1, 2, 5, 10, 20, 50...
    const niceStep = (max, ticks) => {
        const raw = Math.max(max, 1) / ticks;
        const pow = Math.pow(10, Math.floor(Math.log10(raw)));
        return [1, 2, 5, 10].map((m) => m * pow).find((s) => s >= raw);
    };

    // A column with a 4px rounded top and a square bottom on the baseline
    const column = (x, y, w, h) => {
        const r = Math.min(4, h, w / 2);
        if (h <= 0) { return ""; }
        return `M${x},${y + h} V${y + r} Q${x},${y} ${x + r},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${y + h} Z`;
    };

    const tip = document.createElement("div");
    tip.className = "chart-tip";
    tip.hidden = true;
    holder.appendChild(tip);

    const showTip = (week, band) => {
        tip.replaceChildren();
        const head = document.createElement("p");
        head.className = "chart-tip-head";
        head.textContent = week.partial ? "This week so far" : "Week of " + week.label;
        tip.appendChild(head);
        SERIES.forEach((s) => {
            const row = document.createElement("p");
            row.className = "chart-tip-row";
            const key = document.createElement("span");
            key.className = "chart-key-line " + s.cls;
            const value = document.createElement("strong");
            value.textContent = String(week[s.key]);
            const name = document.createElement("span");
            name.textContent = s.name.toLowerCase();
            row.append(key, value, " ", name);
            tip.appendChild(row);
        });
        tip.hidden = false;
        // Sit above the hovered week, kept inside the chart
        const box = holder.getBoundingClientRect();
        const b = band.getBoundingClientRect();
        const left = Math.min(Math.max(b.left - box.left + b.width / 2 - tip.offsetWidth / 2, 0),
                              box.width - tip.offsetWidth);
        tip.style.left = left + "px";
        tip.style.top = Math.max(b.top - box.top - tip.offsetHeight - 6, 0) + "px";
    };

    const draw = () => {
        holder.querySelectorAll("svg").forEach((s) => s.remove());
        const width = Math.max(holder.clientWidth, 280);
        const height = 240;
        const m = { top: 24, right: 8, bottom: 28, left: 32 };
        const plotW = width - m.left - m.right;
        const plotH = height - m.top - m.bottom;
        const max = Math.max(...weeks.map((w) => Math.max(w.reported, w.resolved)), 1);
        const step = niceStep(max, 4);
        const top = Math.ceil(max / step) * step;
        const y = (v) => m.top + plotH - (v / top) * plotH;
        const band = plotW / weeks.length;
        const barW = Math.min(24, (band - 10) / 2);
        const labelEvery = band < 56 ? 2 : 1;  // a week label ("26 Oct", "This week") needs about 56px

        const svg = el("svg", { width, height, viewBox: `0 0 ${width} ${height}`, role: "img",
                                "aria-labelledby": "trend-title", class: "trend-svg" });
        // Gridlines and y ticks
        for (let v = 0; v <= top; v += step) {
            el("line", { x1: m.left, x2: width - m.right, y1: y(v), y2: y(v),
                         class: v === 0 ? "chart-baseline" : "chart-grid" }, svg);
            const t = el("text", { x: m.left - 8, y: y(v) + 4, "text-anchor": "end", class: "chart-tick" }, svg);
            t.textContent = String(v);
        }
        weeks.forEach((w, i) => {
            const cx = m.left + band * i + band / 2;
            const g = el("g", { class: "chart-week" + (w.partial ? " is-partial" : "") }, svg);
            SERIES.forEach((s, j) => {
                const x = j === 0 ? cx - barW - 1 : cx + 1;  // 2px gap between the pair
                const h = y(0) - y(w[s.key]);
                const d = column(x, y(w[s.key]), barW, h);
                if (d) { el("path", { d, class: "chart-col " + s.cls }, g); }
            });
            // On narrow screens label every other week (always including this week) so labels never collide;
            // every week is still in the hover readout and the table
            if ((weeks.length - 1 - i) % labelEvery === 0) {
                const label = el("text", { x: cx, y: height - 8, "text-anchor": "middle", class: "chart-tick" }, svg);
                label.textContent = w.label;
            }
            // The whole week is the hover and focus target, not just the thin columns
            const hit = el("rect", { x: m.left + band * i, y: m.top, width: band, height: plotH,
                                     class: "chart-hit", tabindex: "0",
                                     "aria-label": `${w.partial ? "This week so far" : "Week of " + w.label}: ` +
                                                   `${w.reported} reported, ${w.resolved} resolved` }, svg);
            const on = () => { g.classList.add("is-hover"); showTip(w, hit); };
            const off = () => { g.classList.remove("is-hover"); tip.hidden = true; };
            hit.addEventListener("pointerenter", on);
            hit.addEventListener("pointerleave", off);
            hit.addEventListener("focus", on);
            hit.addEventListener("blur", off);
        });
        // Label only the latest full week, so the eye has one anchor; the table has the rest
        const last = weeks.length - 2;
        if (last >= 0) {
            const cx = m.left + band * last + band / 2;
            SERIES.forEach((s, j) => {
                const v = weeks[last][s.key];
                const t = el("text", { x: j === 0 ? cx - barW / 2 - 1 : cx + barW / 2 + 1, y: y(v) - 6,
                                       "text-anchor": "middle", class: "chart-value" }, svg);
                t.textContent = String(v);
            });
        }
        holder.insertBefore(svg, tip);
    };

    draw();
    let frame;
    window.addEventListener("resize", () => {
        cancelAnimationFrame(frame);
        frame = requestAnimationFrame(draw);
    });
})();
