/* jshint esversion: 6 */
// Adds an eye button next to every password box so people can check what they typed.
(() => {
    "use strict";

    document.querySelectorAll('input[type="password"]').forEach((input) => {
        // Wrap the input in a Bootstrap input group so the button sits inside the field's border
        const group = document.createElement("div");
        group.className = "input-group";
        input.parentNode.insertBefore(group, input);
        group.appendChild(input);

        const button = document.createElement("button");
        button.type = "button";
        button.className = "btn btn-outline-secondary password-toggle";
        button.setAttribute("aria-controls", input.id);
        button.setAttribute("aria-pressed", "false");
        button.setAttribute("aria-label", "Show password");
        button.title = "Show password";
        button.innerHTML = '<i class="fa-solid fa-eye" aria-hidden="true"></i>';
        group.appendChild(button);

        // Keep any error message under the field (Bootstrap needs it inside the group)
        const feedback = group.nextElementSibling;
        if (feedback && feedback.classList.contains("invalid-feedback")) {
            group.classList.add("has-validation");
            group.appendChild(feedback);
        }

        button.addEventListener("click", () => {
            const show = input.type === "password";
            input.type = show ? "text" : "password";
            const label = show ? "Hide password" : "Show password";
            button.setAttribute("aria-pressed", String(show));
            button.setAttribute("aria-label", label);
            button.title = label;
            button.querySelector("i").className = show ? "fa-solid fa-eye-slash" : "fa-solid fa-eye";
            input.focus();
        });
    });

    // Never submit a password while it is visible on screen
    document.querySelectorAll("form").forEach((form) => {
        form.addEventListener("submit", () => {
            form.querySelectorAll(".password-toggle").forEach((button) => {
                if (button.getAttribute("aria-pressed") === "true") button.click();
            });
        });
    });
})();
