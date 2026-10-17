// 剧集库：采集到的所有剧，包括已经掉榜的，可按剧名、题材搜索。

import { h, clear } from "../lib/dom.js";
import * as fmt from "../lib/format.js";
import * as ui from "../lib/ui.js";

export default {
  id: "search",
  title: "剧集库",
  async render(root, app) {
    const data = await app.data.get("dramas");
    let query = app.params.get("q") || "";
    root.append(ui.pageHead("剧集库", `采集以来出现过的 ${data.count} 部剧，包括已经掉榜的。可以搜剧名或题材。`));
    const input = h("input", { type: "search", placeholder: "剧名或题材", value: query, "aria-label": "搜索", style: { width: "min(100%, 320px)" } });
    const body = h("div", { class: "section" });
    root.append(h("div", { class: "controls" }, input), body);
    input.addEventListener("input", () => { query = input.value.trim(); app.setParams({ q: query }); draw(); });

    function draw() {
      const q = query.toLowerCase();
      const rows = q ? data.items.filter((r) => (r.title || "").toLowerCase().includes(q) || (r.tags || []).some((t) => t.includes(query))) : data.items;
      clear(body).append(ui.card(`${rows.length} 部`, null, ui.table([
        { key: "title", label: "剧名", render: (r) => ui.dramaLink(app, r) },
        { key: "ranks", label: "今天名次", sortable: false, render: (r) => Object.entries(r.ranks || {}).map(([b, v]) => `${app.boardLabel(b)} ${v}`).join(" · ") || "不在榜" },
        { key: "best", label: "历史最好", num: true },
        { key: "heat", label: "最近热度", num: true, render: (r) => fmt.count(r.heat) },
        { key: "last_seen", label: "最后出现" },
        { key: "tags", label: "题材", sortable: false, render: (r) => ui.tagChips(r.tags) },
      ], rows, { limit: 100 })));
    }
    draw();
  },
};
