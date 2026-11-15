/* jshint esversion: 6 */
// Messages after an action show as toasts (templates/base.html). Each one with data-bs-autohide="true"
// fades after a few seconds; Bootstrap pauses the countdown while the pointer is over it or something in it
// has keyboard focus, and starts it again when they leave. The rest stay until closed. Toasts are drawn
// already showing, so without this script they just stay on screen.
(() => {
    "use strict";
    if (!window.bootstrap) { return; }
    const DELAY = 6000;
    document.querySelectorAll(".site-toast").forEach((el) => {
        const toast = window.bootstrap.Toast.getOrCreateInstance(el, { delay: DELAY });
        // Already showing: hand it to Bootstrap so its countdown and close button work
        el.classList.remove("show");
        toast.show();
        // Gone: take it out of the page so it isn't read out or tabbed to any more
        el.addEventListener("hidden.bs.toast", () => el.remove());
    });
})();
