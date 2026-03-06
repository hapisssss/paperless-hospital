from configs.db import Base
from sqlalchemy import BigInteger, Column, String, Text, Integer, DateTime

class KlaimBpjs(Base):
    __tablename__ = "klaim_bpjs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_name = Column(Text)
    document_extraction = Column(Text)
    retrieval_content_query = Column(Text)
    prompt = Column(Text)
    response = Column(Text)
    token_request = Column(BigInteger)
    token_response = Column(BigInteger)
    token_counts = Column(BigInteger)
    timestamp = Column(DateTime)

# from sqlalchemy.dialects.mysql import LONGTEXT
# from configs.db import Base
# from sqlalchemy import BigInteger, Column, String, Text, Integer, DateTime

# class KlaimBpjs(Base):
#     __tablename__ = "klaim_bpjs"
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     document_name = Column(Text)
#     document_extraction = Column(LONGTEXT)
#     retrieval_content_query = Column(LONGTEXT)
#     prompt = Column(LONGTEXT)
#     response = Column(LONGTEXT)
#     token_request = Column(BigInteger)
#     token_response = Column(BigInteger)
#     token_counts = Column(BigInteger)
#     timestamp = Column(DateTime)