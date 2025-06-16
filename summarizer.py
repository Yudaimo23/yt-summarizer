# summarizer.py
from pathlib import Path
from typing import List
import json, os, tiktoken, google.generativeai as genai
from openai import OpenAI, OpenAIError
from enum import Enum

class Backend(str, Enum):
    OPENAI = "openai"
    GEMINI = "gemini"

_oa_client = OpenAI()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

def _chunk(transcript: List[dict], limit_tokens: int) -> List[str]:
    enc = tiktoken.get_encoding("cl100k_base")
    buf, tok, out = [], 0, []
    for seg in transcript:
        t = enc.encode(seg["text"])
        if tok + len(t) > limit_tokens and buf:
            out.append(" ".join(buf))
            buf, tok = [], 0
        buf.append(seg["text"])
        tok += len(t)
    if buf:
        out.append(" ".join(buf))
    return out

def _llm_call(text: str, backend: Backend, prompt: str) -> str:
    if backend == Backend.OPENAI:
        res = _oa_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": f"{prompt}\n\n{text}"}],
        )
        return res.choices[0].message.content.strip()
    else:                                  # GEMINI
        mdl = genai.GenerativeModel("gemini-2.0-flash")
        res = mdl.generate_content(f"{prompt}\n\n{text}")
        return res.text.strip()

def summarize(transcript: list[dict], backend: Backend = Backend.GEMINI, prompt: str = None) -> str:
    """
    字幕データを要約する
    """
    # 字幕テキストを結合
    text = "\n".join([t["text"] for t in transcript])
    
    # 要約生成
    if backend == Backend.GEMINI:
        # Geminiを使用した要約
        summary = generate_summary_with_gemini(text, prompt)
    else:
        raise ValueError(f"Unsupported backend: {backend}")
    
    return summary
