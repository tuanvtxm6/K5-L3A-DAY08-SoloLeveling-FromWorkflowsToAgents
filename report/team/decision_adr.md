# Decision record

Điền sau dấu `:` trên cùng dòng, không xóa nhãn. Giảng viên và `python -m lab8.check_submission` (chạy trong `src/`) đọc các dòng này bằng máy. Không đổi tên hay dời file này khỏi `report/team/`.
`Shape chọn` phải là đúng một trong: `workflow`, `single`, `orchestrator`, `swarm`. Đây là shape được chấm cổng hidden.

- Shape chọn: workflow
- Commit hash: 7d579cf
- Run id dẫn chứng: R-workflow-C-002-s55 (ticket nói dối, seed swarm fail), R-workflow-C-007-s11 (approval hết hạn), R-workflow-C-014-s11 (trần theo đơn) — trong `src/reports/benchmark.json`
- Pass rate / pass^5 / seed min-max / variance: 1.000 / 1.000 / 1.000–1.000 / 0.000000 (70 trial public = 14 claim × 5 seed, `src/reports/benchmark.json`)
- Cost per success (mô phỏng, VND): 28.80 (single 46.72, orchestrator 66.38, swarm 49.57)
- Crash safety: 20/20 (`src/reports/crash.json`)
- Secret leak / approval bypass: 0 / 0 trên 70 trial public của workflow (không trial nào fail `forbidden_substring`; C-004, C-005, C-007 có `approval_ok=false` đều không có dòng ledger). Số hidden do giảng viên chấm

Ví dụ một dòng đã điền: `- Shape chọn: workflow`, `- Crash safety: 20/20 (src/reports/crash.json)`.

## Vì sao shape này

Trên cùng 14 claim public, cùng 5 seed (11, 22, 33, 44, 55), cùng MockLLM và cùng bảng giá, ba shape nhóm viết đều đạt pass rate 1.000, pass^5 1.000 và variance 0. Khi độ đúng bằng nhau thì tiêu chí còn lại là chi phí và mức tự chủ. Workflow rẻ nhất: 28.80 VND cho mỗi lần thành công, so với 46.72 của single (cao hơn 62%) và 66.38 của orchestrator (cao hơn 130%). Workflow cũng dùng ít lời gọi model nhất (trung bình 1.00 lần mỗi claim, chỉ để soạn câu trả lời; single 3.64, orchestrator 3.79) và ít tool nhất (2.79; single 4.50, orchestrator 6.36). Lý do về bản chất: quy trình xử lý claim ở đây là tuần tự và mọi quyết định về tiền đều suy ra được từ dòng order và policy hiện hành. Model không có quyết định nào để đưa ra mà code chưa đưa ra được, nên thêm tự chủ chỉ thêm chi phí và thêm bề mặt lỗi. Swarm tham chiếu cho thấy điều đó: nó là shape duy nhất có trial fail (R-swarm-C-002-s55, tin số ngày trong ticket), pass rate 0.986, pass^5 0.929, variance 0.000816.

## Có đáng đổi lấy multi-agent không

Với dữ liệu hiện có thì không. Multi-agent không cho pass rate cao hơn: orchestrator bằng workflow ở 1.000, swarm thấp hơn ở 0.986. Trong khi đó cost/success của orchestrator gấp 2.3 lần workflow và swarm có variance khác 0. Nếu một shape multi-agent nhỉnh hơn vài phần trăm pass rate nhưng variance cao hơn, nhóm vẫn giữ workflow, vì đây là luồng ghi tiền: một claim sai theo seed là một refund sai, và pass^5 quan trọng hơn pass rate trung bình.

Quyết định sẽ đảo lại khi một trong các điều kiện sau xuất hiện và được đo trên cùng corpus, cùng seed:

- Claim cần hiểu ngôn ngữ tự do mà code không làm được (ví dụ phải hỏi lại khách để tìm mã đơn, hoặc phân loại bằng chứng hỏng hàng từ mô tả), và workflow tụt dưới ngưỡng 0.75 trong khi single hoặc orchestrator giữ được.
- Việc điều tra tách được thành nhiều nhánh độc lập trên nhiều nguồn dữ liệu, khi đó investigator chạy song song có thể giảm thời gian. Lab này không đo latency nên chưa kết luận được.
- Với model thật, chênh lệch pass^5 giữa orchestrator và workflow lớn hơn độ dao động giữa các seed.

## Trace và bằng chứng

Trace của ba shape ghi các event sau, theo đúng thứ tự xử lý:

- `claim_view`: chỉ hai cờ `found` và `has_order_id`.
- `order_lookup`: `visible`, lý do nếu không thấy đơn, và năm field số/trạng thái của order (`status`, `delay_days`, `shipping_fee_vnd`, `paid_vnd`, `damage_verified`).
- `quote`: số tiền, lý do và danh sách clause do `compute_compensation` trả về.
- `host_refund`: kết quả của `durability.issue_refund` (`ok`, `reason`, `conflict`, số tiền host đã ghi).
- `decision`: `status`, `proposal_amount`, lý do.
- `crash`: điểm crash, ghi trước khi `InjectedCrash` được ném tiếp ra ngoài.
- Riêng single: `thought`, `action` (tên tool), `final`, `refund_history`, `model_final_overruled`.
- Riêng orchestrator: `plan`, `handoff` (bản đã qua `make_handoff`), `investigator` (kết quả tóm lược).

Các field cố ý không ghi:

- `parent_secret` và `raw_headers`: shape không bao giờ đọc hai cột này, vì claim chỉ được đọc qua `get_claim_view`.
- Nội dung ticket: là chữ của người dùng, có thể chứa PII hoặc câu injection. Trace chỉ ghi ticket có nêu số ngày trễ hay không.
- `principal_id`, và `order_id` khi đơn không thuộc principal: không cần để chấm, lại là định danh khách.
- `phone`, `address`, `internal_note`, `item_name`: `lookup_order` không trả về, và trace chỉ chép năm field liệt kê ở trên chứ không chép cả order view.
- Thông báo của exception: nhánh lỗi nội bộ chỉ ghi tên lớp exception, vì thông báo lỗi có thể chứa dữ liệu.

Shape chỉ ghi một file cho mỗi lần chạy, là `traces/<run_id>.json`, nằm trong vùng scanner quét. Nếu sau này trace phải nằm ngoài vùng đó thì không chứng minh được bằng cách "đọc lại log", mà phải chứng minh bằng cấu trúc: (1) mọi đường ghi đi qua một tracer duy nhất chỉ nhận field trong allowlist; (2) test tự động quét mọi artifact tìm canary và PII, như `test_trace_and_result_hold_no_parent_context` trong `src/tests/test_team_shapes.py`; (3) shape không có quyền đọc cột secret ngay từ đầu.

## Giới hạn

MockLLM không phải model sản xuất. Latency để `unavailable`. Không sửa JSON cho đủ 0.75.

- MockLLM cố định theo seed và không bao giờ chọn sai tool, nên variance 0 của single và orchestrator là giới hạn dưới, không phải dự báo cho model thật.
- Bộ public chỉ có 14 claim. Pass rate 1.000 trên 70 trial không suy ra được pass rate trên 200 trial hidden.
- Tự kiểm trên `student_drop/` (`src/reports/hidden_selfcheck.json`, 40 claim × 5 seed × 3 shape) không có nhãn nên không ra pass rate. Nó chỉ cho biết: 0 trial `error`, 0 trial `leak_suspect`, trace đúng contract, và ba shape cho cùng phân bố status (95 `denied`, 90 `resolved`, 10 `escalated`, 5 `needs_info` trên 200 trial). Pass rate hidden chính thức do giảng viên chấm.
- Cost là VND mô phỏng theo `config/pricing.yaml`, không phải hóa đơn API.
- Cột steps đếm số event trong trace, phụ thuộc vào việc mỗi shape ghi chi tiết đến đâu. Nó không so được khối lượng việc giữa các shape; dùng cost, model call và tool call để so.
