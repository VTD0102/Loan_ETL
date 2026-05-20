"""Integration checks for RAG auto-reject and auto-submission flows.

Run from repository root:
    python backend/tests_local/test_rag_auto_flows.py
"""
import sys
import uuid
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from db.session import SessionLocal
from models.user import User
from models.application import LoanApplication
from models.chat import ChatSession, ChatMessage
from schemas.application import ApplicationCreate
from services import application_service, chat_service


def create_test_user(db, email, cccd):
    # Clean up old test user if exists
    user = db.query(User).filter(User.email == email).first()
    if user:
        # Cascade deletes applications/sessions manually to avoid orphan rows
        db.query(LoanApplication).filter(LoanApplication.user_id == user.id).delete(synchronize_session=False)
        db.query(ChatMessage).filter(ChatMessage.session_id.in_(
            db.query(ChatSession.id).filter(ChatSession.user_id == user.id)
        )).delete(synchronize_session=False)
        db.query(ChatSession).filter(ChatSession.user_id == user.id).delete(synchronize_session=False)
        db.delete(user)
        db.commit()

    user = User(
        email=email,
        username="TestPtit",
        password_hash="fakehash",
        cccd=cccd,
        role="customer"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_auto_reject_flow():
    print("--------------------------------------------------")
    print("Testing Auto-Reject Flow...")
    db = SessionLocal()
    db.begin() # Start transaction to isolate database modifications
    try:
        user = create_test_user(db, "test_autoreject@example.com", "123456789012")
        
        # High risk payload (bad debt, very high DTI)
        payload = ApplicationCreate(
            monthly_income=Decimal("1000"),
            loan_amount=Decimal("50000"),
            term=36,
            employment_status="Unemployed",
            dti=Decimal("0.85"),
            is_homeowner=False,
            listing_category=1,
            credit_score=400,
            occupation_type="Other",
            years_employed=Decimal("0"),
            num_bureau_records=5,
            num_active_credit=5,
            total_overdue_amount=Decimal("10000"),
            max_credit_overdue_days=90,
            has_bad_debt=True,
            income_verifiable_flag=False,
            age_years=25,
            gender_male_flag=True,
            education_ordinal=2,
            cnt_children=1,
            cnt_fam_members=2,
            is_married_flag=False,
        )
        
        res = application_service.evaluate(db, user.email, payload)
        
        # Verify status is AUTO_REJECTED
        assert res["status"] == "AUTO_REJECTED", f"Expected AUTO_REJECTED, got {res['status']}"
        assert res["application_id"] is not None, "Application ID should not be None"
        
        # Verify it was saved to DB
        app_in_db = db.query(LoanApplication).filter(LoanApplication.id == res["application_id"]).first()
        assert app_in_db is not None, "Application should be saved in database"
        assert app_in_db.status == "AUTO_REJECTED", f"DB status expected AUTO_REJECTED, got {app_in_db.status}"
        print("-> Auto-Reject Flow passed!")
    finally:
        db.rollback()
        db.close()


def test_rag_auto_submission_flow():
    print("--------------------------------------------------")
    print("Testing RAG Auto-Submission Flow...")
    db = SessionLocal()
    db.begin()
    
    # Mock RAG invoke to avoid external OpenAI API calls
    original_rag_invoke = chat_service._rag_invoke
    
    rag_calls = []
    mock_reply = "Dựa trên hồ sơ bị từ chối của bạn, tôi đề xuất giảm số tiền vay xuống 8000 USD với kỳ hạn 60 tháng. Bạn có đồng ý nộp đơn với phương án này không?"
    
    def fake_rag_invoke(question, context, chat_history, **kwargs):
        rag_calls.append({"question": question, "context": context})
        return {"answer": mock_reply, "source_documents": []}
    
    chat_service._rag_invoke = fake_rag_invoke
    
    try:
        user = create_test_user(db, "test_rag_autosubmit@example.com", "987654321098")
        
        # 1. Create a rejected application for this user
        rejected_app = LoanApplication(
            user_id=user.id,
            status="AUTO_REJECTED",
            monthly_income=Decimal("15000"),
            loan_amount=Decimal("100000"),
            term=12,
            employment_status="Employed",
            occupation_type="Laborers",
            years_employed=Decimal("5"),
            dti=Decimal("0.10"),
            is_homeowner=True,
            listing_category="personal",
            credit_score=780,
            num_bureau_records=0,
            num_active_credit=0,
            total_overdue_amount=Decimal("0"),
            max_credit_overdue_days=0,
            has_bad_debt=False,
            income_verifiable_flag=True,
            age_years=35,
            gender_male_flag=False,
            education_ordinal=4,
            cnt_children=0,
            cnt_fam_members=1,
            is_married_flag=False,
            default_probability=Decimal("0.85"),
            risk_level="High",
            risk_score=15,
            model_version="test-model",
            feature_snapshot={},
            imputed_features=[],
            recommended_amount=Decimal("10000"),
            recommended_term=36,
        )
        db.add(rejected_app)
        db.commit()
        
        all_apps = db.query(LoanApplication).filter(LoanApplication.user_id == user.id).all()
        print("ALL APPS FOR USER:", [(a.id, a.loan_amount, a.status) for a in all_apps])
        
        # 2. Start a chat session
        session = ChatSession(user_id=user.id)
        db.add(session)
        db.commit()
        db.refresh(session)
        
        # 3. Simulate user asking for suggestion
        user_message = "Đổi kỳ hạn giúp tôi"
        res1 = chat_service.send(db, user.email, user_message, session_id=session.id)
        
        # Verify suggestion response was received and pending action was created
        print("CHAT RESPONSE 1:", res1["response"])
        db.refresh(session)
        print("PENDING ACTION IN SESSION:", session.pending_action)
        if session.pending_action is None:
            # Let's run the tool directly and print its results
            from services import loan_adjustment_tool
            direct_res = loan_adjustment_tool.find_best_reapplication_option(db, user.id)
            print("DIRECT TOOL STATUS:", direct_res.status)
            print("DIRECT TOOL MESSAGE:", direct_res.message)
            print("DIRECT TOOL PROPOSAL:", direct_res.proposal)
            print("DIRECT TOOL BEST OBSERVED:", direct_res.best_observed)

        assert session.pending_action is not None, "Pending action should be created"
        assert session.pending_action["type"] == "loan_term_adjustment"
        assert session.pending_action["status"] == "pending_confirmation"
        assert session.pending_action["proposal"] is not None
        proposed_amount = Decimal(session.pending_action["proposal"]["loan_amount"])
        proposed_term = int(session.pending_action["proposal"]["term"])
        
        # 4. Simulate user saying "đồng ý" to confirm the proposal
        confirm_message = "Đồng ý nộp đơn"
        res2 = chat_service.send(db, user.email, confirm_message, session_id=session.id)
        
        # Verify the chatbot response confirms submission
        assert "Đã nộp lại hồ sơ mới" in res2["response"]
        
        # Verify pending action is cleared
        db.refresh(session)
        assert session.pending_action is None, "Pending action should be cleared"
        
        # Verify that a new loan application is created in database
        apps = db.query(LoanApplication).filter(
            LoanApplication.user_id == user.id,
            LoanApplication.status != "AUTO_REJECTED"
        ).all()
        
        assert len(apps) == 1, f"Expected 1 new application, found {len(apps)}"
        new_app = apps[0]
        assert new_app.loan_amount == proposed_amount
        assert new_app.term == proposed_term
        assert new_app.status == "PENDING_REVIEW"
        
        print("-> RAG Auto-Submission Flow passed!")
    finally:
        chat_service._rag_invoke = original_rag_invoke
        db.rollback()
        db.close()


if __name__ == "__main__":
    test_auto_reject_flow()
    test_rag_auto_submission_flow()
    print("--------------------------------------------------")
    print("All auto flow tests passed successfully!")
