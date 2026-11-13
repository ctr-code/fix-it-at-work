/* jshint esversion: 8 */
/* global L */
// "Show us the exact spot" on the report form: two optional ways to fill the hidden latitude/longitude fields.
// - "Use my current location" asks the browser for the device's position (only shown where that's possible).
// - "Pick on a map" opens a map: tap or click to drop a pin and drag it to adjust, or (keyboard) pan with the
//   arrow keys and press "Pin the centre of the map". The map library (Leaflet, from cdnjs, checked with
//   Subresource Integrity) and the OpenStreetMap tiles load only when the map is first opened.
// location_method records which was used. "Remove location" clears either. The form works the same without any.
(() => {
    "use strict";

    const box = document.querySelector("[data-locate]");
    const lat = document.getElementById("id_latitude");
    const lng = document.getElementById("id_longitude");
    const method = document.getElementById("id_location_method");
    if (!box || !lat || !lng || !method) { return; }

    const locateBtn = box.querySelector("[data-locate-button]");
    const openBtn = box.querySelector("[data-pin-open]");
    const clearBtn = box.querySelector("[data-locate-clear]");
    const status = box.querySelector("[data-locate-status]");
    const wrap = box.querySelector("[data-pin-wrap]");
    const mapEl = box.querySelector("[data-pin-map]");
    const centreBtn = box.querySelector("[data-pin-centre]");
    const closeBtn = box.querySelector("[data-pin-close]");
    const building = document.getElementById("id_building");
    const points = JSON.parse((document.getElementById("building-points") || {}).textContent || "{}");

    const LEAFLET = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/";
    const SRI = {
        css: "sha384-c6Rcwz4e4CITMbu/NBmnNS8yN2sC3cUElMEMfP3vqqKFp7GOYaaBBCqmaWBjmkjb",
        js: "sha384-NElt3Op+9NBMCYaef5HxeJmU4Xeard/Lku8ek6hoPTvYkQPh3zLIrJP7KiRocsxO",
    };

    const say = (text, kind) => {
        status.textContent = text;
        status.className = "locate-status" + (kind ? " is-" + kind : "");
    };
    // About a metre is plenty to find a problem
    const set = (latitude, longitude, how) => {
        lat.value = latitude.toFixed(5);
        lng.value = longitude.toFixed(5);
        method.value = how;
        clearBtn.hidden = false;
    };

    box.hidden = false;
    if ("geolocation" in navigator) { locateBtn.hidden = false; }
    // Coming back to the form after an error keeps a location already added
    if (lat.value && lng.value) {
        clearBtn.hidden = false;
        say(method.value === "map" ? "Your pin will be sent with your report." :
            "Your location will be sent with your report.", "ok");
    }

    // ---------- Use my current location ----------
    locateBtn.addEventListener("click", () => {
        locateBtn.disabled = true;
        say("Finding your location…");
        navigator.geolocation.getCurrentPosition((pos) => {
            locateBtn.disabled = false;
            set(pos.coords.latitude, pos.coords.longitude, "device");
            if (marker) { placePin(pos.coords.latitude, pos.coords.longitude, false); }
            const near = pos.coords.accuracy ? ` (accurate to about ${Math.round(pos.coords.accuracy)} m)` : "";
            say(`Location added${near}. It will be sent with your report.`, "ok");
        }, (err) => {
            locateBtn.disabled = false;
            say(err.code === err.PERMISSION_DENIED
                ? "Location wasn't shared. That's fine: the building and area are enough, or pick the spot on a map."
                : "We couldn't find your location. That's fine: the building and area are enough, or pick the spot on a map.",
                "error");
        }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 });
    });

    // ---------- Pick on a map ----------
    let map = null;
    let marker = null;
    let loading = null;

    const loadLeaflet = () => {
        if (window.L) { return Promise.resolve(); }
        if (loading) { return loading; }
        const add = (tag, attrs) => new Promise((resolve, reject) => {
            const el = document.createElement(tag);
            Object.assign(el, attrs);
            el.crossOrigin = "anonymous";
            el.referrerPolicy = "no-referrer";
            el.onload = resolve;
            el.onerror = reject;
            document.head.appendChild(el);
        });
        loading = Promise.all([
            add("link", { rel: "stylesheet", href: LEAFLET + "leaflet.min.css", integrity: SRI.css }),
            add("script", { src: LEAFLET + "leaflet.min.js", integrity: SRI.js }),
        ]);
        return loading;
    };

    // Open where the problem most likely is: the pin already chosen, else the building named in the form,
    // else around all our buildings
    const startView = () => {
        if (lat.value && lng.value) { return { centre: [Number(lat.value), Number(lng.value)], zoom: 18 }; }
        const named = building && Object.keys(points).find((n) => n.toLowerCase() === building.value.trim().toLowerCase());
        if (named) { return { centre: points[named], zoom: 17 }; }
        const all = Object.values(points);
        if (all.length) {
            const avg = (i) => all.reduce((sum, p) => sum + p[i], 0) / all.length;
            return { centre: [avg(0), avg(1)], zoom: 13 };
        }
        return { centre: [52.4862, -1.8904], zoom: 12 };  // Birmingham, if no buildings are set up yet
    };

    function placePin(latitude, longitude, announce) {
        if (!marker) {
            const icon = L.divIcon({ className: "map-pin-icon", iconSize: [34, 34], iconAnchor: [17, 34],
                                     html: '<i class="fa-solid fa-location-dot" aria-hidden="true"></i>' });
            marker = L.marker([latitude, longitude], { icon, draggable: true, keyboard: false,
                                                       title: "Your pin", alt: "Your pin" }).addTo(map);
            marker.on("dragend", () => {
                const p = marker.getLatLng();
                set(p.lat, p.lng, "map");
                say("Pin moved. It will be sent with your report.", "ok");
            });
        } else {
            marker.setLatLng([latitude, longitude]);
        }
        if (announce) {
            set(latitude, longitude, "map");
            say("Pin dropped. Drag it to adjust, or tap somewhere else. It will be sent with your report.", "ok");
        }
    }

    const openMap = async () => {
        wrap.hidden = false;
        openBtn.setAttribute("aria-expanded", "true");
        if (map) { map.invalidateSize(); return; }
        say("Loading the map…");
        try {
            await loadLeaflet();
        } catch (e) {
            wrap.hidden = true;
            openBtn.setAttribute("aria-expanded", "false");
            say("The map couldn't load. That's fine: the building and area are enough.", "error");
            return;
        }
        const view = startView();
        map = L.map(mapEl, { keyboard: true }).setView(view.centre, view.zoom);
        L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',
        }).addTo(map);
        map.getContainer().setAttribute("aria-label", "Map. Tap or click where the problem is to drop a pin.");
        map.on("click", (e) => placePin(e.latlng.lat, e.latlng.lng, true));
        if (lat.value && lng.value) { placePin(Number(lat.value), Number(lng.value), false); }
        // The instructions are right above the map, so only speak up if there's already a pin
        say(lat.value ? "Your pin is on the map. Drag it, or tap somewhere else, to change it." : "");
    };

    const closeMap = () => {
        wrap.hidden = true;
        openBtn.setAttribute("aria-expanded", "false");
        openBtn.focus();
    };

    openBtn.addEventListener("click", () => (wrap.hidden ? openMap() : closeMap()));
    closeBtn.addEventListener("click", closeMap);
    centreBtn.addEventListener("click", () => {
        if (!map) { return; }
        const c = map.getCenter();
        placePin(c.lat, c.lng, true);
    });

    // ---------- Remove ----------
    clearBtn.addEventListener("click", () => {
        lat.value = "";
        lng.value = "";
        method.value = "";
        clearBtn.hidden = true;
        if (marker) { marker.remove(); marker = null; }
        say("Location removed. It won't be sent.");
        openBtn.focus();
    });
})();
