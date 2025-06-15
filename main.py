from dotenv import load_dotenv
import json, subprocess, pathlib, argparse, sys
from utils.youtube import parse_url
from transcript import get_transcript
from summarizer import summarize, Backend
import tempfile, os
from openai import OpenAI

load_dotenv()
# ── A. ローカル whispercpp ─────────────────────────
def whisper_local(url: str, model="small") -> list[dict]:
    out = "audio.m4a"
    subprocess.run(["yt-dlp", "-f", "bestaudio", "-o", out, url], check=True)
    subprocess.run(["whispercpp", "-m", model, "-f", out, "-otxt"], check=True)
    with open(out + ".txt") as f:
        return [{"text": l.strip(), "start": 0, "duration": 0} for l in f]

# ── B. OpenAI Audio API (2025-Q2 仕様) ───────────────
def _dl_bestaudio(url: str) -> str:
    """bestaudio を m4a/webm でそのまま保存"""
    tmp = tempfile.NamedTemporaryFile(suffix=".m4a", delete=False)
    subprocess.run(["yt-dlp", "-f", "bestaudio", "-o", tmp.name, url],
                   check=True)
    return tmp.name

def _convert_to_wav(src: str) -> str:
    """ffmpeg で 16 kHz mono WAV に確実変換"""
    dst = src.rsplit(".", 1)[0] + ".wav"
    subprocess.run(
        ["ffmpeg", "-y", "-i", src, "-ar", "16000", "-ac", "1", dst],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return dst

from openai import OpenAI, OpenAIError
import tempfile, subprocess, os

def whisper_api(url: str, model="whisper-1"):
    # ① best オールインワン（mp4/h264+aac）を DL
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vid:
        subprocess.run(
            ["yt-dlp",
             "-f", "best",                   # 映像+音声1本化
             "--merge-output-format", "mp4",
             "-o", vid.name, url],
            check=True)
    
    # ② mp4 → 16 kHz mono WAV 抽出
    wav = vid.name.replace(".mp4", ".wav")
    subprocess.run(
        ["ffmpeg", "-y", "-i", vid.name,
         "-vn", "-ar", "16000", "-ac", "1", wav],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # ③ Whisper API
    client = OpenAI()
    res = client.audio.transcriptions.create(
        model=model, file=open(wav, "rb"), response_format="verbose_json"
    )
    return [
        {"text": s["text"],
         "start": s.get("offset_ms",0)/1000,
         "duration": s.get("duration_ms",0)/1000}
        for s in res.segments
    ]




def run(url: str, method: str, whisper: str = "local", backend: Backend = Backend.OPENAI):
    vid = parse_url(url)
    try:
        tr = get_transcript(vid)
        print("✓ caption API")
    except Exception as e:
        sys.exit("× この動画には字幕がありません（処理をスキップします）")

    pathlib.Path("outputs").mkdir(exist_ok=True)
    json_path = pathlib.Path(f"outputs/{vid}.json")
    json_path.write_text(json.dumps(tr, ensure_ascii=False, indent=2))
    md_path = pathlib.Path(f"outputs/{vid}_summary.md")
    summarize(json_path, md_path, backend=backend)
    print(f"✓ summary saved → {md_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="YouTube URL")
    parser.add_argument(
        "--method",
        choices=["auto", "caption", "whisper"],
        default="auto",
        help="auto = caption→fallback, caption = 字幕のみ, whisper = 強制音声起こし",
    )
    parser.add_argument(
        "--whisper",
        choices=["local", "api"],
        default="local",
        help="whisper backend: local=whispercpp, api=OpenAI Audio",
    )
    parser.add_argument(
        "--backend",
        choices=["openai", "gemini"],
        default="openai",
        help="LLM backend for summarization",
    )
    args = parser.parse_args()
    run(args.url, args.method, args.whisper, Backend(args.backend))
