from urllib.parse import urlparse, parse_qs

def parse_url(url: str) -> str:
    """
    どんな YouTube URL でも video_id を返す。
    - https://youtu.be/<id>
    - https://www.youtube.com/watch?v=<id>&t=5s
    """
    parts = urlparse(url)
    if parts.netloc in ("youtu.be", "www.youtu.be"):
        return parts.path.lstrip("/")
    if parts.netloc.endswith("youtube.com"):
        return parse_qs(parts.query).get("v", [""])[0]
    raise ValueError("Invalid YouTube URL")
