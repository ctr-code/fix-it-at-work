/* jshint esversion: 6 */
// "Use my current location" on the report form. Asks the browser for the device's position only when the
// reporter presses the button, puts it in the hidden latitude/longitude fields, and lets them remove it.
// The block stays hidden in browsers without geolocation, and the report works the same without it.
(() => {
    "use strict";

    const box = document.querySelector("[data-locate]");
    const lat = document.getElementById("id_latitude");
    const lng = document.getElementById("id_longitude");
    if (!box || !lat || !lng || !("geolocation" in navigator)) { return; }

    const button = box.querySelector("[data-locate-button]");
    const clear = box.querySelector("[data-locate-clear]");
    const status = box.querySelector("[data-locate-status]");
    const label = button.innerHTML;

    const say = (text, kind) => {
        status.textContent = text;
        status.className = "locate-status" + (kind ? " is-" + kind : "");
    };
    const showSaved = (accuracy) => {
        const near = accuracy ? ` (accurate to about ${Math.round(accuracy)} m)` : "";
        say(`Location added${near}. It will be sent with your report.`, "ok");
        clear.hidden = false;
        button.innerHTML = label.replace("Use my current location", "Update my location");
    };

    box.hidden = false;
    // Coming back to the form after an error keeps a location already added
    if (lat.value && lng.value) { showSaved(); }

    button.addEventListener("click", () => {
        button.disabled = true;
        say("Finding your location…");
        navigator.geolocation.getCurrentPosition((pos) => {
            // About a metre is plenty to find a problem
            lat.value = pos.coords.latitude.toFixed(5);
            lng.value = pos.coords.longitude.toFixed(5);
            button.disabled = false;
            showSaved(pos.coords.accuracy);
        }, (err) => {
            button.disabled = false;
            say(err.code === err.PERMISSION_DENIED
                ? "Location wasn't shared. That's fine: the building and area are enough."
                : "We couldn't find your location. That's fine: the building and area are enough.", "error");
        }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 });
    });

    clear.addEventListener("click", () => {
        lat.value = "";
        lng.value = "";
        clear.hidden = true;
        button.innerHTML = label;
        say("Location removed. It won't be sent.");
        button.focus();
    });
})();
