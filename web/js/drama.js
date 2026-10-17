// 剧集详情抽屉：基本信息 + 热度、收藏、名次走势（分开画，不共用纵轴）。

import { h, clear } from "./lib/dom.js";
import * as fmt from "./lib/format.js";
import * as ui from "./lib/ui.js";
import { lineChart } from "./lib/charts.js";
import { icon } from "./lib/icons.js";

let current = null;
let appRef = null;
let lastFocus = null;

export function closeDrama() {
  const drawer = document.getElementById("drawer");
  if (drawer.hidden) return;
  drawer.hidden = true;
  document.getElementById("drawer-backdrop").hidden = true;
  current = null;
  appRef?.setParams({ drama: null });
  lastFocus?.focus?.();
}

function metaItem(label, value) {
  return h("div", {}, h("dt", {}, label), h("dd", {}, value ?? "—"));
}

export async function openDrama(app, id) {
  appRef = app;
  current = id;
  lastFocus = document.activeElement;
  const drawer = document.getElementById("drawer");
  const body = document.getElementById("drawer-body");
  const title = document.getElementById("drawer-title");
  drawer.hidden = false;
  document.getElementById("drawer-backdrop").hidden = false;
  title.textContent = "加载中…";
  clear(body);
  app.setParams({ drama: id });
  document.getElementById("drawer-close").focus();

  let rec;
  try {
    rec = await app.data.drama(id);
  } catch (err) {
    title.textContent = "没有找到这部剧";
    body.append(ui.empty(`读取失败：${err.message}`));
    return;
  }
  if (current !== id) return;
  title.textContent = rec.title;
  const meta = rec.meta || {};
  const latest = rec.latest || {};
  const last = rec.points[rec.points.length - 1] || {};
  const ranks = Object.entries(last.ranks || {}).map(([b, r]) => `${app.boardLabel(b)}第 ${r}`).join("、") || "今天不在榜";
  const best = Object.entries(rec.best_ranks || {}).map(([b, r]) => `${app.boardLabel(b)}第 ${r}`).join("、") || "—";
  const adaptation = meta.adaptation ? `${meta.adaptation.platform}《${meta.adaptation.work}》${meta.adaptation.author ? "，" + meta.adaptation.author : ""}` : "未注明";

  body.append(
    h("div", { class: "tags" }, latest.kind ? ui.kindBadge(latest.kind) : null, ui.tagChips(meta.tags), latest.is_new ? h("span", { class: "chip fresh" }, "新剧") : null),
    h("dl", { class: "meta-list" },
      metaItem("今天名次", ranks),
      metaItem("历史最好", best),
      metaItem("热度", fmt.count(last.heat)),
      metaItem("热度日增", fmt.count(latest.d_heat, { signed: true })),
      metaItem("收藏", fmt.count(last.fav)),
      metaItem("收藏日增", fmt.count(latest.d_fav, { signed: true })),
      metaItem("点赞", fmt.count(last.like)),
      metaItem("评分", last.rating ? `${fmt.rating(last.rating)}（${fmt.count(last.rating_count)} 人）` : "—"),
      metaItem("评论", fmt.count(last.review_count)),
      metaItem("集数", meta.episodes ? `${meta.episodes} 集` : "—"),
      metaItem("上线日期", meta.first_visible ? `${meta.first_visible}（${latest.age_days ?? "?"} 天）` : "—"),
      metaItem("改编来源", adaptation),
      metaItem("首次采集到", meta.first_seen),
      metaItem("演员", (meta.cast || []).join("、") || "—"),
    ),
    rec.url ? h("p", {}, h("a", { class: "ext-link", href: rec.url, target: "_blank", rel: "noopener" }, "在官网查看", icon("external", { size: 16 }))) : null,
    meta.synopsis ? h("p", { class: "synopsis" }, meta.synopsis) : null,
  );

  if (rec.points.length < 2) {
    body.append(ui.notice("目前只有 1 天的数据，走势图从第二天起显示。"));
    return;
  }
  const heatEl = h("div", { class: "chart short" });
  const favEl = h("div", { class: "chart short" });
  const rankEl = h("div", { class: "chart short" });
  body.append(ui.card("热度", null, heatEl), h("div", { class: "section" }, ui.card("收藏", null, favEl)), h("div", { class: "section" }, ui.card("名次", "纵轴倒置：越靠上名次越好", rankEl)));
  lineChart(heatEl, [{ name: "热度", points: rec.points.filter((p) => p.heat != null).map((p) => [p.date, p.heat]) }]);
  lineChart(favEl, [{ name: "收藏", points: rec.points.filter((p) => p.fav != null).map((p) => [p.date, p.fav]) }]);
  const boards = Object.keys(app.source.boards || {});
  const rankSeries = boards
    .map((b, i) => ({ name: app.boardLabel(b), slot: i, points: rec.points.filter((p) => p.ranks?.[b]).map((p) => [p.date, p.ranks[b]]) }))
    .filter((s) => s.points.length);
  if (rankSeries.length) lineChart(rankEl, rankSeries, { inverse: true, yMin: 1, valueFormat: (v) => `第 ${v} 名`, axisFormat: (v) => String(v) });
  else rankEl.replaceWith(ui.empty("采集期间没上过榜"));

  const rows = rec.points.slice().reverse();
  body.append(h("details", { class: "datatable section" }, h("summary", {}, "查看每日数据表"), ui.table([
    { key: "date", label: "日期" },
    { key: "heat", label: "热度", num: true, render: (r) => fmt.count(r.heat) },
    { key: "fav", label: "收藏", num: true, render: (r) => fmt.count(r.fav) },
    { key: "like", label: "点赞", num: true, render: (r) => fmt.count(r.like) },
    { key: "review_count", label: "评论", num: true, render: (r) => fmt.count(r.review_count) },
    ...boards.map((b) => ({ key: `rank_${b}`, label: app.boardLabel(b), num: true, value: (r) => r.ranks?.[b] ?? null })),
  ], rows)));
}
