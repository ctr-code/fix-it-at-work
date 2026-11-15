/* jshint esversion: 6 */
// Asks before a form does something that can't be undone, such as sending the outcome letter.
// <form data-confirm="#dialog-id"> opens that Bootstrap dialog instead of sending. Its [data-confirm-yes]
// button sends the form; [data-confirm-cancel] (or Escape) closes it and puts focus back on the form's
// button, so nothing is lost. If the form isn't filled in properly, the browser and the server's
// checks run first, as they would without the dialog.
(() => {
    "use strict";
    if (!window.bootstrap) { return; }  // no dialog available: the button sends straight away
    document.querySelectorAll("form[data-confirm]").forEach((form) => {
        const box = document.querySelector(form.dataset.confirm);
        if (!box) { return; }
        const dialog = window.bootstrap.Modal.getOrCreateInstance(box);
        const yes = box.querySelector("[data-confirm-yes]");
        const cancel = box.querySelector("[data-confirm-cancel]");
        const send = form.querySelector('button[type="submit"]');
        let confirmed = false;

        form.addEventListener("submit", (event) => {
            if (confirmed) { return; }
            if (!form.checkValidity()) { return; }  // let the usual "please fill in" messages show
            event.preventDefault();
            dialog.show();
        });
        // The safe choice gets focus, so pressing Enter by habit doesn't send
        box.addEventListener("shown.bs.modal", () => { if (cancel) { cancel.focus(); } });
        box.addEventListener("hidden.bs.modal", () => { if (!confirmed && send) { send.focus(); } });
        yes.addEventListener("click", () => {
            confirmed = true;
            yes.disabled = true;
            yes.setAttribute("aria-busy", "true");
            if (send) { send.disabled = true; }
            // Send the form itself (not through its button, which is now disabled)
            HTMLFormElement.prototype.submit.call(form);
        });
    });
})();
