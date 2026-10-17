// 读取分析结果。路径全部是相对路径，部署在 GitHub Pages 的子目录下也能用。

const cache = new Map();

async function getJSON(path) {
  if (!cache.has(path)) {
    cache.set(path, fetch(path, { cache: "no-cache" }).then((res) => {
      if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
      return res.json();
    }).catch((err) => {
      cache.delete(path);
      throw err;
    }));
  }
  return cache.get(path);
}

export function loadManifest() {
  return getJSON("data/manifest.json");
}

export function sourceData(sourceId) {
  const base = `data/${encodeURIComponent(sourceId)}`;
  return {
    id: sourceId,
    base,
    get: (name) => getJSON(`${base}/${name}.json`),
    drama: (id) => getJSON(`${base}/dramas/${encodeURIComponent(id)}.json`),
    url: (relpath) => `${base}/${relpath}`,
  };
}
