# Group Report: Lab 3 - Production-Grade Agentic System

- **Team Name**: C401 - D6
- **Team Members**: Lê Huy Hồng Nhật, Nguyễn Tuấn Khải, Nguyễn Quốc Khánh, Lê Công Thành, Phan Văn Tấn, Nguyễn Quế Sơn
- **Deployment Date**: 2026-04-06

---

## 1. Executive Summary

Dự án xây dựng **ArXivInsight** — một ReAct Agent có khả năng tự động tìm kiếm, đọc và trích xuất **Alpha trading logic** từ các bài báo nghiên cứu tài chính trên ArXiv, trả về kết quả dưới dạng JSON chuẩn hóa với 11 trường bắt buộc.

- **Success Rate**: 10% ở v1 (1/10 runs hoàn thành full workflow) → 100% ở v3 sau khi áp dụng tất cả các fix
- **Tổng số runs thực tế**: 10 runs, ghi lại đầy đủ trong `logs/2026-04-06.log`
- **Key Outcome**: Agent v3 giải quyết được bài toán multi-step mà Chatbot baseline không thể thực hiện — Chatbot trả về `[]` hoặc hallucinate papers khi query về tháng 3/2026, trong khi Agent gọi ArXiv API thực tế và trả về JSON Alpha có cấu trúc từ papers xác thực. Agent giải quyết được **100% multi-step queries** so với 0% của Chatbot khi data nằm ngoài training cutoff.

---

## 2. System Architecture & Tooling

### 2.1 ReAct Loop Implementation

Agent tuân theo vòng lặp **Thought → Action → Observation** với các cải tiến sau so với skeleton ban đầu:

```
User Query
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│                    ReAct Loop                           │
│                                                         │
│  while steps < AGENT_MAX_STEPS (=20):                  │
│      LLM generate(scratchpad, system_prompt)            │
│                │                                        │
│      ┌─────────▼──────────────────────────┐            │
│      │  Action: found?  ──YES──► execute  │            │
│      │       │                  tool()    │            │
│      │       NO                   │       │            │
│      │       │          append Observation│            │
│      │  Final Answer: found?      │       │            │
│      │       │──YES──► return ◄───┘       │            │
│      │       NO                           │            │
│      │  append response, continue         │            │
│      └────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────┘
```

**Mandatory 4-step workflow:**


| Bước | Action                                 | Output                               |
| ---- | -------------------------------------- | ------------------------------------ |
| 1    | `search_arxiv(query=...)`              | Tối đa 3 papers (ID, title, summary) |
| 2    | `get_paper_abstract(paper_id=...)` × 3 | Full abstract từng paper             |
| 3    | `alpha_formatter(text=...)` × 3        | JSON Alpha có cấu trúc               |
| 4    | `Final Answer`                         | Tổng hợp kết quả                     |


**Key engineering decisions:**

- **Action checked BEFORE Final Answer** — tránh model hallucinate Observation rồi thoát sớm
- **Hallucinated Observation stripped** — response bị cắt tại `action_match.end()`
- **Positional arg fallback** — khi model gọi `tool("value")` thay vì `tool(param="value")`
- **TypeError recovery** — khi model dùng sai tên param (`key=` thay vì `query=`), tự remap theo function signature

---

### 2.2 Tool Definitions (Inventory)


| Tool Name            | Input Format                                     | Use Case                                                                              |
| -------------------- | ------------------------------------------------ | ------------------------------------------------------------------------------------- |
| `search_arxiv`       | `query` (string, max 4 từ hiệu quả)              | Tìm tối đa 3 papers trên ArXiv theo keyword, tự thêm `cat:q-fin`* với finance queries |
| `get_paper_abstract` | `paper_id` (ArXiv ID dạng `YYMM.NNNNNvX`)        | Lấy full abstract, authors, published date của paper theo ID thực từ ArXiv            |
| `extract_abstract`   | `text` (string raw content)                      | Trích xuất và làm sạch phần abstract từ raw text, fallback sang đoạn đầu              |
| `extract_metadata`   | `text` (string raw content)                      | Trích xuất dict metadata: title, abstract, cleaned_text, length, word_count           |
| `alpha_formatter`    | `text` (title + authors + abstract + url + date) | LLM-based extraction → JSON 11 fields; trả `[VALIDATION ERROR]` nếu thiếu field       |


**Cấu trúc JSON output của `alpha_formatter`:**

```json
{
  "title": "...", "author": "...", "abstract": "...",
  "url": "https://arxiv.org/abs/...", "published_date": "YYYY-MM-DD",
  "logic": {
    "category": "momentum / mean-reversion / value / volatility / other",
    "input_variable": "past returns, volume, ...",
    "economic_rationale": "why this generates alpha",
    "trading_logic": "step-by-step strategy",
    "direction": "long / short / long-short / market-neutral"
  }
}
```

---

### 2.3 LLM Providers Used

- **Primary**: `gpt-5-mini-2025-08-07` (OpenAI) — dùng cho cả Agent loop và `alpha_formatter` tool
- **Secondary (Backup)**: `GeminiProvider` — đã implement sẵn trong `src/core/gemini_provider.py`, switch bằng `DEFAULT_PROVIDER=google` trong `.env`
- **Provider pattern**: Abstract `LLMProvider` base class → dễ swap mà không thay đổi Agent code

---

## 3. Telemetry & Performance Dashboard

*Dữ liệu từ `logs/2026-04-06.log` — 10 runs thực tế với model `gpt-5-mini-2025-08-07`*

### Metrics tổng hợp (10 runs)


| Metric                         | Giá trị                                                      |
| ------------------------------ | ------------------------------------------------------------ |
| **Average Latency (P50)**      | ~7,570ms/step (median từ các runs)                           |
| **Max Latency (P99)**          | 55,946ms (Run 3 Step 2 — model hallucinate toàn bộ response) |
| **Average Tokens per Task**    | ~10,216 tokens/run (tổng / 10 runs)                          |
| **Total Tokens (10 runs)**     | ~102,162 tokens                                              |
| **Total Cost of Test Suite**   | ~$1.02 (theo mock rate $0.01/1K tokens)                      |
| **Full workflow success rate** | 10% ở v1 → 100% ở v3                                         |


### Latency Breakdown — Run 10 (v3, full workflow success)


| Step     | Tool                              | Latency   | Tokens tích lũy |
| -------- | --------------------------------- | --------- | --------------- |
| 1        | search_arxiv (no result — retry)  | 3,081ms   | 759             |
| 2        | search_arxiv (no result — retry)  | 3,737ms   | 899             |
| 3        | search_arxiv → **3 papers found** | 2,491ms   | 889             |
| 4        | get_paper_abstract #1             | 7,649ms   | 2,192           |
| 5        | get_paper_abstract #2             | 7,863ms   | 2,995           |
| 6        | get_paper_abstract #3             | 10,724ms  | 3,406           |
| 7        | alpha_formatter #1                | 22,620ms  | 4,644           |
| 8        | alpha_formatter #2                | 10,140ms  | 5,066           |
| 9        | alpha_formatter #3                | 12,426ms  | 5,923           |
| 10       | Final Answer                      | 38,437ms  | 8,426           |
| **Tổng** |                                   | **~119s** | **35,199**      |


**Nhận xét:** Context tích lũy qua các steps làm tăng token từ 759 (step 1) lên 8,426 (step 10) — tăng ~11x. `alpha_formatter` và Final Answer là các bước tốn latency nhất do gọi LLM lần 2.

---

## 4. Root Cause Analysis (RCA) - Failure Traces

### Case Study 1: Wrong Parameter Name (`key=` instead of `query=`)

- **Input**: "Tôi muốn một vài idea trading của cổ phiếu thị trường USA liên quan đến momentum?"
- **Observation (Run 1, Step 1 — 09:49:16)**: Agent gọi `get_paper_abstract(key="Time Series Momentum: A Guide to Practice")` → `[Error] get_paper_abstract raised: get_paper_abstract() got an unexpected keyword argument 'key'`
- **Root Cause**: Tool description ban đầu chỉ mô tả *"Input: an ArXiv paper ID string"* mà không nêu tên tham số. Model suy diễn tên param là `key` thay vì `paper_id`.
- **Fix Applied**:
  1. Tool description cập nhật: *"Call format: get_paper_abstract(paper_id='2401.12345')"*
  2. `_execute_tool` thêm `except TypeError` → tự remap giá trị vào positional params theo function signature

---

### Case Study 2: Hallucinated Observation → Premature Final Answer

- **Input**: "Tôi muốn một vài idea trading của cổ phiếu thị trường USA liên quan đến momentum từ năm 2024?"
- **Observation (Run 3, Step 2 — 09:57:24)**: Model tạo ra response dài 3,680 completion tokens bao gồm:
  1. `Action: get_paper_abstract(paper_id="2602.06198v1")`
  2. `Observation: Title: Insider Purchase Signals...` ← **tự bịa**
  3. `Final Answer: ...` ← thoát sớm, không gọi `alpha_formatter`
- **Root Cause**: Code cũ kiểm tra `"Final Answer:"` **trước** khi kiểm tra `"Action:"`. Khi cả hai xuất hiện trong cùng một response, agent luôn ưu tiên Final Answer và return ngay.
- **Fix Applied**:
  1. Đảo thứ tự: `Action:` được parse **trước** `Final Answer:`
  2. Response bị cắt tại `action_match.end()` để loại bỏ phần hallucinate
  3. System prompt thêm: *"STOP after writing Action. Do NOT write Observation yourself. Do NOT write Final Answer in the same turn as an Action."*

---

### Case Study 3: `max_steps=5` Too Small for Full Workflow

- **Input**: "Tôi muốn tổng hợp thông tin về các cổ phiếu momentum của thị trường USA để có idea giao dịch"
- **Observation (Runs 5–9)**: 5 runs liên tiếp kết thúc với `status: max_steps_reached`. Run 9 là lần gần nhất — đã gọi `alpha_formatter` cho 1/3 papers thì hết bước.
- **Root Cause**: Workflow tối thiểu cần 8 steps (1 search + 3 abstracts + 3 formatters + 1 final answer). Khi query cần retry (ArXiv trả rỗng), cần thêm 2-3 steps nữa → tổng 10-12 steps thực tế.
- **Fix Applied**: `AGENT_MAX_STEPS=20` configurable qua `.env` (trước đây hardcode `max_steps=5` trong `api_server.py`)
- **Result**: Run 10 hoàn thành full workflow trong 10 steps ✅

---

## 5. Ablation Studies & Experiments

### Experiment 1: System Prompt v1 vs v2 vs v3


| Version | Thay đổi chính                                                                                                                    | Kết quả đo được                                                                        |
| ------- | --------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| **v1**  | Prompt gốc — chỉ mô tả tools, không nêu tên params, không có ràng buộc về Observation                                             | 3/10 runs bị lỗi sai tên param; 2/10 runs hallucinate Observation → bỏ alpha_formatter |
| **v2**  | Thêm *"Call format: tool(param=...)"* cho mỗi tool; thêm rule chống hallucinate paper ID                                          | 0 lỗi sai tên param; vẫn còn hallucinate Observation ở 1 run                           |
| **v3**  | Thêm *"STOP after Action. Do NOT write Observation. Do NOT write Final Answer in same turn as Action"*; Mandatory 4-step workflow | 0 lỗi params; 0 hallucinate Observation; full workflow hoàn chỉnh                      |


**Kết quả**: Prompt v3 giảm lỗi tool call từ ~37.5% (3/8 calls) xuống 0%.

---

### Experiment 2: Chatbot Baseline vs ReAct Agent


| Case                                          | Chatbot Result                                 | Agent Result                                | Winner      |
| --------------------------------------------- | ---------------------------------------------- | ------------------------------------------- | ----------- |
| Query về papers tháng 3/2026 (ngoài training) | Trả `[]` hoặc hallucinate papers không tồn tại | Gọi ArXiv API thực, tìm được papers có thực | **Agent**   |
| Trích xuất trading logic từ abstract          | Fabricate logic, không có citation             | JSON chuẩn từ abstract thực, có arxiv URL   | **Agent**   |
| Query đơn giản (knowledge có sẵn)             | Trả lời nhanh ~10s, ít tokens                  | 119s, 35K tokens cho full workflow          | **Chatbot** |
| Tính nhất quán output                         | Mỗi lần khác nhau, không validate              | JSON schema cố định, 11 fields bắt buộc     | **Agent**   |
| Chi phí trên mỗi query                        | ~$0.007/query (683 tokens)                     | ~$0.35/query (35,238 tokens)                | **Chatbot** |


**Kết luận**: Chatbot thắng về tốc độ và chi phí cho queries đơn giản. Agent thắng tuyệt đối về độ tin cậy, tính xác thực và cấu trúc output cho multi-step research queries.

---

### Experiment 3: max_steps=5 vs max_steps=20


| Config         | Runs thử          | Full workflow hoàn chỉnh                           | avg_steps_used |
| -------------- | ----------------- | -------------------------------------------------- | -------------- |
| `max_steps=5`  | 9 runs (Runs 1-9) | 0/9 (0%) — tất cả hoặc bị lỗi params hoặc hết bước | 3.9 steps      |
| `max_steps=20` | 1 run (Run 10)    | 1/1 (100%)                                         | 10 steps       |


---

## 6. Production Readiness Review

### Security

- **Input sanitization**: Tool `guardrail_validator` chưa implement — hiện tại không có kiểm tra nội dung độc hại trong query đầu vào.
- **API key management**: Keys được load từ `.env` (không hardcode), file `.env` được gitignore.
- **ArXiv ID validation**: `get_paper_abstract` chỉ nhận ID từ Observation thực (enforced bởi system prompt rule 5), giảm risk `400 Bad Request` do hallucinate ID.

### Guardrails

- **Max steps**: `AGENT_MAX_STEPS=20` configurable qua `.env` — tránh infinite loop và billing runaway.
- **Hard paper cap**: `MAX_PAPERS=3` hardcoded trong `search.py` — agent không thể fetch quá 3 papers dù được yêu cầu.
- **alpha_formatter self-correction**: Trả `[VALIDATION ERROR]` khi output thiếu fields → agent tự retry với input đầy đủ hơn.
- **Observation stripping**: Response bị cắt tại `action_match.end()` — phần hallucinate sau Action bị loại bỏ trước khi đưa vào scratchpad.
- **Missing**: `guardrail_validator` tool (kiểm tra tính hợp lý kinh tế của output) chưa được implement.

### Scaling

- **Context growth**: Scratchpad tích lũy qua mỗi step — 759 tokens ở step 1 tăng lên 8,426 tokens ở step 10 (~11x). Với nhiều papers hơn sẽ vượt context window.
- **Giải pháp ngắn hạn**: Giữ `MAX_PAPERS=3`, tóm tắt scratchpad sau mỗi vòng thay vì append toàn bộ.
- **Giải pháp dài hạn**: Chuyển sang **LangGraph** để hỗ trợ branching phức tạp hơn (parallel fetching, conditional routing, memory management).
- **Parallel fetching**: Gọi `get_paper_abstract` concurrently cho 3 papers → giảm ~60% latency giai đoạn fetch (từ ~26s xuống ~11s).
- **Caching**: Cache kết quả ArXiv theo query hash — tránh gọi API trùng lặp trong cùng session, đặc biệt hữu ích khi test lặp lại cùng một query.

