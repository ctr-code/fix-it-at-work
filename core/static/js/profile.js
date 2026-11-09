/* jshint esversion: 6 */
/* global bootstrap */
(() => {
    "use strict";
    // If the signout button is present, show a confirmation modal when it is clicked
    const signoutButton = document.getElementById("signoutButton");
    if (signoutButton) {
        signoutButton.addEventListener("click", () => {
            const signoutModal = new bootstrap.Modal(document.getElementById("signoutModal"));
            signoutModal.show();
        });
    }
    document.getElementById("id_email").addEventListener("input", () => {
        document.getElementById("submitButton").disabled = false;
    });
})();
