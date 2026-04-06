# ArXivInsight ReAct Agent — Tổng quan kỹ thuật

> **Dự án:** Lab 3 — Chatbot vs ReAct Agent
> **Model:** `gpt-5-mini-2025-08-07` (OpenAI)
> **Ngày chạy thực tế:** 06/04/2026
> **Tổng số runs ghi lại:** 10 runs

---

## 1. Tổng quan bài toán

### Mục tiêu

Xây dựng một **ReAct Agent** có khả năng tự động tìm kiếm, đọc và trích xuất **Alpha trading logic** từ các bài báo nghiên cứu tài chính trên ArXiv, trả về kết quả dưới dạng JSON có cấu trúc chuẩn.

### So sánh Chatbot thông thường vs ReAct Agent

| | Chatbot thông thường | ReAct Agent |
|---|---|---|
| Nguồn dữ liệu | Parametric knowledge (training data) | ArXiv API thời gian thực |
| Độ tin cậy | Có thể hallucinate papers không tồn tại | Chỉ dùng dữ liệu từ Observation thực |
| Khả năng cập nhật | Cố định theo training cutoff | Gọi API mỗi request |
| Kết quả | Fabricate paper ID, title, abstract | Paper ID và abstract xác thực từ ArXiv |
| Cấu trúc output | Tùy model quyết định | JSON chuẩn, được validate 11 fields |
| Khi query quá mới | Trả `[]` hoặc hallucinate | Tự điều chỉnh query để tìm kết quả |

### Workflow bắt buộc (Mandatory 4-step pipeline)

```
User Query
    │
    ▼
[Step 1] Action: search_arxiv(query="...")
         → Observation: tối đa 3 papers (ID, title, summary)
    │
    ▼
[Step 2] Action: get_paper_abstract(paper_id="...")   ← lặp cho mỗi paper
         → Observation: full abstract, authors, published date
    │
    ▼
[Step 3] Action: alpha_formatter(text="...")           ← lặp cho mỗi paper
         → Observation: JSON Alpha có cấu trúc chuẩn
    │
    ▼
[Step 4] Final Answer: tổng hợp kết quả cho user
```

---

## 2. Các Tools Agent có thể gọi

### Tool 1 — `search_arxiv`

| Thuộc tính | Chi tiết |
|---|---|
| **File** | `src/tools/search.py` |
| **Call format** | `search_arxiv(query="momentum stock market")` |
| **Input** | `query` (string) — từ khóa tìm kiếm |
| **Output** | Tối đa 3 papers: ID, title, authors, published date, summary (300 ký tự) |
| **Hard cap** | `MAX_PAPERS = 3` — không thể vượt quá dù truyền `max_results` lớn hơn |
| **Nguồn dữ liệu** | ArXiv API (`export.arxiv.org/api/query`) |
| **Fallback** | Mock JSON file khi API không khả dụng |
| **Filter tự động** | Query chứa keywords tài chính (momentum, alpha, stock...) → thêm `cat:q-fin*` |

---

### Tool 2 — `get_paper_abstract`

| Thuộc tính | Chi tiết |
|---|---|
| **File** | `src/tools/search.py` |
| **Call format** | `get_paper_abstract(paper_id="2401.12345")` |
| **Input** | `paper_id` (string) — ArXiv ID dạng `YYMM.NNNNNvX` |
| **Output** | Title, authors, published date, full abstract (không cắt ngắn) |
| **Lưu ý** | Chỉ nhận ID thực từ Observation — ID hallucinate sẽ gây `400 Bad Request` |

---

### Tool 3 — `extract_abstract`

| Thuộc tính | Chi tiết |
|---|---|
| **File** | `src/tools/reader.py` |
| **Call format** | `extract_abstract(text="raw paper content")` |
| **Input** | `text` (string) — nội dung raw của bài báo |
| **Output** | Chuỗi abstract đã được làm sạch |
| **Logic** | Tìm section "Abstract/Summary/Overview" trước, fallback sang đoạn đầu tiên |

---

### Tool 4 — `extract_metadata`

| Thuộc tính | Chi tiết |
|---|---|
| **File** | `src/tools/reader.py` |
| **Call format** | `extract_metadata(text="raw paper content")` |
| **Input** | `text` (string) — nội dung raw |
| **Output** | Dict: `abstract`, `title`, `cleaned_text`, `length`, `word_count` |

---

### Tool 5 — `alpha_formatter`

| Thuộc tính | Chi tiết |
|---|---|
| **File** | `src/tools/formatter.py` |
| **Call format** | `alpha_formatter(text="title + authors + abstract + url + date")` |
| **Input** | `text` (string) — nội dung đầy đủ của bài báo |
| **Output** | JSON object 6 top-level fields + 5 logic fields (xem schema bên dưới) |
| **Self-correction** | Trả `[VALIDATION ERROR: Missing fields: ...]` → Agent đọc được và tự retry |
| **Validation** | Reject `None` và `""` — chấp nhận `"N/A"` (LLM dùng khi thiếu thông tin) |

**Cấu trúc JSON output:**

```json
{
  "title": "full paper title",
  "author": "author name(s)",
  "abstract": "brief abstract summary (2-3 sentences)",
  "url": "https://arxiv.org/abs/XXXX.XXXXX",
  "published_date": "YYYY-MM-DD",
  "logic": {
    "category": "momentum / mean-reversion / value / volatility / other",
    "input_variable": "variables used (e.g. past 12-month returns, volume)",
    "economic_rationale": "why this strategy generates alpha",
    "trading_logic": "step-by-step description of the strategy",
    "direction": "long / short / long-short / market-neutral"
  }
}
```

---

## 3. Lỗi đã gặp & Cách giải quyết

> **Tổng quan:** 9/10 runs đầu tiên có ít nhất 1 lỗi. Run 10 là lần đầu tiên hoàn thành full workflow (10 steps).

---

### Lỗi 1 — Sai tên tham số: `key=` thay vì `query=` / `paper_id=`

| | Chi tiết |
|---|---|
| **Biểu hiện** | `search_arxiv() got an unexpected keyword argument 'key'` |
| **Log** | Run 1 step 1 (09:49:16) — `get_paper_abstract(key="Time Series Momentum...")` |
| | Run 2 step 1 (09:52:26) — `search_arxiv(key="momentum US stock 2024...")` |
| **Nguyên nhân** | Tool description chỉ nói *"Input: a search query string"*, không nêu tên param → Model tự đặt `key=` |
| **Fix 1** | Thêm `"Call format: search_arxiv(query=...)"` vào tool description |
| **Fix 2** | `_execute_tool` thêm `except TypeError` fallback: remap values vào positional params theo thứ tự signature |

```
TRƯỚC:  search_arxiv(key="momentum US stock 2024")   → TypeError
SAU:    search_arxiv(query="momentum US stock 2024") → hoạt động
```

---

### Lỗi 2 — Gọi positional argument không có `=`

| | Chi tiết |
|---|---|
| **Biểu hiện** | `search_arxiv() missing 1 required positional argument: 'query'` |
| **Log** | Run 2 step 2-3 (09:52:40–09:52:44) — `search_arxiv("momentum 2024 US equities...")` |
| **Nguyên nhân** | Model bỏ `query=`, gọi dạng `search_arxiv("...")` → `_parse_args` regex cần `key=value`, không match được string thuần |
| **Fix** | `_parse_args`: nếu không tìm thấy `key=value` nào → map toàn bộ string vào `first_param` của function signature |

```
TRƯỚC:  search_arxiv("momentum US stocks 2024")  → missing argument
SAU:    tự remap → search_arxiv(query="momentum US stocks 2024") → hoạt động
```

---

### Lỗi 3 — ArXiv API trả về rỗng với query quá dài / quá cụ thể

| | Chi tiết |
|---|---|
| **Biểu hiện** | `No papers found on ArXiv for query: 'momentum stock market US equities...'` |
| **Tần suất** | Xuất hiện ở **8/10 runs** ít nhất 1 lần |
| **Nguyên nhân** | ArXiv dùng AND logic cho nhiều từ — query dài → không có bài nào khớp tất cả |
| **Pattern thành công** | Query ngắn 2-4 từ: `"momentum stock"`, `"momentum factor stock market"` → có kết quả |
| **Agent tự xử lý** | Tự broaden query ở bước tiếp theo (self-correcting behavior) |
| **Ví dụ từ log** | Run 8 step 2: `"momentum factor stock market"` → tìm được 3 papers |

---

### Lỗi 4 — Model hallucinate paper ID không tồn tại trên ArXiv

| | Chi tiết |
|---|---|
| **Biểu hiện** | `400 Client Error: Bad Request for url: .../query?id_list=0402134` |
| **Log** | Run 4 step 1 (10:21:54) — `get_paper_abstract(paper_id="0402134")` |
| **Nguyên nhân** | Agent gọi `get_paper_abstract` trước khi search — dùng ID từ parametric knowledge (paper Jegadeesh & Titman 1993 không có trên ArXiv) |
| **Fix** | System prompt thêm rule: *"Never fabricate paper IDs — only use IDs/data from Observations"* |
| **Fix thứ 2** | Workflow bắt buộc: `search_arxiv` PHẢI được gọi đầu tiên |

---

### Lỗi 5 — Model tự viết `Observation:` trong response (hallucinate Observation)

| | Chi tiết |
|---|---|
| **Biểu hiện** | Model viết `Action: get_paper_abstract(...)` rồi tự bịa `Observation: {...}` rồi viết `Final Answer:` trong cùng 1 turn |
| **Log** | Run 3 step 2 (09:57:24) — 55,946ms, 3,680 completion tokens |
| | Run 4 step 3 (10:22:45) — 39,765ms, 2,772 completion tokens |
| **Hậu quả** | Agent thoát vòng lặp ngay khi thấy `Final Answer:`, bỏ qua `alpha_formatter` hoàn toàn |
| **Nguyên nhân code** | Code cũ kiểm tra `Final Answer:` **trước** `Action:` — khi cả hai xuất hiện, Final Answer thắng |
| **Fix 1 (system prompt)** | Thêm: *"STOP after writing Action. Do NOT write Observation yourself. Do NOT write Final Answer in the same turn as an Action"* |
| **Fix 2 (code)** | Đảo thứ tự: kiểm tra `Action:` **trước**, `Final Answer:` chỉ được xử lý khi **không có** `Action:` |
| **Fix 3 (code)** | Cắt response tại `action_match.end()` — loại bỏ phần hallucinate sau Action |

```python
# TRƯỚC (lỗi): Final Answer được check trước
if "Final Answer:" in response_text:
    return final   # thoát dù chưa gọi alpha_formatter

# SAU (đúng): Action được check trước
action_match = re.search(r"Action:...", response_text)
if action_match:
    # xử lý tool call, bỏ qua Final Answer
elif "Final Answer:" in response_text:
    return final   # chỉ thoát khi không còn Action nào
```

---

### Lỗi 6 — `max_steps=5` không đủ cho full workflow

| | Chi tiết |
|---|---|
| **Biểu hiện** | `AGENT_END: status: max_steps_reached` — agent dừng trước khi gọi `alpha_formatter` |
| **Log** | Run 5 (10:32:36), Run 6 (10:38:32), Run 7 (10:39:46), Run 8 (10:45:36), Run 9 (10:46:45) |
| **Nguyên nhân** | Workflow tối thiểu: 1 search + 3 abstracts + 3 formatters + 1 final = **8 steps** |
| | Các bước retry query thêm 2-3 steps nữa → cần ít nhất **10-12 steps** |
| **Fix** | `AGENT_MAX_STEPS=20` configurable qua `.env` (default 20) |
| **Kết quả** | Run 10 (10:51:01): hoàn thành full workflow trong **10 steps** với `max_steps=20` |

---

### Lỗi 7 — `formatter.py` validate reject `"N/A"` mâu thuẫn với system prompt

| | Chi tiết |
|---|---|
| **Biểu hiện** | `[VALIDATION ERROR] Missing or empty required fields: url` khi LLM điền `"N/A"` |
| **Nguyên nhân** | System prompt bảo model dùng `"N/A"` khi thiếu info, nhưng `_validate` reject `"N/A"` → vòng lặp validation vô tận |
| **Fix** | `_validate` chỉ reject `None` và `""` — chấp nhận `"N/A"` là giá trị hợp lệ |

---

### Lỗi 8 — `metrics.py` thiếu param `metadata` (phát hiện qua code review)

| | Chi tiết |
|---|---|
| **Biểu hiện** | `TypeError: track_request() got an unexpected keyword argument 'metadata'` |
| **Nguyên nhân** | `monitor.py` gọi `tracker.track_request(..., metadata=metadata)` nhưng `track_request` chỉ có 4 params |
| **Fix** | Thêm `metadata: Optional[Dict[str, Any]] = None` vào signature + merge vào metric dict |

---

### Lỗi 9 — `reader.py` gọi `clean_text()` trước regex xóa mất newlines (phát hiện qua code review)

| | Chi tiết |
|---|---|
| **Biểu hiện** | `extract_abstract` luôn fallback sang đoạn đầu, không bao giờ match section "Abstract" |
| **Nguyên nhân** | `clean_text()` replace `\s+` → single space, xóa hết `\n\n` mà regex `(?=\n\n\|...)` dựa vào |
| **Fix** | Gọi `clean_text()` **sau** khi extract, không phải trước |

---

### Lỗi 10 — `src/tools/__init__.py` không tồn tại (phát hiện qua code review)

| | Chi tiết |
|---|---|
| **Biểu hiện** | `ImportError: cannot import name 'ALL_TOOLS' from 'src.tools'` khi khởi động `api_server.py` |
| **Nguyên nhân** | File `__init__.py` chưa được tạo — `ALL_TOOLS` không được export |
| **Fix** | Tạo `src/tools/__init__.py` với `ALL_TOOLS = [SEARCH_ARXIV_TOOL, GET_PAPER_ABSTRACT_TOOL, ALPHA_FORMATTER_TOOL, EXTRACT_ABSTRACT_TOOL, EXTRACT_METADATA_TOOL]` |

---

## 4. Performance

### Telemetry đầy đủ — 10 runs (06/04/2026)

| Run | Timestamp | Query | Steps | Tổng tokens | Avg latency/step | Status | Vấn đề |
|---|---|---|---|---|---|---|---|
| Run 1 | 09:49:16 | "momentum idea trading USA" | 3 | 4,003 | ~12,469ms | `success` | Sai param `key=`, no papers |
| Run 2 | 09:52:26 | "momentum từ năm 2024" | 5 | 5,106 | ~6,960ms | `success` | 3/5 steps lỗi params |
| Run 3 | 09:56:19 | "momentum từ năm 2024" | 2 | 5,817 | ~32,275ms | `success` | Hallucinate Observation, bỏ alpha_formatter |
| Run 4 | 10:21:36 | "tổng hợp momentum USA" | 3 | 6,967 | ~22,687ms | `success` | Hallucinate paper ID, bỏ alpha_formatter |
| Run 5 | 10:32:36 | "tổng hợp momentum USA" | 5 | 7,761 | ~5,369ms | `max_steps_reached` | Hết bước trước alpha_formatter |
| Run 6 | 10:38:32 | "tổng hợp momentum USA" | 5 | 9,397 | ~7,409ms | `max_steps_reached` | Fetched 3 abstracts, không đủ bước format |
| Run 7 | 10:39:46 | "tổng hợp momentum USA" | 5 | 8,456 | ~5,545ms | `max_steps_reached` | Fetched 3 abstracts, không đủ bước format |
| Run 8 | 10:45:36 | "tổng hợp momentum USA" | 5 | 8,173 | ~5,888ms | `max_steps_reached` | Fetched 3 abstracts, không đủ bước format |
| Run 9 | 10:46:45 | "tổng hợp momentum USA" | 5 | 12,244 | ~7,570ms | `max_steps_reached` | Gọi alpha_formatter 1/3 papers, hết bước |
| **Run 10** | **10:51:01** | **"tổng hợp momentum USA"** | **10** | **35,238** | **~9,746ms** | **`success`** | **Full workflow hoàn chỉnh** |

### Timeline cải tiến theo phiên bản

```
v1 (Runs 1-4): max_steps=5
  ├── Vấn đề: Sai tên params, positional args
  ├── Vấn đề: Hallucinate Observation → bỏ qua alpha_formatter
  └── Vấn đề: Hallucinate paper ID → 400 error

v2 (Runs 5-9): max_steps=5, fixed params + fallback remap
  ├── Đã fix: Sai tên params (tool description + fallback remap)
  ├── Đã fix: Positional args (_parse_args detect và remap)
  ├── Vẫn còn: max_steps=5 quá ít (workflow cần 8+ steps)
  └── Vẫn còn: Hallucinate Observation

v3 (Run 10): max_steps=20, fixed hallucination, Action-before-FinalAnswer
  ├── Đã fix: max_steps=20 (configurable via .env)
  ├── Đã fix: Action check trước Final Answer trong code
  ├── Đã fix: System prompt cấm tự viết Observation
  └── KẾT QUẢ: Full workflow hoàn chỉnh lần đầu tiên
```

### Phân tích token consumption

| Metric | Giá trị |
|---|---|
| Run thành công đầy đủ (Run 10) | 35,238 tokens / 10 steps |
| Avg tokens/step (Run 10) | ~3,524 tokens |
| Tăng trưởng context | Step 1: 759 tokens → Step 10: 8,426 tokens (~11x) |
| Token hiệu quả nhất (partial) | Run 5: 7,761 tokens, 5 steps, capped before formatter |
| Tổng tokens 10 runs | ~102,162 tokens |
| Ước tính chi phí 10 runs | ~$1.02 (theo $0.01/1K tokens mock rate) |

### Latency breakdown (Run 10 — run thành công)

| Step | Tool | Latency | Tokens |
|---|---|---|---|
| 1 | search_arxiv (no result) | 3,081ms | 759 |
| 2 | search_arxiv (no result) | 3,737ms | 899 |
| 3 | search_arxiv → 3 papers | 2,491ms | 889 |
| 4 | get_paper_abstract #1 | 7,649ms | 2,192 |
| 5 | get_paper_abstract #2 | 7,863ms | 2,995 |
| 6 | get_paper_abstract #3 | 10,724ms | 3,406 |
| 7 | alpha_formatter #1 | 22,620ms | 4,644 |
| 8 | alpha_formatter #2 | 10,140ms | 5,066 |
| 9 | alpha_formatter #3 | 12,426ms | 5,923 |
| 10 | Final Answer | 38,437ms | 8,426 |
| **Tổng** | | **~119s** | **35,199** |

---

## 5. Kiến trúc hệ thống

```
┌──────────────────────────────────────────────────────────┐
│                 React Frontend (UI)                      │
│          localhost:5173  —  ui/src/App.jsx               │
│  POST { query } → GET { answer }                        │
└────────────────────────┬─────────────────────────────────┘
                         │ POST /api/chat
                         ▼
┌──────────────────────────────────────────────────────────┐
│           FastAPI Backend (api_server.py)                │
│               0.0.0.0:8000                               │
│   AGENT_MAX_STEPS=20 (configurable via .env)            │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│             ReActAgent (src/agent/agent.py)              │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Thought → Action → Observation loop              │  │
│  │  ✓ Action checked BEFORE Final Answer             │  │
│  │  ✓ Hallucinated Observation stripped              │  │
│  │  ✓ Positional arg fallback remap                  │  │
│  │  ✓ TypeError → param remap recovery               │  │
│  └───────────────────────────────────────────────────┘  │
│                         │                               │
│     ┌───────────────────┼────────────────────┐         │
│     ▼                   ▼                    ▼         │
│ search_arxiv     get_paper_abstract    alpha_formatter  │
│ (ArXiv API)       (ArXiv API)          (OpenAI LLM)    │
│ MAX_PAPERS=3                           self-correction  │
│     │                                                   │
│     ▼                                                   │
│ extract_abstract / extract_metadata (reader.py)        │
└──────────────────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│        Telemetry (logger.py + metrics.py)                │
│   logs/YYYY-MM-DD.log — JSON structured events          │
│   Events: AGENT_START · AGENT_STEP · TOOL_CALL          │
│           AGENT_END · LLM_METRIC · LLM_ERROR            │
│   Metrics: latency_ms · tokens · cost_estimate          │
└──────────────────────────────────────────────────────────┘
```

### Cấu hình quan trọng (`.env`)

```env
DEFAULT_PROVIDER=openai
DEFAULT_MODEL=gpt-5-mini-2025-08-07
AGENT_MAX_STEPS=20       # tăng lên nếu cần xử lý nhiều papers hơn
```

---

## 6. Hướng cải thiện tiếp theo

### Đã implement ✅
- Fallback remap khi sai tên param (`key=` → `query=`)
- Positional arg auto-mapping
- Action-before-FinalAnswer priority
- Stricter system prompt chống hallucinate Observation
- Hard cap `MAX_PAPERS=3`
- Configurable `AGENT_MAX_STEPS` via `.env`
- `get_summary()` cho `PerformanceTracker`
- `src/tools/__init__.py` với `ALL_TOOLS`

### Cần làm tiếp 🔲
1. **Guardrail Validator** — Tool kiểm tra tính hợp lý kinh tế của JSON output (direction vs logic phải nhất quán, category phải thuộc whitelist) trước khi trả Final Answer.
2. **Performance Monitor** — Tool BONUS ghi Latency & Token count mỗi step, xuất CSV để vẽ biểu đồ so sánh v1 vs v2 vs v3.
3. **Query Preprocessor** — Tiền xử lý query của user: trích xuất 2-3 từ khóa cốt lõi trước khi gọi `search_arxiv`, tránh query dài → no results.
4. **Parallel abstract fetching** — Gọi `get_paper_abstract` concurrently cho 3 papers thay vì tuần tự → giảm ~60% latency giai đoạn fetch.
5. **Result caching** — Cache kết quả ArXiv theo query hash, tránh gọi API trùng lặp trong cùng session.
6. **Multi-round conversation** — Cho phép user follow-up trên kết quả đã trích xuất (so sánh strategies, lọc theo direction, v.v.).
