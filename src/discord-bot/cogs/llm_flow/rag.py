import os
from typing import Any, Dict
from dotenv import load_dotenv

from langchain.chains.llm import LLMChain
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.chains.question_answering import load_qa_chain

from langchain_community.vectorstores.pgvector import PGVector
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.prompts import PromptTemplate
from langchain.chains import ConversationalRetrievalChain
from langchain.chains.conversational_retrieval.prompts import CONDENSE_QUESTION_PROMPT

from langchain_community.chat_models import ChatOpenAI

prompt_template = """SYSTEM: You are a loremaster with knowledge of the setting and world of a Dungeons and Dragons campaign, and answser user questions about the history of the setting and previous events that have transpired in the course of the campaign.
---
Stylise your answers as though you are roleplaying a wise old sage or loremaster who is providing wisdom to fantasy characters in the Dungeons and Dragons campaign.
Use the following pieces of context to answer the question at the end. If you don't know the answer, just say that you don't know, don't try to make up an answer.
Ensure the answer fits within a 2000 character limit, and try to avoid starting every answer with "Ah, ...".

{context}

Question: {question}
Loremaster's Answer:"""
QA_PROMPT = PromptTemplate(
    template=prompt_template, input_variables=["context", "question"]
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

    """Establish vector DB and retriever"""
    print("rag.py -- Establishing vector DB")
    embeddings = HuggingFaceEmbeddings()
    collection_name = config["COLLECTION_NAME"]
    vectors = PGVector.from_existing_index(
        embedding=embeddings,
        collection_name=collection_name,
        connection_string=f"postgresql+psycopg2://{config['POSTGRES_USER']}:{config['POSTGRES_PASSWORD']}@{config['POSTGRES_HOST']}:{config['POSTGRES_PORT']}/{config['POSTGRES_DBNAME']}",
    )
    retriever = vectors.as_retriever(search_type=search_type, search_kwargs={"k": k})

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
        prompt=QA_PROMPT,
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
