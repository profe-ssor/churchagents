"""
langsmith_setup.py — Call configure() at the top of every agent file.
Enables automatic LangSmith tracing for all LLM + tool calls.
"""
import os
from dotenv import load_dotenv

load_dotenv()


def configure():
    """Enable LangSmith tracing. Call once at agent startup."""
    # LangChain traces use LANGCHAIN_*; LangSmith UI exports LANGSMITH_API_KEY — sync them.
    if not os.getenv("LANGCHAIN_API_KEY"):
        smith_key = os.getenv("LANGSMITH_API_KEY")
        if smith_key:
            os.environ["LANGCHAIN_API_KEY"] = smith_key
    if not os.getenv("LANGCHAIN_PROJECT"):
        smith_proj = (os.getenv("LANGSMITH_PROJECT") or "").strip().strip("\"'")
        if smith_proj:
            os.environ["LANGCHAIN_PROJECT"] = smith_proj

    required = ["LANGCHAIN_API_KEY", "LANGCHAIN_PROJECT"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        print(f"[LangSmith] WARNING: missing env vars: {missing} — tracing disabled")
        return
    # LangChain reads these env vars automatically
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    print(f"[LangSmith] Tracing ON → project: {os.getenv('LANGCHAIN_PROJECT')}")
