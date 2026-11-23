/*
 * 員工選擇器（原生 JS，給 Jinja／Django template 等沒有 React 的專案）。規格同 PersonPicker.jsx。
 *
 * HTML：
 *   <div class="person-picker" data-person-picker data-name="owner_account" data-required
 *        data-search-url="api/admin/employees" data-label="負責人"></div>
 *   <link rel="stylesheet" href="person-picker.css"><script src="person-picker.js" defer></script>
 *
 * 表單只會送出隱藏欄位 <input type="hidden" name="owner_account"> 的工號。
 * 已有選定值時加 data-account="A1001" data-person-name="王小明"。
 * 選定時在元素上發出 "person-pick" 事件（event.detail = 員工物件或 null）。
 * data-required：送出表單時沒選就擋下並提示「請從清單選擇員工」。
 */
(function () {
  "use strict";
  var LIMIT = 20;

  function label(p) { return p ? (p.name ? p.name + "（" + p.account + "）" : p.account) : ""; }
  function detail(p) {
    return [p.department, p.title, p.email || (p.email === "" ? "無 Email" : "")].filter(Boolean).join(" · ");
  }
  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text) node.textContent = text;   // 一律 textContent，不用 innerHTML（姓名來自資料庫）
    return node;
  }

  function mount(root) {
    var name = root.dataset.name || "account";
    var url = root.dataset.searchUrl || "api/admin/employees";
    var listId = "pp-" + Math.random().toString(36).slice(2);
    var picked = root.dataset.account ? { account: root.dataset.account, name: root.dataset.personName || "" } : null;
    var items = [], active = -1, timer = null, seq = 0, controller = null;

    if (root.dataset.label) root.appendChild(el("span", "", root.dataset.label));
    var box = el("div", "person-picker-box");
    var input = el("input");
    input.type = "search"; input.autocomplete = "off";
    input.placeholder = root.dataset.placeholder || "搜尋工號 / 姓名 / 部門";
    input.setAttribute("role", "combobox"); input.setAttribute("aria-controls", listId); input.setAttribute("aria-expanded", "false");
    input.setAttribute("aria-label", root.dataset.label || input.placeholder);
    var hidden = el("input"); hidden.type = "hidden"; hidden.name = name;
    var list = el("div", "person-picker-list"); list.id = listId; list.setAttribute("role", "listbox"); list.hidden = true;
    var hint = el("span", "person-picker-hint", "請從清單選擇員工"); hint.hidden = true; hint.setAttribute("role", "alert");
    box.appendChild(input); box.appendChild(list);
    root.appendChild(box); root.appendChild(hidden); root.appendChild(hint);

    function setPicked(p, keepText) {
      picked = p;
      hidden.value = p ? p.account : "";
      root.classList.toggle("picked", !!p);
      if (!keepText) input.value = label(p);
      hint.hidden = true; input.removeAttribute("aria-invalid");
      root.dispatchEvent(new CustomEvent("person-pick", { detail: p }));
    }
    function close() { list.hidden = true; input.setAttribute("aria-expanded", "false"); active = -1; }
    function note(text, cls) { list.appendChild(el("div", "person-picker-note" + (cls ? " " + cls : ""), text)); }
    function render(state) {
      list.textContent = "";
      list.hidden = false; input.setAttribute("aria-expanded", "true");
      if (state.loading) return note("搜尋中…");
      if (state.error) return note(state.error, "error");
      if (!items.length) return note("查無符合的人員");
      items.forEach(function (p, i) {
        var b = el("button", i === active ? "active" : "");
        b.type = "button"; b.id = listId + "-" + i; b.setAttribute("role", "option");
        b.setAttribute("aria-selected", i === active ? "true" : "false");
        b.appendChild(el("b", "", p.name || p.account));
        b.appendChild(document.createTextNode(" "));
        b.appendChild(el("span", "person-picker-account", p.account));
        b.appendChild(el("span", "person-picker-detail", detail(p)));
        b.addEventListener("mousedown", function (e) { e.preventDefault(); choose(p); });
        list.appendChild(b);
      });
      if (state.limited) note("只列出前 " + LIMIT + " 筆，請輸入更完整的工號或姓名");
      input.setAttribute("aria-activedescendant", active >= 0 ? listId + "-" + active : "");
    }
    function choose(p) { setPicked(p); close(); }

    function run(query) {
      var my = ++seq;
      if (controller) controller.abort();
      controller = new AbortController();
      items = []; render({ loading: true });
      fetch(url + "?q=" + encodeURIComponent(query), { signal: controller.signal, credentials: "same-origin",
                                                      headers: { Accept: "application/json" } })
        .then(function (r) { return r.json().catch(function () { return {}; }).then(function (d) {
          if (!r.ok) throw new Error(d.message || "搜尋失敗（" + r.status + "）");
          return d;
        }); })
        .then(function (d) {
          if (my !== seq) return;              // 晚到的舊結果丟掉
          items = d.results || []; active = items.length ? 0 : -1;
          render({ limited: d.limited });
        })
        .catch(function (e) {
          if (e.name !== "AbortError" && my === seq) { items = []; render({ error: e.message || "搜尋失敗，請稍後再試" }); }
        });
    }

    input.addEventListener("input", function () {
      if (picked) setPicked(null, true);       // 一改字就不再是選定的人
      clearTimeout(timer);
      var q = input.value.trim();
      if (!q) { seq++; close(); return; }
      timer = setTimeout(function () { run(q); }, 250);
    });
    input.addEventListener("keydown", function (e) {
      if (list.hidden || !items.length) {
        if (e.key === "Enter") e.preventDefault();   // 不送出打出來的名字
        if (e.key === "Escape") close();
        return;
      }
      if (e.key === "ArrowDown") { e.preventDefault(); active = Math.min(active + 1, items.length - 1); render({}); }
      else if (e.key === "ArrowUp") { e.preventDefault(); active = Math.max(active - 1, 0); render({}); }
      else if (e.key === "Enter") { e.preventDefault(); if (items[active]) choose(items[active]); }
      else if (e.key === "Escape") close();
    });
    input.addEventListener("blur", function () { setTimeout(close, 150); });

    var form = root.closest("form");
    if (form && root.hasAttribute("data-required")) {
      form.addEventListener("submit", function (e) {
        if (!hidden.value) { e.preventDefault(); hint.hidden = false; input.setAttribute("aria-invalid", "true"); input.focus(); }
      });
    }
    if (picked) setPicked(picked);
  }

  function init() { document.querySelectorAll("[data-person-picker]").forEach(mount); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
  window.PersonPicker = { mount: mount };
})();
