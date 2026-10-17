// ECharts 封装：颜色取自 CSS 变量（深浅色各自一套），切换主题、改变尺寸时自动重绘。
// 规则：分类色按固定顺序分配、最多 8 条；只用一根纵轴；细线、发丝网格；悬停有十字线和提示。

import { h, escapeHtml } from "./dom.js";
import * as fmt from "./format.js";

const live = new Set();
const resizer = new ResizeObserver((entries) => {
  for (const entry of entries) {
    for (const item of live) if (item.el === entry.target) item.chart?.resize();
  }
});

function css(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export function palette() {
  return [1, 2, 3, 4, 5, 6, 7, 8].map((i) => css(`--s${i}`));
}

function tokens() {
  return {
    ink: css("--ink"), ink2: css("--ink-2"), muted: css("--muted"), grid: css("--grid"),
    axis: css("--axis"), surface: css("--surface"), font: css("--font"), accent: css("--s1"),
  };
}

function waitForEcharts() {
  return new Promise((resolve) => {
    if (window.echarts) return resolve(window.echarts);
    const started = Date.now();
    const timer = setInterval(() => {
      if (window.echarts || Date.now() - started > 10000) {
        clearInterval(timer);
        resolve(window.echarts || null);
      }
    }, 50);
  });
}

function mount(el, build) {
  const item = { el, build, chart: null };
  live.add(item);
  waitForEcharts().then((echarts) => {
    if (!live.has(item)) return;
    if (!echarts) {
      el.replaceWith(h("p", { class: "empty" }, "图表库没有加载出来（可能是网络问题），可以展开下方的数据表查看。"));
      return;
    }
    item.chart = echarts.init(el, null, { renderer: "svg" });
    item.chart.setOption(build(tokens()));
    resizer.observe(el);
  });
  return item;
}

export function disposeAll() {
  for (const item of live) {
    resizer.unobserve(item.el);
    item.chart?.dispose();
  }
  live.clear();
}

export function rerenderAll() {
  const t = tokens();
  for (const item of live) {
    if (!item.chart) continue;
    item.chart.clear();
    item.chart.setOption(item.build(t));
  }
}

function baseOption(t) {
  return {
    textStyle: { fontFamily: t.font, color: t.ink2 },
    grid: { left: 8, right: 16, top: 16, bottom: 8, containLabel: true },
    animationDuration: 250,
    tooltip: {
      backgroundColor: t.surface,
      borderColor: t.axis,
      borderWidth: 1,
      textStyle: { color: t.ink, fontFamily: t.font, fontSize: 12 },
      extraCssText: "box-shadow:0 4px 14px rgba(0,0,0,.12);border-radius:8px;",
      confine: true,
    },
  };
}

function lineKey(color) {
  return `<span style="display:inline-block;width:14px;height:2px;border-radius:1px;background:${color};vertical-align:middle;margin-right:8px"></span>`;
}

/**
 * 折线图。series: [{ name, slot?, points: [[date, value], ...] }]（最多 8 条）
 * options: valueFormat(v)、axisFormat(v)、inverse（名次图纵轴倒置）、yMin
 */
export function lineChart(el, series, options = {}) {
  const list = series.slice(0, 8);
  const dates = [...new Set(list.flatMap((s) => s.points.map((p) => p[0])))].sort();
  const valueFormat = options.valueFormat || ((v) => fmt.count(v));
  const direct = list.length > 1 && list.length <= 4;
  return mount(el, (t) => {
    const colors = palette();
    const option = baseOption(t);
    option.color = list.map((s, i) => colors[(s.slot ?? i) % 8]);
    if (list.length > 1) {
      option.legend = {
        top: 0, left: 0, type: "scroll", icon: "rect", itemWidth: 14, itemHeight: 2,
        textStyle: { color: t.ink2 }, pageTextStyle: { color: t.muted },
      };
      option.grid.top = 36;
    }
    if (direct) option.grid.right = 72;
    option.tooltip = {
      ...option.tooltip,
      trigger: "axis",
      axisPointer: { type: "line", lineStyle: { color: t.axis, width: 1 } },
      formatter: (params) => {
        const rows = params.filter((p) => p.value !== null && p.value !== undefined)
          .sort((a, b) => (options.inverse ? a.value - b.value : b.value - a.value))
          .map((p) => `<div style="display:flex;align-items:center;gap:4px;margin-top:2px">${lineKey(p.color)}<b>${escapeHtml(valueFormat(p.value))}</b><span style="color:${t.muted};margin-left:6px">${escapeHtml(p.seriesName)}</span></div>`);
        return `<div style="color:${t.muted};margin-bottom:2px">${escapeHtml(fmt.shortDate(params[0]?.axisValue))}</div>${rows.join("") || "无数据"}`;
      },
    };
    option.xAxis = {
      type: "category", data: dates, boundaryGap: dates.length < 3,
      axisLine: { lineStyle: { color: t.axis } }, axisTick: { show: false },
      axisLabel: { color: t.muted, formatter: (d) => fmt.shortDate(d), hideOverlap: true, alignMinLabel: "left", alignMaxLabel: "right" },
    };
    option.yAxis = {
      type: "value", inverse: !!options.inverse, min: options.yMin, scale: options.yMin === undefined,
      splitLine: { lineStyle: { color: t.grid, width: 1 } },
      axisLabel: { color: t.muted, formatter: (v) => (options.axisFormat || valueFormat)(v) },
    };
    option.series = list.map((s) => {
      const map = new Map(s.points);
      return {
        name: s.name, type: "line", data: dates.map((d) => (map.has(d) ? map.get(d) : null)),
        showSymbol: dates.length <= 3, symbol: "circle", symbolSize: 8,
        lineStyle: { width: 2 }, emphasis: { focus: "series", lineStyle: { width: 2.5 } },
        endLabel: direct ? { show: true, formatter: s.name, color: t.ink2, distance: 6 } : undefined,
        labelLayout: direct ? { moveOverlap: "shiftY" } : undefined,
      };
    });
    return option;
  });
}

/**
 * 条形图（单系列，一种颜色）。items: [{ label, value }]
 * options: valueFormat、axisFormat、horizontal（默认 true）、slot
 */
export function barChart(el, items, options = {}) {
  const horizontal = options.horizontal !== false;
  const valueFormat = options.valueFormat || ((v) => fmt.count(v));
  if (horizontal) el.style.height = `${Math.max(200, items.length * 28 + 24)}px`;
  return mount(el, (t) => {
    const color = palette()[(options.slot ?? 0) % 8];
    const option = baseOption(t);
    option.grid.right = horizontal ? 64 : 16;
    option.tooltip = {
      ...option.tooltip,
      trigger: "item",
      formatter: (p) => `<div style="color:${t.muted}">${escapeHtml(p.name)}</div><b>${escapeHtml(valueFormat(p.value))}</b>`,
    };
    const cat = {
      type: "category", data: items.map((d) => d.label), inverse: horizontal,
      axisLine: { lineStyle: { color: t.axis } }, axisTick: { show: false },
      axisLabel: { color: t.ink2, width: 90, overflow: "truncate", interval: 0 },
    };
    const val = {
      type: "value", splitLine: { lineStyle: { color: t.grid } },
      axisLabel: { color: t.muted, formatter: (v) => (options.axisFormat || valueFormat)(v), hideOverlap: true },
      splitNumber: el.clientWidth && el.clientWidth < 480 ? 3 : 5,
    };
    option.xAxis = horizontal ? val : cat;
    option.yAxis = horizontal ? cat : val;
    option.series = [{
      type: "bar", data: items.map((d) => d.value), barMaxWidth: 16, barCategoryGap: "35%",
      itemStyle: { color, borderRadius: horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0] },
      emphasis: { itemStyle: { opacity: 0.85 } },
      label: { show: true, position: horizontal ? "right" : "top", color: t.ink2, formatter: (p) => valueFormat(p.value) },
    }];
    return option;
  });
}
