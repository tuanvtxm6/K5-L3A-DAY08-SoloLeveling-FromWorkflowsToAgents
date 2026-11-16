# Báo cáo nhóm — Lab 8 LogiX-VN

Tối đa 5 trang ngoài phụ lục. Số liệu lấy từ file trong `src/reports/`, không chép tay từ terminal.

## 1. Thông tin nhóm

- Tên nhóm: SoloLeveling
- Thành viên: xem `TEAM.md`
- Commit chốt (trùng `report/team/decision_adr.md`): 7d579cf

## 2. Mục tiêu và cách tiếp cận

Bài toán: xử lý claim hoàn phí vận chuyển của LogiX-VN bằng bốn kiến trúc có cùng chữ ký `run_claim`, rồi chọn kiến trúc ít tự chủ nhất mà vẫn làm đúng việc, dựa trên số đo chứ không dựa trên cảm tính.

Nhóm hiểu grader chấm ba thứ: `RunResult`, ledger SQLite và trace. Câu chữ trả lời khách không được chấm. Vì vậy nhóm đặt ba nguyên tắc trước khi viết code:

1. Tiền do code tính bằng `compute_compensation` từ dòng order và policy hiện hành. Model không chọn số tiền và không ghi refund.
2. Mọi lần ghi tiền đi qua `durability.issue_refund` với quote đầy đủ. Host kiểm approval, trần theo đơn và idempotency.
3. Trace là ranh giới bảo mật. Chỉ ghi field đã qua allowlist; không ghi ticket, principal, claim row hay order row thô.

Thứ tự làm: đọc `swarm_reference.py` và host (`durability.py`, `handoff.py`, `runtime.py`) → viết workflow (đơn giản nhất, làm chuẩn so sánh) → single → orchestrator → thêm test cho các tình huống bộ hidden mô tả → chạy benchmark và crash suite → viết ADR.

## 3. Giải pháp

Cả ba shape có chung khung: mở store, chạy logic, đóng store. `InjectedCrash` được ghi vào trace rồi ném tiếp ra ngoài, không bị nuốt. Mọi exception khác trả `failed` kèm trace hợp lệ, vì `run_claim` không được ném exception. Mọi nhánh return đều qua `finish()` để `refund_effects` và `committed_audit_count` lấy từ ledger.

| Shape | Đọc gì | Model làm gì | Ai quyết tiền và ghi refund |
| --- | --- | --- | --- |
| A `workflow` | `get_claim_view` → `lookup_order` → `compute_compensation`, theo thứ tự cố định | Một lần gọi, chỉ soạn câu trả lời. Prompt chỉ chứa `status` | Code của shape tính quote, gọi `issue_refund` |
| B `single` | Vòng `run_react` tối đa 8 bước: `lookup_order` → `lookup_refund_history` → `compute_compensation` → final | Mỗi bước một lần gọi model, chọn một tool đọc hoặc dừng | Sau vòng lặp, code tính lại quote từ order view; final của model lệch thì bị bỏ (`model_final_overruled`). Code gọi `issue_refund` |
| C `orchestrator` | Investigator 1 (`order_facts`): `lookup_order`, `lookup_refund_history`. Investigator 2 (`check_applicable_policy`): `lookup_policy` | Orchestrator lập kế hoạch; mỗi investigator một lần gọi; một lần soạn trả lời | Orchestrator tính quote từ order view của investigator và gọi `issue_refund`. Investigator không có tool ghi |

Ranh giới code / model:

- Model được đọc ticket (single, orchestrator) nhưng kết quả đọc không đi vào phép tính tiền. Số ngày trễ luôn lấy từ cột `delay_days`. Mã đơn luôn lấy từ field `order_id` của claim, không lấy từ câu chữ.
- Runtime từ chối tool ghi ở tầng `dispatch`. Shape single còn kiểm thêm: nếu vòng lặp kết thúc mà chưa tra đơn thì trả `failed`.
- Shape tự từ chối khi quote = 0 (`denied`, `proposal_amount` 0, không gọi host). Khi quote > 0, shape luôn gọi host để host ghi audit `policy_denied` nếu từ chối; `proposal_amount` giữ quote đầy đủ.

Handoff: orchestrator dựng handoff bằng `make_handoff`. Handoff đầu không có fact nào. Handoff thứ hai chỉ mang năm fact lấy từ order view đã qua allowlist (`delay_days`, `damage_verified`, `order_status`, `shipping_fee_vnd`, `paid_vnd`); `carrier` được phép nhưng nhóm bỏ vì bước kiểm policy không cần. Ticket, principal, `parent_secret` và header không vào handoff. Nếu `make_handoff` phát hiện canary hoặc tool ghi, shape trả `failed` chứ không chuyển tiếp.

Trace: danh sách event và các field cố ý không ghi nằm ở mục "Trace và bằng chứng" của `report/team/decision_adr.md`.

## 4. Kết quả

Bộ public: 14 claim × 5 seed = 70 trial mỗi shape. Nguồn: `src/reports/benchmark.json`.

| Shape | Pass rate | Pass^5 | Seed min–max | Variance | Cost/success (VND) | Mean / p95 steps | Mean model call | Mean tool call |
| --- | ---: | ---: | --- | ---: | ---: | --- | ---: | ---: |
| workflow | 1.000 | 1.000 | 1.000–1.000 | 0.000000 | 28.80 | 4.43 / 5 | 1.00 | 2.79 |
| single | 1.000 | 1.000 | 1.000–1.000 | 0.000000 | 46.72 | 9.93 / 11 | 3.64 | 4.50 |
| orchestrator | 1.000 | 1.000 | 1.000–1.000 | 0.000000 | 66.38 | 8.00 / 9 | 3.79 | 6.36 |
| swarm | 0.986 | 0.929 | 0.929–1.000 | 0.000816 | 49.57 | 2.80 / 3 | 3.00 | 4.66 |

- Swarm fail đúng một trial: `R-swarm-C-002-s55`, trả `resolved` trong khi nhãn là `denied`. Đây là điểm yếu cố ý: ở seed chia hết cho 5 swarm tin số ngày trong ticket. Ba shape của nhóm pass trial này.
- Cột steps là số event trong trace nên phụ thuộc mức chi tiết mỗi shape ghi. Single có 9.93 event nhưng vòng ReAct chỉ chạy tối đa 4 bước, dưới trần 8. Swarm ít event nhất vì ghi ít chứ không phải làm ít. Để so khối lượng việc, dùng cost, model call và tool call.
- Crash safety: `20/20` (`src/reports/crash.json`).
- Ma trận student: `python -m pytest -q -m student -o addopts=` ra 248 passed. Cổng host: `python -m pytest -q` ra 166 passed, gồm 112 test nhóm thêm trong `src/tests/test_team_shapes.py`.
- Tự kiểm hidden: chưa chạy vì nhóm không có thư mục `student_drop/`.

Quyết định kiến trúc và lý do: xem `report/team/decision_adr.md`. Phiếu nghiên cứu và ablation: xem `report/team/research_card.md`.

## 5. Khó khăn và cách xử lý

- Lệnh `py -3 -m venv .venv` trong README báo `The term 'py' is not recognized` trên máy Windows của nhóm (không cài Python launcher). Xử lý: dùng `python -m venv .venv` với Python 3.13.5, rồi gọi thẳng `.\.venv\Scripts\python.exe`.
- Cổng host lúc mới clone ra `54 passed, 248 deselected`, khác con số `52 passed` ghi trong `src/README.md`. Không có test nào fail nên nhóm coi là tài liệu chưa cập nhật và làm tiếp.
- Shape single: `run_react` chỉ truyền cho `decide` kết quả của tool gần nhất. Để code kiểm lại được sau vòng lặp, `decide` lưu kết quả từng tool vào một dict do code giữ; quote cuối cùng được tính lại từ order view trong dict đó, không lấy từ final của model.
- Trần theo đơn (T13, T14): shape truyền quote đầy đủ, không tự trừ phần đã hoàn. `lookup_refund_history` chỉ dùng làm ngữ cảnh và ghi trace.

## 6. Tổng hợp đóng góp

Chi tiết đóng góp của từng thành viên nằm trong `TEAM.md` (bảng đóng góp) và báo cáo cá nhân `report/team/MSSV_HoTen.md`.

## 7. Hạn chế và hướng cải thiện

MockLLM không phải model sản xuất; latency là `unavailable`.

- MockLLM không bao giờ chọn sai tool hay bịa số, nên variance 0 của single và orchestrator không dự báo được hành vi với model thật. Với model thật, phần `decide` của single phải được thay bằng lời gọi model và đo lại trên nhiều seed.
- Bộ public chỉ có 14 claim và workflow đã đạt trần, nên benchmark này không phân biệt được ba shape về độ đúng. Kết luận "workflow đủ dùng" chỉ đúng cho loại claim mà mọi dữ kiện nằm sẵn trong order và policy.
- Kết luận sẽ đổi nếu claim cần hiểu ngôn ngữ tự do mà code không xử lý được, hoặc nếu việc điều tra tách được thành nhánh song song và latency trở thành tiêu chí. Điều kiện cụ thể ghi trong ADR.
- Hướng cải thiện: chạy tự kiểm trên `student_drop/` khi có; thêm ablation orchestrator một investigator so với hai investigator để tách chi phí của từng handoff.

## 8. Tài liệu tham khảo

- Tài liệu của lab: `README.md`, `docs/business_rules.md`, `docs/contracts.md`, `docs/metrics.md`, `docs/architecture.md`.
- Code tham chiếu: `src/lab8/shapes/swarm_reference.py`, `src/lab8/durability.py`, `src/lab8/handoff.py`, `src/lab8/runtime.py`.
- Google Research, *Towards a Science of Scaling Agent Systems* (thư viện tham khảo của buổi lý thuyết, slide 68–69).
