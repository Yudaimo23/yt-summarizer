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
    日本語字幕を優先的に取得
    """
    try:
        ydl_opts = {
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['ja', 'ja-JP', 'en'],  # 日本語を優先
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
            'outtmpl': f'temp/{video_id}/%(id)s.%(ext)s'
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f"yt-dlpで字幕を取得開始: {video_id}")
            
            # 動画情報を取得
            info = ydl.extract_info(f'https://www.youtube.com/watch?v={video_id}', download=True)
            
            # 字幕ファイルのパスを取得
            subtitle_path = None
            if 'subtitles' in info:
                # 日本語字幕を優先
                for lang in ['ja', 'ja-JP', 'en']:
                    if lang in info['subtitles']:
                        subtitle_path = info['subtitles'][lang][0]['data']
                        logger.info(f"字幕ファイルを発見: {lang}")
                        break
            
            if not subtitle_path:
                logger.warning("字幕ファイルが見つかりません")
                return []
            
            # 字幕の利用可能性を確認
            if 'subtitles' in info:
                available_langs = list(info['subtitles'].keys())
                logger.info(f"利用可能な字幕言語: {available_langs}")
            
            # VTTファイルを読み込んでパース
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                content = f.read()
                logger.debug(f"字幕ファイルの内容:\n{content}")
                return parse_vtt(content)
                
    except Exception as e:
        logger.error(f"yt-dlpでの取得に失敗: {str(e)}")
        return []

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
    特殊な形式（align:start position:0%など）にも対応
    """
    lines = content.split('\n')
    transcript = []
    current_text = []
    current_start = None
    current_duration = None
    
    for line in lines:
        line = line.strip()
        
        # WEBVTTヘッダーをスキップ
        if line.startswith('WEBVTT') or not line:
            continue
            
        if '-->' in line:
            # タイムスタンプ行
            try:
                # タイムスタンプ部分だけを抽出
                timestamp_part = line.split(' align:')[0] if ' align:' in line else line
                start, end = timestamp_part.split(' --> ')
                current_start = start
                # 時間の差分を計算
                start_sec = time_to_seconds(start)
                end_sec = time_to_seconds(end)
                current_duration = end_sec - start_sec
            except Exception as e:
                logger.error(f"タイムスタンプのパースエラー: {str(e)}")
                continue
                
        elif line and current_start is not None:
            # テキスト行
            # 特殊なタグを除去
            clean_text = line
            # <c>タグを除去
            clean_text = clean_text.replace('<c>', '').replace('</c>', '')
            # 時間タグを除去
            import re
            clean_text = re.sub(r'<\d{2}:\d{2}:\d{2}\.\d{3}>', '', clean_text)
            
            if clean_text.strip():  # 空でない場合のみ追加
                current_text.append(clean_text.strip())
            
            # 次の行が空行またはタイムスタンプの場合、現在のセグメントを保存
            if not current_text:
                continue
                
            # 重複を除去
            unique_text = ' '.join(dict.fromkeys(current_text))
            
            transcript.append({
                'text': unique_text,
                'start': current_start,
                'duration': current_duration if current_duration is not None else 0.0
            })
            current_text = []
            current_start = None
            current_duration = None
    
    # 最後のセグメントを処理
    if current_text and current_start is not None:
        # 重複を除去
        unique_text = ' '.join(dict.fromkeys(current_text))
        transcript.append({
            'text': unique_text,
            'start': current_start,
            'duration': current_duration if current_duration is not None else 0.0
        })
    
    # 重複するセグメントを除去
    unique_transcript = []
    seen_texts = set()
    
    for segment in transcript:
        if segment['text'] not in seen_texts:
            seen_texts.add(segment['text'])
            unique_transcript.append(segment)
    
    return unique_transcript

def time_to_seconds(time_str: str) -> float:
    """
    VTTの時間形式を秒に変換
    例: 00:00:01.000 や 00:01:00,000 などの形式に対応
    """
    try:
        # カンマをドットに変換
        time_str = time_str.replace(',', '.')
        
        # 時間部分を分割
        parts = time_str.split(':')
        
        if len(parts) == 3:  # HH:MM:SS.mmm 形式
            hours = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            return hours * 3600 + minutes * 60 + seconds
        elif len(parts) == 2:  # MM:SS.mmm 形式
            minutes = float(parts[0])
            seconds = float(parts[1])
            return minutes * 60 + seconds
        else:
            logger.warning(f"予期しない時間形式: {time_str}")
            return 0.0
    except Exception as e:
        logger.error(f"時間変換エラー: {str(e)}")
        return 0.0
