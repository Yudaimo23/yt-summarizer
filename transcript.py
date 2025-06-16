from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled
from proxy_utils import get_free_proxy
import os, subprocess, tempfile, html, json, random

PAID_PROXY = os.getenv("PAID_PROXY")        # 例: http://user:pass@brd.superproxy.io:22225

def _get_via_api(vid, proxies):
    return YouTubeTranscriptApi.get_transcript(vid, languages=["ja","en"], proxies=proxies)

def _get_via_ytdlp(vid):
    with tempfile.NamedTemporaryFile(suffix=".vtt", delete=False) as f:
        subprocess.run(["yt-dlp", f"https://youtu.be/{vid}",
                        "--write-auto-sub", "--sub-lang", "ja,en",
                        "--skip-download", "-o", f.name[:-4]], check=True)
        txt = open(f.name).read().splitlines()
        return [{"text": html.unescape(t), "start":0,"duration":0}
                for t in txt if "-->" not in t and t.strip()]

def get_transcript(vid: str):
    # ① free proxy を 3 回試す
    for _ in range(3):
        prox = get_free_proxy()
        if not prox: break
        try:
            return _get_via_api(vid, prox)
        except NoTranscriptFound:
            raise
        except Exception:
            continue

    # ② yt-dlp 自動字幕
    try:
        return _get_via_ytdlp(vid)
    except Exception:
        pass

    # ③ 有料プロキシ（設定されていれば）
    if PAID_PROXY:
        prox = {"http": PAID_PROXY, "https": PAID_PROXY}
        return _get_via_api(vid, prox)

    raise RuntimeError("字幕が取得できません（IP ブロックの可能性）")
