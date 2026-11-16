# Báo cáo cá nhân — 2A202603634_LucAnhTuan

## 1. Thông tin thành viên

- Họ tên: Lục Anh Tuấn
- MSSV: 2A202603634
- Email: 26ai.tuanla2@vinuni.edu.vn
- GitHub: tuanvtxm6

## 2. Phần việc phụ trách

Nhóm SoloLeveling chỉ có một thành viên nên tôi phụ trách toàn bộ bài:

- Ba shape: A `workflow`, B `single`, C `orchestrator`.
- Test của nhóm cho các tình huống bộ hidden mô tả.
- Chạy benchmark 4 shape × 5 seed và crash suite 20 điểm.
- ADR, research card, báo cáo nhóm và `TEAM.md`.

## 3. Đóng góp cụ thể

Commit chính:

- `7d579cf` — feat: implement workflow, single and orchestrator shapes (ba file shape, `src/tests/test_team_shapes.py`, `src/reports/benchmark.json`, `src/reports/crash.json`).
- `16fdeac` — docs: fill ADR, research card, group report and team table.

Test đã thêm: `src/tests/test_team_shapes.py`, 112 test chạy trong cổng host (`python -m pytest -q`):

- Ticket nói dối số ngày trễ → `denied`, không ghi ledger.
- Injection có nêu mã đơn trên claim thiếu `order_id` → `needs_info`.
- Approval mượn của claim khác, hoặc không có approval → `denied`, `proposal_amount` là quote đầy đủ, có audit `policy_denied`.
- Crash ở cả ba điểm rồi resume hai lần → đúng một dòng ledger và một audit `refund_committed`.
- Trace và `RunResult` không chứa canary, ticket, principal, SĐT, địa chỉ, tên hàng.
- Claim không tồn tại và store không đọc được → `failed`, không ném exception.
- Single: không quá 8 bước, chỉ chọn tool đọc, final lệch quote của model bị code bỏ.
- Orchestrator: handoff chỉ có field, fact và tool trong allowlist.

Quyết định kỹ thuật:

- Shape luôn truyền quote đầy đủ vào `durability.issue_refund`, không tự trừ phần đơn đã được hoàn. Host tự trừ; nếu shape trừ trước thì T14 bị trừ hai lần.
- Shape tự từ chối khi quote = 0 và không gọi host. Khi quote > 0 thì luôn gọi host, để host ghi audit `policy_denied` nếu từ chối.
- `InjectedCrash` được ghi vào trace rồi ném tiếp. Exception khác trả `failed` kèm trace hợp lệ.
- Ở single, quote được code tính lại từ order view sau vòng ReAct, không lấy số trong final của model.
- Ở orchestrator, handoff thứ hai chỉ mang năm fact; bỏ `carrier` vì bước kiểm policy không cần.
- Trace chỉ chép năm field số/trạng thái của order, không chép cả order view và không ghi ticket.
- Chọn `workflow` trong ADR: ba shape cùng pass rate 1.000 trên bộ public, workflow có cost/success thấp nhất (28.80 VND so với 46.72 và 66.38).

## 4. Bằng chứng

- Ma trận student: `python -m pytest -q -m student -o addopts=` ra 248 passed.
- Cổng host: `python -m pytest -q` ra 166 passed.
- `src/reports/benchmark.json`: workflow, single, orchestrator pass rate 1.000, pass^5 1.000, variance 0; swarm 0.986 / 0.929.
- `src/reports/crash.json`: `crash_safety` = `20/20`.
- `python -m lab8.check_submission`: 0 FAIL.
- Run id dẫn chứng: `R-workflow-C-002-s55`, `R-workflow-C-007-s11`, `R-workflow-C-014-s11`.

## 5. Công cụ AI đã dùng

- Công cụ: Claude Code (Anthropic), chạy trong VS Code.
- Dùng vào việc: đọc codebase và tài liệu của lab; viết code ba shape và file test `test_team_shapes.py`; chạy các lệnh benchmark, crash suite và `check_submission`; soạn bản nháp ADR, research card, báo cáo nhóm và báo cáo này.
- Số liệu không do AI tự đặt ra: mọi con số trong báo cáo lấy từ `src/reports/benchmark.json` và `src/reports/crash.json` do công cụ của lab sinh ra; không file JSON nào bị sửa tay.
- Cách tự kiểm tra: chạy lại `python -m pytest -q`, ma trận student, benchmark và crash suite trên máy mình và đối chiếu với số trong báo cáo; đọc lại ba file shape để kiểm ranh giới code / model (model không chọn số tiền, không gọi tool ghi) và việc truyền quote đầy đủ vào host; mở file trace trong `src/traces/` để xác nhận không có secret hay PII.
- Phần chưa kiểm được: nguồn trích dẫn trong research card (link arXiv và tóm tắt kết luận của paper) cần đối chiếu với slide 68–69.

## 6. Tự đánh giá

- Đã đạt: ba shape qua toàn bộ ma trận public, crash 20/20, không lộ secret trên bộ public, `check_submission` 0 FAIL.
- Tự kiểm hidden (`src/reports/hidden_selfcheck.json`): ba shape chạy hết 200 trial, 0 `error`, 0 `leak_suspect`. Bộ này không có nhãn nên chưa biết pass rate hidden chính thức.
- Chưa đạt: chưa làm bonus.
- Giới hạn: kết quả đo trên MockLLM và 14 claim public; variance 0 của single và orchestrator không dự báo được hành vi với model thật.
