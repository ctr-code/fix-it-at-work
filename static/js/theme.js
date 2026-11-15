/* jshint esversion: 6 */
// Light or dark colours. The page starts in the right one (a small script in templates/base.html's <head>);
// this adds the choice in the footer: "Same as my device" (the default), Light or Dark, kept on this device.
// With "Same as my device", the page also follows the device when it switches, e.g. at sunset.
(() => {
    "use strict";
    const KEY = "fiaw-theme";
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const load = () => { try { return window.localStorage.getItem(KEY) || "auto"; } catch (e) { return "auto"; } };
    const save = (value) => {
        try {
            if (value === "auto") { window.localStorage.removeItem(KEY); } else { window.localStorage.setItem(KEY, value); }
        } catch (e) { /* blocked: the choice lasts for this page only */ }
    };
    const apply = (choice) => {
        const dark = choice === "dark" || (choice === "auto" && media.matches);
        document.documentElement.setAttribute("data-bs-theme", dark ? "dark" : "light");
    };

    let choice = load();
    apply(choice);
    media.addEventListener("change", () => { if (choice === "auto") { apply(choice); } });

    const picker = document.querySelector("[data-theme-picker]");
    const select = picker && picker.querySelector("select");
    if (!select) { return; }
    select.value = choice;
    select.addEventListener("change", () => {
        choice = select.value;
        save(choice);
        apply(choice);
    });
    picker.hidden = false;
})();
