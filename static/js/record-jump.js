/* jshint esversion: 6 */
// The "Record visit" button on an officer's job page (<a data-record-jump href="#record-visit">).
// It's hidden while the visit form is on screen, since it would only cover it, and shows again when
// the officer scrolls back up. Selecting it scrolls to the form and moves keyboard focus to its heading.
(() => {
    "use strict";
    const button = document.querySelector("[data-record-jump]");
    const form = button && document.querySelector(button.getAttribute("href"));
    if (!form) { return; }
    const heading = form.querySelector("h2");
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if ("IntersectionObserver" in window) {
        // Hidden once any of the form shows above the button's space at the bottom of the screen
        new IntersectionObserver(([entry]) => { button.hidden = entry.isIntersecting; },
            { rootMargin: "0px 0px -96px 0px" }).observe(form);
    }

    button.addEventListener("click", (event) => {
        event.preventDefault();
        form.scrollIntoView({ behavior: still ? "auto" : "smooth", block: "start" });
        if (heading) { heading.focus({ preventScroll: true }); }
        if (window.history.replaceState) { window.history.replaceState(null, "", "#record-visit"); }
    });
})();
