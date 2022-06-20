from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy import Column, DateTime, String, Integer, Float
from sqlalchemy.orm import declarative_base

engine = create_engine('sqlite:///db.sqlite', echo=False)
Base = declarative_base()


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=True)
    created_date = Column(DateTime(), default=datetime.now)
    latitude = Column(Float, default=None)
    longitude = Column(Float, default=None)
    city = Column(String, nullable=True)
    last_update = Column(DateTime())
    last_message = Column(String, default=None)


Base.metadata.create_all(engine)
