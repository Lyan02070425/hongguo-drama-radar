// 潜力新剧：新剧和新上榜的剧按潜力分排序，并列出每项分数的来源。

import { h } from "../lib/dom.js";
import * as fmt from "../lib/format.js";
import * as ui from "../lib/ui.js";

const COMP_LABEL = { fav_growth: "收藏日增", heat_growth_rate: "热度增长率", rank_climb: "名次上升", rating: "评分" };

export default {
  id: "potential",
  title: "潜力新剧",
  async render(root, app) {
    const data = await app.data.get("potential");
    const weights = Object.entries(data.weights).map(([k, w]) => `${COMP_LABEL[k]} ${Math.round(w * 100)}%`).join(" · ");
    root.append(ui.pageHead("潜力新剧", `候选：上线 ${data.max_age_days} 天内或第一次上榜的剧，共 ${data.candidates} 部。`));
    root.append(ui.notice(`潜力分 = 各项指标在候选剧里的百分位加权平均（0–100）。权重：${weights}。某项没有数据时不参与计算，权重分给其余几项${data.components_available.length < 4 ? `；目前可用的只有：${data.components_available.map((c) => COMP_LABEL[c]).join("、")}` : ""}。这是透明的经验规则，不是预测模型，权重可在 config.toml 里调。`));
    const comp = (r, c) => {
      const p = r.components?.[c];
      return p ? `${Math.round(p.pct * 100)}` : "—";
    };
    root.append(ui.card(null, null, ui.table([
      { key: "title", label: "剧名", render: (r) => ui.titleCell(app, r) },
      { key: "score", label: "潜力分", num: true, render: (r) => ui.scoreBar(r.score) },
      { key: "reasons", label: "主要理由", sortable: false, render: (r) => r.reasons.join("；") },
      { key: "d_fav", label: "收藏日增", num: true, render: (r) => ui.signedCount(r.d_fav) },
      { key: "r_heat", label: "热度增长率", num: true, render: (r) => h("span", { class: fmt.trendClass(r.r_heat) }, fmt.pct(r.r_heat, 1, { signed: true })) },
      { key: "rating", label: "评分", num: true, render: (r) => fmt.rating(r.rating) },
      { key: "best_rank", label: "最好名次", num: true, value: (r) => Math.min(...Object.values(r.ranks || {})), render: (r) => Object.entries(r.ranks || {}).map(([b, v]) => `${app.boardLabel(b)} ${v}`).join(" · ") },
      { key: "age_days", label: "上线天数", num: true, render: (r) => fmt.days(r.age_days) },
      { key: "pct", label: "分项百分位", sortable: false, title: "收藏 / 热度增速 / 名次 / 评分", render: (r) => ["fav_growth", "heat_growth_rate", "rank_climb", "rating"].map((c) => comp(r, c)).join(" / ") },
      { key: "tags", label: "题材", sortable: false, render: (r) => ui.tagChips(r.tags) },
    ], data.items, { sortKey: "score", sortDir: "desc" })));
  },
};
