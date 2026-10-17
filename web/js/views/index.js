// 页面注册表。新增页面：写一个模块导出 { id, title, render(root, app) }，加到下面的列表里。

import overview from "./overview.js";
import boards from "./boards.js";
import movers from "./movers.js";
import potential from "./potential.js";
import tags from "./tags.js";
import structure from "./structure.js";
import search from "./search.js";
import downloads from "./downloads.js";

export const VIEWS = [overview, boards, movers, potential, tags, structure, search, downloads];
