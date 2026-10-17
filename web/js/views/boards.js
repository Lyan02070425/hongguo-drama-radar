// 榜单：四个官方榜的完整排名，可搜索、按题材筛选、只看新剧，所有列可排序。

import { h, clear } from "../lib/dom.js";
import * as fmt from "../lib/format.js";
import * as ui from "../lib/ui.js";

export default {
  id: "boards",
  title: "榜单",
  async render(root, app) {
    const data = await app.data.get("boards");
    const boardIds = Object.keys(data.boards);
    let board = boardIds.includes(app.params.get("board")) ? app.params.get("board") : boardIds[0];
    let query = app.params.get("q") || "";
    let tag = app.params.get("tag") || "";
    let onlyNew = app.params.get("new") === "1";

    root.append(ui.pageHead("官方榜单", "名次变化和日增量都是和上一期比。NEW = 第一次上这个榜；回榜 = 昨天不在榜、以前上过。"));
    const controls = h("div", { class: "controls" });
    const summary = h("div", { class: "grid cols-4" });
    const body = h("div", { class: "section" });
    root.append(controls, summary, body);

    const search = h("input", { type: "search", placeholder: "搜索剧名", value: query, "aria-label": "搜索剧名" });
    const tagSelect = h("select", { "aria-label": "按题材筛选" });
    const newBox = h("input", { type: "checkbox", checked: onlyNew });
    controls.append(
      ui.segmented(boardIds.map((b) => ({ value: b, label: data.boards[b].label })), board, (v) => { board = v; app.setParams({ board: v }); fillTags(); draw(); }, "选择榜单"),
      search, tagSelect, h("label", { class: "check" }, newBox, "只看新剧"),
    );
    search.addEventListener("input", () => { query = search.value.trim(); app.setParams({ q: query }); draw(); });
    tagSelect.addEventListener("change", () => { tag = tagSelect.value; app.setParams({ tag }); draw(); });
    newBox.addEventListener("change", () => { onlyNew = newBox.checked; app.setParams({ new: onlyNew ? "1" : null }); draw(); });

    function fillTags() {
      clear(tagSelect);
      const counts = new Map();
      for (const r of data.boards[board].rows) for (const t of r.tags || []) counts.set(t, (counts.get(t) || 0) + 1);
      tagSelect.append(h("option", { value: "" }, "全部题材"));
      for (const [t, c] of [...counts].sort((a, b) => b[1] - a[1])) tagSelect.append(h("option", { value: t, selected: t === tag }, `${t}（${c}）`));
      if (!counts.has(tag)) tag = "";
    }

    function draw() {
      const b = data.boards[board];
      const s = b.summary;
      clear(summary).append(
        ui.kpi("榜单日期", fmt.shortDate(b.date), b.prev_date ? `对比 ${fmt.shortDate(b.prev_date)}` : "第一期，没有对比"),
        ui.kpi("新上榜 / 回榜 / 掉榜", `${s.new_entries} / ${s.back_entries} / ${s.dropped}`),
        ui.kpi("新剧数", String(s.new_dramas), s.median_age !== null ? `上线天数中位数 ${s.median_age} 天` : null),
        ui.kpi("热门题材", s.top_tags.slice(0, 3).join("、") || "—", null, { small: true }),
      );
      let rows = b.rows;
      if (query) rows = rows.filter((r) => (r.title || "").includes(query));
      if (tag) rows = rows.filter((r) => (r.tags || []).includes(tag));
      if (onlyNew) rows = rows.filter((r) => r.is_new);
      clear(body).append(ui.card(`${b.label} · ${rows.length} 部`, null, ui.table([
        { key: "rank", label: "名次", num: true, render: (r) => h("span", { class: "rank" }, r.rank) },
        { key: "delta", label: "变化", num: true, render: (r) => ui.delta(r.delta) },
        { key: "title", label: "剧名", render: (r) => ui.titleCell(app, r) },
        { key: "heat", label: "热度", num: true, render: (r) => fmt.count(r.heat) },
        { key: "d_heat", label: "热度日增", num: true, render: (r) => ui.signedCount(r.d_heat) },
        { key: "fav", label: "收藏", num: true, render: (r) => fmt.count(r.fav) },
        { key: "d_fav", label: "收藏日增", num: true, render: (r) => ui.signedCount(r.d_fav) },
        { key: "rating", label: "评分", num: true, render: (r) => fmt.rating(r.rating) },
        { key: "streak", label: "连续在榜", num: true, title: "连续在榜的期数", render: (r) => `${r.streak} 期` },
        { key: "best", label: "最好名次", num: true },
        { key: "age_days", label: "上线天数", num: true, render: (r) => fmt.days(r.age_days) },
        { key: "episodes", label: "集数", num: true },
        { key: "tags", label: "题材", sortable: false, render: (r) => ui.tagChips(r.tags, (t) => { tag = t; fillTags(); app.setParams({ tag: t }); draw(); }) },
      ], rows, { sortKey: "rank", sortDir: "asc", emptyText: "没有符合条件的剧" })));
      if (b.dropped.length) {
        body.append(h("div", { class: "section" }, ui.card(`今日掉榜 · ${b.dropped.length} 部`, "上一期在榜、今天不在榜", ui.table([
          { key: "last_rank", label: "上期名次", num: true },
          { key: "title", label: "剧名", render: (r) => ui.dramaLink(app, r) },
        ], b.dropped, { sortKey: "last_rank" }))));
      }
    }
    fillTags();
    draw();
  },
};
