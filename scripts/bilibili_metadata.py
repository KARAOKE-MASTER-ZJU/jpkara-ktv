#!/usr/bin/env python3
"""Fetch stable Bilibili video metadata into a reusable JSON sidecar."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


BVID_RE = re.compile(r"(?:bvid=|/video/)?(BV[0-9A-Za-z]{10})", re.IGNORECASE)
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36"


def api_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Referer": "https://www.bilibili.com/"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.load(response)
    if payload.get("code") != 0:
        raise RuntimeError(f"Bilibili API error {payload.get('code')}: {payload.get('message')}")
    return payload


def iso_timestamp(unix: int | float | None) -> str | None:
    if not unix:
        return None
    return dt.datetime.fromtimestamp(unix, dt.timezone.utc).isoformat().replace("+00:00", "Z")


def bvid_from(value: str) -> str:
    match = BVID_RE.search(value)
    if not match:
        raise ValueError(f"could not find a Bilibili BV id in: {value}")
    return match.group(1)


def stream_summary(bvid: str, cid: int) -> dict[str, Any]:
    query = urllib.parse.urlencode({"bvid": bvid, "cid": cid, "fnval": 16, "fnver": 0, "fourk": 1})
    payload = api_json(f"https://api.bilibili.com/x/player/playurl?{query}")
    data = payload.get("data") or {}
    dash = data.get("dash") or {}
    videos = dash.get("video") or []
    audios = dash.get("audio") or []

    def compact(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        seen: set[tuple[Any, ...]] = set()
        for item in items:
            key = (item.get("id"), item.get("width"), item.get("height"), item.get("codecs"))
            if key in seen:
                continue
            seen.add(key)
            # Do not persist base_url: its signed query expires and is not reusable metadata.
            result.append({
                key_name: item.get(key_name)
                for key_name in ("id", "width", "height", "codecs")
                if item.get(key_name) is not None
            })
        return result

    return {
        "selected_quality": data.get("quality"),
        "selected_format": data.get("format"),
        "timelength_ms": data.get("timelength"),
        "support_formats": [
            {
                key: item.get(key)
                for key in ("quality", "display_desc", "new_description", "codecs")
                if item.get(key) is not None
            }
            for item in (data.get("support_formats") or [])
        ],
        "available_video": compact(videos),
        "available_audio": compact(audios),
    }


def fetch(source: str) -> dict[str, Any]:
    bvid = bvid_from(source)
    view = api_json(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}")["data"]
    tag_payload = api_json(f"https://api.bilibili.com/x/web-interface/view/detail/tag?bvid={bvid}")
    tags = tag_payload.get("data") or []

    first_page = (view.get("pages") or [{}])[0]
    cid = first_page.get("cid") or view.get("cid")
    try:
        streams = stream_summary(bvid, cid) if cid else {}
    except Exception as exc:  # Metadata should still be useful if playurl is rate-limited.
        streams = {"error": str(exc)}
    formats = streams.get("support_formats") or []
    quality80 = next((x for x in formats if x.get("quality") == 80), formats[0] if formats else {})
    codec_tokens = quality80.get("codecs") or []
    codec = "H.264" if any(str(x).startswith("avc") for x in codec_tokens) else ("HEVC" if codec_tokens else None)
    audio = next((x for x in streams.get("available_audio", []) if x.get("id") == 30280), (streams.get("available_audio") or [{}])[0])
    description = view.get("desc") or ""
    source_note = None
    source_match = re.search(r"片源\s*[:：]\s*(.+)", description)
    if source_match:
        source_note = source_match.group(1).splitlines()[0].strip()
    metadata = {
        "source_url": f"https://www.bilibili.com/video/{bvid}/",
        "bvid": bvid,
        "cid": cid,
        "title": view.get("title"),
        "description": description,
        # Keep sidecars compact and compatible with the publishing workflow.
        "tags": [tag.get("tag_name") for tag in tags if tag.get("tag_name")][:10],
        "duration_seconds": view.get("duration"),
        "video": {
            "quality_id": quality80.get("quality"),
            "codec": codec,
            "width": (view.get("dimension") or {}).get("width"),
            "height": (view.get("dimension") or {}).get("height"),
            "fps": (view.get("dimension") or {}).get("fps"),
        },
        "audio": {"quality_id": audio.get("id"), "codec": audio.get("codecs")},
        "cover_url": view.get("pic"),
    }
    if source_note:
        metadata["source_note"] = source_note
        source_urls = re.findall(r"https?://[^\s]+", source_note)
        if source_urls:
            metadata["source_material_url"] = source_urls[0].rstrip(".,)")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Bilibili URL or BV id")
    parser.add_argument("output", type=Path, help="JSON sidecar path")
    args = parser.parse_args()
    metadata = fetch(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output} ({len(metadata.get('tags', []))} tag(s))")


if __name__ == "__main__":
    main()
