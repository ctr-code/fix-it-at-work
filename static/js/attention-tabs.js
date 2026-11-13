/* jshint esversion: 6 */
// Tabs over the dashboard's "Needs attention" groups.
// - "All" shows every group, each with its first five cases ([data-attention-extra] rows are hidden) and a
//   "Show all N" button that opens that group's tab.
// - A group's tab shows only that group, full width, with every case in it.
// Arrow keys, Home and End move between tabs (the usual tab keyboard pattern). The chosen tab is remembered
// on this device. Without this script every group and every case shows.
(() => {
    "use strict";

    const bar = document.querySelector("[data-attention-tabs]");
    const panel = document.querySelector("[data-attention-groups]");
    if (!bar || !panel) { return; }
    const tabs = Array.from(bar.querySelectorAll("[data-attention-tab]"));
    const groups = Array.from(panel.querySelectorAll("[data-attention-group]"));
    const KEY = "fiaw-attention-tab";
    const load = () => { try { return window.localStorage.getItem(KEY); } catch (e) { return null; } };
    const save = (v) => { try { window.localStorage.setItem(KEY, v); } catch (e) { /* blocked */ } };

    const select = (key, focus) => {
        const tab = tabs.find((t) => t.dataset.attentionTab === key) || tabs[0];
        const chosen = tab.dataset.attentionTab;
        tabs.forEach((t) => {
            const on = t === tab;
            t.classList.toggle("active", on);
            t.setAttribute("aria-selected", String(on));
            t.tabIndex = on ? 0 : -1;
        });
        panel.setAttribute("aria-labelledby", tab.id);
        groups.forEach((g) => {
            const one = chosen !== "all";
            g.hidden = one && g.dataset.attentionGroup !== chosen;
            g.classList.toggle("col-lg-6", !one);          // a single group gets the full width
            g.querySelectorAll("[data-attention-extra]").forEach((row) => { row.hidden = !one; });
            g.querySelectorAll("[data-attention-show]").forEach((b) => { b.hidden = one; });
        });
        save(chosen);
        if (focus) { tab.focus(); }
    };

    tabs.forEach((tab, i) => {
        tab.addEventListener("click", () => select(tab.dataset.attentionTab));
        tab.addEventListener("keydown", (e) => {
            const next = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: tabs.length - 1 }[e.key];
            if (next === undefined) { return; }
            e.preventDefault();
            select(tabs[(next + tabs.length) % tabs.length].dataset.attentionTab, true);
        });
    });
    // "Show all 13" under a group opens its tab, then takes focus back to the top of the list
    panel.querySelectorAll("[data-attention-show]").forEach((button) => {
        button.addEventListener("click", () => {
            select(button.dataset.attentionShow, true);
            bar.scrollIntoView({ block: "nearest" });
        });
    });

    bar.hidden = false;
    select(load() || "all");
})();
