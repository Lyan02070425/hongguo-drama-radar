// 看板入口：读 manifest → 选数据源 → 按 hash 路由渲染页面。页面在 views/index.js 里注册。

import { h, clear } from "./lib/dom.js";
import { loadManifest, sourceData } from "./lib/data.js";
import * as charts from "./lib/charts.js";
import * as fmt from "./lib/format.js";
import { VIEWS } from "./views/index.js";
import { openDrama, closeDrama } from "./drama.js";
import { icon } from "./lib/icons.js";

const store = {
  get(key) { try { return localStorage.getItem(key); } catch { return null; } },
  set(key, value) { try { localStorage.setItem(key, value); } catch { /* 隐私模式下忽略 */ } },
};

const app = {
  manifest: null,
  source: null, // manifest 里的数据源条目
  data: null,   // sourceData(...)
  params: new URLSearchParams(),
  navigate(view, params = {}) {
    const qs = new URLSearchParams(params).toString();
    location.hash = `#/${view}${qs ? "?" + qs : ""}`;
  },
  setParams(params) {
    const merged = new URLSearchParams(this.params);
    for (const [k, v] of Object.entries(params)) {
      if (v === null || v === undefined || v === "") merged.delete(k);
      else merged.set(k, v);
    }
    const view = currentRoute().view;
    history.replaceState(null, "", `#/${view}${merged.toString() ? "?" + merged : ""}`);
    this.params = merged;
  },
  openDrama(id) { openDrama(app, id); },
  boardLabel(board) { return this.source?.boards?.[board] || board; },
  boardOptions() { return Object.entries(this.source?.boards || {}).map(([value, label]) => ({ value, label })); },
};

function currentRoute() {
  const raw = location.hash.replace(/^#\/?/, "");
  const [path, query] = raw.split("?");
  const view = VIEWS.find((v) => v.id === path) ? path : VIEWS[0].id;
  return { view, params: new URLSearchParams(query || "") };
}

function renderNav(active) {
  const nav = document.getElementById("nav");
  clear(nav);
  for (const v of VIEWS) {
    nav.append(h("a", { href: `#/${v.id}`, "aria-current": v.id === active ? "page" : null }, icon(v.icon || "overview"), h("span", {}, v.title)));
  }
}

async function renderStatus() {
  const el = document.getElementById("status");
  clear(el);
  if (!app.source?.latest_date) {
    el.append(h("span", { class: "pill" }, "还没有数据"));
    return;
  }
  const pill = (text, cls = "") => h("span", { class: `pill ${cls}`.trim() }, text);
  try {
    const s = await app.data.get("status");
    el.append(pill(`${s.label} · ${s.latest_date}`, "live"), pill(`已积累 ${s.history_days} 天`), pill(`追踪 ${s.tracked} 部`));
    if (s.stale) el.append(pill("官方今天未刷新", "warn"));
    if (s.error_count) el.append(pill(`${s.error_count} 个采集错误`, "warn"));
  } catch {
    el.append(pill(`${app.source.label} · ${app.source.latest_date}`, "live"));
  }
  document.getElementById("brand-sub").textContent = `${app.source.label} · 每日更新`;
  document.getElementById("footer-meta").textContent = `页面生成于 ${app.manifest.generated_at.replace("T", " ").replace("Z", " UTC")}`;
}

async function route() {
  const { view, params } = currentRoute();
  app.params = params;
  renderNav(view);
  charts.disposeAll();
  const root = document.getElementById("view");
  clear(root);
  if (!app.source?.latest_date) {
    root.append(h("p", { class: "empty" }, "还没有任何快照。运行一次采集（python -m radar run）或等待定时任务。"));
    return;
  }
  const def = VIEWS.find((v) => v.id === view);
  window.scrollTo(0, 0);
  document.title = `${def.title} · ${app.manifest.title}`;
  try {
    await def.render(root, app);
  } catch (err) {
    console.error(err);
    root.append(h("p", { class: "empty" }, `页面加载失败：${err.message}`));
  }
  const dramaId = params.get("drama");
  if (dramaId) openDrama(app, dramaId);
}

function isDark() {
  const forced = document.documentElement.dataset.theme;
  return forced ? forced === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
}

function setupTheme() {
  const btn = document.getElementById("theme-toggle");
  const saved = store.get("theme");
  if (saved) document.documentElement.dataset.theme = saved;
  const paint = () => {
    clear(btn).append(icon(isDark() ? "sun" : "moon"));
    btn.setAttribute("aria-label", isDark() ? "切换到浅色" : "切换到深色");
    btn.title = btn.getAttribute("aria-label");
  };
  paint();
  btn.addEventListener("click", () => {
    const next = isDark() ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    store.set("theme", next);
    paint();
    charts.rerenderAll();
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { paint(); charts.rerenderAll(); });
}

async function main() {
  setupTheme();
  document.getElementById("drawer-close").append(icon("close"));
  document.getElementById("drawer-close").addEventListener("click", closeDrama);
  document.getElementById("drawer-backdrop").addEventListener("click", closeDrama);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrama(); });
  try {
    app.manifest = await loadManifest();
  } catch (err) {
    clear(document.getElementById("view")).append(h("p", { class: "empty" }, `读取 data/manifest.json 失败：${err.message}`));
    return;
  }
  document.getElementById("site-title").textContent = app.manifest.title;
  const sources = app.manifest.sources || [];
  const select = document.getElementById("source-select");
  const savedSource = store.get("source");
  app.source = sources.find((s) => s.id === savedSource) || sources.find((s) => s.latest_date) || sources[0];
  if (sources.length > 1) {
    select.hidden = false;
    for (const s of sources) select.append(h("option", { value: s.id, selected: s.id === app.source.id }, s.label));
    select.addEventListener("change", () => {
      app.source = sources.find((s) => s.id === select.value);
      app.data = sourceData(app.source.id);
      store.set("source", app.source.id);
      renderStatus();
      route();
    });
  }
  app.data = sourceData(app.source.id);
  window.addEventListener("hashchange", route);
  await renderStatus();
  await route();
}

export { app, fmt };
main();
