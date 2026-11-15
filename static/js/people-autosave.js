/* jshint esversion: 6 */
// People page: a change to someone's role or team is saved as soon as it's chosen, without reloading,
// and the row says "Saved" (or what went wrong). The Save buttons are only for when this can't run.
// - A field officer needs a team, so choosing "Field officer" waits for a team before saving.
// - The team list only applies to field officers, so it's switched off for the other roles.
// - If a save fails, the dropdowns go back to what was last saved, so the page never shows an unsaved role.
// - Each row's role marker and the Role filter's counts are kept up to date.
(() => {
    "use strict";
    const table = document.querySelector("table[data-autosave]");
    if (!table || !window.fetch) { return; }
    const hint = document.querySelector("[data-autosave-hint]");
    if (hint) { hint.hidden = false; }

    const roleFilter = document.getElementById("people-role");
    const recount = () => {
        if (!roleFilter) { return; }
        const rows = Array.from(table.tBodies[0].rows);
        Array.from(roleFilter.options).forEach((o) => {
            const n = o.value ? rows.filter((r) => r.dataset.role === o.value).length : rows.length;
            o.textContent = o.textContent.replace(/\(\d+\)$/, `(${n})`);
        });
    };

    table.querySelectorAll("form[id^='role-']").forEach((form) => {
        const row = form.closest("tr");
        const role = document.querySelector(`select[name="role"][form="${form.id}"]`);
        const team = document.querySelector(`select[name="team"][form="${form.id}"]`);
        const status = row.querySelector("[data-save-status]");
        const button = row.querySelector("[data-save-button]");
        if (!role || !team || !status) { return; }
        if (button) { button.hidden = true; }
        let saved = { role: role.value, team: team.value };

        const say = (text, kind) => {
            status.textContent = text;
            status.className = "save-status" + (kind ? " is-" + kind : "");
        };
        const teamNeeded = () => role.value === "officer";
        const syncTeam = () => {
            team.disabled = !teamNeeded();
            if (!teamNeeded()) { team.value = ""; }
        };

        const save = () => {
            if (teamNeeded() && !team.value) {
                say("Choose a team to finish", "waiting");
                team.focus();
                return;
            }
            say("Saving...", "busy");
            const data = new FormData(form);
            data.set("role", role.value);
            data.set("team", team.value);
            fetch(window.location.pathname, { method: "POST", body: data, headers: { Accept: "application/json" },
                                             credentials: "same-origin" })
                .then((response) => response.json().catch(() => ({ saved: false, message: "Not saved. Try again." })))
                .then((result) => {
                    if (!result.saved) { throw new Error(result.message || "Not saved. Try again."); }
                    saved = { role: role.value, team: team.value };
                    row.dataset.role = result.role;
                    recount();
                    say("Saved", "ok");
                })
                .catch((error) => {
                    role.value = saved.role;
                    team.value = saved.team;
                    syncTeam();
                    say(error.message && !error.message.startsWith("Failed") ? error.message : "Not saved. Check your connection and try again.", "error");
                });
        };

        syncTeam();
        role.addEventListener("change", () => { syncTeam(); save(); });
        team.addEventListener("change", save);
    });
})();
