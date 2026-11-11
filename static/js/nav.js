/* jshint esversion: 6 */
// Header behaviour, shared by every page:
// - on small screens, the menu closes after a link is chosen or Escape is pressed
// - the menu button's label says whether it will open or close the menu
// - a soft shadow appears under the header once the page is scrolled
(() => {
    "use strict";

    const nav = document.getElementById("navbar");
    const menu = document.getElementById("navbarSupportedContent");
    if (!nav || !menu || !window.bootstrap) { return; }
    const toggler = nav.querySelector(".navbar-toggler");
    const collapse = () => window.bootstrap.Collapse.getOrCreateInstance(menu, { toggle: false });
    const isOpen = () => menu.classList.contains("show");

    // Choosing a link closes the small-screen menu (not the profile button, which opens its own list)
    menu.querySelectorAll("a.nav-link:not(.dropdown-toggle), .dropdown-item").forEach((link) => {
        link.addEventListener("click", () => { if (isOpen()) { collapse().hide(); } });
    });

    // Escape closes the menu and returns focus to the menu button.
    // If the profile list is open, Bootstrap closes that first.
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && isOpen() && !nav.querySelector(".dropdown-menu.show")) {
            collapse().hide();
            toggler.focus();
        }
    });

    menu.addEventListener("show.bs.collapse", () => toggler.setAttribute("aria-label", "Close menu"));
    menu.addEventListener("hide.bs.collapse", () => toggler.setAttribute("aria-label", "Open menu"));

    // Coming back with the browser's Back button shows the menu closed
    window.addEventListener("pageshow", (e) => { if (e.persisted && isOpen()) { collapse().hide(); } });

    const onScroll = () => nav.classList.toggle("is-scrolled", window.scrollY > 4);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
})();
