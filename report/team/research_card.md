# Research card

File này nằm cố định ở `report/team/research_card.md`; `python -m lab8.check_submission` đọc cột "Nhóm điền" bằng máy.

Phần này nối tiếp phần mini research ở buổi lý thuyết (slide 62–63). Chọn **một** câu R1–R4, điền 6 dòng, rồi biến nó thành **một ablation** chạy được trong lab: giữ nguyên model (MockLLM), tool, seed, corpus và giá, chỉ thay đổi một biến.

| Câu | Nguồn (thư viện tham khảo, slide 68–69) | Câu hỏi gợi ý cho lab |
| --- | --- | --- |
| R1 · Scaling | Google Research 2026, *Towards a Science of Scaling Agent Systems* | Task claims chủ yếu tuần tự hay song song được? Dự đoán thêm investigator sẽ làm pass rate và cost/success thay đổi thế nào. |
| R2 · Failure taxonomy | MAST, NeurIPS 2025, *Why Do Multi-Agent LLM Systems Fail?* | Các trial fail của swarm (seed 55) thuộc nhóm nào: lỗi giao việc, lệch mục tiêu, hay lỗi kiểm chứng? |
| R3 · Architecture choices | AgentArch, AACL 2026 | Nếu đổi topology mà giữ nguyên mọi thứ khác, biến nào phải cố định để kết luận còn đúng? |
| R4 · Evaluation confounders | EMNLP 2026, *Rethinking Evaluation of MAS Efficiency* | Làm sao chứng minh chênh lệch giữa A/B/C/D là do topology, không phải do prompt, tool hay seed? |

## Phiếu của nhóm

Điền vào cột cuối. Không xóa hai cột đầu.

| Field | Hướng dẫn | Nhóm điền |
| --- | --- | --- |
| CÂU | R1 / R2 / R3 / R4 | R1 · Scaling |
| SOURCE | Paper/blog, năm, URL, loại bằng chứng (benchmark, production report, blog kinh nghiệm) | Kim và cộng sự (Google Research), *Towards a Science of Scaling Agent Systems*, arXiv:2512.08296, bản v1 ngày 09/12/2025, bản v3 ngày 08/04/2026, https://arxiv.org/abs/2512.08296. Loại nghiên cứu: benchmark có kiểm soát (chuẩn hóa tool, prompt và compute giữa các kiến trúc) |
| CLAIM | Một kết luận gốc của nguồn. Không viết rộng hơn phạm vi paper | Hiệu quả của multi-agent so với single-agent phụ thuộc cấu trúc task, không tăng đều theo số agent: so với baseline single-agent, paper báo +80.8% trên task suy luận tài chính tách nhỏ được và −70.0% trên task lập kế hoạch tuần tự. Task dùng nhiều tool chịu thêm chi phí phối hợp, và kiến trúc không có bước kiểm chứng tập trung làm lỗi lan rộng hơn |
| BOUNDARY | Model / dataset / setup giới hạn kết luận đó | Dataset: 6 benchmark agentic. Model: 3 họ LLM thật. Topology: 5 kiến trúc (1 single-agent; 4 multi-agent: independent, centralized, decentralized, hybrid), tổng 260 cấu hình. Giới hạn: mô hình dự đoán của paper chỉ giải thích một phần phương sai (R² cross-validated 0.373); paper không đo task ghi tiền có cổng duyệt và không đo model giả lập như MockLLM, nên con số −70.0% không áp thẳng vào lab này |
| HYPOTHESIS | Nếu đổi shape A→B (hoặc bật/tắt một thành phần), metric X sẽ đổi theo hướng nào, khoảng bao nhiêu | Quy trình claim là tuần tự (đọc claim → tra đơn → tính quote → gọi host). Đổi A `workflow` → C `orchestrator` (thêm hai investigator chỉ đọc) thì pass rate không tăng (chênh ≤ 0.01), còn cost/success tăng ít nhất 1.5 lần |
| METHOD | Biến giữ cố định: model, tools, seed, corpus, giá, evaluator. Biến duy nhất được thay đổi: … | CONTROL (theo slide 69). Giữ cố định: MockLLM, bộ tool đọc và `durability.issue_refund`, seed 11/22/33/44/55, 14 claim public, `config/pricing.yaml`, evaluator `lab8.metrics.trial_pass`, mỗi trial một SQLite mới. Biến duy nhất thay đổi: topology (A không có investigator, C có hai investigator nhận handoff) |
| FAILURE / METRIC | Một lỗi dự kiến và cách đo nó: pass rate, pass^5, variance, cost/success, leak, bypass | Lỗi dự kiến: handoff làm tăng model call và tool call mà không sửa được claim nào workflow đã làm đúng; rủi ro phụ là lộ parent context qua handoff. Đo bằng pass rate, pass^5, cost/success, mean model/tool call trong `benchmark.json`, và số trial fail `forbidden_substring`. FALSIFY (theo slide 69): giả thuyết bị bác bỏ nếu trên cùng corpus và cùng seed, orchestrator có pass rate cao hơn workflow quá 0.01, hoặc cost/success của orchestrator thấp hơn 1.5 lần workflow |

## Kết quả ablation

- Lệnh đã chạy (copy nguyên văn): `python -m lab8.benchmark --shapes workflow,single,orchestrator,swarm --cases data/public_claims.jsonl --seeds 11,22,33,44,55 --out reports/benchmark.json`
- Run id / file report: `src/reports/benchmark.json`, mục `by_shape.workflow` và `by_shape.orchestrator`; ví dụ cặp trial cùng claim cùng seed: `R-workflow-C-014-s11` và `R-orchestrator-C-014-s11`
- Kết quả so với hypothesis (đúng / sai / không kết luận được), kèm số liệu: đúng trên bộ public, không điều kiện bác bỏ nào xảy ra. Pass rate 1.000 → 1.000 và pass^5 1.000 → 1.000 (không tăng); cost/success 28.80 → 66.38 VND (gấp 2.30 lần); mean model call 1.00 → 3.79; mean tool call 2.79 → 6.36; variance giữ 0; 0 trial fail `forbidden_substring` ở cả hai shape. Không kết luận được về latency và về model thật
- Giới hạn: MockLLM không phải model sản xuất, latency là `unavailable`. Workflow đã đạt trần 1.000 trên 14 claim public nên ablation này không thể cho thấy orchestrator tốt hơn dù có; cần corpus khó hơn (bộ hidden) để phân biệt.

Muốn đi xa hơn một ablation để lấy điểm cộng thì xem [docs/bonus_topics.md](../../docs/bonus_topics.md).
