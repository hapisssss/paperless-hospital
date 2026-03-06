from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

DB_DIR = os.getenv('db_dir', './sqlite_databases')
DB_NAME = os.getenv('db_name')

if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR)

db_filename = f"{DB_NAME}.db"
db_path = os.path.join(DB_DIR, db_filename)

SQLALCHEMY_DATABASE_URL = f"sqlite:///{db_path}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# from fastapi import Request, HTTPException
# from sqlalchemy import create_engine
# from sqlalchemy.ext.declarative import declarative_base
# from sqlalchemy.orm import sessionmaker
# from dotenv import load_dotenv
# import os

# load_dotenv()

# DB_DIR = os.getenv('db_dir', './sqlite_databases')
# DB_NAME = os.getenv('db_name')

# if not os.path.exists(DB_DIR):
#     os.makedirs(DB_DIR)

# def get_db():
#     db_filename = f"{DB_NAME}.db"
#     db_path = os.path.join(DB_DIR, db_filename)
    
#     SQLALCHEMY_DATABASE_URL = f"sqlite:///{db_path}"

#     engine = create_engine(
#         SQLALCHEMY_DATABASE_URL, 
#         connect_args={"check_same_thread": False},
#         pool_pre_ping=True
#     )
#     SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()

# Base = declarative_base()