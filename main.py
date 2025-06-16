import json, subprocess, pathlib, argparse, sys
from utils.youtube import parse_url
from transcript import get_transcript
from summarizer import summarize, Backend
import tempfile, os
from pathlib import Path

def run(url: str, method: str, backend: Backend = Backend.GEMINI):
    vid = parse_url(url)
    try:
        tr = get_transcript(vid)
        print("✓ caption API")
        return tr  # 字幕データを返す
    except Exception as e:
        raise Exception(str(e))  # エラーメッセージをそのまま伝播

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="YouTube URL")
    parser.add_argument(
        "--method",
        choices=["auto", "caption"],
        default="auto",
        help="auto = caption→fallback, caption = 字幕のみ",
    )
    parser.add_argument(
        "--backend",
        choices=["gemini"],
        default="gemini",
        help="LLM backend for summarization",
    )
    args = parser.parse_args()
    run(args.url, args.method, Backend(args.backend))
