from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled, VideoUnavailable
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

def get_transcript(video_id: str, lang="ja") -> list[dict]:
    """
    字幕を取得するメイン関数
    複数の方法を試して、最も確実な方法で字幕を取得
    """
    # 方法1: YouTube Transcript APIを試す
    try:
        logger.info("YouTube Transcript APIで字幕を取得中...")
        return YouTubeTranscriptApi.get_transcript(
            video_id,
            languages=[lang, "en", "ja"]
        )
    except Exception as e:
        logger.warning(f"YouTube Transcript APIでの取得に失敗: {str(e)}")
    
    # 方法2: yt-dlpを使用
    try:
        logger.info("yt-dlpで字幕を取得中...")
        return get_transcript_with_ytdlp(video_id)
    except Exception as e:
        logger.error(f"yt-dlpでの取得に失敗: {str(e)}")
        raise Exception("字幕の取得に失敗しました。この動画には字幕がないか、アクセスが制限されています。")

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
        'no_warnings': True,
        'extract_flat': True,  # フラットな形式で抽出
        'ignoreerrors': True,  # エラーを無視して続行
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
                    
                    # デバッグ用のコード
                    if os.path.exists(subtitle_file):
                        with open(subtitle_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                            logger.info(f"VTT file content:\n{content}")
                    
                    # VTTをパースしてJSON形式に変換
                    return parse_vtt(content)
                else:
                    # 字幕ファイルが見つからない場合、自動生成字幕を試す
                    logger.info("自動生成字幕を試みます...")
                    return get_auto_generated_subtitles(video_id)
                    
        except Exception as e:
            logger.error(f"字幕取得エラー: {str(e)}")
            raise Exception(f"字幕の取得に失敗しました: {str(e)}")

def get_auto_generated_subtitles(video_id: str) -> list[dict]:
    """
    自動生成字幕を取得
    """
    try:
        return YouTubeTranscriptApi.get_transcript(
            video_id,
            languages=['ja', 'en'],
            preserve_formatting=True
        )
    except Exception as e:
        logger.error(f"自動生成字幕の取得に失敗: {str(e)}")
        raise Exception("自動生成字幕の取得に失敗しました")

def parse_vtt(content: str) -> list[dict]:
    """
    VTTファイルをパースしてJSON形式に変換
    """
    lines = content.split('\n')
    transcript = []
    current_text = []
    current_start = None
    current_duration = None
    
    for line in lines:
        if '-->' in line:
            # タイムスタンプ行
            start, end = line.split(' --> ')
            current_start = start
            # 時間の差分を計算
            start_sec = time_to_seconds(start)
            end_sec = time_to_seconds(end)
            current_duration = end_sec - start_sec
        elif line.strip() and not line.startswith('WEBVTT'):
            # テキスト行
            current_text.append(line.strip())
        elif not line.strip() and current_text:
            # 空行で区切られた段落の終わり
            if current_start and current_duration is not None:
                transcript.append({
                    'text': ' '.join(current_text),
                    'start': current_start,
                    'duration': current_duration
                })
            current_text = []
            current_start = None
            current_duration = None
    
    return transcript

def time_to_seconds(time_str: str) -> float:
    """
    VTTの時間形式を秒に変換
    """
    h, m, s = time_str.split(':')
    return float(h) * 3600 + float(m) * 60 + float(s.replace(',', '.'))
