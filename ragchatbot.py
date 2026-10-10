import os
import json
from dotenv import load_dotenv
from openai import OpenAI
import chromadb
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__)

load_dotenv()
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)
print("client created successfully")
with open(BASE_DIR / "doc1.txt", "r", encoding="utf-8") as f:
    doc1 = f.read()
with open(BASE_DIR / "doc2.txt", "r", encoding="utf-8") as f:
    doc2 = f.read()
with open(BASE_DIR / "doc3.txt", "r", encoding="utf-8") as f:
    doc3 = f.read()
def chunk_document(text,source_name):
    paragraphs=text.strip().split("\n\n")
    chunks=[]
    for para in paragraphs:
        if len(para)<20:
            continue
        if para.startswith("=="):
            continue
        chunks.append({
            "text":para,
            "source":source_name
        })
    return chunks
doc1_chunks=chunk_document(doc1,"RAG Architecture and LLM Limitations")
doc2_chunks=chunk_document(doc2,"Data Ingestion, Chunking Strategies, and Vector Embeddings")
doc3_chunks=chunk_document(doc3,"Prompt Augmentation, Generation, and Evaluation Strategies")
all_chunks=doc1_chunks+doc2_chunks+doc3_chunks
print(len(doc1_chunks))
print(len(doc2_chunks))
print(len(doc3_chunks))
print(len(all_chunks))

model=SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

chroma_client=chromadb.Client()
collection=chroma_client.create_collection(name="company_docs")
documents=[]
ids=[]
metadatas=[]
for i,chunk in enumerate(all_chunks):
    documents.append(chunk["text"])
    ids.append(f"chunk {i}")
    metadatas.append({"source":chunk["source"]})
print(documents[1])
print(ids[1])
print(metadatas[1])
collection.add(
    documents = documents,
    ids = ids,
    metadatas = metadatas
)
print(f" Stored {len(documents)} chunks in chroma db")


def search_docs(query:str)->str:
    results=collection.query(
        query_texts=[query],
        n_results=3
    )
    chunks=results["documents"][0]
    return "\n\n".join(chunks)

rag_tools = [
    {
        "type": "function",
        "function": {
            "name": "search_docs",
            "description": (
                "Search the uploaded knowledge documents for information about "
                "RAG architecture, LLM limitations, data ingestion, chunking, "
                "vector embeddings, prompt augmentation, generation, and evaluation. "
                "Use this tool when the question needs information from these documents."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to retrieve relevant document chunks.",
                    }
                },
                "required": ["query"],
            },
        },
    }
]
available_tools={
    "search_docs":search_docs
}
print("rag tool defined")
def rag_agent(question: str, verbose: bool = True):
    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant with access to a document knowledge base "
                "about RAG, document ingestion, chunking, vector embeddings, prompt "
                "augmentation, generation, and evaluation.\n\n"
                "Follow these rules:\n"
                "1. If the question is about the topics covered by the knowledge base, "
                "use the search_docs tool to retrieve relevant information.\n"
                "2. After searching, check whether the retrieved text actually answers "
                "the user's question.\n"
                "3. If the retrieved text contains the answer, answer using that text.\n"
                "4. If the retrieved text does not contain the answer, answer using "
                "your general knowledge. Do not say you cannot answer just because "
                "the information is missing from the documents.\n"
                "5. If the question is unrelated to the document topics and is a "
                "general-knowledge question, answer directly using your general "
                "knowledge without searching the documents.\n"
                "6. Never invent information or claim that general knowledge came "
                "from the documents.\n"
                "7. Give a clear, direct answer to the user's question."
            ),
        },
        {
            "role": "user",
            "content": question,
        },
    ]

    if verbose:
          print(f"\n{'═' * 60}")
          print(f"🧑 Question: {question}")
          print(f"{'─' * 60}")

    max_steps = 3
    for step in range(max_steps):
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=messages,
            tools=rag_tools,
        )
        choice = response.choices[0]
        if choice.finish_reason == "stop":
            answer = choice.message.content
            if verbose:
                print(f"🤖 Answer: {answer}")
                print(f"{'═' * 60}")
            save_chat_history(question, answer)
            return answer
        if choice.message.tool_calls:
            messages.append(choice.message)
            for tool_call in choice.message.tool_calls:
                func_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                if verbose:
                    print(f"  🔍 Searching: \"{args['query']}\"")
                result = available_tools[func_name](**args)
                if verbose:
                    print(f"  📄 Found {len(result)} chars of context")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })
    return "Could not answer within step limit."
print("✅ RAG Agent ready!")

HISTORY_FILE = Path(__file__).parent / "chat_history.json"
MAX_QUESTIONS = 10



def load_chat_history():
    if not HISTORY_FILE.exists():
        return {"session": 1, "messages": []}

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as file:
            history = json.load(file)

        if not isinstance(history, dict) or not isinstance(history.get("messages"), list):
            return {"session": 1, "messages": []}

        if not isinstance(history.get("session"), int):
            history["session"] = 1

        return history

    except (json.JSONDecodeError, OSError):
        return {"session": 1, "messages": []}

def save_chat_history(question, answer):
    history = load_chat_history()

    # Start a new session when the previous session has 10 questions
    if len(history["messages"]) >= MAX_QUESTIONS:
        history = {
            "session": history["session"] + 1,
            "messages": []
        }

    history["messages"].append({
        "question": question,
        "answer": answer,
        "timestamp": datetime.now().isoformat(timespec="seconds")
    })

    with open(HISTORY_FILE, "w", encoding="utf-8") as file:
        json.dump(history, file, indent=4, ensure_ascii=False)

    print(
        f"Chat history saved: "
        f"{len(history['messages'])}/{MAX_QUESTIONS} questions "
        f"(Session {history['session']})"
    )



@app.route("/")
def home():
    return send_from_directory(str(BASE_DIR), "index.html")

@app.route("/style.css")
def stylesheet():
    return send_from_directory(str(BASE_DIR), "style.css")

@app.route("/script.js")
def javascript():
    return send_from_directory(str(BASE_DIR), "script.js")


@app.route("/api/ask", methods=["POST"])
def api_ask():
    try:
        data = request.get_json(silent=True) or {}
        question = data.get("question", "").strip()

        if not question:
            return jsonify({"error": "Please enter a question."}), 400

        answer = rag_agent(question, verbose=False)

        return jsonify({
            "answer": answer,
            "sources": []
        })

    except Exception:
        app.logger.exception("Error processing question")
        return jsonify({
            "error": "Failed to generate an answer. Check the backend terminal."
        }), 500


@app.route("/api/status", methods=["GET"])
def api_status():
    return jsonify({
        "chunks": collection.count()
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )