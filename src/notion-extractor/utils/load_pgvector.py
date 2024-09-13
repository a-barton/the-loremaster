"""
Adapted from https://github.com/johntday/notion-load/blob/main/notion_load/qdrant_util.py
"""

import os
import re
from datetime import datetime

from langchain_huggingface import HuggingFaceEmbeddings
#from langchain_community.vectorstores.pgvector import PGVector
from langchain_postgres import PGVector
from langchain_postgres.vectorstores import PGVector

import psycopg
from psycopg.rows import namedtuple_row

from typing import List
from langchain.docstore.document import Document

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

    db_config = {
        "host": POSTGRES_HOST,
        "port": POSTGRES_PORT,
        "dbname": POSTGRES_DBNAME,
        "user": POSTGRES_USER,
        "password": POSTGRES_PASSWORD,
    }

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

    if args.incremental:
        load_incremental_docs(
            original_docs=original_docs,
            collection_name=COLLECTION_NAME,
            db_config=db_config,
            reset=args.reset,
        )
    else:
        initialise_and_load_docs(
            original_docs=original_docs, 
            collection_name=COLLECTION_NAME,
            db_config=db_config,
        )

def load_incremental_docs(
    original_docs: List[Document],
    collection_name: str,
    db_config: dict,
    reset: bool,
):
    # Determine which are new or updated docs
    new_docs, updated_docs = determine_docs_to_load(
        original_docs,
        collection_name,
        db_config,
    )

    # Leverage Huggingface embeddings model
    embeddings_model = HuggingFaceEmbeddings()

    connection_string = f"postgresql+psycopg://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['dbname']}"
    
    # Initialise existing vector store
    db = PGVector.from_existing_index(
        embedding=embeddings_model,
        collection_name=collection_name,
        connection=connection_string,
        pre_delete_collection=reset,
    )

    print(f"length of new_docs: {len(new_docs)}")
    if new_docs:
        chunked_new_docs = prepare_chunks(new_docs)
        db.add_documents(documents=chunked_new_docs)
        db.add_documents(documents=new_docs)

    print(f"length of updated_docs: {len(updated_docs)}")
    if updated_docs:
        chunked_updated_docs = prepare_chunks(updated_docs)
        delete_old_chunks(
            docs=updated_docs,
            db_config=db_config,
            vector_db=db,
            collection_name=collection_name,
        )
        db.add_documents(documents=chunked_updated_docs)
        db.add_documents(documents=updated_docs)

    
    
def initialise_and_load_docs(
    original_docs: List[Document], 
    collection_name: str,
    db_config: dict,
):
    # Split documents into chunks
    chunked_docs = prepare_chunks(original_docs)

    # Leverage Huggingface embeddings model
    embeddings_model = HuggingFaceEmbeddings()

    connection_string = f"postgresql+psycopg://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['dbname']}"
    
    db = PGVector.from_documents(
        documents=chunked_docs,
        embedding=embeddings_model,
        collection_name=collection_name,
        connection=connection_string,
        use_jsonb=True,
    )
    db.add_documents(original_docs)
    
def prepare_chunks(
    docs: List[Document],
):
    # Split documents into chunks
    chunked_docs = split_documents(docs)

    # Add metadata field to identify original docs
    for doc in docs:
        doc.metadata["embedding_type"] = "document"

    # Extract session numbers from names of session notes docs
    if any([True for doc in docs if "Session Notes" in doc.metadata["tags"]]):
        session_notes = [doc for doc in docs if "Session Notes" in doc.metadata["tags"]]
        for doc in session_notes:
            doc.metadata["session_number"] = int(re.findall(r"\d+", doc.metadata["name"])[0])

        # Find doc with latest created date and set metadata flag against it
        latest_session_notes = max(session_notes, key=lambda d: d.metadata["created time"])
        latest_session_notes.metadata["is_latest"] = True

    return chunked_docs
    


def determine_docs_to_load(
    notion_docs: List[Document],
    collection_name: str, 
    db_config: dict
):
    conn = psycopg.connect(**db_config)
    cur = conn.cursor(row_factory=namedtuple_row)

    cur.execute(
        f"""
        SELECT embeddings.cmetadata->>'id' AS page_id,
                (embeddings.cmetadata->>'last modified')::TIMESTAMP AS last_modified_timestamp
        FROM langchain_pg_embedding embeddings
        JOIN langchain_pg_collection collection
            ON embeddings.collection_id = collection.uuid
        WHERE collection.name = '{collection_name}'
        AND embeddings.cmetadata->>'embedding_type' = 'document';
        """
    )
    existing_docs = cur.fetchall()

    cur.close()
    conn.close()

    existing_doc_modified_timestamps = {
        doc.page_id: doc.last_modified_timestamp for doc in existing_docs
    }

    new_docs = []
    updated_docs = []
    for doc in notion_docs:
        if doc.metadata["id"] not in existing_doc_modified_timestamps.keys():
            new_docs.append(doc)
        elif datetime.strptime(doc.metadata["last modified"], "%Y-%m-%dT%H:%M:%S.%f%z").replace(tzinfo=None) > existing_doc_modified_timestamps[doc.metadata["id"]]:
            updated_docs.append(doc)

    return new_docs, updated_docs

def delete_old_chunks(
    docs: List[Document],
    db_config: dict,
    vector_db: PGVector, 
    collection_name: str
):

    # Retrieve IDs of all chunks belonging to one of the nominated docs
    conn = psycopg.connect(**db_config)
    cur = conn.cursor()

    cur.execute(
        f"""
        SELECT embeddings.id
        FROM langchain_pg_embedding embeddings
        JOIN langchain_pg_collection collection
            ON embeddings.collection_id = collection.uuid
        WHERE collection.name = '{collection_name}'
        AND embeddings.cmetadata->>'embedding_type' = 'chunk'
        AND embeddings.cmetadata->>'id' = ANY(ARRAY{[[doc.id for doc in docs]]});
        """
    )
    chunk_ids_to_delete = list(cur.fetchall())

    vector_db.delete(
        ids=[chunk_id[0] for chunk_id in chunk_ids_to_delete],
    )

    cur.close()
    conn.close()