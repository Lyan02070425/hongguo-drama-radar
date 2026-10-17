// 数字与日期格式。

export function count(value, { signed = false } = {}) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  let sign = "";
  let v = value;
  if (signed) {
    sign = v > 0 ? "+" : v < 0 ? "−" : "";
    v = Math.abs(v);
  }
  let text;
  if (Math.abs(v) >= 1e8) text = (v / 1e8).toFixed(2).replace(/\.?0+$/, "") + "亿";
  else if (Math.abs(v) >= 1e4) text = (v / 1e4).toFixed(Math.abs(v) >= 1e6 ? 0 : 1).replace(/\.0$/, "") + "万";
  else text = Math.round(v).toLocaleString("zh-CN");
  return sign + text;
}

export function pct(value, digits = 1, { signed = false } = {}) {
  if (value === null || value === undefined) return "—";
  const text = (Math.abs(value) * 100).toFixed(digits) + "%";
  if (!signed) return (value < 0 ? "−" : "") + text;
  return (value > 0 ? "+" : value < 0 ? "−" : "") + text;
}

export function pp(value) {
  if (value === null || value === undefined) return "—";
  return (value > 0 ? "+" : value < 0 ? "−" : "") + Math.abs(value).toFixed(1) + " pp";
}

export function rating(value) {
  return value === null || value === undefined ? "—" : Number(value).toFixed(1);
}

export function days(value) {
  return value === null || value === undefined ? "—" : `${value} 天`;
}

export function shortDate(iso) {
  if (!iso) return "—";
  const [, m, d] = iso.split("-");
  return `${Number(m)}月${Number(d)}日`;
}

export function trendClass(value) {
  if (value === null || value === undefined || value === 0) return "flat";
  return value > 0 ? "up" : "down";
}
