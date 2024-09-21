from typing import Any, Dict
import psycopg
from psycopg.rows import namedtuple_row

from langchain.chains.llm import LLMChain
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.chains.question_answering import load_qa_chain

#from langchain_community.vectorstores.pgvector import PGVector
from langchain_postgres import PGVector
from langchain_postgres.vectorstores import PGVector
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.prompts import PromptTemplate
from langchain.chains import ConversationalRetrievalChain
from langchain.chains.conversational_retrieval.prompts import CONDENSE_QUESTION_PROMPT

from langchain_community.chat_models import ChatOpenAI

lore_prompt_template = """SYSTEM: You are a loremaster with knowledge of the setting and world of a Dungeons and Dragons campaign, and answser user questions about the history of the setting and previous events that have transpired in the course of the campaign.
---
Stylise your answers as though you are roleplaying a wise old sage or loremaster who is providing wisdom to fantasy characters in the Dungeons and Dragons campaign.
Use the following pieces of context to answer the question at the end. If you don't know the answer, just say that you don't know, don't try to make up an answer.
Ensure the answer fits within a 2000 character limit, and try to AVOID beginning every answer with "Ah, ...".

{context}

Question: {question}
Loremaster's Answer:"""

LAST_SESSION_PROMPT_TEMPLATE = """SYSTEM: You are a loremaster with knowledge of the setting and world of a Dungeons and Dragons campaign.
Your job is to synthesise a summary of what happened in the last session of the story/campaign, given a clinical summary of said session (and a collection of summaries of sessions before that for additional context).
---
Stylise your answers as though you are roleplaying a charismatic storyteller/bard who is regaling the fantasy characters in the Dungeons and Dragons campaign with a tale of the exploits in the previous session.
Use the following pieces of context to answer the question at the end. If you don't know the answer, just say that you don't know, don't try to make up an answer.
Ensure the answer fits within a 2000 character limit, and try to AVOID beginning every answer with "Ah, ...".

--- CONTEXT - PREVIOUS SESSION SUMMARIES ---

{previous_summaries_context}

--- CONTEXT - LAST SESSION SUMMARY ---

{last_session_context}

--- STORY OF LAST SESSION BEGINS ---

Question: Tell me the story of what happened in the last session.
Storyteller's Answer:"""

LORE_QA_PROMPT = PromptTemplate(
    template=lore_prompt_template, input_variables=["context", "question"]
)

async def prompt_rag_flow(
    query,
    config,
    model_name="gpt-4o",
    temperature=0.5,
    k=5,
    search_type="similarity",
    history="",
    verbose=False,
) -> Dict[str, Any]:

    # Establish vector DB and retriever
    print("rag.py -- Establishing vector DB")
    embeddings = HuggingFaceEmbeddings()
    collection_name = config["COLLECTION_NAME"]
    vectors = PGVector.from_existing_index(
        embedding=embeddings,
        collection_name=collection_name,
        connection=f"postgresql+psycopg://{config['POSTGRES_USER']}:{config['POSTGRES_PASSWORD']}@{config['POSTGRES_HOST']}:{config['POSTGRES_PORT']}/{config['POSTGRES_DBNAME']}",
    )

    retriever = vectors.as_retriever(search_type=search_type, search_kwargs={"k": k, "filter": {"embedding_type":"document"}})

    # Construct a ConversationalRetrievalChain with a streaming llm for combine docs
    # and a separate, non-streaming llm for question generation
    print("rag.py -- Establishing OpenAI connection")
    llm = ChatOpenAI(temperature=temperature, model_name=model_name, api_key=config["OPENAI_API_KEY"])
    streaming_llm = ChatOpenAI(
        streaming=True,
        model_name=model_name,
        callbacks=[StreamingStdOutCallbackHandler()],
        temperature=temperature,
        api_key=config["OPENAI_API_KEY"],
    )

    question_generator = LLMChain(
        llm=llm, prompt=CONDENSE_QUESTION_PROMPT, verbose=verbose
    )
    doc_chain = load_qa_chain(
        streaming_llm,
        chain_type="stuff",
        prompt=LORE_QA_PROMPT,
        verbose=verbose,
    )

    qa = ConversationalRetrievalChain(
        retriever=retriever,
        combine_docs_chain=doc_chain,
        question_generator=question_generator,
        verbose=verbose,
        return_source_documents=True,
    )

    result = qa({"question": query, "chat_history": history})

    return result["answer"]

async def prompt_rag_flow_last_session(
    config,
    n_previous_sessions_context=5,
    model_name="gpt-4o",
    temperature=0.5,
    verbose=False,
) -> Dict[str, Any]:

    collection_name = config["COLLECTION_NAME"]
    
    # Connect directly to vector DB to retrieve documents based on metadata rather than vector search
    conn = psycopg.connect(
        host=config["POSTGRES_HOST"],
        user=config["POSTGRES_USER"],
        password=config["POSTGRES_PASSWORD"],
        port=config["POSTGRES_PORT"],
        dbname=config["POSTGRES_DBNAME"]
    )
    cur = conn.cursor(row_factory=namedtuple_row)

    # Retrieve the most recent session summary
    cur.execute(
        # f"""
        # SELECT embeddings.*
        # FROM langchain_pg_embedding embeddings
        # JOIN langchain_pg_collection collection
        #     ON embeddings.collection_id = collection.uuid
        # WHERE collection.name = '{collection_name}'
        # AND embeddings.cmetadata->>'name' LIKE 'Session Notes%'
        # AND (embeddings.cmetadata->>'is_latest')::boolean = true;
        # """
        f"""
        SELECT embeddings.*
        FROM langchain_pg_embedding embeddings
        JOIN langchain_pg_collection collection
            ON embeddings.collection_id = collection.uuid
        WHERE collection.name = '{collection_name}'
        AND embeddings.cmetadata->>'name' LIKE 'Session Notes%'
        AND embeddings.cmetadata->>'embedding_type' = 'document'
        ORDER BY (embeddings.cmetadata->>'session_number')::INT DESC
        LIMIT 1;
        """
    )

    last_session_summary = cur.fetchone().document

    # Retrieve the next most recent n sessions summaries
    cur.execute(
        f"""
        SELECT embeddings.*
        FROM langchain_pg_embedding embeddings
        JOIN langchain_pg_collection collection
            ON embeddings.collection_id = collection.uuid
        WHERE collection.name = '{collection_name}'
        AND embeddings.cmetadata->>'embedding_type' = 'document'
        AND embeddings.cmetadata->>'name' LIKE 'Session Notes%'
        AND (embeddings.cmetadata->>'is_latest') IS NULL 
        ORDER BY (embeddings.cmetadata->>'session_number')::INT DESC
        LIMIT {n_previous_sessions_context};
        """
    )

    # Join previous session summaries into a contiguous string in prepartion for prompt injection
    previous_session_summaries = "\n".join([
        f"-- SESSION {row.cmetadata['session_number']} -- \n{row.document}"
        for row in cur.fetchall() 
    ])

    cur.close()
    conn.close()

    prompt = LAST_SESSION_PROMPT_TEMPLATE.format(
        previous_summaries_context=previous_session_summaries,
        last_session_context=last_session_summary,
    )

    llm = ChatOpenAI(temperature=temperature, model_name=model_name, api_key=config["OPENAI_API_KEY"])
    result = llm.invoke(prompt)

    return result.content

