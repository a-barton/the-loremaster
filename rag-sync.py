import os
from typing import Any
import pgvector
import psycopg2
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

{context}

Question: {question}
Helpful Answer:"""
QA_PROMPT = PromptTemplate(
    template=prompt_template, input_variables=["context", "question"]
)

def qa(query,
       model_name,
       temperature,
       k,
       search_type,
       history,
       verbose
       ) -> dict[str, Any]:

    load_dotenv()
    COLLECTION_NAME = os.getenv("COLLECTION_NAME")
    POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
    POSTGRES_HOST = os.getenv('POSTGRES_HOST')

    """Establish vector DB and retriever"""
    embeddings = HuggingFaceEmbeddings()
    collection_name = COLLECTION_NAME
    vectors = PGVector.from_existing_index(
        embedding=embeddings, 
        collection_name=collection_name, 
        connection_string=f"postgresql+psycopg2://postgres:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:5432/postgres"
    )
    retriever = vectors.as_retriever(search_type=search_type, search_kwargs={'k': k})

    # Construct a ConversationalRetrievalChain with a streaming llm for combine docs
    # and a separate, non-streaming llm for question generation
    llm = ChatOpenAI(temperature=temperature, model_name=model_name)
    streaming_llm = ChatOpenAI(streaming=True, model_name=model_name, callbacks=[StreamingStdOutCallbackHandler()], temperature=temperature)

    question_generator = LLMChain(
        llm=llm,
        prompt=CONDENSE_QUESTION_PROMPT,
        verbose=verbose
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

if __name__ == "__main__":
    query = "What powerful artifact did Tandris gift to Veren?"
    response = qa(
        query=query,
        model_name="gpt-4o",
        temperature=0.7,
        k=3,
        search_type="similarity",
        history="",
        verbose=True,
    )
    print(response)