/* jshint esversion: 6 */
// Keeps Bootstrap tabs in step with the address, so a tab can be linked to and survives the Back button.
// - Opening a page whose address ends in a tab's id (e.g. /triage/#unhappy) opens that tab.
// - Choosing a tab puts its id in the address without adding a history entry or jumping the page,
//   so opening a case and pressing Back returns to the same tab.
// - <ul data-remember-tab="fiaw-queue-tab"> also remembers the last tab on this device, so coming back
//   to the page later (from the navbar, say) opens it there. A tab named in the address still wins.
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
    const remembered = document.querySelector("[data-remember-tab]");
    const storeKey = remembered && remembered.dataset.rememberTab;
    const load = () => { try { return window.localStorage.getItem(storeKey); } catch (e) { return null; } };
    const save = (value) => { try { window.localStorage.setItem(storeKey, value); } catch (e) { /* blocked */ } };

    if (showFromAddress()) {
        window.addEventListener("load", () => setTimeout(toTop, 0), { once: true });
    } else if (storeKey) {
        // No tab in the address: open the one used last time, if it's still there
        const tab = tabFor(load());
        if (tab) {
            window.bootstrap.Tab.getOrCreateInstance(tab).show();
            history.replaceState(null, "", tab.dataset.bsTarget);
            window.addEventListener("load", () => setTimeout(toTop, 0), { once: true });
        }
    }
    window.addEventListener("hashchange", showFromAddress);

    document.querySelectorAll('[data-bs-toggle="tab"]').forEach((tab) => {
        tab.addEventListener("shown.bs.tab", () => {
            history.replaceState(null, "", tab.dataset.bsTarget);
            if (storeKey && remembered.contains(tab)) { save(tab.dataset.bsTarget); }
        });
    });
})();
