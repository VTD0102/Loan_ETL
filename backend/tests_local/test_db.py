import traceback
from db.session import SessionLocal
from sqlalchemy import text
db = SessionLocal()
try:
    cols = db.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='chat_messages';")).fetchall()
    print("chat_messages:", cols)
    
    cols2 = db.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='chat_sessions';")).fetchall()
    print("chat_sessions:", cols2)
except Exception as e:
    traceback.print_exc()
finally:
    db.close()
