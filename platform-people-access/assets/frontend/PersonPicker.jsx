// 員工選擇器（React）。整理自 GMS 監控平台 frontend/src/components/PersonPicker.jsx，與 power-bill-agent 的
// employee_picker 同一規格（references/person-picker.md）。樣式在 person-picker.css。
//
// 用法：
//   <PersonPicker label="負責人" picked={owner} onPick={setOwner} />
//   <PersonPicker label="再加一位" clearOnPick exclude={members.map((m) => m.account)}
//                 onPick={(p) => p && setMembers([...members, p])} />
//   <PersonPicker search={searchPlatformUsers} disabledReason={(p) => (p.email ? "" : "無 Email，不能擔任負責人")} ... />
//
// 規則：選定只送工號；一改字就清掉已選的人；Enter 在沒有候選時不送出表單——打出來的文字永遠不會被當成一個人。
import { useEffect, useId, useRef, useState } from "react";

/** 依專案的 API 前綴調整。IIS 子路徑部署時不要寫死 "/"，用相對路徑或從設定取前綴。 */
const SEARCH_URL = "api/admin/employees";
export const SEARCH_LIMIT = 20;

/** 「姓名（工號）」：選定的人在各處都這樣顯示。 */
export function personLabel(person) {
  if (!person) return "";
  return person.name ? `${person.name}（${person.account}）` : person.account;
}

/** 候選第二行：部門 · 職稱 · Email（有什麼列什麼；沒有 Email 標「無 Email」）。 */
function detail(item) {
  return [item.department, item.title, item.email || (item.email === "" ? "無 Email" : "")].filter(Boolean).join(" · ");
}

/** 查員工資料表。回 {items, note}；伺服器錯誤時丟出帶 message 的 Error。 */
export async function searchEmployees(query, signal) {
  const response = await fetch(`${SEARCH_URL}?q=${encodeURIComponent(query)}`, {
    signal, credentials: "same-origin", headers: { Accept: "application/json" },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.message || `搜尋失敗（${response.status}）`);
  return { items: data.results || [], note: data.limited ? `只列出前 ${SEARCH_LIMIT} 筆，請輸入更完整的工號或姓名` : "" };
}

export function PersonPicker({ label, placeholder = "搜尋工號 / 姓名 / 部門", search = searchEmployees, picked, onPick,
  exclude = [], disabledReason, autoFocus = false, clearOnPick = false, required = false }) {
  const listId = useId();
  const [text, setText] = useState(personLabel(picked));
  const [state, setState] = useState({ open: false, items: [], active: -1, note: "", error: "", loading: false });
  const timer = useRef(null);
  const seq = useRef(0);
  const controller = useRef(null);

  useEffect(() => { setText(personLabel(picked)); }, [picked?.account, picked?.name]);
  useEffect(() => () => { clearTimeout(timer.current); controller.current?.abort(); }, []);

  const skip = new Set(exclude.filter(Boolean).map((a) => a.toLowerCase()));
  const items = state.items.filter((item) => !skip.has(item.account.toLowerCase()));

  function close() {
    setState((s) => ({ ...s, open: false, active: -1 }));
  }

  function run(query) {
    const my = ++seq.current;              // 晚到的舊結果丟掉
    controller.current?.abort();
    controller.current = new AbortController();
    setState({ open: true, items: [], active: -1, note: "", error: "", loading: true });
    search(query, controller.current.signal)
      .then(({ items: found, note }) => {
        if (my === seq.current) setState({ open: true, items: found, active: found.length ? 0 : -1, note: note || "", error: "", loading: false });
      })
      .catch((error) => {
        if (error.name !== "AbortError" && my === seq.current) {
          setState({ open: true, items: [], active: -1, note: "", error: error.message || "搜尋失敗，請稍後再試", loading: false });
        }
      });
  }

  function change(value) {
    setText(value);
    if (picked) onPick(null);              // 一改字就不再是選定的人
    clearTimeout(timer.current);
    const query = value.trim();
    if (!query) {
      seq.current += 1;
      close();
      return;
    }
    timer.current = setTimeout(() => run(query), 250);
  }

  function choose(item) {
    if (disabledReason?.(item)) return;
    onPick(item);
    setText(clearOnPick ? "" : personLabel(item));
    close();
  }

  function keyDown(event) {
    if (!state.open || !items.length) {
      if (event.key === "Enter") event.preventDefault();   // 不送出打出來的名字
      if (event.key === "Escape") close();
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setState((s) => ({ ...s, active: Math.min(s.active + 1, items.length - 1) }));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setState((s) => ({ ...s, active: Math.max(s.active - 1, 0) }));
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (items[state.active]) choose(items[state.active]);
    } else if (event.key === "Escape") {
      close();
    }
  }

  const activeId = state.open && state.active >= 0 ? `${listId}-${state.active}` : undefined;
  const missing = required && !picked && text.trim() && !state.open;
  return (
    <div className={`field person-picker${picked ? " picked" : ""}`}>
      {label ? <span>{label}</span> : null}
      <div className="person-picker-box">
        <svg className="person-picker-glass" width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="11" cy="11" r="6.5" fill="none" stroke="currentColor" strokeWidth="1.8" />
          <path d="M16 16l4 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
        <input type="search" autoComplete="off" value={text} placeholder={placeholder} aria-label={label || placeholder}
          role="combobox" aria-expanded={state.open} aria-controls={listId} aria-activedescendant={activeId}
          aria-invalid={missing || undefined} autoFocus={autoFocus}
          onChange={(e) => change(e.target.value)} onKeyDown={keyDown} onBlur={() => setTimeout(close, 150)} />
        {state.open ? (
          <div className="person-picker-list" id={listId} role="listbox">
            {state.loading ? <div className="person-picker-note">搜尋中…</div> : null}
            {state.error ? <div className="person-picker-note error" role="alert">{state.error}</div> : null}
            {!state.loading && !state.error && !items.length ? <div className="person-picker-note">查無符合的人員</div> : null}
            {items.map((item, i) => {
              const reason = disabledReason?.(item);
              return (
                <button key={item.account} id={`${listId}-${i}`} type="button" role="option" aria-selected={i === state.active}
                  aria-disabled={Boolean(reason)} className={`${i === state.active ? "active" : ""}${reason ? " disabled" : ""}`}
                  onMouseDown={(e) => { e.preventDefault(); choose(item); }}>
                  <b>{item.name || item.account}</b> <span className="person-picker-account">{item.account}</span>
                  <span className="person-picker-detail">{reason || detail(item)}</span>
                </button>
              );
            })}
            {state.note ? <div className="person-picker-note">{state.note}</div> : null}
          </div>
        ) : null}
      </div>
      {missing ? <span className="person-picker-hint" role="alert">請從清單選擇員工</span> : null}
    </div>
  );
}

/** 已指定的人：頭像字、姓名、工號、部門 · 職稱；flag 例如「查無此工號」。 */
export function PersonCard({ person, flag, onRemove }) {
  if (!person) return <span className="person-picker-account">（未設定）</span>;
  return (
    <div className="person-card">
      <span className="person-card-avatar" aria-hidden="true">{(person.name || person.account).slice(0, 1)}</span>
      <div>
        <b>{person.name || "—"}</b> <span className="person-picker-account">{person.account}</span>
        {flag ? <> <span className="person-card-flag">{flag}</span></> : null}
        {detail(person) ? <div className="person-picker-detail">{detail(person)}</div> : null}
      </div>
      {onRemove ? <button type="button" className="person-card-remove" onClick={onRemove}>移除</button> : null}
    </div>
  );
}
