# ML Backend Frontend Integration

Ngay 2026-05-13, da ket noi lai cac model hien co trong `machinelearning/ml/models` voi backend va frontend.

## Da thuc hien

- Cap nhat `backend/services/ml_service.py` de dung truc tiep `machinelearning/ml/models/customer_risk_model.pkl`, bo fallback mock cu.
- Chuan hoa input tu form frontend sang schema model:
  - `dti` nhap dang phan tram se duoc doi ve ty le 0-1 khi predict.
  - `listing_category` ho tro ca label frontend va ma so model.
  - `is_homeowner` doi ve 0/1.
- Chuan hoa output ML tra ve:
  - `default_probability`
  - `risk_level` theo `LOW`, `MEDIUM`, `HIGH`
  - `risk_score` la diem rui ro 0-100, khop voi UI admin.
  - `recommended_amount`, `recommended_term`
- Bat endpoint preview `/predict` trong `backend/main.py`.
- Cap nhat API submit don de tra ket qua ML ca trong `prediction` va top-level, giup frontend hien modal dung du lieu.
- Cap nhat `backend/services/admin_service.py` de response admin list/detail co them `user_email` va `user_username`, khop voi cac man admin frontend dang doc.
- Cap nhat schema application de chap nhan `listing_category` dang chuoi hoac so, va khai bao cac field user bo sung cho response admin.
- Cap nhat `backend/services/credit_score_service.py` de build du 25 feature ma `scorecard_model.pkl` hien tai yeu cau.
- Lam nhe `backend/services/__init__.py` de import tung service khong keo theo config/auth dependency khong can thiet khi test ML.

## Kiem tra da chay

- `backend`: `python tests_local/test_ml.py`
  - Ket qua mau: `default_probability=0.1087`, `risk_level=LOW`, `risk_score=11`.
- `backend`: `python -m compileall api services schemas models core`
- `frontend`: `npm run build`
  - Build thanh cong, chi con canh bao chunk lon cua Vite.

## Luu y

- Da chay `npm install` trong `frontend/` de cai dependency local truoc khi build.
- Endpoint `/credit-score/me` van can du lieu user/application that trong database de chay day du.
