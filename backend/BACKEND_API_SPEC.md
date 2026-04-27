# 📚 CreditIntel Backend API Specification

This document provides a comprehensive summary of all available REST endpoints in the CreditIntel system, including their required inputs, expected outputs, and authentication rules.

---

## 🔐 1. Authentication Module

### 1.1 Register Customer
Create a new user account. Role is strictly assigned as `customer`.
- **Endpoint**: `POST /auth/register`
- **Auth Required**: No (Public)
- **Input Schema** (`UserCreate`):
  ```json
  {
    "email": "user@example.com",
    "username": "johndoe",
    "password": "securepassword123"
  }
  ```
- **Response** `201 Created`: Returns JWT Token (`access_token`, `token_type`)

### 1.2 Login
Authenticate an existing user.
- **Endpoint**: `POST /auth/login`
- **Auth Required**: No (Public)
- **Input Schema** (`UserLogin`):
  ```json
  {
    "email": "user@example.com",
    "password": "securepassword123"
  }
  ```
- **Response** `200 OK`: Returns JWT Token

---

## 👤 2. Customer Application Module
*All endpoints here require standard Customer Bearer Token (`require_customer`).*

### 2.1 Submit Application
Creates a new loan application. Auto-triggers ML Prediction internally to determine status (`PENDING_REVIEW` or `AUTO_REJECTED`).
- **Endpoint**: `POST /applications/submit`
- **Input Schema** (`ApplicationCreate`):
  ```json
  {
    "monthly_income": 5000,
    "loan_amount": 10000,
    "term": 24,
    "employment_status": "Employed",
    "dti": 0.3,
    "is_homeowner": true,
    "listing_category": 1,
    "credit_score": 700
  }
  ```
- **Response** `201 Created`: Returns App ID, resulting Status, and ML Predictions.

### 2.2 List My Applications
Retrieve all applications belonging to the current user, sorted by newest first.
- **Endpoint**: `GET /applications/me`
- **Response** `200 OK`: `List[ApplicationSummary]`

### 2.3 Get Application Details
Fetch full details of a specific application. Enforces strict Ownership Check.
- **Endpoint**: `GET /applications/{app_id}`
- **Response** `200 OK`: `ApplicationRead`

### 2.4 Submit Personal Information
Supply personal ID details if the application status is strictly `AWAITING_INFO`.
- **Endpoint**: `POST /applications/{app_id}/personal-info`
- **Input Schema** (`PersonalInfoCreate`):
  ```json
  {
    "full_name": "John Doe",
    "id_card_number": "123456789012",
    "phone": "0901234567",
    "email": "user@example.com",
    "date_of_birth": "1990-01-01",
    "address": "123 Street, NY"
  }
  ```
- **Response** `201 Created`: `PersonalInfoRead`

---

## 🛡️ 3. Admin Module
*All endpoints here require Admin Bearer Token (`require_admin`).*

### 3.1 Dashboard Summary
Get count of applications by status for the current day.
- **Endpoint**: `GET /admin/dashboard/summary`
- **Response** `200 OK`: `{"today_total": ..., "pending_review": ...}`

### 3.2 Risk Distribution
Get aggregation of all applications grouped by Risk Level.
- **Endpoint**: `GET /admin/dashboard/risk-distribution`
- **Response** `200 OK`: `[{"risk_level": "Low", "count": 10}, ...]`

### 3.3 List Pending Applications
Paginated list of all FIFO pending applications.
- **Endpoint**: `GET /admin/applications/pending?page=1&limit=20`
- **Response** `200 OK`: `List[ApplicationPendingSummary]`

### 3.4 All Applications Master List
Paginated full list with dynamic query filtering.
- **Endpoint**: `GET /admin/applications?status=PENDING_REVIEW&from_date=2026-04-01`
- **Response** `200 OK`: `List[ApplicationRead]`

### 3.5 Approve Application
Moves application status to `AWAITING_INFO`.
- **Endpoint**: `POST /admin/applications/{app_id}/approve`
- **Response** `200 OK`: `ApplicationRead`

### 3.6 Reject Application
Moves application status to `ADMIN_REJECTED`.
- **Endpoint**: `POST /admin/applications/{app_id}/reject`
- **Input Schema** `AdminReject`: `{"admin_note": "Score too low"}` (Optional)
- **Response** `200 OK`: `ApplicationRead`

### 3.7 Get Application Personal Info
Retrieve sensitive submitted personal info.
- **Endpoint**: `GET /admin/applications/{app_id}/personal-info`
- **Response** `200 OK`: `PersonalInfoRead` (or `404 Not Found` if missing)

---
