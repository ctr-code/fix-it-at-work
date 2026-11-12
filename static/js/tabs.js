/* jshint esversion: 6 */
// Keeps Bootstrap tabs in step with the address, so a tab can be linked to and survives the Back button.
// - Opening a page whose address ends in a tab's id (e.g. /triage/#unhappy) opens that tab.
// - Choosing a tab puts its id in the address without adding a history entry or jumping the page,
//   so opening a case and pressing Back returns to the same tab.
(() => {
    "use strict";
    if (!window.bootstrap) { return; }

    const tabFor = (hash) => hash && document.querySelector(
        '[data-bs-toggle="tab"][data-bs-target="' + CSS.escape(hash) + '"]');

    // The browser jumps down to the id in the address, which can hide the tabs under the fixed header.
    // Go back to the top so the tabs and the start of the chosen list are both in view.
    const toTop = () => window.scrollTo(0, 0);
    const showFromAddress = () => {
        const tab = tabFor(window.location.hash);
        if (!tab) { return false; }
        window.bootstrap.Tab.getOrCreateInstance(tab).show();
        toTop();
        return true;
    };
    if (showFromAddress()) {
        window.addEventListener("load", () => setTimeout(toTop, 0), { once: true });
    }
    window.addEventListener("hashchange", showFromAddress);

    document.querySelectorAll('[data-bs-toggle="tab"]').forEach((tab) => {
        tab.addEventListener("shown.bs.tab", () => {
            history.replaceState(null, "", tab.dataset.bsTarget);
        });
    });
})();
