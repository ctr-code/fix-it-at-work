/* jshint esversion: 8 */
// Voice note on the officer's "Record your visit" form. Records from the microphone with the browser's
// MediaRecorder, lets the officer play it back or remove it, and puts the recording into the real "audio"
// file input, which is what the form sends. Choosing a file in that input works too (and is all there is in
// browsers that can't record). Recording stops by itself after MAX_SECONDS.
(() => {
    "use strict";

    const box = document.querySelector("[data-voice]");
    const input = document.getElementById("id_audio");
    if (!box || !input) { return; }
    const recordBtn = box.querySelector("[data-voice-record]");
    const removeBtn = box.querySelector("[data-voice-remove]");
    const timer = box.querySelector("[data-voice-timer]");
    const preview = box.querySelector("[data-voice-preview]");
    const status = box.querySelector("[data-voice-status]");
    const fileLabel = document.querySelector("[data-voice-file-label]");
    const MAX_SECONDS = 10 * 60;

    const canRecord = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder &&
                         window.DataTransfer);
    let recorder = null;
    let started = 0;
    let tick = null;
    let url = null;

    const say = (text, kind) => {
        status.textContent = text;
        status.className = "locate-status" + (kind ? " is-" + kind : "");
    };
    const clock = (secs) => `${Math.floor(secs / 60)}:${String(Math.floor(secs % 60)).padStart(2, "0")}`;
    const label = (text, icon) => {
        recordBtn.querySelector("span").textContent = text;
        recordBtn.querySelector("i").className = "fa-solid " + icon;
    };

    const showPreview = (file) => {
        if (url) { URL.revokeObjectURL(url); }
        url = file ? URL.createObjectURL(file) : null;
        preview.hidden = !file;
        if (url) { preview.src = url; } else { preview.removeAttribute("src"); }
        removeBtn.hidden = !file;
    };

    // Recorders give WebM (Chrome, Edge, Firefox) or MP4 (Safari); name the file to match
    const extensionFor = (type) => (type.includes("mp4") ? "m4a" : type.includes("ogg") ? "ogg" : "webm");

    const stop = () => { if (recorder && recorder.state === "recording") { recorder.stop(); } };

    const start = async () => {
        let stream;
        try {
            stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        } catch (e) {
            say("The microphone isn't available, so nothing was recorded. You can type instead, or choose a recording below.", "error");
            return;
        }
        const chunks = [];
        recorder = new MediaRecorder(stream);
        recorder.addEventListener("dataavailable", (e) => { if (e.data.size) { chunks.push(e.data); } });
        recorder.addEventListener("stop", () => {
            clearInterval(tick);
            stream.getTracks().forEach((t) => t.stop());
            recordBtn.classList.remove("is-recording");
            const type = (recorder.mimeType || "audio/webm").split(";")[0];
            const secs = (Date.now() - started) / 1000;
            const file = new File(chunks, `voice-note.${extensionFor(type)}`, { type });
            const list = new DataTransfer();
            list.items.add(file);
            input.files = list.files;
            showPreview(file);
            label("Record again", "fa-microphone-lines");
            timer.textContent = clock(secs);
            say(`Voice note recorded (${clock(secs)}). Play it back to check it, then save the visit.`, "ok");
        });
        recorder.start();
        started = Date.now();
        recordBtn.classList.add("is-recording");
        label("Stop recording", "fa-stop");
        say("Recording… press Stop when you've finished.");
        timer.textContent = "0:00";
        tick = setInterval(() => {
            const secs = (Date.now() - started) / 1000;
            timer.textContent = clock(secs);
            if (secs >= MAX_SECONDS) { stop(); }
        }, 500);
    };

    if (canRecord) {
        box.hidden = false;
        fileLabel.textContent = "Or choose a recording from your device";
        recordBtn.addEventListener("click", () => (recorder && recorder.state === "recording" ? stop() : start()));
    }

    // A file chosen by hand gets the same preview and Remove button
    input.addEventListener("change", () => {
        const file = input.files[0];
        showPreview(file);
        if (file) {
            box.hidden = false;
            timer.textContent = "";
            say(`${file.name} will be saved with the visit.`, "ok");
        }
    });

    removeBtn.addEventListener("click", () => {
        stop();
        input.value = "";
        showPreview(null);
        timer.textContent = "";
        label("Record a voice note", "fa-microphone-lines");
        say("Voice note removed. It won't be saved.");
        (canRecord ? recordBtn : input).focus();
    });
})();
