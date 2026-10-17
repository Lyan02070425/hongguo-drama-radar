// 内容结构：剧龄分布、集数分布、改编来源、上线到上榜要多久。

import { h, clear } from "../lib/dom.js";
import * as fmt from "../lib/format.js";
import * as ui from "../lib/ui.js";
import { barChart, disposeAll } from "../lib/charts.js";

export default {
  id: "structure",
  title: "内容结构",
  icon: "structure",
  async render(root, app) {
    const data = await app.data.get("lifecycle");
    const boardIds = Object.keys(data.boards);
    let board = boardIds.includes(app.params.get("board")) ? app.params.get("board") : boardIds[0];
    root.append(ui.pageHead("内容结构", "榜上都是什么样的剧：上线多久、多少集、是不是小说改编。"));
    const controls = h("div", { class: "controls" });
    const body = h("div");
    root.append(controls, body);
    controls.append(ui.segmented(boardIds.map((b) => ({ value: b, label: data.boards[b].label })), board, (v) => { board = v; app.setParams({ board: v }); draw(); }, "选择榜单"));

    function draw() {
      disposeAll();
      clear(body);
      const b = data.boards[board];
      const ageEl = h("div", { class: "chart short" });
      const epEl = h("div", { class: "chart short" });
      const bucketCols = [
        { key: "bucket", label: "区间", sortable: false },
        { key: "count", label: "部数", num: true },
        { key: "heat_share", label: "热度占比", num: true, render: (r) => fmt.pct(r.heat_share) },
      ];
      body.append(h("div", { class: "grid cols-2" },
        ui.card("上线多久了", "按上线天数分组的部数（悬停看热度占比）", ageEl, h("details", { class: "datatable" }, h("summary", {}, "查看数据表"), ui.table(bucketCols, b.age))),
        ui.card("多少集", "按集数分组的部数", epEl, h("details", { class: "datatable" }, h("summary", {}, "查看数据表"), ui.table(bucketCols, b.episodes))),
      ));
      barChart(ageEl, b.age.map((x) => ({ label: x.bucket, value: x.count })), { horizontal: false, valueFormat: (v) => `${v} 部` });
      barChart(epEl, b.episodes.map((x) => ({ label: x.bucket, value: x.count })), { horizontal: false, valueFormat: (v) => `${v} 部` });

      const adaptedHere = data.adapted;
      body.append(h("div", { class: "grid cols-2 section" },
        ui.card("改编来源", `${b.label}里，简介中注明「改编自…」的剧`, ui.table([
          { key: "platform", label: "来源", sortable: false },
          { key: "count", label: "部数", num: true },
        ], b.adaptation, { sortKey: "count", sortDir: "desc" })),
        ui.card("上线到首次上榜", data.time_to_board.count ? `统计 ${data.time_to_board.count} 部，中位数 ${data.time_to_board.median_days} 天` : "采集第一天就在榜的剧不统计，需要积累几天", ui.table([
          { key: "title", label: "剧名", render: (r) => ui.dramaLink(app, r) },
          { key: "first_visible", label: "上线", render: (r) => fmt.shortDate(r.first_visible) },
          { key: "first_on", label: "首次上榜", render: (r) => fmt.shortDate(r.first_on) },
          { key: "days", label: "用时", num: true, render: (r) => fmt.days(r.days) },
        ], data.time_to_board.recent, { limit: 10, emptyText: "暂无" })),
      ));
      body.append(h("div", { class: "section" }, ui.card(`注明改编的在榜剧 · ${adaptedHere.length} 部`, "所有榜去重，按最好名次排序", ui.table([
        { key: "best_rank", label: "最好名次", num: true },
        { key: "title", label: "剧名", render: (r) => ui.dramaLink(app, r) },
        { key: "platform", label: "来源" },
        { key: "work", label: "原作", render: (r) => `《${r.work}》` },
        { key: "author", label: "作者" },
        { key: "heat", label: "热度", num: true, render: (r) => fmt.count(r.heat) },
      ], adaptedHere, { sortKey: "best_rank", limit: 20 }))));
    }
    draw();
  },
};
