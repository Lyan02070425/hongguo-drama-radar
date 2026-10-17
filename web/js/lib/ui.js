// 通用界面组件：卡片、分段按钮、标签、名次变化、可排序表格。

import { h, clear } from "./dom.js";
import * as fmt from "./format.js";

export function card(title, sub, ...children) {
  return h("section", { class: "card" }, title ? h("h2", {}, title) : null, sub ? h("p", { class: "sub" }, sub) : null, ...children);
}

export function pageHead(title, desc) {
  return h("div", { class: "page-head" }, h("h1", {}, title), desc ? h("p", {}, desc) : null);
}

export function notice(text) {
  return h("div", { class: "notice" }, text);
}

export function empty(text = "暂无数据") {
  return h("p", { class: "empty" }, text);
}

export function kpi(label, value, foot, { small = false } = {}) {
  return h("div", { class: "card kpi" }, h("div", { class: "label" }, label), h("div", { class: "value" + (small ? " small" : "") }, value), foot ? h("div", { class: "foot" }, foot) : null);
}

// 分段按钮：options = [{value, label}]；onChange(value)
export function segmented(options, current, onChange, label = "") {
  const wrap = h("div", { class: "seg", role: "group", "aria-label": label });
  const render = (active) => {
    clear(wrap);
    for (const opt of options) {
      wrap.append(h("button", {
        type: "button",
        "aria-pressed": String(opt.value === active),
        onclick: () => { render(opt.value); onChange(opt.value); },
      }, opt.label));
    }
  };
  render(current);
  return wrap;
}

export function tagChips(tags, onTag) {
  const wrap = h("span", { class: "tags" });
  for (const t of tags || []) {
    wrap.append(onTag ? h("button", { class: "chip", type: "button", onclick: (e) => { e.stopPropagation(); onTag(t); } }, t) : h("span", { class: "chip" }, t));
  }
  return wrap;
}

export function badge(row) {
  if (row.badge === "new") return h("span", { class: "chip new", title: "之前从没上过这个榜" }, "NEW");
  if (row.badge === "back") return h("span", { class: "chip back", title: "昨天不在榜，以前上过" }, "回榜");
  return null;
}

export function delta(value) {
  if (value === null || value === undefined) return h("span", { class: "flat" }, "—");
  if (value === 0) return h("span", { class: "flat" }, "0");
  return h("span", { class: value > 0 ? "up" : "down", title: value > 0 ? "名次上升" : "名次下降" }, (value > 0 ? "↑" : "↓") + Math.abs(value));
}

export function signedCount(value) {
  return h("span", { class: fmt.trendClass(value) }, fmt.count(value, { signed: true }));
}

export function dramaLink(app, row) {
  return h("button", { class: "drama-link", type: "button", onclick: () => app.openDrama(row.id) }, row.title || row.id);
}

export function titleCell(app, row, { withStatus = true } = {}) {
  return h("div", { class: "title-cell" },
    dramaLink(app, row),
    badge(row),
    withStatus ? (row.status_tags || []).map((t) => h("span", { class: "chip fresh" }, t)) : null,
  );
}

export function scoreBar(score) {
  return h("div", { class: "score" }, h("b", {}, score.toFixed(0)), h("div", { class: "bar", role: "img", "aria-label": `潜力分 ${score.toFixed(0)}` }, h("span", { style: { width: `${Math.max(0, Math.min(100, score))}%` } })));
}

/**
 * 可排序表格。
 * columns: [{ key, label, value: row => 可比较值, render: row => Node|string, num: bool, wrap: bool }]
 */
export function table(columns, rows, { sortKey = null, sortDir = "asc", limit = 0, emptyText = "暂无数据" } = {}) {
  const wrap = h("div", { class: "table-wrap" });
  if (!rows || !rows.length) {
    wrap.append(empty(emptyText));
    return wrap;
  }
  let key = sortKey;
  let dir = sortDir;
  let showAll = !limit;
  const tbl = h("table");
  const thead = h("thead");
  const tbody = h("tbody");
  tbl.append(thead, tbody);
  wrap.append(tbl);
  const more = h("div", { class: "more-row" });
  wrap.append(more);

  const valueOf = (col, row) => (col.value ? col.value(row) : row[col.key]);
  const draw = () => {
    clear(thead);
    clear(tbody);
    const tr = h("tr");
    for (const col of columns) {
      const sortable = col.sortable !== false;
      const th = h("th", {
        class: [sortable ? "sortable" : "", col.num ? "num" : ""].join(" ").trim(),
        scope: "col",
        "aria-sort": key === col.key ? (dir === "asc" ? "ascending" : "descending") : null,
        tabindex: sortable ? "0" : null,
        title: col.title || null,
      }, col.label);
      if (sortable) {
        const toggle = () => {
          if (key === col.key) dir = dir === "asc" ? "desc" : "asc";
          else { key = col.key; dir = col.num ? "desc" : "asc"; }
          draw();
        };
        th.addEventListener("click", toggle);
        th.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); } });
      }
      tr.append(th);
    }
    thead.append(tr);
    let sorted = rows.slice();
    if (key) {
      const col = columns.find((c) => c.key === key);
      sorted.sort((a, b) => {
        const va = valueOf(col, a);
        const vb = valueOf(col, b);
        if (va === vb) return 0;
        if (va === null || va === undefined) return 1;
        if (vb === null || vb === undefined) return -1;
        const cmp = typeof va === "string" ? va.localeCompare(vb, "zh-CN") : va - vb;
        return dir === "asc" ? cmp : -cmp;
      });
    }
    const visible = showAll ? sorted : sorted.slice(0, limit);
    for (const row of visible) {
      const r = h("tr");
      for (const col of columns) {
        const content = col.render ? col.render(row) : valueOf(col, row);
        r.append(h("td", { class: [col.num ? "num" : "", col.wrap ? "wrap" : ""].join(" ").trim() || null }, content ?? "—"));
      }
      tbody.append(r);
    }
    clear(more);
    if (!showAll && sorted.length > limit) {
      more.append(`显示前 ${limit} / ${sorted.length} 条 · `, h("a", { href: "#", onclick: (e) => { e.preventDefault(); showAll = true; draw(); } }, "显示全部"));
    }
  };
  draw();
  return wrap;
}
