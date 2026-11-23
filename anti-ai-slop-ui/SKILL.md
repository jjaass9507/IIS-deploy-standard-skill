---
name: anti-ai-slop-ui
description: 統整自 GitHub 六大去 AI Slop 前端設計 Skills（JCarterJohnson/vibecoded-design-tells、Krirox/anti-ai-slop-skills、Ilm-Alan/frontend-design、wjgoarxiv/my-frontend-design-skill、Junaid-PK/frontend-design-skill、aref-vc/tufte-claude-skill）並內建 Platform Hub 定案之「Editorial Chapter Spread & Multi-Layer Ceramic Glaze Craft System」完整 Style Seed。用於偵測並消除網頁介面、企業入口網、Dashboard 與管理後台中的第一代／第二代 AI Slop 預設感，提供可直接複用的 Light/Dark 礦物紙面與玄武岩 CSS Token、七組陶瓷釉色、非對稱章節跨頁版型、48×48 四層自製 SVG 徽章規範、Tufte 例外回報帳本與靜態掃描稽核流程。只要是在設計或重構網頁前端 UI、調整配色字體版型、改善管理後台視覺、消除 AI 模板感或執行前端去 Slop 稽核時，都應使用這個 skill。
---

# Anti-AI-Slop UI 設計規範與 Platform Hub Style Seed（v2.0）

本 Skill 結合 GitHub 上 6 個代表性去 AI Slop 開源規範，並收錄經過實戰打磨且通過零違規掃描的 **Platform Hub Style Seed（Editorial Chapter Spread & Multi-Layer Ceramic Glaze Craft System）**，可直接套用至任何企業入口網、內部系統、資料目錄或管理後台。

### 方法論來源（GitHub 6 大 Skills）
1. **[`JCarterJohnson/vibecoded-design-tells`](https://github.com/JCarterJohnson/vibecoded-design-tells)**：基於 47 個 Subreddit、320 萬篇貼文統計之 12 大 AI 視覺破綻與自動掃描器 `devibe_scan.py`。
2. **[`Krirox/anti-ai-slop-skills`](https://github.com/Krirox/anti-ai-slop-skills)**：Deliberate-Violation Playbook（刻意打破 AI 預設對照表）、禁用空洞行銷文案與完整狀態覆蓋。
3. **[`Ilm-Alan/frontend-design`](https://github.com/Ilm-Alan/frontend-design)**：明確視覺錨點承諾，嚴格鎖定 CSS Token，禁止混搭與虛假英文大寫裝飾副標。
4. **[`wjgoarxiv/my-frontend-design-skill`](https://github.com/wjgoarxiv/my-frontend-design-skill)**：20 點 Anti-Slop 檢核表與靜態檢查工具 `slop_checker.py`。
5. **[`Junaid-PK/frontend-design-skill`](https://github.com/Junaid-PK/frontend-design-skill)**：克制、高可讀性的生產級介面——色彩只服務語意、狀態與明確焦點。
6. **[`aref-vc/tufte-claude-skill`](https://github.com/aref-vc/tufte-claude-skill)**：Edward Tufte 高資料墨水比（Data-Ink Ratio）與例外回報（Exception Reporting），廢除無脈絡的 4 格巨型 KPI 數字卡。

---

## 一、核心認知：同時避開「兩代 AI Slop 預設陷阱」

模型在沒有明確設計約束時，會自動收斂到訓練資料的平均值：

- **第一代 AI Slop（2024–2025 預設）**：
  - 藍紫漸層（`#6366f1`、`#8b5cf6`）、Tailwind 預設藍（`#3b82f6`、`#2563eb`）、霓虹文字漸層（`background-clip: text`）。
  - 滿版膠囊圓角（`border-radius: 999px` / `9999px`）、對稱三欄浮動卡片海（每張卡都有相同「開啟系統」藍色 CTA 按鈕）。
  - 制式左欄深色 Sidebar ＋ 頂部 4 張大號 KPI 數字卡骨架。
  - 無腦使用 `Inter`、`Geist`、`Roboto`、`Arial`、`system-ui`，搭配隨處貼上的單線條 Lucide/Heroicons 小圖示。
- **第二代 AI Slop（2026「假裝有品味」預設 — Tell #0）**：
  - 暖米色／奶油紙背景（`#faf8f5`、`#f5f1e8`）＋襯線大標題（`Instrument Serif`、`Fraunces`、`Playfair Display`）＋鼠尾草綠（Sage Green）。用第二代模板取代第一代並不是去 Slop，只是換一套 AI 預設。

---

## 二、刻意打破預設對照表（Deliberate-Violation Playbook）

| AI Slop 預設寫法 | Platform Hub 去 Slop 設計決策（Editorial Craft System） |
|---|---|
| 制式左欄 Sidebar ＋ 頂部 4 格大號 KPI 卡 | **三段式深色建築感頁首（3-Tier Masthead）**＋**黏性水平章節導覽帶（Sticky Chapter Ribbon）**；統計數據壓縮為單行 **Tufte 狀態帳本（`.tufte-telemetry-bar`）** |
| 對稱三欄均分卡片海（Card Soup） | **非對稱雙欄章節跨頁（Asymmetric Editorial Spread）**：左側 `270px` 黏性章節海報（超大章節號 `01`–`06`＋`68×68` 領域徽章）＋右側 `minmax(410px, 1fr)` 啟動磚 |
| 每張卡片右下角塞重複的藍色「開啟系統」按鈕 | 改為 `36×36` **實體觸覺啟動鍵帽（`.tile-launch-keycap` `↗`）**，Hover 翻轉為墨黑底白箭頭；搭配全域 `/` 搜尋與 `1`–`9` 瞬開快捷鍵 |
| Tailwind 預設藍 `#3b82f6` 或紫 `#6366f1`；或暖米色＋鼠尾草綠 | 淺色採用**礦物展覽紙（`#f1f2ed`）＋木炭墨黑（`#14171a`）**、深色採用**深玄武岩（`#0b0d10`）**；主動作採**群青鈷藍（`#164e78`）**＋**朱砂紅信號色（`#d14828`）** |
| 到處貼 1px 單線條 Lucide 通用小圖示 | 關鍵領域與系統改用**原創 `48×48` 四層幾何／等距雙色 SVG 徽章**（底板、中調切面、精密線條、互補 `.svg-signal` 信號點），配 7 組低彩度礦物陶瓷釉色 |
| 所有系統都掛一顆綠色大膠囊「正常運行」 | **Tufte 例外回報（Quiet Normal / Loud Exception）**：正常狀態僅顯示 `7px` 安靜綠點；只有「維護中」或「異常中斷」才展開明確的語意警示條 |
| 到處都是 `border-radius: 999px` 膠囊 | 嚴格鎖定建築感階梯圓角：`4px` / `7px` / `10px` / `13px`，**禁用 `999px`/`9999px`**（僅 `7px` 狀態圓點使用 `50%`） |
| 預設 `Inter` / `Roboto` 或 `Instrument Serif` | 人文幾何無襯線 `Plus Jakarta Sans` + `Noto Sans TC`，搭配工程等寬 `IBM Plex Mono`（全面啟用 `font-variant-numeric: tabular-nums`） |
| 置中大標題＋空洞行銷廢話（「整合各部門…提供無縫體驗」） | **零廢話資訊標頭**：直接呈現指令列搜尋框、快捷鍵提示、真實公告與精準分類計數 |

---

## 三、Platform Hub Style Seed（可直接複製複用）

> 完整版含所有元件藍圖另存於 `references/platform-hub-styleseed.md`；16 枚原創四層 SVG 徽章完整程式碼收錄於 `assets/bespoke-emblems.js`。

### 3.1 完整 CSS Design Tokens（Light：礦物展覽紙 / Dark：深玄武岩）

```css
:root {
  /* Light Mode: Mineral Gallery Paper & Charcoal Ink */
  --bg-canvas: #f1f2ed;
  --bg-surface: #ffffff;
  --bg-surface-hover: #fcfcfa;
  --bg-surface-subtle: #e8eae3;
  --bg-surface-muted: #dfe2d9;
  --bg-header: #12161b;
  --bg-ribbon: #191f26;
  --bg-modal-backdrop: rgba(15, 19, 24, 0.62);

  /* Ink Hierarchy */
  --text-primary: #14171a;
  --text-secondary: #394048;
  --text-muted: #616973;
  --text-faint: #8c949e;

  /* Structural Rules & Borders */
  --rule-color: #d5d8ce;
  --rule-strong: #14171a;
  --border-subtle: #d5d8ce;
  --border-strong: #aab0a3;

  /* Primary Accents: Ultramarine Cobalt & Cinnabar Vermilion */
  --brand-primary: #164e78;
  --brand-primary-hover: #0f3959;
  --brand-primary-soft: #eaf1f7;
  --brand-primary-border: #b5cde0;
  --cinnabar: #d14828;
  --gold-star: #d4820a;

  /* Exception Status Tokens */
  --status-op-dot: #159957;
  --status-maint-fg: #944600;
  --status-maint-bg: #fff6e5;
  --status-maint-border: #f2cf8d;
  --status-maint-dot: #d97706;
  --status-outage-fg: #b42318;
  --status-outage-bg: #fef1f1;
  --status-outage-border: #f5bcbc;
  --status-outage-dot: #dc2626;
  --status-build-dot: #64748b;

  /* 7 Ceramic Glaze Palettes (fg / bg / border / complementary signal) */
  --glaze-teal-fg: #0b5e58;    --glaze-teal-bg: #e6f4f1;    --glaze-teal-border: #add9d1;    --glaze-teal-signal: #d14828;
  --glaze-blue-fg: #144973;    --glaze-blue-bg: #e8f1f8;    --glaze-blue-border: #b3cee5;    --glaze-blue-signal: #d96b27;
  --glaze-cyan-fg: #0a5875;    --glaze-cyan-bg: #e6f4f9;    --glaze-cyan-border: #add7e8;    --glaze-cyan-signal: #0b8a73;
  --glaze-emerald-fg: #135c3d; --glaze-emerald-bg: #e7f4ed; --glaze-emerald-border: #afd9c2; --glaze-emerald-signal: #d4820a;
  --glaze-amber-fg: #874308;   --glaze-amber-bg: #fbf1e3;   --glaze-amber-border: #e8cba3;   --glaze-amber-signal: #c83e2b;
  --glaze-slate-fg: #2c3540;   --glaze-slate-bg: #eaedf0;   --glaze-slate-border: #c3cbd4;   --glaze-slate-signal: #164e78;
  --glaze-rose-fg: #94223c;    --glaze-rose-bg: #fae9ed;    --glaze-rose-border: #e8b7c3;    --glaze-rose-signal: #144973;

  /* Tactile Shadows */
  --shadow-tile: 0 1px 2px rgba(20, 23, 26, 0.04), 0 4px 12px -3px rgba(20, 23, 26, 0.05);
  --shadow-tile-hover: 0 10px 24px -6px rgba(20, 23, 26, 0.11), 0 2px 6px -1px rgba(20, 23, 26, 0.05);
  --shadow-modal: 0 24px 48px -12px rgba(15, 19, 24, 0.32);

  /* Typography & Radii (NO 999px) */
  --font-sans: 'Plus Jakarta Sans', 'Noto Sans TC', sans-serif;
  --font-mono: 'IBM Plex Mono', monospace;
  --radius-xs: 4px;
  --radius-sm: 7px;
  --radius-md: 10px;
  --radius-lg: 13px;
}

/* Dark Mode: Deep Basalt Obsidian */
html[data-theme="dark"] {
  --bg-canvas: #0b0d10;
  --bg-surface: #13171d;
  --bg-surface-hover: #181d25;
  --bg-surface-subtle: #1a2029;
  --bg-surface-muted: #232a36;
  --bg-header: #080a0d;
  --bg-ribbon: #0f1318;
  --bg-modal-backdrop: rgba(0, 0, 0, 0.78);

  --text-primary: #eef1f5;
  --text-secondary: #bcc4cf;
  --text-muted: #848f9e;
  --text-faint: #596370;

  --rule-color: #222934;
  --rule-strong: #eef1f5;
  --border-subtle: #222934;
  --border-strong: #374252;

  --brand-primary: #2b7ab8;
  --brand-primary-hover: #3a8ecf;
  --brand-primary-soft: rgba(43, 122, 184, 0.18);
  --brand-primary-border: rgba(58, 142, 207, 0.38);
  --cinnabar: #eb5e3c;
  --gold-star: #f59e0b;

  --status-maint-fg: #fbbf24;  --status-maint-bg: rgba(217, 119, 6, 0.16);  --status-maint-border: rgba(251, 191, 36, 0.32);
  --status-outage-fg: #f87171; --status-outage-bg: rgba(220, 38, 38, 0.16); --status-outage-border: rgba(248, 113, 113, 0.32);

  --glaze-teal-fg: #38cbbd;    --glaze-teal-bg: rgba(15, 118, 110, 0.2);   --glaze-teal-border: rgba(56, 203, 189, 0.3);   --glaze-teal-signal: #f26849;
  --glaze-blue-fg: #66b0ea;    --glaze-blue-bg: rgba(22, 78, 120, 0.25);   --glaze-blue-border: rgba(102, 176, 234, 0.32); --glaze-blue-signal: #f59e0b;
  --glaze-cyan-fg: #4ec5f1;    --glaze-cyan-bg: rgba(10, 88, 117, 0.24);   --glaze-cyan-border: rgba(78, 197, 241, 0.3);   --glaze-cyan-signal: #34d399;
  --glaze-emerald-fg: #44cf92; --glaze-emerald-bg: rgba(19, 92, 61, 0.24); --glaze-emerald-border: rgba(68, 207, 146, 0.3);--glaze-emerald-signal: #fbbf24;
  --glaze-amber-fg: #f7b955;   --glaze-amber-bg: rgba(135, 67, 8, 0.24);   --glaze-amber-border: rgba(247, 185, 85, 0.3);  --glaze-amber-signal: #f87171;
  --glaze-slate-fg: #cbd5e1;   --glaze-slate-bg: rgba(51, 65, 85, 0.28);   --glaze-slate-border: rgba(148, 163, 184, 0.28);--glaze-slate-signal: #4ec5f1;
  --glaze-rose-fg: #f47292;    --glaze-rose-bg: rgba(148, 34, 60, 0.24);   --glaze-rose-border: rgba(244, 114, 146, 0.3);  --glaze-rose-signal: #fbbf24;

  --shadow-tile: 0 2px 8px rgba(0, 0, 0, 0.3);
  --shadow-tile-hover: 0 12px 26px rgba(0, 0, 0, 0.5);
}
```

### 3.2 核心骨架與關鍵元件規則
1. **頁首（`.editorial-header`）**：深黑底（`--bg-header: #12161b`）三段結構——Utility Strip（品牌＋全域工具）→ 指令搜尋列（`/` 快捷聚焦）→ 黏性水平章節帶（`--bg-ribbon: #191f26`，頁籤帶朱砂紅等寬編號 `01`–`06`，啟用態白底黑字）。
2. **章節跨頁（`.editorial-chapter`）**：頂部 `2px solid var(--rule-strong)` 分隔；`grid-template-columns: 270px minmax(0, 1fr)`；左側 `.chapter-poster` 設 `position: sticky; top: 1.25rem`，顯示 `2.15rem` 粗體編號與 `68×68` 領域徽章；右側 `.chapter-tiles-grid` 為 `repeat(auto-fill, minmax(410px, 1fr))`。
3. **互動啟動磚（`.launch-tile`）**：`grid-template-columns: 58px minmax(0, 1fr) auto`。左為 `58×58` 陶瓷釉色徽章盒（右下掛等寬 `.tile-folio-tag`）；中為標題、狀態點、等寬代碼/環境標籤、兩行內精簡說明與雙負責人（系統／業務）標記；右為星號收藏＋右下角 `36×36` 實體觸覺鍵帽（`.tile-launch-keycap`）。
4. **Tufte 帳本與比例長條（`.tufte-telemetry-bar`）**：`grid-template-columns: repeat(4, 1fr); gap: 1px; background: var(--border-subtle)`，所有指標同列橫向對照；排行圖表使用純 CSS 行內比例長條，不引入肥大圖表框架。

### 3.3 原創 48×48 四層 SVG 徽章配方
所有核心領域與系統徽章一律採 `viewBox="0 0 48 48" fill="none"` 四層結構（16 枚現成徽章見 `assets/bespoke-emblems.js`）：
- **L1 底板**：`fill="currentColor" fill-opacity="0.10–0.14"`＋`stroke="currentColor" stroke-width="1.7–1.8"`
- **L2 中調切面**：`fill="currentColor" fill-opacity="0.22–0.30"`
- **L3 精密工程線**：`stroke="currentColor" stroke-width="1.4–2.1" stroke-linecap="round"`
- **L4 互補信號點**：`<circle ... class="svg-signal"/>`（CSS 綁定 `.svg-signal { fill: var(--emblem-signal, var(--cinnabar)); }`）

---

## 四、文案與權限視覺紀律（Copy & Role Hygiene）

1. **刪除所有無資訊量的形容詞**：若刪除一句話不減少使用者的實際決策資訊，該句即為 Slop Filler，必須刪掉。
2. **具體動詞＋真實數據**：按鈕直接寫動作結果（如「新增連結」、「匯出 JSON」、「重置變更理由」），禁用「探索更多」、「無縫整合」、「一站式賦能」等空洞用語。
3. **非管理員零管理雜訊**：一般使用者進入系統後，必須完全隱藏後台管理按鈕、分類設定入口、卡片編輯按鈕與管理用空狀態引導（不可留灰化按鈕）。
4. **元件視覺統一**：新增的任何業務元件（例如 `platform-people-access` 的人員選擇器 `PersonPicker`、在職異常警示 `查無此工號 ⚠`、使用統計與稽核日誌）皆須沿用同一組 CSS Token 與 `IBM Plex Mono` 等寬欄位對齊。

---

## 五、自動化靜態掃描與交付前檢核表

修改或完成任何前端程式碼（HTML / CSS / JS / JSX / TSX / Vue / Svelte）後，執行本 skill 內附的兩支靜態掃描腳本（只依賴 Python 3.8+ 標準函式庫），目標達成 **0 findings / 0 FAIL / 0 WARN**：

```bash
# 1. Reddit 320 萬篇實證 Vibe-coded Tells 掃描器（目標：vibe score = 0）
python3 scripts/devibe_scan.py <前端原始碼目錄或檔案>

# 2. 20 點 Anti-Slop 靜態檢查器（目標：0 FAIL, 0 WARN）
python3 scripts/slop_checker.py --verbose <HTML 或 CSS 檔案路徑>
```

兩支腳本皆支援 `--json` 輸出供 CI 整合；`devibe_scan.py` 遇蓄意設計例外可在該行加上 `unslop-ignore` 註解略過。

### 交付前 10 點快速自檢
1. 畫布與色彩：無 `#6366f1`/`#8b5cf6`/`#3b82f6`/`#2563eb`、無 `background-clip: text` 漸層字、無暖米色 `#faf8f5`＋鼠尾草綠。
2. 圓角節制：無 `999px`/`9999px` 膠囊氾濫，所有容器與標籤落在 `4px`～`13px` 階梯內。
3. 字體配對：已載入 `Plus Jakarta Sans` + `Noto Sans TC` + `IBM Plex Mono`，數字與代碼皆套用 `tabular-nums`，未落回 `Inter`/`Roboto`/`Instrument Serif`。
4. 骨架結構：非制式左欄 Sidebar ＋ 4 張大 KPI 卡；採用深色頁首＋章節導覽＋非對稱跨頁或單行 Tufte 帳本。
5. 例外回報：正常狀態保持安靜，異常（維護／中斷／查無工號）明確高亮。
6. 動作呈現：無重複滿版藍色 CTA 按鈕，改用觸覺鍵帽（`↗`）或簡潔工具列動作。
7. 圖示工藝：核心領域與系統圖示符合 `48×48` 四層結構與 `.svg-signal` 互補信號點。
8. 雙色模式：Light（礦物展覽紙）與 Dark（深玄武岩）皆定義完整對比度 Token，無寫死白底或黑字。
9. 權限潔癖：非管理員看不到任何管理功能入口與編輯按鈕。
10. 零廢話文案：標題、副標、空狀態與按鈕皆為具體資訊與明確動詞。

---

## 檔案

```text
anti-ai-slop-ui/
├─ SKILL.md                             核心規範、對照表、CSS Token 與 10 點自檢（先讀這份）
├─ references/
│  └─ platform-hub-styleseed.md         完整 Style Seed、版面建築藍圖與四層 SVG 規格
├─ scripts/
│  ├─ devibe_scan.py                    12 大 AI 視覺破綻目錄掃描器（Python 標準函式庫）
│  └─ slop_checker.py                   HTML/CSS Anti-Slop 靜態檢查器（Python 標準函式庫）
└─ assets/
   ├─ bespoke-emblems.js                16 枚原創 48×48 四層陶瓷釉色 SVG 徽章（可直接複製引用）
   └─ tests/
      └─ test_scanners.py               兩支掃描腳本的自測套件
```
