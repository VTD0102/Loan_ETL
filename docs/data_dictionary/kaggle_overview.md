# Kaggle Home Credit Credit Risk Model Stability - Dataset Overview
- Tổng dung lượng: ~27GB thô.
- Định dạng: Parquet chia làm 138 file để tối ưu I/O.
- Tính chất: Dữ liệu quan hệ đa bảng (Multi-table relational).
- Các bảng chính: 
  + `train_base.parquet` (depth=0, chứa target `is_default`). Tỷ lệ default rate cực thấp: ~3.14% (Mất cân bằng nhãn trầm trọng).
  + Các bảng tĩnh (static): `train_static_0`, `train_static_cb_0` (depth=0).
  + Các bảng lịch sử (depth=1): `train_person_1` (nhân khẩu), `train_credit_bureau_a_1` (lịch sử CIC), `train_applprev_1` (lịch sử đơn vay).