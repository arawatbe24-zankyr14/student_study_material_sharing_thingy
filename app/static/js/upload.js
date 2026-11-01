/* Upload page: quick checks in the browser so mistakes are caught before the
   upload starts. The server repeats every check, so this is only a convenience. */
(function () {
  "use strict";

  const form = document.getElementById("upload-form");
  if (!form) return;

  const input = form.elements.file;
  const hint = document.getElementById("file-hint");
  const error = document.getElementById("file-error");
  const submit = form.querySelector('button[type="submit"]');
  const maxMb = Number(form.dataset.maxMb) || 20;
  const allowed = ["pdf", "ppt", "pptx"];

  function formatSize(bytes) {
    if (bytes < 1024 * 1024) return Math.max(1, Math.round(bytes / 1024)) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }

  input.addEventListener("change", function () {
    hint.textContent = "";
    error.textContent = "";
    const file = input.files[0];
    if (!file) return;

    const extension = file.name.includes(".") ? file.name.split(".").pop().toLowerCase() : "";
    let problem = "";
    if (!allowed.includes(extension)) {
      problem = "Only PDF, PPT and PPTX files are allowed.";
    } else if (file.size === 0) {
      problem = "That file is empty.";
    } else if (file.size > maxMb * 1024 * 1024) {
      problem = "That file is " + formatSize(file.size) + ". The limit is " + maxMb + " MB.";
    }

    if (problem) {
      error.textContent = problem;
      input.value = "";
    } else {
      hint.textContent = "Selected: " + file.name + " (" + formatSize(file.size) + ")";
    }
  });

  form.addEventListener("submit", function () {
    submit.disabled = true;
    submit.textContent = "Uploading\u2026";
  });

  // If the browser restores this page from its back/forward cache, re-enable the button.
  window.addEventListener("pageshow", function () {
    submit.disabled = false;
    submit.textContent = "Upload resource";
  });
})();
