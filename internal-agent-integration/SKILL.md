---
name: internal-agent-integration
description: 串接公司內部 Agent 平台（看起來像 OpenAI 相容的 /v1/chat/completions 與 /v1/files，但行為不相容）的完整作法：防禦式 client、檔案上傳與 type:file 引用、HTTP 狀態碼不可信的處理、重試分層、JSON 容錯抽取、輸出上限下的分批、圖片判讀與標籤橫幅、來源比對（grounding）與自我更正、測試用假平台與上線前 selftest。只要是在寫或修改「呼叫內部 Agent／內部 LLM 平台」的 Python 程式、設定 BASE_URL / API_KEY / MODEL_ID、上傳附件給 Agent、要 Agent 輸出 JSON、處理 Agent 回 200 卻空白、429、504、500「No static resource」、自簽憑證 SSLError、回應被截斷、模型捏造數字或引用，或使用者提到「串接內部 Agent」「接 Agent 平台」「Agent API」「AI 解析」時，都要使用這個 skill——即使使用者沒有說出平台名稱。
---

# 串接內部 Agent 平台

這份 skill 整理自「工程進度簡報 AI 解析平台」實際上線的串接方式。那個專案踩過的每個坑都寫成了程式碼；新專案照這裡做，可以不用再踩一次。

**最重要的一句話：這個平台長得像 OpenAI API，但不能照 OpenAI SDK 的慣例用。** 不要裝 `openai` 套件、不要用 LangChain 之類的封裝——它們會送出平台靜默忽略或直接卡死的參數，而且會把平台不可信的狀態碼當真。一律用 `scripts/agent_client.py`（只依賴 `requests`）。

## 平台行為速查（決定架構的硬限制）

| 平台行為 | 必須的因應 |
|---|---|
| `BASE_URL` 不含 `/v1`；`/v1/models` 未實作 | `MODEL_ID` 是 UUID，只能從平台 UI 取得，寫在設定裡 |
| 不吃 `messages` 歷史，**跨呼叫無記憶** | 每次呼叫都是**單則自足的 user 訊息**；上下文靠附件與 prompt 內文 |
| `temperature` / `top_p` / `seed` / `stop` / `n` / `response_format` / `tools` / `stream` **全部靜默忽略** | 一律不送（client 用 assert 擋）；JSON 靠 prompt 約束＋容錯抽取 |
| 檔案只認 `{"type":"file","file":{"file_id":...}}` | `{"type":"file_id"}` 會讓後端卡死回 504；attachments、body 層 file_ids、在文字裡提檔名都無效 |
| 上傳後要等索引，太快引用拿到空回應 | 上傳後等 `UPLOAD_SETTLE_SECONDS`（預設 3 秒）並 `GET /v1/files/{id}` 確認；批次上傳只等一次 |
| **HTTP 200 不等於成功** | 必須檢查 `choices[0].message.content` 非空；也接受非標準的 `choices[0].text` |
| 路由不存在回 **500** + `No static resource` | 看到這個字串就是「路由不存在」，不是服務掛掉，不要重試 |
| **429 可能是參數錯**（例如 `max_tokens` 負數） | 先檢查參數；送出前就把 `max_tokens` 夾在 1–4096 |
| 5xx（如 `database_timeout` 的 504）是暫時性 | 重試；但 401、TLS、路由不存在是決定性的，不重試 |
| 可解析格式白名單 `txt md csv json html xml log pdf docx`，**不含 pptx / xlsx** | 本地先轉成 Markdown（＋圖片）再上傳 |
| 輸出上限約 **1,825 tokens** | 長輸入分批呼叫，本地合併；`completion_tokens ≥ 1800` 視為可能截斷 |
| 每次呼叫固定約 **3,863 prompt tokens**（平台自己的 system prompt），檔案內容不計入 | 合併能合併的呼叫；畫面上顯示實際用量 |
| `finish_reason` 永遠 `stop`、`tool_calls` 永遠空、串流是假的 | 沒有任何稽核軌跡：結論要在本地驗證；UI 用狀態輪詢，不做串流 |
| **會自信地捏造**，給空清單會掰一個編號填進去 | 本地來源比對；沒有資料的欄位連 prompt 都不要出現 |
| 內網常用自簽憑證 | `CA_BUNDLE` 指向內部 CA（建議）；`VERIFY_SSL=false` 只限受控內網 |
| 租戶隔離與併發未經驗證 | 背景工作預設序列化（併發 1） |

> 這些是在某一個平台版本上量到的。新環境先跑 `scripts/selftest.py` 確認一次，數字不一樣就以實測為準。

細節、錯誤訊息原文與判斷方式見 `references/platform-quirks.md`。

## 工作流程

### 1. 先弄清楚要串的是什麼

能從程式碼看出來就不要問使用者：

| 問題 | 影響 |
|---|---|
| 輸入是什麼格式？ | 不在白名單（pptx、xlsx、圖片以外的二進位）→ 先在本地轉成 md / pdf |
| 要不要看圖？ | 要 → 圖片單張上傳＋標籤橫幅（第 5 步） |
| 輸出要給程式用還是給人看？ | 給程式用 → JSON 契約＋容錯抽取＋降級路徑（第 4 步） |
| 單次輸入／輸出會不會超過上限？ | 會 → 分批＋本地合併（第 6 步） |
| 結論會不會被當成事實往下游送？ | 會 → 來源錨點＋本地比對（第 7 步），這一步不能省 |
| 是網站請求中同步呼叫，還是背景工作？ | 一次呼叫常要 10–60 秒以上 → 放背景工作，前端輪詢狀態 |

### 2. 放進 client 與設定

1. 把 `scripts/agent_client.py` 與 `scripts/jsonx.py` 複製進專案（例如 `<套件>/core/`），需要 `requests`。
2. 設定項加到 `.env.example`（樣板見 `references/config.md`）：`BASE_URL`、`API_KEY`、`MODEL_ID`、`REQUEST_TIMEOUT`、`MAX_RETRIES`、`RETRY_BACKOFF`、`UPLOAD_SETTLE_SECONDS`、`MAX_TOKENS`、`VERIFY_SSL`、`CA_BUNDLE`、`DEMO_MODE`、`KEEP_REMOTE_FILES`。
3. 用一個工廠函式建立 client，**設定不完整時講清楚缺什麼**，`CA_BUNDLE` 指到不存在的檔案時在啟動就報錯，不要拖到第一次呼叫：

```python
def make_client(cfg):
    if cfg.demo_mode:
        return DemoClient()          # 介面與 AgentClient 相同，回擬真資料
    missing = [k for k in ("BASE_URL", "API_KEY", "MODEL_ID") if not getattr(cfg, k.lower())]
    if missing:
        raise AgentPlatformError(f"平台設定不完整，缺少：{', '.join(missing)}。"
                                 "請在 .env 設定，或設 DEMO_MODE=true 先用模擬資料。")
    verify = cfg.ca_bundle or cfg.verify_ssl   # 有 CA_BUNDLE 就用路徑，否則 True/False
    return AgentClient(cfg.base_url, cfg.api_key, cfg.model_id,
                       timeout=cfg.request_timeout, max_retries=cfg.max_retries,
                       retry_backoff=cfg.retry_backoff,
                       upload_settle_seconds=cfg.upload_settle_seconds, verify=verify)
```

4. 呼叫只用這幾個方法：`upload_file` / `upload_files`、`chat(text, file_ids, max_tokens=)`、`delete_file`、`healthcheck`。**不要另外寫 `requests.post` 打平台。**

### 3. 寫 prompt：單則、自足、可改與不可改分開

- 每一次呼叫的背景、規則、任務、輸出格式**全部壓在同一段文字**；不要假設上一輪講過的話它還記得。
- 附件在 prompt 裡列清楚「附件 1 是什麼、附件 2 是什麼」，並給內容**錨點**（例如 `[S03]` 第 3 頁、`[T03-1]` 第 3 頁第 1 個表格、`[IMG S03-1]` 第 3 頁第 1 張圖）。要求每一條結論帶 `cite` 欄位。
- **沒有資料的段落整段拿掉**，不要寫「節點清單：（無）」——它會掰一個編號填進去。
- 明說「附件中查不到就回答查不到／填 null」，並把「不知道」講成沒有代價的選項。
- 把 prompt 拆成**可改段落**（角色、著重點、用詞，可以開放給使用者在後台調整）與**契約段落**（JSON schema、錨點格式、附件清單，留在程式碼）。使用者文字代入佔位符時用 `str.replace`，不要用 `str.format`（使用者寫的 `{`、`}` 會讓整份解析當掉）。

範本與完整例子見 `references/patterns.md` §1。

### 4. 拿 JSON：prompt 約束＋容錯抽取＋一次嚴格重試＋降級

`response_format` 無效，所以：

```python
data = extract_json_object(result.content)          # 圍欄、前言、截斷都能救
if data is None:
    retry = client.chat(strict_json_retry_prompt(prompt), file_ids, max_tokens=max_tokens)
    data = extract_json_object(retry.content)       # 只重試一次
if data is None:
    # 不拋例外：保留原文，讓工作以「只有原始文字」完成，而不是整份失敗
    record.parse_status = "raw_only"
```

模型給的欄位型別不可信：清單用 `as_list()`、文字用 `as_text()` 正規化後再用。完整寫法見 `references/patterns.md` §2。

### 5. 圖片：單張上傳、標籤畫在像素上、回報讀到的標籤

- 每張圖正規化（長邊縮到約 1600px、轉 RGB JPEG）後**單獨上傳**，用 `type:file` 引用；太小的（logo、icon，例如面積 < 6400 px²）不送；同一張圖去重。
- **在圖片上方接一條橫幅，把標籤（`IMG S03-1`）畫進像素**（不要蓋住原圖，工地照上緣常有日期戳記）。檔名和 prompt 裡的順序都在圖片外面，平台若沒把檔名交給模型或打亂附件順序，結果會錯位而沒人發現。`scripts/label_banner.py` 可以直接用。
- 要求模型回報 `visible_label`（從圖上讀到的），對應以它為準；不符的那張**一次一張**重送，仍不符就捨棄並標「可能錯位」。
- 一批約 6 張（受輸出上限所限），各批結果再彙整。模型看不到圖時（selftest 會測）改走退路：把圖逐張畫進 PDF、頁首印標籤，整份上傳。

### 6. 超過上限就分批，能在本地合併就不要再問模型

- 輸入：每次約 25 頁／6 張圖一批；輸出：預估會超過 ~1,800 tokens 就拆。
- 各批是獨立的自足呼叫。**純資料串接在本地合併**——再呼叫一次模型合併會多燒約 3,863 tokens，還可能在改寫時引入幻覺。只有需要「綜合判斷」時才多一次彙整呼叫，而且彙整呼叫吃的是前面各批的結構化結果，不是原文。
- 截斷時 `jsonx` 會補括號救回前面完整的項目；`ChatResult.maybe_truncated` 為真時記錄並在 UI 標示。

### 7. 來源比對：結論在本地驗證，確定錯的退回一次

平台沒有任何稽核軌跡，可信度只能在 client 端建立。對每一條帶 `cite` 的結論：

1. **引用存在嗎？** 錨點是否真的在送出的內容裡 → 不存在是 `bad_cite`。
2. **沒標來源？** → `no_cite`。
3. **數值有據嗎？** 結論裡的數字（去掉千分位、忽略 0–10 與 100 這種常見數）是否出現在它引用的位置 → 找不到是 `unverified_number`；在別頁找到則提示「可能標錯頁」。
4. **只引用圖片的結論**是 `visual_only`：中性、獨立計數，**不算失敗**——視覺觀察本來就不會出現在文字裡，混進失敗數會把機制灌成雜訊，使用者很快就會學會忽略它。

確定錯的（前三種）把問題清單退回模型**一輪**，要它三選一：更正（附新的 text/cite）、收回、堅持（附理由，仍留給人裁決）。只跑一輪；把「收回」講成沒有代價的選項。之後**來源全部不存在的結論不准往下游走**（不進報表、不進下一次比對），但原文保留在紀錄裡——排除不是刪除。

骨架程式碼見 `references/patterns.md` §4–§5。

### 8. 重試分兩層、失敗要看得見

- **呼叫層**（client 內建）：網路錯誤、timeout、空回應、5xx 立即重試 `MAX_RETRIES` 次，間隔 `RETRY_BACKOFF`；用完拋 `RetryExhausted`。`AuthError`、`TlsError`、`RouteNotImplemented`、`ValueError` 不重試。
- **工作層**（背景工作）：收到 `RetryExhausted` 時整份工作進「等待自動重試」，延遲後重跑（例如 2 次、間隔 60 秒）；必要階段沒全部成功前**不寫成完成、不觸發下游**（寄信、報表）。
- 每次呼叫留一筆紀錄：label、file_ids、prompt 字數、prompt/completion tokens、耗時、嘗試次數、`parse_status`（`ok` / `repaired` / `raw_only`）、是否可能截斷、原始回應、錯誤。放在 UI 的「呼叫日誌」——平台出問題時這是唯一的線索。
- 用完遠端檔案就 `delete_file`（除錯時可用 `KEEP_REMOTE_FILES=true` 保留）。

### 9. 測試與上線前驗證

- **單元測試不打真平台**：把 `assets/tests/fake_platform.py` 的 `FakePlatformSession` 傳進 `AgentClient(session=..., sleep=lambda s: None)`。它重現固定 prompt 開銷、`choices[].text`、500 指紋、`type:file_id` 的 504、空回應、偽 429；可以植入捏造的數字確認來源比對真的攔得下來。範例測試在 `assets/tests/test_agent_client.py`。
- 提供 `DEMO_MODE`：一個介面相同、回擬真資料的 `DemoClient`，讓沒有憑證的人也能把整個流程走完。
- **新環境部署後先跑 `scripts/selftest.py`**（讀 `.env` 或環境變數）：連線與認證、固定 token 開銷、上傳與引用、檔案內容不計 token、JSON 輸出、幻覺測試（問不存在的資料看會不會拒答）、視覺能力（單張上傳 vs PDF 包裝）、清理遠端檔案。

## 不要做的事

- 不要用 `openai` SDK、LangChain、LlamaIndex 等封裝呼叫這個平台。
- 不要送 `temperature`、`response_format`、`tools`、`stream` 等參數，也不要寫「之後再打開」的註解——它們不會生效，只會誤導維護者。
- 不要依賴多輪對話或 `thread_id`。
- 不要只看 HTTP 狀態碼判斷成功；不要把 500 一律當成伺服器掛掉。
- 不要對 401、TLS 錯誤、路由不存在做重試。
- 不要把 `verify=False` 設成預設值；不要每次呼叫都噴 `InsecureRequestWarning`（client 只記一次警告）。
- 不要把模型自報的圖片編號、頁碼、數字直接當事實；不要給它空清單。
- 不要把 API key 寫進程式碼、log 或前端；`.env.example` 只放空值。
- 不要在網站請求的執行緒裡同步等模型回應數十秒。

## 檢查清單（交付前逐項確認）

- [ ] 只透過 `AgentClient` 呼叫平台；專案裡搜不到 `openai`、`temperature=`、`response_format`、`"file_id"` 型別的 content
- [ ] `.env.example` 有平台設定項且值為空；`DEMO_MODE` 可跑完整流程
- [ ] 每個 prompt 是單則自足訊息；沒有資料的段落整段不出現
- [ ] 要 JSON 的地方都有 `extract_json_object` → 嚴格重試一次 → 降級保存原文
- [ ] 輸入或輸出可能超過上限的地方有分批，合併在本地做
- [ ] 圖片有標籤橫幅並查核 `visible_label`
- [ ] 往下游送的結論有來源錨點與本地比對；圖片判讀不算失敗
- [ ] 呼叫層與工作層重試分開；失敗的工作不觸發下游；每次呼叫有紀錄
- [ ] 遠端檔案用完會刪
- [ ] 測試用 `FakePlatformSession`，不需要 API key 就能跑
- [ ] 已提醒使用者在正式環境跑 `scripts/selftest.py`

## 參考檔案

- `references/platform-quirks.md`：每個平台怪異行為的原始現象、判斷方式與 client 的對應處理。
- `references/patterns.md`：prompt 範本、JSON 呼叫包裝、分批與合併、來源比對與自我更正、呼叫紀錄的程式碼骨架。
- `references/config.md`：`.env.example` 片段與每個設定的說明、TLS 設定方式。
- `scripts/agent_client.py`：防禦式 client（直接複製使用）。
- `scripts/jsonx.py`：容錯 JSON 抽取與型別正規化。
- `scripts/label_banner.py`：圖片正規化與標籤橫幅（需要 Pillow）。
- `scripts/selftest.py`：對真實平台的上線前檢查。
- `assets/tests/fake_platform.py`、`assets/tests/test_agent_client.py`：假平台與範例測試。
