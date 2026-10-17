// 潜力新剧：新剧和新上榜的剧按潜力分排序，可按真人 / AI / 漫剧筛选，或三类分组对比。

import { h, clear } from "../lib/dom.js";
import * as fmt from "../lib/format.js";
import * as ui from "../lib/ui.js";

const COMP_LABEL = { fav_growth: "收藏日增", heat_growth_rate: "热度增长率", rank_climb: "名次上升", rating: "评分" };
const KINDS = ["real", "ai", "comic"];

function bestRank(app, r) {
  return Object.entries(r.ranks || {}).map(([b, v]) => `${app.boardLabel(b)} ${v}`).join(" · ") || "—";
}

function groupColumn(app, kind, rows, onMore) {
  const top = rows.slice(0, 10);
  return h("section", { class: "card kind-col" },
    h("h2", {}, ui.kindBadge(kind), `潜力前 ${Math.min(10, rows.length)}`),
    h("p", { class: "sub" }, `共 ${rows.length} 部候选`),
    top.length
      ? h("ol", { class: "rank-list" }, top.map((r) => h("li", {},
          ui.rankPill(r.kind_rank),
          h("div", { class: "who" }, ui.dramaLink(app, r), h("div", { class: "meta" }, r.reasons.join("；"))),
          ui.scoreBar(r.score))))
      : ui.empty("这一类今天没有候选"),
    rows.length > 10 ? h("p", { class: "more-row" }, h("a", { href: "#", onclick: (e) => { e.preventDefault(); onMore(kind); } }, `查看全部 ${rows.length} 部 →`)) : null,
  );
}

export default {
  id: "potential",
  title: "潜力新剧",
  icon: "potential",
  async render(root, app) {
    const data = await app.data.get("potential");
    const items = data.items || [];
    const counts = data.by_kind || {};
    const modes = ["all", ...KINDS, "group"];
    let mode = modes.includes(app.params.get("kind")) ? app.params.get("kind") : "all";

    const weights = Object.entries(data.weights).map(([k, w]) => `${COMP_LABEL[k]} ${Math.round(w * 100)}%`).join(" · ");
    const skipped = data.candidates - items.length;
    root.append(ui.pageHead("潜力新剧", `候选：上线 ${data.max_age_days} 天内或第一次上榜的剧，共 ${items.length} 部参与排序${skipped > 0 ? `（另有 ${skipped} 部刚上榜、还没有评分和增量，暂不打分）` : ""}。`));
    root.append(ui.notice(`潜力分 = 各项指标在全部候选里的百分位加权平均（0–100），所以真人、AI、漫剧之间可以直接比较。权重：${weights}。某项没有数据时不参与计算${data.components_available.length < 4 ? `；目前可用：${data.components_available.map((c) => COMP_LABEL[c]).join("、")}` : ""}。这是透明的经验规则，不是预测模型，权重可在 config.toml 里调。`));

    const controls = h("div", { class: "controls" });
    const body = h("div");
    root.append(controls, body);
    const setMode = (v) => { mode = v; app.setParams({ kind: v === "all" ? null : v }); renderControls(); draw(); };
    function renderControls() {
      clear(controls).append(ui.segmented([
        { value: "all", label: "全部", count: items.length },
        ...KINDS.map((k) => ({ value: k, label: ui.KIND_LABEL[k], count: counts[k] || 0 })),
        { value: "group", label: "分组对比" },
      ], mode, setMode, "按类型查看"));
    }

    const comp = (r, c) => {
      const p = r.components?.[c];
      return p ? `${Math.round(p.pct * 100)}` : "—";
    };

    function draw() {
      clear(body);
      if (mode === "group") {
        body.append(h("div", { class: "grid cols-3" }, KINDS.map((k) => groupColumn(app, k, items.filter((r) => r.kind === k), setMode))));
        return;
      }
      const rows = mode === "all" ? items : items.filter((r) => r.kind === mode);
      const title = mode === "all" ? `全部候选 · ${rows.length} 部` : `${ui.KIND_LABEL[mode]} · ${rows.length} 部`;
      body.append(ui.card(title, mode === "all" ? "点「类型」列可以按类型排序；也可以切到上面的分组对比" : `「类内排名」是在${ui.KIND_LABEL[mode]}里的名次`, ui.table([
        { key: "pos", label: mode === "all" ? "#" : "类内排名", num: true, value: (r) => (mode === "all" ? items.indexOf(r) + 1 : r.kind_rank), render: (r) => ui.rankPill(mode === "all" ? items.indexOf(r) + 1 : r.kind_rank) },
        { key: "title", label: "剧名", render: (r) => ui.titleCell(app, r) },
        { key: "kind", label: "类型", render: (r) => ui.kindBadge(r.kind) },
        { key: "score", label: "潜力分", num: true, render: (r) => ui.scoreBar(r.score) },
        { key: "reasons", label: "主要理由", sortable: false, render: (r) => r.reasons.join("；") },
        { key: "d_fav", label: "收藏日增", num: true, render: (r) => ui.signedCount(r.d_fav) },
        { key: "r_heat", label: "热度增长率", num: true, render: (r) => h("span", { class: fmt.trendClass(r.r_heat) }, fmt.pct(r.r_heat, 1, { signed: true })) },
        { key: "rating", label: "评分", num: true, render: (r) => fmt.rating(r.rating) },
        { key: "best_rank", label: "所在榜单", num: true, value: (r) => Math.min(...Object.values(r.ranks || {})), render: (r) => bestRank(app, r) },
        { key: "age_days", label: "上线天数", num: true, render: (r) => fmt.days(r.age_days) },
        { key: "pct", label: "分项百分位", sortable: false, title: "收藏 / 热度增速 / 名次 / 评分", render: (r) => ["fav_growth", "heat_growth_rate", "rank_climb", "rating"].map((c) => comp(r, c)).join(" / ") },
        { key: "tags", label: "题材", sortable: false, render: (r) => ui.tagChips(r.tags) },
      ], rows, { sortKey: "score", sortDir: "desc", limit: 50, emptyText: "这一类今天没有候选" })));
    }
    renderControls();
    draw();
  },
};
