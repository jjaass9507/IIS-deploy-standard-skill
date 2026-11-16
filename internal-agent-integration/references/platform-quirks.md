# 平台怪異行為對照表

每一項：**現象**（你會看到什麼）→ **判斷**（怎麼確認是這個原因）→ **處理**（`scripts/agent_client.py` 怎麼做、呼叫端要做什麼）。

這些行為是在實際平台上量到的。平台升級後可能改變，新環境請先跑 `scripts/selftest.py`。

---

## 1. 端點與認證

| 項目 | 內容 |
|---|---|
| 可用端點 | `POST /v1/chat/completions`、`POST /v1/files`（multipart，欄位 `file`、`purpose=assistants`）、`GET /v1/files`、`GET /v1/files/{id}`、`DELETE /v1/files/{id}` |
| 未實作 | `/v1/models`（無法列舉模型）、其他所有 OpenAI 路徑 |
| 認證 | `Authorization: Bearer <API_KEY>`；key 錯誤回 401（認證是真的會生效的） |
| `BASE_URL` | 不含 `/v1`，client 自己組。使用者在 `.env` 填了 `/v1` 會變成 `/v1/v1/...` → 500 指紋 |
| `MODEL_ID` | UUID，只能從平台 UI 或後端設定取得 |

## 2. 請求格式

**唯一有效的附件形狀：**

```json
{
  "model": "<MODEL_ID>",
  "messages": [{
    "role": "user",
    "content": [
      {"type": "text", "text": "完整、自足的指示……"},
      {"type": "file", "file": {"file_id": "file-xxxx"}},
      {"type": "file", "file": {"file_id": "file-yyyy"}}
    ]
  }],
  "max_tokens": 2048
}
```

| 寫法 | 結果 |
|---|---|
| `{"type":"file","file":{"file_id":...}}` | ✅ 唯一有效 |
| `{"type":"file_id","file_id":...}` | ❌ 後端卡死，最後 504。client 結構上不可能產生它 |
| `attachments: [...]`、body 層 `file_ids` | ❌ 靜默無效，模型看不到檔案 |
| 只在文字裡寫檔名 | ❌ 無效 |
| 多則 `messages`（含 assistant 歷史） | ❌ 歷史不被使用；平台沒有跨呼叫記憶 |
| `temperature` / `top_p` / `top_k` / `seed` / `stop` / `n` / `presence_penalty` / `frequency_penalty` / `logit_bias` / `logprobs` / `response_format` / `tools` / `tool_choice` / `functions` / `function_call` / `stream` | 靜默忽略。client 的 `FORBIDDEN_PARAMS` 用 assert 確保不會送出 |
| `max_tokens` ≤ 0 | 回 **429 rate_limit_exceeded**（錯誤映射錯亂）。client 送出前就拋 `ValueError` |
| `max_tokens` 很大 | 實際輸出仍約 1,825 tokens 封頂。client 夾在 4096 |

## 3. 回應

| 現象 | 判斷 | 處理 |
|---|---|---|
| HTTP 200，`choices[0].message.content` 是空字串 | 常見於上傳後太快引用、或平台內部失敗 | `EmptyCompletion` → 重試 |
| 內容在 `choices[0].text` 而不是 `message.content` | 平台的非標準欄位 | `_read_completion` 兩個都讀 |
| `finish_reason` 永遠 `stop` | 即使被截斷也是 | 不能用它判斷截斷；改看 `completion_tokens ≥ 1800`（`ChatResult.maybe_truncated`） |
| `tool_calls` 永遠空 | 平台內部有工具，但不回傳軌跡 | 無稽核軌跡 → 本地來源比對 |
| `usage.prompt_tokens` 一次就 ~3,863 | 平台自己的 system prompt 與工具 schema | 固定成本；檔案內容不計入。估算成本用 `呼叫次數 × 3,863 + prompt 字數/≈2` |
| 回應有 `thread_id` | 看起來像對話 ID | 不要用；下一次呼叫不會記得 |
| `stream: true` | 所有 chunk 同時到達（假串流） | 不做串流，UI 輪詢工作狀態 |

## 4. 錯誤碼

| 現象 | 意義 | client 例外 | 重試？ |
|---|---|---|---|
| 401 | API key 無效 | `AuthError` | 否 |
| 500，body 含 `No static resource` | **路由不存在**（`/v1` 底下是 catch-all），不是服務掛掉 | `RouteNotImplemented` | 否 |
| 429 | 可能真的是限流，**更常是參數非法** | `AgentPlatformError`（訊息提醒先檢查參數） | 否 |
| 5xx（例如 504 `{"error":{"code":"database_timeout","message":"Database query timeout. Please retry later."}}`） | 暫時性 | `TransientServerError` | 是 |
| 其他 4xx | 請求錯誤 | `AgentPlatformError` | 否 |
| `requests` 連線錯誤、timeout | 網路 | — | 是 |
| `SSLError` | 憑證不受信任，是**決定性**的 | `TlsError`（訊息直接告訴使用者改 `CA_BUNDLE` 或 `VERIFY_SSL`） | 否 |
| 重試用完 | — | `RetryExhausted`（交給工作層稍後重跑） | 工作層決定 |

判斷順序很重要：**先看 body 有沒有路由不存在的指紋**，再看狀態碼——不然路由錯誤會被當成 5xx 一直重試。

## 5. 檔案

| 現象 | 處理 |
|---|---|
| 上傳後立刻引用，回 200 但內容空、或模型說看不到附件 | 上傳後等 `UPLOAD_SETTLE_SECONDS`（3 秒），再 `GET /v1/files/{id}` 確認有 `id`。批次上傳時**先全部送出、只等一次**（20 張圖從 60 秒降到 3 秒多） |
| 索引確認本身也不穩 | 確認失敗只記 warning，不中止；真的失敗會在 chat 階段以空回應出現並重試 |
| 可解析格式只有 `txt md csv json html xml log pdf docx` | pptx、xlsx、xls 等先在本地抽成 Markdown；圖片照常上傳（jpg/png） |
| 上傳的檔案不會自動清 | 用完 `delete_file`；`KEEP_REMOTE_FILES=true` 保留供除錯 |
| 檔名 | 帶上語意（例如 `IMG_S03-1.jpg`、`deck_text.md`）方便在 prompt 裡指名，但**不要依賴模型看得到檔名** |

## 6. 模型行為

| 現象 | 處理 |
|---|---|
| 自信地捏造數字、頁碼、設備編號 | 要求每條結論帶 `cite`；本地比對（`patterns.md` §4） |
| 給空清單會掰一個編號填進去 | 沒有資料時整段不要出現在 prompt |
| 查不到時硬回答 | prompt 明說「查不到就回答『附件中無此資料』／填 null」；selftest 第 5 項測這件事 |
| `response_format` 無效，常包 Markdown 圍欄或加前言 | `jsonx.extract_json_object`；失敗再用嚴格措辭重試一次 |
| 長清單在中途被截斷 | `jsonx` 補齊括號、或砍到最後一個完整項目 |
| 把錨點代號寫進句子（「完成 68% [S12]」） | prompt 要求「來源只填 cite 欄位」；呈現層再把句中代號抽出來併進來源（不要改存檔的原文） |
| 同一份輸入兩次結果不同 | `temperature`/`seed` 無效，輸出不可重現。要穩定就把判斷改成本地規則 |
| 圖片與標籤對應錯位 | 標籤畫進像素＋回報 `visible_label`（SKILL.md 第 5 步） |

## 7. TLS

| 情況 | 錯誤 | 設定 |
|---|---|---|
| 平台用內部 CA 或自簽憑證 | `certificate verify failed: self-signed certificate` / `unable to get local issuer certificate` | **建議**：`CA_BUNDLE=<內部 CA 的 .pem>`，驗證仍然生效 |
| 只能先跑起來 | 同上 | `VERIFY_SSL=false`：連線仍加密但不確認對方身分，只限受控內網；client 只記一次 warning 並關掉 `InsecureRequestWarning` 洗版 |
| 環境變數 `REQUESTS_CA_BUNDLE` / `CURL_CA_BUNDLE` | 會蓋掉 `Session.verify` | client 每次呼叫明確傳 `verify=`，結果才可預測 |

## 8. 併發

租戶隔離與併發行為未經驗證。背景工作預設一次只跑一份（`WORKER_CONCURRENCY=1`），要提高請先實測同時呼叫是否會串到別人的附件或回應。
