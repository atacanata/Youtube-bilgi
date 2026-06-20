"""YouTube Data API v3 — resmi metadata cekme (ban-free katman).

search.list KULLANILMAZ (pahali). Kanal ID -> uploads playlist -> playlistItems
-> videos.list akisi kullanilir.
"""
from __future__ import annotations

import os

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.utils import iso8601_duration_to_sec, video_url


def _client():
    """developerKey ile YouTube servis nesnesi."""
    key = os.getenv("YOUTUBE_API_KEY")
    if not key:
        raise RuntimeError(
            "YOUTUBE_API_KEY yok. youtube_research_agent/.env dosyasina ekleyin "
            "(.env.example'a bakin)."
        )
    return build("youtube", "v3", developerKey=key)


def get_uploads_playlist_id(channel_id: str) -> tuple[str, str]:
    """Kanal ID'den (uploads_playlist_id, kanal_basligi) dondurur."""
    yt = _client()
    try:
        resp = yt.channels().list(part="contentDetails,snippet", id=channel_id).execute()
    except HttpError as e:
        raise RuntimeError(f"channels.list hatasi: {e}") from e
    items = resp.get("items", [])
    if not items:
        raise RuntimeError(f"Kanal bulunamadi: {channel_id}")
    uploads = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    title = items[0]["snippet"]["title"]
    return uploads, title


def list_upload_playlist_items(playlist_id: str, limit: int) -> list[str]:
    """Uploads playlist'inden en yeni 'limit' video ID'sini (sayfali) dondurur."""
    yt = _client()
    ids: list[str] = []
    token = None
    while len(ids) < limit:
        try:
            resp = yt.playlistItems().list(
                part="snippet,contentDetails",
                playlistId=playlist_id,
                maxResults=50,
                pageToken=token,
            ).execute()
        except HttpError as e:
            raise RuntimeError(f"playlistItems.list hatasi: {e}") from e
        for it in resp.get("items", []):
            vid = it["contentDetails"].get("videoId")
            if vid:
                ids.append(vid)
            if len(ids) >= limit:
                break
        token = resp.get("nextPageToken")
        if not token:
            break
    return ids[:limit]


def get_video_details(video_ids: list[str]) -> list[dict]:
    """videos.list ile detay (baslik, aciklama, sure, istatistik, thumbnail)."""
    if not video_ids:
        return []
    yt = _client()
    out: list[dict] = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        try:
            resp = yt.videos().list(
                part="snippet,contentDetails,statistics",
                id=",".join(batch),
            ).execute()
        except HttpError as e:
            raise RuntimeError(f"videos.list hatasi: {e}") from e
        for it in resp.get("items", []):
            sn = it.get("snippet", {})
            st = it.get("statistics", {})
            cd = it.get("contentDetails", {})
            thumbs = sn.get("thumbnails", {})
            thumb = (thumbs.get("high") or thumbs.get("medium")
                     or thumbs.get("default") or {}).get("url", "")
            out.append({
                "video_id": it["id"],
                "title": sn.get("title", ""),
                "description": sn.get("description", ""),
                "published_at": sn.get("publishedAt", ""),
                "duration_sec": iso8601_duration_to_sec(cd.get("duration")),
                "view_count": int(st.get("viewCount", 0) or 0),
                "like_count": int(st.get("likeCount", 0) or 0),
                "comment_count": int(st.get("commentCount", 0) or 0),
                "thumbnail_url": thumb,
                "url": video_url(it["id"]),
            })
    return out
