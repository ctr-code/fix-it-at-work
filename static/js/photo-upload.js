/* jshint esversion: 6 */
// Drag-and-drop photo upload for the report form.
// The real <input type="file"> stays in the form; this script keeps its file list in
// step with the previews, so only the photos shown are submitted with the report.
(() => {
    "use strict";

    const ACCEPTED = ["image/jpeg", "image/png", "image/webp"];
    const EXTENSIONS = /\.(jpe?g|png|webp)$/i;

    document.querySelectorAll(".photo-upload").forEach((root) => {
        const input = root.querySelector(".dropzone-input");
        const zone = root.querySelector("[data-dropzone]");
        const list = root.querySelector("[data-list]");
        const status = root.querySelector("[data-status]");
        const maxFiles = parseInt(root.dataset.maxFiles, 10) || 1;
        const maxBytes = (parseFloat(root.dataset.maxMb) || 10) * 1024 * 1024;

        // Browsers that can't edit a file input's list keep the plain file picker
        let canSync = true;
        try { new DataTransfer(); } catch (e) { canSync = false; }
        if (!canSync) { return; }

        root.classList.add("is-enhanced");
        let photos = [];   // { file, url }
        let problems = []; // { name, message }

        const say = (text) => { status.textContent = ""; setTimeout(() => { status.textContent = text; }, 50); };

        const formatSize = (bytes) => bytes >= 1024 * 1024
            ? (bytes / (1024 * 1024)).toFixed(1) + " MB"
            : Math.max(1, Math.round(bytes / 1024)) + " KB";

        // Put the shown photos into the real input, so the form submits exactly these
        const sync = () => {
            const dt = new DataTransfer();
            photos.forEach((p) => dt.items.add(p.file));
            input.files = dt.files;
        };

        const render = () => {
            list.innerHTML = "";
            photos.forEach((p, i) => {
                const li = document.createElement("li");
                li.className = "photo-item";
                li.innerHTML =
                    '<img class="photo-thumb-sm" alt="">' +
                    '<div class="photo-meta"><span class="photo-name"></span><span class="photo-size"></span></div>' +
                    '<button type="button" class="photo-remove"><i class="fa-solid fa-xmark" aria-hidden="true"></i><span class="photo-remove-text">Remove</span></button>';
                li.querySelector("img").src = p.url;
                li.querySelector(".photo-name").textContent = p.file.name;
                li.querySelector(".photo-size").textContent = formatSize(p.file.size) + " · ready to send with your report";
                const btn = li.querySelector("button");
                btn.setAttribute("aria-label", "Remove " + p.file.name);
                btn.addEventListener("click", () => removePhoto(i));
                list.appendChild(li);
            });
            problems.forEach((p, i) => {
                const li = document.createElement("li");
                li.className = "photo-item is-error";
                li.setAttribute("role", "alert");
                li.innerHTML =
                    '<span class="photo-error-icon" aria-hidden="true"><i class="fa-solid fa-circle-exclamation"></i></span>' +
                    '<div class="photo-meta"><span class="photo-name"></span><span class="photo-size"></span></div>' +
                    '<button type="button" class="photo-remove"><i class="fa-solid fa-xmark" aria-hidden="true"></i><span class="photo-remove-text">Dismiss</span></button>';
                li.querySelector(".photo-name").textContent = p.name;
                li.querySelector(".photo-size").textContent = p.message;
                const btn = li.querySelector("button");
                btn.setAttribute("aria-label", "Dismiss message about " + p.name);
                btn.addEventListener("click", () => { problems.splice(i, 1); render(); });
                list.appendChild(li);
            });
            root.classList.toggle("is-full", photos.length >= maxFiles);
        };

        const addFiles = (fileList) => {
            problems = [];
            const added = [];
            Array.from(fileList).forEach((file) => {
                const typeOk = ACCEPTED.includes(file.type) || (!file.type && EXTENSIONS.test(file.name));
                if (!typeOk) {
                    problems.push({ name: file.name, message: "This file type can't be used. Please choose a JPG, PNG or WEBP image." });
                } else if (file.size > maxBytes) {
                    problems.push({ name: file.name, message: "This photo is " + formatSize(file.size) + ". The limit is " + root.dataset.maxMb + "MB, so please choose a smaller one." });
                } else if (photos.length >= maxFiles) {
                    problems.push({ name: file.name, message: maxFiles === 1
                        ? "Only one photo can be sent with a report. Remove the current photo first if you'd like to use this one instead."
                        : "You can add up to " + maxFiles + " photos. Remove one first to add this." });
                } else if (photos.some((p) => p.file.name === file.name && p.file.size === file.size)) {
                    problems.push({ name: file.name, message: "This photo is already added." });
                } else {
                    photos.push({ file, url: URL.createObjectURL(file) });
                    added.push(file.name);
                }
            });
            sync();
            render();
            const parts = [];
            if (added.length) { parts.push("Added " + added.join(", ") + "."); }
            if (problems.length) { parts.push(problems.length === 1 ? "One file wasn't added: " + problems[0].message : problems.length + " files weren't added. Details are listed below."); }
            say(parts.join(" "));
            // When the drop area hides because the limit is reached, keep keyboard focus nearby
            if (added.length && photos.length >= maxFiles) {
                const remove = list.querySelector(".photo-remove");
                if (remove) { remove.focus(); }
            }
        };

        const removePhoto = (i) => {
            const [gone] = photos.splice(i, 1);
            URL.revokeObjectURL(gone.url);
            problems = [];
            sync();
            render();
            say("Removed " + gone.file.name + ".");
            root.querySelector("[data-browse]").focus();
        };

        // Browsing: the picker replaces the input's list, so merge its choice with what's shown
        input.addEventListener("change", () => {
            const chosen = Array.from(input.files);
            sync(); // put back the photos already shown before adding the new ones
            if (chosen.length) { addFiles(chosen); }
        });
        root.querySelector("[data-browse]").addEventListener("click", (e) => { e.stopPropagation(); input.click(); });
        zone.addEventListener("click", (e) => { if (e.target !== input) { input.click(); } });

        // Dragging files over the drop area
        let depth = 0;
        const hasFiles = (e) => e.dataTransfer && Array.from(e.dataTransfer.types || []).includes("Files");
        zone.addEventListener("dragenter", (e) => { if (!hasFiles(e)) { return; } e.preventDefault(); depth += 1; zone.classList.add("is-dragover"); });
        zone.addEventListener("dragover", (e) => { if (!hasFiles(e)) { return; } e.preventDefault(); e.dataTransfer.dropEffect = "copy"; });
        zone.addEventListener("dragleave", () => { depth = Math.max(0, depth - 1); if (!depth) { zone.classList.remove("is-dragover"); } });
        zone.addEventListener("drop", (e) => {
            e.preventDefault();
            depth = 0;
            zone.classList.remove("is-dragover");
            if (e.dataTransfer && e.dataTransfer.files.length) { addFiles(e.dataTransfer.files); }
        });
        // A file dropped just outside the area shouldn't open in the browser and lose the form
        ["dragover", "drop"].forEach((type) => window.addEventListener(type, (e) => {
            if (hasFiles(e) && !zone.contains(e.target)) { e.preventDefault(); }
        }));

        // Free the preview images when the page is closed (not when it's kept for the back button)
        window.addEventListener("pagehide", (e) => { if (!e.persisted) { photos.forEach((p) => URL.revokeObjectURL(p.url)); } });
    });
})();
