# Tổng quan Dataset Home Credit Credit Risk Model Stability

## 1\. Thống kê các bảng dữ liệu

| Bảng | Vai trò | Số cột | Số bản ghi | Khóa chính |
| --- | --- | --- | --- | --- |
| train_base | Bảng trung tâm chứa nhãn dự đoán | 5   | 1,526,659 | case_id |
| train_static_0 | Thông tin tín dụng tổng hợp của khách hàng | 168 | 1,526,659 | case_id |
| train_static_cb_0 | Thông tin tổng hợp từ Credit Bureau | 53  | 1,500,476 | case_id |
| train_person_1 | Thông tin cá nhân và người liên quan | 37  | 2,973,991 | case_id |
| train_applprev_1 | Lịch sử các đơn vay trước đây | 41  | 6,525,979 | case_id |
| train_credit_bureau_a_1 | Chi tiết lịch sử tín dụng từ Credit Bureau | 79  | 15,940,537 | case_id |

## 2\. Bảng train_base

**Số cột:** 5  
**Số bản ghi:** 1,526,659

| STT | Tên cột |
| --- | --- |
| 1   | case_id |
| 2   | date_decision |
| 3   | MONTH |
| 4   | WEEK_NUM |
| 5   | target |

## 3\. Bảng train_static_0

**Số cột:** 168  
**Số bản ghi:** 1,526,659

### Nhóm thông tin tín dụng

- credamount_770A
- currdebt_22A
- currdebtcredtyperange_828A
- disbursedcredamount_1113A
- totaldebt_9A
- totalsettled_863A
- price_1097A

### Nhóm thông tin trả góp

- annuity_780A
- annuitynextmonth_57A
- monthsannuity_845L
- maxannuity_159A
- maxannuity_4075009A

### Nhóm lịch sử quá hạn (DPD)

- actualdpdtolerance_344P
- avgdbddpdlast24m_3658932P
- avgdbddpdlast3m_4187120P
- avgdpdtolclosure24_3658938P
- maxdpdlast3m_392P
- maxdpdlast6m_474P
- maxdpdlast9m_1059P
- maxdpdlast12m_727P
- maxdpdlast24m_143P

### Nhóm thông tin khách hàng

- bankacctype_710L
- cardtype_51L
- credtype_322L
- paytype_783L
- paytype1st_925L
- typesuite_864L

### Nhóm thời gian

- datefirstoffer_1144D
- lastapplicationdate_877D
- lastapprdate_640D
- lastrejectdate_50D
- lastrepayingdate_696D
- validfrom_1069D

Tổng cộng: 168 cột.

## 4\. Bảng train_static_cb_0

**Số cột:** 53  
**Số bản ghi:** 1,500,476

### Một số cột tiêu biểu

- case_id
- assignmentdate_238D
- birthdate_574D
- days30_165L
- days90_310L
- days180_256L
- days360_512L
- numberofqueries_373L
- pmtaverage_3A
- pmtcount_693L
- pmtssum_45A
- riskassesment_302T
- riskassesment_940T

Tổng cộng: 53 cột.

## 5\. Bảng train_person_1

**Số cột:** 37  
**Số bản ghi:** 2,973,991

| STT | Tên cột |
| --- | --- |
| 1   | case_id |
| 2   | birth_259D |
| 3   | birthdate_87D |
| 4   | childnum_185L |
| 5   | contaddr_district_15M |
| 6   | contaddr_matchlist_1032L |
| 7   | contaddr_smempladdr_334L |
| 8   | contaddr_zipcode_807M |
| 9   | education_927M |
| 10  | empl_employedfrom_271D |
| 11  | empl_employedtotal_800L |
| 12  | empl_industry_691L |
| 13  | empladdr_district_926M |
| 14  | empladdr_zipcode_114M |
| 15  | familystate_447L |
| 16  | gender_992L |
| 17  | housetype_905L |
| 18  | housingtype_772L |
| 19  | incometype_1044T |
| 20  | isreference_387L |
| 21  | language1_981M |
| 22  | mainoccupationinc_384A |
| 23  | maritalst_703L |
| 24  | num_group1 |
| 25  | personindex_1023L |
| 26  | persontype_1072L |
| 27  | persontype_792L |
| 28  | registaddr_district_1083M |
| 29  | registaddr_zipcode_184M |
| 30  | relationshiptoclient_415T |
| 31  | relationshiptoclient_642T |
| 32  | remitter_829L |
| 33  | role_1084L |
| 34  | role_993L |
| 35  | safeguarantyflag_411L |
| 36  | sex_738L |
| 37  | type_25L |

## 6\. Bảng train_applprev_1

**Số cột:** 41  
**Số bản ghi:** 6,525,979

### Các cột chính

- case_id
- actualdpd_943P
- annuity_853A
- approvaldate_319D
- credamount_590A
- currdebt_94A
- outstandingdebt_522A
- dateactivated_425D
- dtlastpmt_581D
- education_1138M
- familystate_726L
- isdebitcard_527L
- mainoccupationinc_437A
- rejectreason_755M
- status_219L
- tenor_203L

Tổng cộng: 41 cột.

## 7\. Bảng train_credit_bureau_a_1

**Số cột:** 79  
**Số bản ghi:** 15,940,537

### Các cột chính

- case_id
- credlmt_230A
- credlmt_935A
- debtoutstand_525A
- debtoverdue_47A
- dpdmax_139P
- dpdmax_757P
- financialinstitution_382M
- financialinstitution_591M
- instlamount_768A
- interestrate_508L
- monthlyinstlamount_332A
- nominalrate_281L
- outstandingamount_354A
- overdueamount_31A
- purposeofcred_426M
- residualamount_488A
- totalamount_6A
- totaldebtoverduevalue_178A
- totaloutstanddebtvalue_39A

Tổng cộng: 79 cột.

## 8\. Quan hệ giữa các bảng

train_base  
│  
├── train_static_0  
├── train_static_cb_0  
├── train_person_1  
├── train_applprev_1  
└── train_credit_bureau_a_1

Tất cả các bảng đều liên kết với nhau thông qua khóa case_id.