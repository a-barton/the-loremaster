"""
Adapted from https://github.com/johntday/notion-load/blob/main/notion_load/qdrant_util.py
"""

import os
import uuid

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores.pgvector import PGVector
from langchain.schema import Document

from .MyNotionDBLoader import MyNotionDBLoader

from .load_util import split_documents


def load_pgvector(args):
    """Fetch documents from Notion"""
    notion_loader = MyNotionDBLoader(
        os.getenv("NOTION_TOKEN"),
        os.getenv("NOTION_DATABASE_ID"),
        args.verbose,
        validate_missing_content=True,
        validate_missing_metadata=['id'],
        metadata_filter_list=['id', 'title', 'tags', 'version', 'myid'],
    )
    original_docs = notion_loader.load()
    print(f"\nFetched {len(original_docs)} documents from Notion")

    """Split documents into chunks"""
    chunked_docs = split_documents(original_docs)
    print(chunked_docs)

    """Embed vectors"""
    embeddings_model = HuggingFaceEmbeddings()

    connection_string = f"postgresql+psycopg2://postgres:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:5432/postgres"
    collection_name = os.getenv("COLLECTION_NAME")
    db = PGVector.from_documents(
        embedding=embeddings_model,
        documents=chunked_docs,#[d for d in chunked_docs],
        collection_name=collection_name,
        connection_string = connection_string,
    )

    id_key = "doc_id"
    doc_ids = [uuid.uuid4().hex for _ in range(len(chunked_docs))]
    documents_with_ids = [Document(page_content=doc.page_content, metadata={'id': doc_id}) for doc, doc_id in zip(original_docs, doc_ids)]
    db.add_documents(documents_with_ids)

    similar = db.similarity_search_with_score("What artifact did Tandris give Veren?", k=3)
    print("SIMILARITY SEARCH RESULTS:")
    print(similar)

    print("Finished loading documents")
