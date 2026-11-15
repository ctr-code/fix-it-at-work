/* jshint esversion: 6 */
// Keeps a half-filled form as a draft on this device, so nothing is lost if the page is closed or the
// reporter goes somewhere else before sending.
// - <form data-draft-key="fiaw-draft-report-7" data-draft-restore> saves what's typed and chosen, a moment
//   after each change. The key names the person (and the report, for "Add more details"), so drafts never
//   cross between accounts on a shared computer.
// - data-draft-restore is only there on a fresh form. After a failed send, the page already shows what was
//   sent, so the draft isn't put back over it.
// - A [data-draft-notice] inside the form says a draft was restored, with a [data-draft-discard] button to
//   start again.
// Photos, voice notes and the map location aren't kept: files can't be saved this way, and a location
// should be chosen again on the spot. The draft is removed when the form is sent, after a week, and when
// anyone signs out on this device (base.html).
(() => {
    "use strict";
    const WEEK = 7 * 24 * 60 * 60 * 1000;
    const load = (key) => { try { return JSON.parse(window.localStorage.getItem(key)); } catch (e) { return null; } };
    const save = (key, value) => { try { window.localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* blocked */ } };
    const remove = (key) => { try { window.localStorage.removeItem(key); } catch (e) { /* blocked */ } };

    // The fields worth keeping: what the person typed or chose, not files, hidden values or the CSRF token
    const fields = (form) => Array.from(form.elements).filter((el) => el.name && !el.disabled
        && !["file", "hidden", "submit", "button", "reset", "password"].includes(el.type));

    const read = (form) => {
        const values = {};
        fields(form).forEach((el) => {
            if (el.type === "radio") {
                if (el.checked) { values[el.name] = el.value; }
            } else if (el.type === "checkbox") {
                values[el.name] = el.checked;
            } else {
                values[el.name] = el.value;
            }
        });
        return values;
    };

    const fill = (form, values) => {
        fields(form).forEach((el) => {
            if (!(el.name in values)) { return; }
            const value = values[el.name];
            if (el.type === "radio") {
                el.checked = el.value === value;
            } else if (el.type === "checkbox") {
                el.checked = Boolean(value);
            } else {
                el.value = value;
            }
        });
        // Let other scripts (counters, choice cards) catch up with the new values
        fields(form).forEach((el) => el.dispatchEvent(new Event("change", { bubbles: true })));
    };

    const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

    document.querySelectorAll("form[data-draft-key]").forEach((form) => {
        const key = form.dataset.draftKey;
        const blank = read(form);  // the form as the page gave it: a draft only exists once this changes
        const notice = form.querySelector("[data-draft-notice]");
        const when = notice && notice.querySelector("[data-draft-when]");

        const draft = load(key);
        if (draft && (!draft.saved || Date.now() - draft.saved > WEEK)) { remove(key); }
        else if (draft && form.hasAttribute("data-draft-restore") && !same(draft.values, blank)) {
            fill(form, draft.values);
            if (notice) {
                if (when) {
                    when.textContent = new Date(draft.saved).toLocaleString("en-GB", {
                        weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" });
                }
                notice.hidden = false;
            }
        }

        let timer = null;
        const keep = () => {
            window.clearTimeout(timer);
            timer = window.setTimeout(() => {
                const values = read(form);
                if (same(values, blank)) { remove(key); } else { save(key, { saved: Date.now(), values }); }
            }, 400);
        };
        form.addEventListener("input", keep);
        form.addEventListener("change", keep);
        // Sent: the draft has done its job. If the server finds a problem, the page comes back filled in.
        form.addEventListener("submit", () => { window.clearTimeout(timer); remove(key); });

        const discard = notice && notice.querySelector("[data-draft-discard]");
        if (discard) {
            discard.addEventListener("click", () => {
                window.clearTimeout(timer);
                remove(key);
                fill(form, blank);
                notice.hidden = true;
                const first = fields(form)[0];
                if (first) { first.focus(); }
            });
        }
    });

    // Signing out removes every draft on this device, so the next person can't see them
    document.querySelectorAll("form[data-clear-drafts]").forEach((form) => {
        form.addEventListener("submit", () => {
            try {
                Object.keys(window.localStorage).filter((k) => k.startsWith("fiaw-draft-"))
                    .forEach((k) => window.localStorage.removeItem(k));
            } catch (e) { /* blocked */ }
        });
    });
})();
