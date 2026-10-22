// 给 @deepseek-ai/dsh-app-boot 打补丁：ctx.get("hmr") 在插件刚创建的同一轮拿不到（见 danielpang/bento#195），
// 改成最多轮询 1 秒。可以反复跑；已经打过就跳过；找不到原句就报错退出（说明 dsh 版本变了，要人看）。
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const file = process.argv[2] || join(here, "node_modules/@deepseek-ai/dsh-app-boot/lib/index.js");
const MARK = "/* evo-multica:hmr-poll */";
if (!existsSync(file)) { console.error(`✗ 找不到 ${file}`); process.exit(1); }
let src = readFileSync(file, "utf8");
if (src.includes(MARK)) { console.log("✓ dsh-app-boot 已打过补丁，跳过"); process.exit(0); }
const re = /const\s+(\w+)\s*=\s*ctx\.get\(\s*["']hmr["']\s*\)\s*;/;
const m = src.match(re);
if (!m) { console.error("✗ dsh-app-boot 里没找到 ctx.get(\"hmr\")，dsh 版本可能变了，补丁没打"); process.exit(1); }
const v = m[1];
const repl = `${MARK} let ${v} = ctx.get("hmr"); if (${v} === void 0) { for (let i = 0; i < 20; i++) { await new Promise((r) => setTimeout(r, 50)); ${v} = ctx.get("hmr"); if (${v} !== void 0) break; } }`;
src = src.replace(re, repl);
writeFileSync(file, src);
console.log("✓ dsh-app-boot 补丁已打（hmr 轮询 1 秒）");
