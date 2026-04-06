# ArXivInsight ReAct Agent — Tổng quan kỹ thuật

> **Dự án:** Lab 3 — Chatbot vs ReAct Agent  
> **Model:** `gpt-5-mini-2025-08-07` (OpenAI)  
> **Ngày chạy:** 06/04/2026  

---

## 1. Tổng quan bài toán

### Mục tiêu

Xây dựng một **ReAct Agent** có khả năng tự động tìm kiếm, đọc và trích xuất **Alpha trading logic** từ các bài báo nghiên cứu tài chính trên ArXiv, sau đó trả về kết quả dưới dạng JSON có cấu trúc.

### So sánh hai cách tiếp cận

| | Chatbot thông thường | ReAct Agent |
|---|---|---|
| Nguồn dữ liệu | Parametric knowledge (training data) | ArXiv API thời gian thực |
| Độ tin cậy | Có thể hallucinate | Chỉ dùng dữ liệu từ Observation |
| Khả năng cập nhật | Không có (cố định theo training) | Có (gọi API mỗi lần) |
| Kết quả | Có thể fabricate papers | Paper ID và abstract thực |
| Cấu trúc output | Tùy model | JSON chuẩn, được validate |

### Flow tổng quát

```
User Query
    │
    ▼
Thought: Phân tích yêu cầu
    │
    ▼
Action: search_arxiv(query="...")
    │
    ▼
Observation: Danh sách papers (ID, title, summary)
    │
    ▼
Action: get_paper_abstract(paper_id="...")   ← lặp cho mỗi paper
    │
    ▼
Observation: Abstract đầy đủ
    │
    ▼
Action: alpha_formatter(text="...")
    │
    ▼
Observation: JSON Alpha có cấu trúc
    │
    ▼
Final Answer: Trả kết quả cho user
```

---

## 2. Các Tools Agent có thể gọi

### Tool 1 — `search_arxiv`

| Thuộc tính | Chi tiết |
|---|---|
| **File** | `src/tools/search.py` |
| **Call format** | `search_arxiv(query="momentum stock market")` |
| **Input** | `query` (string) — từ khóa tìm kiếm |
| **Output** | Danh sách papers: ID, title, authors, published date, summary |
| **Nguồn dữ liệu** | ArXiv API (`export.arxiv.org/api/query`) |
| **Fallback** | Mock JSON file khi API không khả dụng |
| **Filter tự động** | Query chứa keywords tài chính → thêm `cat:q-fin*` |

---

### Tool 2 — `get_paper_abstract`

| Thuộc tính | Chi tiết |
|---|---|
| **File** | `src/tools/search.py` |
| **Call format** | `get_paper_abstract(paper_id="2401.12345")` |
| **Input** | `paper_id` (string) — ArXiv ID |
| **Output** | Title, authors, published date, full abstract |
| **Ghi chú** | Cần ID hợp lệ (dạng `YYMM.NNNNN`), không phải title |

---

### Tool 3 — `extract_abstract`

| Thuộc tính | Chi tiết |
|---|---|
| **File** | `src/tools/reader.py` |
| **Call format** | `extract_abstract(text="raw paper content")` |
| **Input** | `text` (string) — nội dung raw của bài báo |
| **Output** | Chuỗi abstract đã được làm sạch |
| **Logic** | Tìm section "Abstract/Summary/Overview", fallback sang đoạn đầu |

---

### Tool 4 — `extract_metadata`

| Thuộc tính | Chi tiết |
|---|---|
| **File** | `src/tools/reader.py` |
| **Call format** | `extract_metadata(text="raw paper content")` |
| **Input** | `text` (string) — nội dung raw |
| **Output** | Dict gồm: `abstract`, `title`, `cleaned_text`, `length`, `word_count` |

---

### Tool 5 — `alpha_formatter`

| Thuộc tính | Chi tiết |
|---|---|
| **File** | `src/tools/formatter.py` |
| **Call format** | `alpha_formatter(text="paper title + authors + abstract + url + date")` |
| **Input** | `text` (string) — nội dung đầy đủ của bài báo |
| **Output** | JSON object có cấu trúc chuẩn (xem bên dưới) |
| **Self-correction** | Trả `[VALIDATION ERROR]` nếu thiếu field → Agent tự retry |

**Cấu trúc JSON output:**

```json
{
  "title": "full paper title",
  "author": "author name(s)",
  "abstract": "brief abstract summary",
  "url": "arxiv paper URL",
  "published_date": "YYYY-MM-DD",
  "logic": {
    "category": "momentum / mean-reversion / value / ...",
    "input_variable": "past 12-month returns, volume, ...",
    "economic_rationale": "why this strategy generates alpha",
    "trading_logic": "step-by-step strategy description",
    "direction": "long / short / long-short / market-neutral"
  }
}
```

---

## 3. Lỗi đã gặp & Cách giải quyết

### Lỗi 1 — Sai tên tham số: `key=` thay vì `query=` / `paper_id=`

| | Chi tiết |
|---|---|
| **Biểu hiện** | `search_arxiv() got an unexpected keyword argument 'key'` |
| **Log** | Step 1, Run 1 (09:49:16) & Step 1, Run 2 (09:52:26) |
| **Nguyên nhân** | Tool description không nêu rõ tên param → Model tự đặt `key=` |
| **Fix** | Thêm `"Call format: search_arxiv(query=...)"` vào description |
| **Fix bổ sung** | `_execute_tool` thêm fallback remap khi gặp `TypeError` |

```
TRƯỚC (lỗi):  search_arxiv(key="momentum US stock 2024")
SAU (đúng):   search_arxiv(query="momentum US stock 2024")
```

---

### Lỗi 2 — Gọi positional argument không có tên tham số

| | Chi tiết |
|---|---|
| **Biểu hiện** | `search_arxiv() missing 1 required positional argument: 'query'` |
| **Log** | Step 2-3, Run 2 (09:52:40 — 09:52:44) |
| **Nguyên nhân** | Model bỏ `query=`, gọi dạng `search_arxiv("momentum 2024...")` → `_parse_args` không parse được |
| **Fix** | `_parse_args` detect khi không có `=` → tự map string vào first param của function |

```
TRƯỚC (lỗi):  search_arxiv("momentum US stocks 2024")
SAU (đúng):   → tự remap thành search_arxiv(query="momentum US stocks 2024")
```

---

### Lỗi 3 — ArXiv API trả về rỗng với query quá dài

| | Chi tiết |
|---|---|
| **Biểu hiện** | `No papers found on ArXiv for query: 'momentum stock market US equities...'` |
| **Log** | Step 2, Run 1 (09:49:43) & Step 4, Run 2 (09:52:51) |
| **Nguyên nhân** | Query quá dài, nhiều điều kiện → ArXiv API AND logic không tìm được kết quả |
| **Giải pháp (Agent tự xử lý)** | Agent tự broadening query ở bước tiếp theo |
| **Kết quả** | Run 3 (09:56:28) với `query="momentum stock market 2024"` → tìm được 2 papers |

---

### Lỗi 4 — Paper ID không hợp lệ

| | Chi tiết |
|---|---|
| **Biểu hiện** | `400 Client Error: Bad Request for url: .../query?id_list=0402134` |
| **Log** | Step 1, Run 4 (10:21:54) |
| **Nguyên nhân** | Agent hallucinate paper ID `0402134` (paper cổ điển Jegadeesh & Titman 1993 không có trên ArXiv) |
| **Fix** | System prompt thêm rule: *"Never fabricate paper IDs — only use IDs from Observations"* |

---

### Lỗi 5 — `formatter.py` validate reject `"N/A"`

| | Chi tiết |
|---|---|
| **Biểu hiện** | `[VALIDATION ERROR] Missing or empty required fields: url` (khi LLM điền `"N/A"`) |
| **Nguyên nhân** | System prompt bảo dùng `"N/A"` khi thiếu info, nhưng `_validate` lại reject `"N/A"` |
| **Fix** | `_validate` chỉ reject `None` và `""`, chấp nhận `"N/A"` là hợp lệ |

---

## 4. Performance

### Telemetry từ log (06/04/2026)

| Run | Query | Steps | Tổng tokens | Latency trung bình/step | Kết quả |
|---|---|---|---|---|---|
| Run 1 | "momentum idea trading USA" | 3 | 4,003 | ~12,469 ms | `success` — nhưng query quá dài → no papers |
| Run 2 | "momentum từ năm 2024" | 5 | 5,106 | ~6,960 ms | `success` — 3/5 steps bị lỗi params |
| Run 3 | "momentum từ năm 2024" (sau fix) | 2 | 5,817 | ~32,275 ms | `success` — tìm được paper thực |
| Run 4 | "tổng hợp momentum USA" | 3 | 6,967 | ~22,687 ms | `success` — tìm được paper, extract abstract |

### Phân tích

- **Token consumption:** Trung bình ~1,500 tokens/step. Context tích lũy qua các bước làm tăng `prompt_tokens` đáng kể (từ 417 → 1,085 tokens trong một session).
- **Latency:** Step đầu tiên thường chậm nhất (7,000–18,000 ms) do context ngắn nhưng model "thinking" nhiều. Step có tool call thực sự (get_paper_abstract) tốn ~56,000 ms ở Run 3.
- **Error rate trước fix:** 3/8 tool calls đầu tiên bị lỗi sai tên param (~37.5%).
- **Error rate sau fix:** 0 lỗi sai param — fallback remap tự động xử lý.

### Chi phí ước tính (gpt-5-mini)

| Metric | Giá trị |
|---|---|
| Tổng tokens (4 runs) | ~21,893 tokens |
| Ước tính chi phí | ~$0.22 (theo $0.01/1K tokens mock rate) |
| Token hiệu quả nhất | Run 3: 5,817 tokens, 2 steps, tìm được paper thực |

---

## 5. Kiến trúc hệ thống

```
┌─────────────────────────────────────────────────────┐
│                   React Frontend (UI)                │
│           localhost:5173  —  App.jsx                │
└──────────────────────┬──────────────────────────────┘
                       │ POST /api/chat
                       ▼
┌─────────────────────────────────────────────────────┐
│              FastAPI Backend (api_server.py)         │
│                  0.0.0.0:8000                        │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│              ReActAgent (agent.py)                   │
│  ┌──────────────────────────────────────────────┐   │
│  │  Thought → Action → Observation loop         │   │
│  │  max_steps=5, scratchpad accumulation        │   │
│  └──────────────────────────────────────────────┘   │
│                       │                             │
│        ┌──────────────┼──────────────┐             │
│        ▼              ▼              ▼             │
│  search_arxiv  get_paper_abstract  alpha_formatter  │
│  (ArXiv API)   (ArXiv API)         (OpenAI LLM)    │
└─────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│         Telemetry (logger.py + metrics.py)           │
│   logs/YYYY-MM-DD.log  —  JSON structured events    │
│   Events: AGENT_START, AGENT_STEP, TOOL_CALL,       │
│           AGENT_END, LLM_METRIC, LLM_ERROR          │
└─────────────────────────────────────────────────────┘
```

---

## 6. Hướng cải thiện tiếp theo

1. **Guardrail Validator** — Thêm tool kiểm tra tính hợp lý kinh tế của JSON output trước khi trả Final Answer.
2. **Performance Monitor** — Tool ghi Latency & Token count mỗi step để vẽ biểu đồ so sánh v1 vs v2.
3. **Query optimization** — Tiền xử lý query của user thành 1-3 từ khóa ngắn gọn trước khi gọi `search_arxiv`.
4. **Multi-paper batch** — Gọi `get_paper_abstract` song song cho nhiều papers thay vì tuần tự.
5. **Caching** — Cache kết quả ArXiv theo query để tránh gọi API trùng lặp.
