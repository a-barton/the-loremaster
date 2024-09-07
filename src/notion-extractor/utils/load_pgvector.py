"""
Adapted from https://github.com/johntday/notion-load/blob/main/notion_load/qdrant_util.py
"""

import os
import re

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores.pgvector import PGVector

from .MyNotionDBLoader import MyNotionDBLoader

from .load_util import split_documents


def load_pgvector(args):
    """Fetch documents from Notion"""

    SECRET__NOTION_TOKEN = os.getenv("SECRET__NOTION_TOKEN")
    NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
    COLLECTION_NAME = os.getenv("COLLECTION_NAME")
    POSTGRES_USER = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
    POSTGRES_DBNAME = os.getenv("POSTGRES_DBNAME")
    POSTGRES_HOST = os.getenv("POSTGRES_HOST")
    POSTGRES_PORT = os.getenv("POSTGRES_PORT")

    notion_loader = MyNotionDBLoader(
        SECRET__NOTION_TOKEN,
        NOTION_DATABASE_ID,
        args.verbose,
        validate_missing_content=True,
        validate_missing_metadata=["id"],
        metadata_filter_list=["id", "name", "tags", "created time", "last modified"],
    )
    original_docs = notion_loader.load()
    print(f"\nFetched {len(original_docs)} documents from Notion")

    # Split documents into chunks
    chunked_docs = split_documents(original_docs)

    # Add metadata field to identify original docs
    for doc in original_docs:
        doc.metadata["embedding_type"] = "document"

    # Extract session numbers from names of session notes docs
    session_notes = [doc for doc in original_docs if "Session Notes" in doc.metadata["tags"]]
    for doc in session_notes:
        doc.metadata["session_number"] = int(re.findall(r"\d+", doc.metadata["name"])[0])

    # Find doc with latest created date and set metadata flag against it
    latest_session_notes = max(session_notes, key=lambda d: d.metadata["created time"])
    latest_session_notes.metadata["is_latest"] = True

    # Embed vectors
    embeddings_model = HuggingFaceEmbeddings()

    connection_string = f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DBNAME}"
    
    db = PGVector.from_existing_index(
        embedding=embeddings_model,
        collection_name=COLLECTION_NAME,
        connection_string=connection_string,
        pre_delete_collection=args.reset,
    )

    db.add_documents(documents=chunked_docs)
    db.add_documents(documents=original_docs)
