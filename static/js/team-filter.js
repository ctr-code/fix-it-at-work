/* jshint esversion: 6 */
// Choose a team first: the category and officer lists then only offer that team's options.
// Needs <script id="by-team" type="application/json"> with {category: {teamId: [ids]}, officer: {...}}
// and selects #id_team, #id_category and #id_officer (as Django names them).
// Options are rebuilt rather than hidden, because hidden <option>s still show in some browsers.
(() => {
    "use strict";
    const data = document.getElementById("by-team");
    const team = document.getElementById("id_team");
    if (!data || !team) { return; }
    const byTeam = JSON.parse(data.textContent);
    const lists = ["category", "officer"].map((name) => {
        const select = document.getElementById("id_" + name);
        return select && { name, select, options: [...select.options] };
    }).filter(Boolean);

    const filterByTeam = () => {
        for (const { name, select, options } of lists) {
            const allowed = byTeam[name][team.value] || [];
            const current = select.value;
            select.replaceChildren(...options.filter((o) => !o.value || allowed.includes(Number(o.value))));
            select.value = allowed.includes(Number(current)) ? current : "";
            select.disabled = !team.value;
        }
    };
    team.addEventListener("change", filterByTeam);
    filterByTeam();
})();
