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
    except Exception as e:
        sys.exit("× この動画には字幕がありません（処理をスキップします）")

    # 一時ディレクトリの作成
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        
        # JSONファイルの保存
        json_path = temp_dir_path / f"{vid}.json"
        json_path.write_text(json.dumps(tr, ensure_ascii=False, indent=2))
        
        # 要約の生成と保存
        md_path = temp_dir_path / f"{vid}_summary.md"
        summarize(json_path, md_path, backend=backend)
        print(f"✓ summary saved → {md_path}")

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
