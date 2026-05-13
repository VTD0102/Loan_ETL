import sys
from sqlalchemy import create_engine, Column, Integer, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    applications = relationship("Application", foreign_keys="[Application.user_id]")

class Application(Base):
    __tablename__ = 'applications'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))

engine = create_engine('sqlite:///:memory:')
try:
    Base.metadata.create_all(engine)
    print("SUCCESS")
except Exception as e:
    print("ERROR:", e)
