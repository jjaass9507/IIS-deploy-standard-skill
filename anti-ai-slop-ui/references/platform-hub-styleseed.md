# Platform Hub Style Seed — Editorial Chapter Spread & Ceramic Glaze Craft System

本文件完整收錄 `platform-hub` 定案之視覺設計系統（Style Seed），可直接複製套用至任何企業入口網、內部工具平台、知識目錄或高密度管理後台，以徹底消除第一代（藍紫漸層／圓角膠囊／浮動卡片海）與第二代（暖米色／襯線體／鼠尾草綠）AI Slop 預設感。

---

## 1. 美學錨點（Aesthetic Commitment）

- **視覺血統**：Monocle Directories（編輯部目錄編排）× Japanese Editorial Portals（礦物紙面與明確版面節奏）× Teenage Engineering（觸覺實體鍵帽與精準工程信號點）。
- **核心設計原則**：
  1. **拒絕左欄 AI Dashboard 骨架**：以「三段式深色建築感頁首（3-Tier Architectural Masthead）」＋「黏性水平章節導覽帶（Sticky Chapter Ribbon）」取代制式側邊欄。
  2. **非對稱雙欄章節跨頁（Asymmetric Editorial Chapter Spread）**：左側 `270px` 黏性章節海報（超大章節序號 `01`–`06`＋`68×68` 領域釉色徽章）＋右側 `minmax(410px, 1fr)` 互動啟動磚，打破對稱三欄卡片海。
  3. **靜態安靜、異常高聲（Tufte Exception Reporting）**：正常運行中的系統僅以安靜的 `7px` 狀態圓點（`#159957`）標示；唯有「維護中」或「異常中斷」才展開明確的語意警示條（`.tile-exception-pill`）。
  4. **觸覺鍵帽取代重複藍色按鈕**：移除滿版重複的「開啟系統」藍色按鈕，改於啟動磚右下角配置 `36×36` 實體鍵帽（`.tile-launch-keycap` `↗`），並內建鍵盤 `/` 搜尋與 `1`–`9` 瞬開快捷鍵。
  5. **Tufte 單行狀態帳本（Inline Telemetry Ledger）**：以單行髮絲線分隔帳本列（`.tufte-telemetry-bar`）與行內 CSS 比例長條取代 4 格巨型 KPI 數字卡。
  6. **克制的陶瓷釉色＋原創 4 層 SVG 徽章**：不使用滿版彩虹粉彩卡片與單線條現成圖示庫；僅在 `58×58` 徽章容器套用低彩度礦物陶瓷釉色（7 組釉色各配對互補信號點 `.svg-signal`）。

---

## 2. 完整 CSS Design Tokens（可直接複製為 `styles.css` 基底）

```css
:root {
  /* === Light Mode: Mineral Gallery Paper & Charcoal Ink === */
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

  /* Exception Status Tokens (Quiet Normal / Loud Exception) */
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

  /* 7 Ceramic Glaze Palettes (fg / bg / border / complementary signal node) */
  --glaze-teal-fg: #0b5e58;     /* 青瓷綠 */
  --glaze-teal-bg: #e6f4f1;
  --glaze-teal-border: #add9d1;
  --glaze-teal-signal: #d14828;

  --glaze-blue-fg: #144973;     /* 群青藍 */
  --glaze-blue-bg: #e8f1f8;
  --glaze-blue-border: #b3cee5;
  --glaze-blue-signal: #d96b27;

  --glaze-cyan-fg: #0a5875;     /* 天青釉 */
  --glaze-cyan-bg: #e6f4f9;
  --glaze-cyan-border: #add7e8;
  --glaze-cyan-signal: #0b8a73;

  --glaze-emerald-fg: #135c3d;  /* 松葉綠 */
  --glaze-emerald-bg: #e7f4ed;
  --glaze-emerald-border: #afd9c2;
  --glaze-emerald-signal: #d4820a;

  --glaze-amber-fg: #874308;    /* 琥珀銅 */
  --glaze-amber-bg: #fbf1e3;
  --glaze-amber-border: #e8cba3;
  --glaze-amber-signal: #c83e2b;

  --glaze-slate-fg: #2c3540;    /* 玄武岩 */
  --glaze-slate-bg: #eaedf0;
  --glaze-slate-border: #c3cbd4;
  --glaze-slate-signal: #164e78;

  --glaze-rose-fg: #94223c;     /* 朱砂印 */
  --glaze-rose-bg: #fae9ed;
  --glaze-rose-border: #e8b7c3;
  --glaze-rose-signal: #144973;

  /* Tactile Shadows (Subtle ink-tinted elevation, never neon glow) */
  --shadow-tile: 0 1px 2px rgba(20, 23, 26, 0.04), 0 4px 12px -3px rgba(20, 23, 26, 0.05);
  --shadow-tile-hover: 0 10px 24px -6px rgba(20, 23, 26, 0.11), 0 2px 6px -1px rgba(20, 23, 26, 0.05);
  --shadow-modal: 0 24px 48px -12px rgba(15, 19, 24, 0.32);

  /* Typography & Radii (STRICTLY NO 999px pill soup) */
  --font-sans: 'Plus Jakarta Sans', 'Noto Sans TC', sans-serif;
  --font-mono: 'IBM Plex Mono', monospace;
  --radius-xs: 4px;
  --radius-sm: 7px;
  --radius-md: 10px;
  --radius-lg: 13px;
}

/* === Dark Mode: Deep Basalt Obsidian === */
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

  --status-maint-fg: #fbbf24;
  --status-maint-bg: rgba(217, 119, 6, 0.16);
  --status-maint-border: rgba(251, 191, 36, 0.32);

  --status-outage-fg: #f87171;
  --status-outage-bg: rgba(220, 38, 38, 0.16);
  --status-outage-border: rgba(248, 113, 113, 0.32);

  --glaze-teal-fg: #38cbbd;
  --glaze-teal-bg: rgba(15, 118, 110, 0.2);
  --glaze-teal-border: rgba(56, 203, 189, 0.3);
  --glaze-teal-signal: #f26849;

  --glaze-blue-fg: #66b0ea;
  --glaze-blue-bg: rgba(22, 78, 120, 0.25);
  --glaze-blue-border: rgba(102, 176, 234, 0.32);
  --glaze-blue-signal: #f59e0b;

  --glaze-cyan-fg: #4ec5f1;
  --glaze-cyan-bg: rgba(10, 88, 117, 0.24);
  --glaze-cyan-border: rgba(78, 197, 241, 0.3);
  --glaze-cyan-signal: #34d399;

  --glaze-emerald-fg: #44cf92;
  --glaze-emerald-bg: rgba(19, 92, 61, 0.24);
  --glaze-emerald-border: rgba(68, 207, 146, 0.3);
  --glaze-emerald-signal: #fbbf24;

  --glaze-amber-fg: #f7b955;
  --glaze-amber-bg: rgba(135, 67, 8, 0.24);
  --glaze-amber-border: rgba(247, 185, 85, 0.3);
  --glaze-amber-signal: #f87171;

  --glaze-slate-fg: #cbd5e1;
  --glaze-slate-bg: rgba(51, 65, 85, 0.28);
  --glaze-slate-border: rgba(148, 163, 184, 0.28);
  --glaze-slate-signal: #4ec5f1;

  --glaze-rose-fg: #f47292;
  --glaze-rose-bg: rgba(148, 34, 60, 0.24);
  --glaze-rose-border: rgba(244, 114, 146, 0.3);
  --glaze-rose-signal: #fbbf24;

  --shadow-tile: 0 2px 8px rgba(0, 0, 0, 0.3);
  --shadow-tile-hover: 0 12px 26px rgba(0, 0, 0, 0.5);
}
```

### Google Fonts 載入（或內網離線字體對應）

```html
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link
  href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=Noto+Sans+TC:wght@400;500;600;700;900&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap"
  rel="stylesheet"
/>
```

`body` 必須啟用 `font-variant-numeric: tabular-nums;`，所有序號（`01`）、系統代碼（`MES-CORE`）、環境標章（`PROD`/`UAT`/`DEV`）、快捷鍵（`1`–`9`）、時間戳與分機號一律使用 `var(--font-mono)`。

---

## 3. 版面建築結構藍圖（Layout Blueprints）

### 3.1 三段式深色頁首（3-Tier Architectural Masthead）
- **Tier 1 Utility Bar**（`--bg-header: #12161b`）：左側幾何印記徽章（含 `--cinnabar` 中心點）＋平台名稱；右側佈景切換、檢視模式切換、管理入口（僅對管理員顯示）、使用者身分晶片。
- **Tier 2 Command Stage**（`--bg-header`）：單行高對比指令列搜尋框（`/` 聚焦提示）＋環境／狀態篩選器，絕不放置空洞行銷標語或裝飾大 Hero 圖。
- **Tier 3 Sticky Chapter Ribbon**（`--bg-ribbon: #191f26`）：水平章節索引頁籤，每個頁籤帶朱砂紅等寬編號 `.ribbon-tab-code`（`01`、`02`...）與筆數計數；Active 狀態翻轉為純白底墨黑字（`#ffffff` / `#12161b`）。

### 3.2 非對稱雙欄章節跨頁（Asymmetric Chapter Spread）
```css
.editorial-chapter {
  display: grid;
  grid-template-columns: 270px minmax(0, 1fr);
  gap: 1.5rem;
  align-items: start;
  padding-top: 1.5rem;
  border-top: 2px solid var(--rule-strong);
}

.chapter-poster {
  position: sticky;
  top: 1.25rem;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 1.25rem;
  box-shadow: var(--shadow-tile);
}

.chapter-index-num {
  font-size: 2.15rem;
  font-weight: 900;
  line-height: 1;
  letter-spacing: -0.04em;
}

.chapter-tiles-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(410px, 1fr));
  gap: 0.95rem;
}
```

### 3.3 互動啟動磚與實體鍵帽（Launch Tile & 36×36 Keycap）
```css
.launch-tile {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 1.05rem 1.15rem;
  box-shadow: var(--shadow-tile);
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr) auto;
  gap: 1rem;
  align-items: start;
}

.tile-launch-keycap {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  background: var(--bg-surface-subtle);
  border: 1px solid var(--border-subtle);
  color: var(--text-secondary);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all 0.16s ease;
}

.launch-tile:hover .tile-launch-keycap {
  background: var(--rule-strong);
  border-color: var(--rule-strong);
  color: var(--bg-surface);
}
```

### 3.4 Tufte 單行狀態帳本（Inline Telemetry Ledger）
禁止 4 張獨立陰影 KPI 大卡片；使用共享 `1px` 內線之單行帳本列：
```css
.tufte-telemetry-bar {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1px;
  background: var(--border-subtle);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.telemetry-cell {
  background: var(--bg-surface);
  padding: 0.75rem 1.15rem;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
}

.telemetry-val {
  font-family: var(--font-mono);
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--brand-primary);
}
```

---

## 4. 原創 48×48 四層陶瓷釉色 SVG 徽章規範（Bespoke Emblem Spec）

為消除 AI 預設「到處貼現成單線 Lucide/Heroicons 圖示」的廉價感，本系統要求核心領域與系統圖示採用 **48×48 四層幾何／等距雙色 SVG 結構**：

| 層級 | 繪製元素 | 色彩與透明度規則 |
|---|---|---|
| **Layer 1 底板（Base Plate）** | 外框幾何體或等距底面 | `fill="currentColor" fill-opacity="0.10–0.14"`、`stroke="currentColor" stroke-width="1.7–1.8"` |
| **Layer 2 中調切面（Mid-tone Facet）** | 陰影切面、內層面板或重疊結構 | `fill="currentColor" fill-opacity="0.22–0.30"` |
| **Layer 3 精密工程線條（Precision Linework）** | 刻度、接腳、軸線、虛線或折角 | `stroke="currentColor" stroke-width="1.4–2.1"`、`stroke-linecap="round"` |
| **Layer 4 互補信號點（Signal Node）** | 核心指標點、狀態燈、游標或書籤帶 | `class="svg-signal"`，由 CSS 變數 `var(--emblem-signal)` 填入互補高辨識釉色 |

### CSS 釉色綁定範例
```css
[data-color="teal"].tile-emblem,
[data-color="teal"].chapter-illustration {
  background: var(--glaze-teal-bg);
  color: var(--glaze-teal-fg);
  border-color: var(--glaze-teal-border);
  --emblem-signal: var(--glaze-teal-signal);
}

.svg-signal {
  fill: var(--emblem-signal, var(--cinnabar));
}
```

### 四層 SVG 範本（可直接延伸新圖示）
```html
<!-- Silicon Wafer / PLC Circuit (4-Layer Bespoke Emblem) -->
<svg viewBox="0 0 48 48" fill="none" aria-hidden="true">
  <!-- Layer 1: Base Plate -->
  <rect x="8" y="8" width="32" height="32" rx="6"
        fill="currentColor" fill-opacity="0.12"
        stroke="currentColor" stroke-width="1.8" />
  <!-- Layer 2: Mid-tone Facet -->
  <path d="M16 16H32V32H16V16Z"
        fill="currentColor" fill-opacity="0.24"
        stroke="currentColor" stroke-width="1.8" />
  <!-- Layer 3: Precision Engineering Linework -->
  <path d="M15 4V8M24 4V8M33 4V8M15 40V44M24 40V44M33 40V44M4 15H8M4 24H8M4 33H8M40 15H44M40 24H44M40 33H44"
        stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
  <path d="M20 24H28M24 20V28"
        stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
  <!-- Layer 4: Complementary Signal Node -->
  <circle cx="24" cy="24" r="3.2" class="svg-signal" />
  <circle cx="13" cy="13" r="1.5" fill="currentColor" />
  <circle cx="35" cy="35" r="1.5" fill="currentColor" />
</svg>
```

內建 16 枚領域徽章語意對照（完整程式碼見 `assets/bespoke-emblems.js` 的 `BESPOKE_SVGS`）：
`cpu`（製程/MES）、`layers`（ERP/財務）、`sparkles`（AI/智慧分析）、`users`（HR/組織）、`terminal`（DevOps/部署）、`book`（ISO/SOP 文件）、`chart`（BI/能源報表）、`database`（資料庫稽核）、`bolt`（廠務/電力監控）、`wrench`（設備保養 PM）、`file-check`（電子簽核 BPM）、`shield`（資安/權限）、`server`（主機與排程）、`globe`（網路與外部服務）、`clock`（差勤與定時作業）、`mail`（通報與告警）。

---

## 5. 權限與狀態視覺潔癖（Role & State Hygiene）

1. **非管理員零管理雜訊**：一般使用者進入平台自動 SSO 後，畫面上**完全隱藏**後台管理按鈕、分類設定按鈕、卡片編輯按鈕與空狀態「前往後台新增」引導，不出現停用灰化按鈕。
2. **純淨空狀態**：無資料時僅以簡潔單欄說明現況，不塞入假示範資料或誇張插圖。
3. **單一視覺系統貫穿所有元件**：自訂元件（如 `PersonPicker` 搜尋下拉、在職/離職標記 `查無此工號 ⚠`、使用統計長條圖、稽核日誌表）必須全數引用同一套 CSS 變數（`--bg-surface`、`--border-subtle`、`--brand-primary`、`--status-outage-*`、`--font-mono`），嚴禁在子頁面或彈窗混入另一套色票。
