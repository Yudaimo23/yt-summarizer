from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (        # ← 名前を修正
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

def get_transcript(video_id: str, lang="ja") -> list[dict]:
    """
    指定 video_id の字幕を取得。
    取得できない場合は例外を投げて呼び出し元に任せる。
    """
    try:
        return YouTubeTranscriptApi.get_transcript(
            video_id,
            languages=[lang, "en", "ja"]
        )
    except (NoTranscriptFound, TranscriptsDisabled, VideoUnavailable):
        raise
