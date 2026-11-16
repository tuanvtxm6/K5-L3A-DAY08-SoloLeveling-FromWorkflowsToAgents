# Team

## Thông tin nhóm

- Tên nhóm: SoloLeveling
- Lớp: L3A
- Repo nhóm: `K5-L3A-DAY08-SoloLeveling-FromWorkflowsToAgents` (xem [SUBMISSION.md](SUBMISSION.md))
- URL repo, nhánh nộp, commit chốt: https://github.com/tuanvtxm6/K5-L3A-DAY08-SoloLeveling-FromWorkflowsToAgents, nhánh `main`, commit chốt ghi trong `report/team/decision_adr.md`

## Thành viên

| STT | Họ tên | MSSV | Email | GitHub | Vai trò |
| --: | ------ | ---- | ----- | ------ | ------- |
|   1 | Lục Anh Tuấn | 2A202603634 | 26ai.tuanla2@vinuni.edu.vn | tuanvtxm6 | Làm cả nhóm: workflow, single, orchestrator, handoff, crash, eval, report |

Gợi ý chia vai:

- Nhóm 6 người: integration; workflow; single agent; orchestrator; ledger/policy/crash; eval/report.
- Nhóm 4 người: workflow + integration; single; orchestrator + handoff; ledger + evaluation.

## Bảng đóng góp

`python -m lab8.check_submission` đọc bảng này bằng máy: giữ nguyên tiêu đề `## Bảng đóng góp` và các cột. Mỗi người một dòng: commit có nội dung và ít nhất một test đã thêm hoặc sửa.

| Người | Vai | Commit | Test đã thêm hoặc sửa |
| --- | --- | --- | --- |
| Lục Anh Tuấn | Cả ba shape, test, benchmark, báo cáo | `7d579cf` feat: implement workflow, single and orchestrator shapes | `src/tests/test_team_shapes.py` (112 test: ticket nói dối, injection, approval mượn, 3 điểm crash, trace sạch, trần 8 bước, handoff allowlist) |

## Cá nhân

Mỗi thành viên đồng thời tạo một báo cáo riêng trong `report/` theo dạng:

```text
report/team/MSSV_HoTen.md
```

Ví dụ: `report/team/20241234_NguyenVanAn.md`.

Sao chép mục dưới đây cho từng thành viên.

## 2A202603634_LucAnhTuan

### Phần việc phụ trách

- Nhóm một người: ba shape `workflow`, `single`, `orchestrator`; test; benchmark và crash suite; ADR, research card, báo cáo nhóm.

### Đóng góp cụ thể

- Viết `src/lab8/shapes/workflow.py`, `single.py`, `orchestrator.py` theo cùng chữ ký `run_claim`.
- Thêm `src/tests/test_team_shapes.py` (112 test trong cổng host).
- Sinh `src/reports/benchmark.json` và `src/reports/crash.json` bằng công cụ của lab.

### Bằng chứng

- Commit `7d579cf` (code, test, report JSON) và `16fdeac` (báo cáo).
- Báo cáo cá nhân: `report/team/2A202603634_LucAnhTuan.md`.
