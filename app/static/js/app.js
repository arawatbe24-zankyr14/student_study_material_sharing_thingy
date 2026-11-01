/* Shared helpers: CSRF token, toast messages and the Delete button.
   Loaded on every page. No inline scripts are used anywhere (see CSP). */
(function () {
  "use strict";

  const meta = document.querySelector('meta[name="csrf-token"]');
  const csrfToken = meta ? meta.content : "";

  function showToast(message, kind) {
    const region = document.getElementById("toast");
    if (!region) return;
    region.textContent = message;
    region.className = "toast toast-" + kind;
    region.hidden = false;
    clearTimeout(showToast.timer);
    showToast.timer = setTimeout(function () { region.hidden = true; }, 6000);
  }

  async function deleteResource(button) {
    const id = button.dataset.deleteId;
    const title = button.dataset.title || "this resource";
    if (!window.confirm("Delete \u201C" + title + "\u201D? This removes the file and cannot be undone.")) {
      return;
    }

    button.disabled = true;
    button.textContent = "Deleting\u2026";
    try {
      const response = await fetch("/api/resources/" + encodeURIComponent(id), {
        method: "DELETE",
        credentials: "same-origin",
        headers: { "X-CSRF-Token": csrfToken, "Accept": "application/json" }
      });
      if (response.status === 401) {
        window.location.href = "/login";
        return;
      }
      const data = await response.json().catch(function () { return {}; });
      if (!response.ok) {
        throw new Error(data.error || "The resource could not be deleted.");
      }

      const row = button.closest("[data-resource]");
      const list = row.parentElement;
      row.remove();
      if (list.children.length === 0 && list.dataset.emptyId) {
        list.hidden = true;
        const empty = document.getElementById(list.dataset.emptyId);
        if (empty) empty.hidden = false;
      }
      showToast("Resource deleted.", "success");
      document.dispatchEvent(new CustomEvent("resource:deleted", { detail: { list: list } }));
    } catch (error) {
      button.disabled = false;
      button.textContent = "Delete";
      const offline = error instanceof TypeError;
      showToast(offline ? "Could not reach the server. Check your connection and try again." : error.message, "error");
    }
  }

  document.addEventListener("click", function (event) {
    const button = event.target.closest("[data-delete-id]");
    if (button) deleteResource(button);
  });

  window.NotesApp = { csrfToken: csrfToken, showToast: showToast };
})();
