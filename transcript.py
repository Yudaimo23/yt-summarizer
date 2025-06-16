from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled
from proxy_utils import get_free_proxy
import os, subprocess, tempfile, html, json, random
import yt_dlp
import logging

PAID_PROXY = os.getenv("PAID_PROXY")        # 例: http://user:pass@brd.superproxy.io:22225

logger = logging.getLogger(__name__)

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

def get_transcript_with_ytdlp(video_id: str) -> list[dict]:
    """
    yt-dlpを使用して字幕を取得
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['ja', 'en'],
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,  # 警告を抑制
    }
    
    with tempfile.TemporaryDirectory() as temp_dir:
        ydl_opts['outtmpl'] = f"{temp_dir}/%(id)s.%(ext)s"
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info(f"字幕をダウンロード中: {url}")
                info = ydl.extract_info(url, download=True)
                
                # 字幕ファイルのパスを取得
                subtitle_file = f"{temp_dir}/{video_id}.ja.vtt"
                if not os.path.exists(subtitle_file):
                    subtitle_file = f"{temp_dir}/{video_id}.en.vtt"
                
                if os.path.exists(subtitle_file):
                    logger.info(f"字幕ファイルを読み込み中: {subtitle_file}")
                    # VTTファイルを読み込んでJSON形式に変換
                    with open(subtitle_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # VTTをパースしてJSON形式に変換
                    return parse_vtt(content)
                else:
                    raise Exception("字幕ファイルが見つかりません")
                    
        except Exception as e:
            logger.error(f"字幕取得エラー: {str(e)}")
            raise Exception(f"字幕の取得に失敗しました: {str(e)}")

def parse_vtt(content: str) -> list[dict]:
    """
    VTTファイルをパースしてJSON形式に変換
    """
    lines = content.split('\n')
    transcript = []
    current_text = []
    current_start = None
    
    for line in lines:
        if '-->' in line:
            # タイムスタンプ行
            start, end = line.split(' --> ')
            current_start = start
        elif line.strip() and not line.startswith('WEBVTT'):
            # テキスト行
            current_text.append(line.strip())
        elif not line.strip() and current_text:
            # 空行で区切られた段落の終わり
            if current_start:
                transcript.append({
                    'text': ' '.join(current_text),
                    'start': current_start,
                    'duration': '0'  # 必要に応じて計算
                })
            current_text = []
            current_start = None
    
    return transcript
