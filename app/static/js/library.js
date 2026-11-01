/* Library page: loads resources from /api/resources and re-loads them
   whenever the search box or a filter changes. All text is inserted with
   textContent, never innerHTML, so uploaded titles cannot inject HTML. */
(function () {
  "use strict";

  const form = document.getElementById("filters");
  if (!form) return;

  const list = document.getElementById("results");
  const feedback = document.getElementById("feedback");
  const countLabel = document.getElementById("result-count");
  const clearButton = document.getElementById("clear-filters");
  const MAX_RESULTS = 100; // must match the limit used by the server

  let controller = null;
  let debounceTimer = null;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function currentFilters() {
    return {
      q: form.elements.q.value.trim(),
      subject: form.elements.subject.value,
      category: form.elements.category.value
    };
  }

  function hasFilters(filters) {
    return Boolean(filters.q || filters.subject || filters.category);
  }

  function syncUrl(filters) {
    const params = new URLSearchParams();
    Object.keys(filters).forEach(function (key) { if (filters[key]) params.set(key, filters[key]); });
    const query = params.toString();
    history.replaceState(null, "", query ? "?" + query : window.location.pathname);
  }

  /* Same markup as the resource_row macro in templates/_macros.html */
  function buildRow(r) {
    const li = el("li", "resource");
    li.setAttribute("data-resource", "");
    li.dataset.type = r.file_type;

    const main = el("div", "resource-main");
    main.append(el("h3", "resource-title", r.title));
    if (r.description) main.append(el("p", "resource-desc", r.description));
    const tags = el("p", "resource-tags");
    tags.append(el("span", "tag", r.subject), el("span", "tag", r.category));
    main.append(tags);

    const meta = el("div", "resource-meta");
    meta.append(el("span", "", r.uploader_name), el("span", "", r.uploaded_at), el("span", "", r.file_size));

    const actions = el("div", "resource-actions");
    const download = el("a", "btn btn-small", "Download");
    download.href = r.download_url;
    actions.append(download);
    if (r.can_delete) {
      const del = el("button", "btn btn-small btn-danger", "Delete");
      del.type = "button";
      del.dataset.deleteId = r.resource_id;
      del.dataset.title = r.title;
      actions.append(del);
    }

    li.append(el("span", "resource-type", r.file_type.toUpperCase()), main, meta, actions);
    return li;
  }

  function setCount(count) {
    if (count === 0) {
      countLabel.textContent = "";
    } else if (count >= MAX_RESULTS) {
      countLabel.textContent = "Showing the " + MAX_RESULTS + " newest matches. Narrow your search to see others.";
    } else {
      countLabel.textContent = count + (count === 1 ? " resource" : " resources");
    }
  }

  function showEmpty(filters) {
    const box = el("div", "empty");
    if (hasFilters(filters)) {
      box.append(el("h3", "", "No resources match your search"));
      box.append(el("p", "", "Try fewer words, a different spelling, or remove a filter."));
      const reset = el("button", "btn btn-small", "Clear filters");
      reset.type = "button";
      reset.addEventListener("click", resetFilters);
      box.append(reset);
    } else {
      box.append(el("h3", "", "The library is empty"));
      box.append(el("p", "", "No one has shared a resource yet. Upload the first one for your classmates."));
      const link = el("a", "btn btn-small", "Upload resource");
      link.href = "/upload";
      box.append(link);
    }
    feedback.replaceChildren(box);
  }

  function showError(message) {
    const box = el("div", "flash flash-error");
    box.setAttribute("role", "alert");
    box.append(el("p", "", message));
    const retry = el("button", "btn btn-small", "Try again");
    retry.type = "button";
    retry.addEventListener("click", load);
    box.append(retry);
    list.replaceChildren();
    countLabel.textContent = "";
    feedback.replaceChildren(box);
  }

  function render(resources, filters) {
    list.replaceChildren(...resources.map(buildRow));
    setCount(resources.length);
    if (resources.length === 0) {
      showEmpty(filters);
    } else {
      feedback.replaceChildren();
    }
  }

  async function load() {
    if (controller) controller.abort();
    controller = new AbortController();

    const filters = currentFilters();
    syncUrl(filters);
    feedback.replaceChildren(el("p", "loading", "Loading resources\u2026"));

    const query = new URLSearchParams();
    Object.keys(filters).forEach(function (key) { if (filters[key]) query.set(key, filters[key]); });

    try {
      const response = await fetch("/api/resources?" + query.toString(), {
        signal: controller.signal,
        credentials: "same-origin",
        headers: { "Accept": "application/json" }
      });
      if (response.status === 401) {
        window.location.href = "/login?next=/library";
        return;
      }
      const data = await response.json().catch(function () { return {}; });
      if (!response.ok) throw new Error(data.error || "The library could not be loaded.");
      render(data.resources, filters);
    } catch (error) {
      if (error.name === "AbortError") return;
      showError(error instanceof TypeError
        ? "Could not reach the server. Check your connection and try again."
        : error.message);
    }
  }

  function resetFilters() {
    form.reset();
    load();
  }

  form.addEventListener("submit", function (event) { event.preventDefault(); load(); });
  form.elements.q.addEventListener("input", function () {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(load, 300); // wait until typing pauses
  });
  form.elements.subject.addEventListener("change", load);
  form.elements.category.addEventListener("change", load);
  clearButton.addEventListener("click", resetFilters);

  /* app.js removes the row; here we only refresh the count and empty state. */
  document.addEventListener("resource:deleted", function () {
    const remaining = list.children.length;
    setCount(remaining);
    if (remaining === 0) showEmpty(currentFilters());
  });

  // Restore filters from the URL (so a filtered view can be bookmarked).
  const saved = new URLSearchParams(window.location.search);
  form.elements.q.value = saved.get("q") || "";
  form.elements.subject.value = saved.get("subject") || "";
  form.elements.category.value = saved.get("category") || "";

  load();
})();
