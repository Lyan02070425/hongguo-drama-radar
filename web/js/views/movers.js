// 飙升：按不同口径排出涨得最快、跌得最快的剧。

import { h, clear } from "../lib/dom.js";
import * as fmt from "../lib/format.js";
import * as ui from "../lib/ui.js";


function valueText(list, v) {
  if (list.unit === "%") return h("span", { class: fmt.trendClass(v) }, fmt.pct(v, 1, { signed: true }));
  if (list.unit === "位") return ui.delta(v);
  if (list.unit === "名") return `第 ${v} 名`;
  return ui.signedCount(v);
}

export default {
  id: "movers",
  title: "飙升",
  icon: "movers",
  async render(root, app) {
    const data = await app.data.get("movers");
    const keys = Object.keys(data.lists);
    let key = keys.includes(app.params.get("metric")) ? app.params.get("metric") : "fav";
    let kind = app.params.get("kind") || "";

    root.append(ui.pageHead("飙升与下滑", data.prev_date ? `和 ${fmt.shortDate(data.prev_date)} 相比${data.gap > 1 ? `（间隔 ${data.gap} 天，按天平均）` : ""}。` : "目前只有一期数据，增量和名次变化从第二期起才有。"));
    const controls = h("div", { class: "controls" });
    const body = h("div");
    root.append(controls, body);
    const order = ["fav", "heat", "heat_rate", "rank_up", "new_entries", "review", "rating_count", "like", "heat_7d", "fav_7d", "heat_drop", "rank_down"].filter((k) => keys.includes(k));
    controls.append(
      ui.segmented(order.map((k) => ({ value: k, label: data.lists[k].label })), key, (v) => { key = v; app.setParams({ metric: v }); draw(); }, "排序口径"),
      ui.segmented([{ value: "", label: "全部" }, { value: "real", label: "真人" }, { value: "ai", label: "AI" }, { value: "comic", label: "漫剧" }], kind, (v) => { kind = v; app.setParams({ kind: v }); draw(); }, "剧集类型"),
    );

    function draw() {
      const list = data.lists[key];
      const rows = list.items.filter((r) => !kind || r.kind === kind).map((r, i) => ({ ...r, pos: i + 1 }));
      const boardCol = list.unit === "位" || list.unit === "名";
      clear(body).append(ui.card(list.label, list.desc, ui.table([
        { key: "pos", label: "#", num: true },
        { key: "title", label: "剧名", render: (r) => ui.titleCell(app, r) },
        { key: "value", label: list.label, num: true, render: (r) => valueText(list, r.value) },
        boardCol ? { key: "board_label", label: "所在榜", render: (r) => `${r.board_label} 第 ${r.rank}` } : { key: "rank", label: "最好名次", num: true, value: (r) => Math.min(...Object.values(r.ranks || {}), 999), render: (r) => { const v = Math.min(...Object.values(r.ranks || {})); return Number.isFinite(v) ? v : "不在榜"; } },
        { key: "heat", label: "热度", num: true, render: (r) => fmt.count(r.heat) },
        { key: "fav", label: "收藏", num: true, render: (r) => fmt.count(r.fav) },
        { key: "rating", label: "评分", num: true, render: (r) => fmt.rating(r.rating) },
        { key: "age_days", label: "上线天数", num: true, render: (r) => fmt.days(r.age_days) },
        { key: "kind", label: "类型", render: (r) => ui.kindBadge(r.kind) },
        { key: "tags", label: "题材", sortable: false, render: (r) => ui.tagChips(r.tags) },
      ], rows, { emptyText: data.prev_date ? "没有符合条件的剧" : "积累 2 天以上的数据后才有增量" })));
    }
    draw();
  },
};
