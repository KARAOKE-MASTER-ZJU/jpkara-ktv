#!/usr/bin/env python3
"""Submit a local KTV video (optionally an ON/OFF pair) to Bilibili.

The script is deliberately dry-run by default.  Add --submit to upload and
publish.  Credentials are read from BILI_SESSDATA/BILI_BILI_JCT or from a
local JSON cookie file; --qr-login can create that file after QR login.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import stat
import time
import urllib.parse
import hashlib
from pathlib import Path
from typing import Any

import requests


API = "https://api.bilibili.com"
MEMBER = "https://member.bilibili.com"
PASSPORT = "https://passport.bilibili.com"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36"


def env_file_value(name: str) -> str | None:
    """Read a simple KEY=VALUE from the repository .env without printing it."""
    for candidate in (Path.cwd() / ".env", Path(__file__).resolve().parents[3] / ".env"):
        if not candidate.is_file():
            continue
        for line in candidate.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith(name + "="):
                value = line.split("=", 1)[1].strip().strip("\"'")
                return value or None
    return None


def json_request(session: requests.Session, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
    response = session.request(method, url, timeout=60, **kwargs)
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(f"Bilibili returned non-JSON from {url}: {response.text[:300]}") from exc
    if isinstance(payload, dict) and payload.get("code", 0) != 0:
        raise RuntimeError(f"Bilibili API {url} failed: code={payload.get('code')} message={payload.get('message')}")
    return payload


def cookie_path(args: argparse.Namespace) -> Path:
    return Path(args.cookie_file or os.environ.get("BILI_COOKIE_FILE", "~/.config/jpkara/bilibili_cookie.json")).expanduser()


def load_cookie_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("cookies"), dict):
        data = data["cookies"]
    return {str(k): str(v) for k, v in data.items() if v is not None}


def save_cookie_file(path: Path, cookies: requests.cookies.RequestsCookieJar) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(cookies), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def qr_login(session: requests.Session, path: Path, wait_seconds: int = 300) -> dict[str, str]:
    generated = json_request(session, "GET", f"{PASSPORT}/x/passport-login/web/qrcode/generate")
    data = generated.get("data") or {}
    key, url = data.get("qrcode_key"), data.get("url")
    if not key or not url:
        raise RuntimeError(f"二维码生成响应缺少 qrcode_key/url: {generated}")
    print("请用哔哩哔哩手机客户端扫码登录：")
    print(url)
    print(f"二维码登录链接有效期约 {wait_seconds} 秒，等待扫码确认…", flush=True)
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        result = json_request(session, "GET", f"{PASSPORT}/x/passport-login/web/qrcode/poll", params={"qrcode_key": key})
        poll = result.get("data") or {}
        code = poll.get("code")
        if code == 0:
            save_cookie_file(path, session.cookies)
            print(f"登录成功，Cookie 已保存到 {path}")
            return dict(session.cookies)
        if code in (86090, 86038):
            print("二维码已扫码，请在手机上确认…", flush=True)
        elif code == 86101:
            pass
        else:
            print(f"二维码状态：{poll.get('message', code)}", flush=True)
        time.sleep(2)
    raise TimeoutError("二维码登录超时，请重新运行 --qr-login")


def make_session(args: argparse.Namespace) -> tuple[requests.Session, dict[str, str]]:
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Referer": "https://member.bilibili.com/"})
    cookies = load_cookie_file(cookie_path(args))
    sessdata = os.environ.get("BILI_SESSDATA") or env_file_value("BILI_SESSDATA")
    bili_jct = os.environ.get("BILI_BILI_JCT") or env_file_value("BILI_BILI_JCT")
    if sessdata:
        cookies["SESSDATA"] = sessdata
    if bili_jct:
        cookies["bili_jct"] = bili_jct
    session.cookies.update(cookies)
    if args.qr_login or not (cookies.get("SESSDATA") and cookies.get("bili_jct")):
        cookies = qr_login(session, cookie_path(args))
    if not (cookies.get("SESSDATA") and cookies.get("bili_jct")):
        raise RuntimeError("缺少 SESSDATA/bili_jct；请设置 BILI_SESSDATA、BILI_BILI_JCT 或使用 --qr-login")
    return session, cookies


def upload_file(session: requests.Session, video: Path) -> tuple[dict[str, Any], str]:
    size = video.stat().st_size
    pre = json_request(session, "GET", f"{MEMBER}/preupload", params={
        "name": video.name, "r": "upos", "profile": "ugcfx/bup", "size": size,
    })
    info = pre
    if info.get("OK") != 1:
        raise RuntimeError(f"预上传失败: {pre}")
    endpoint = str(info["endpoint"])
    uri = str(info["upos_uri"]).replace("upos://", "", 1).lstrip("/")
    upload_url = "https:" + endpoint.rstrip("/") + "/" + uri
    chunk_size = int(info.get("chunk_size") or 10 * 1024 * 1024)
    common = {"uploads": "", "output": "json", "profile": "ugcfx/bup", "filesize": size,
              "partsize": chunk_size, "biz_id": info["biz_id"]}
    posted = session.post(upload_url, params=common, headers={"X-Upos-Auth": info["auth"]}, timeout=60)
    posted.raise_for_status()
    meta = posted.json()
    upload_id = meta.get("upload_id")
    if not upload_id:
        raise RuntimeError(f"上传元数据失败: {meta}")
    chunks = (size + chunk_size - 1) // chunk_size
    print(f"开始上传 {video.name}：{size / 1024 / 1024:.1f} MiB，{chunks} 个分片")
    with video.open("rb") as stream:
        for index in range(chunks):
            start = index * chunk_size
            body = stream.read(chunk_size)
            params = {"partNumber": index + 1, "uploadId": upload_id, "chunk": index,
                      "chunks": chunks, "size": len(body), "start": start,
                      "end": start + len(body), "total": size}
            response = session.put(upload_url, params=params, data=body, headers={
                "X-Upos-Auth": info["auth"], "Content-Type": "application/octet-stream",
            }, timeout=300)
            response.raise_for_status()
            if "MULTIPART_PUT_SUCCESS" not in response.text and response.status_code != 200:
                raise RuntimeError(f"分片 {index + 1} 上传失败: {response.text[:300]}")
            print(f"  {index + 1}/{chunks}", flush=True)
    parts = [{"partNumber": i + 1, "eTag": "etag"} for i in range(chunks)]
    done = session.post(upload_url, params={"output": "json", "name": video.name,
                                             "profile": "ugcfx/bup", "uploadId": upload_id,
                                             "biz_id": info["biz_id"]}, json={"parts": parts},
                        headers={"X-Upos-Auth": info["auth"]}, timeout=120)
    done.raise_for_status()
    finished = done.json()
    if finished.get("OK") != 1:
        raise RuntimeError(f"结束上传失败: {finished}")
    return info, str(info["biz_id"])


def publication_title(metadata: dict[str, Any], args: argparse.Namespace, paired: bool) -> str:
    """Require the account's complete KTV title, never the source video's title."""
    raw = args.title or metadata.get("publication_title")
    if not raw:
        raise ValueError("缺少投稿标题：请传 --title 或在元数据中写 publication_title；不能沿用片源 title")
    title = re.sub(r"【纯[kK]自用】", "", str(raw)).strip() + "【纯K自用】"
    if len(title) > 80:
        raise ValueError(f"投稿标题超过 80 字符（{len(title)}）；请人工缩短，不能自动截断")
    prefix = "【ニコカラ/ktv字幕】"
    marker = "（On/Off Vocal）" if paired else r"（(?:On/Off|On|Off) Vocal）"
    pattern = rf"^{re.escape(prefix)}\S.* - \S.*{marker}【纯K自用】$"
    if not re.fullmatch(pattern, title):
        raise ValueError(
            "标题必须为【ニコカラ/ktv字幕】曲名 - 演唱者[作品标签]"
            + ("（On/Off Vocal）" if paired else "（On Vocal）/（Off Vocal）/（On/Off Vocal）")
            + "【纯K自用】；请核对真实曲名、演唱者和作品标签"
        )
    return title


def metadata_payload(metadata: dict[str, Any], video: Path, cid: str, args: argparse.Namespace, csrf: str) -> dict[str, Any]:
    tags = []
    for item in metadata.get("tags") or []:
        tag = str(item).strip()
        if tag and tag not in tags:
            tags.append(tag)
    if len(tags) > 10:
        raise ValueError("投稿标签超过 10 个：请先人工选择与这首歌相关的标签")
    title = publication_title(metadata, args, paired=bool(getattr(args, "off_video", None)))
    # The source video's description belongs to its uploader, not this KTV post.
    desc = args.description if args.description is not None else str(metadata.get("publication_description") or "")
    source_url = metadata.get("source_material_url") or metadata.get("source_url")
    if source_url and source_url not in desc and not args.no_source_note:
        desc = (desc.rstrip() + "\n\n片源：" + str(source_url)).strip()
    for label, value in (
        ("字幕", getattr(args, "subtitle_engine", None) or metadata.get("subtitle_engine")),
        ("分词", getattr(args, "lyrics_split_source", None) or metadata.get("lyrics_split_source")),
    ):
        if value:
            credit = f"{label}：{value}"
            pattern = rf"(?m)^{label}\s*[:：].*$"
            desc = re.sub(pattern, lambda _: credit, desc) if re.search(pattern, desc) else desc.rstrip() + "\n" + credit
    part_title = getattr(args, "part_title", None)
    if not part_title:
        match = re.search(r"(on|off)[_ -]vocal", video.stem, re.IGNORECASE)
        part_title = match.group(1).lower() + " vocal" if match else title
    elif part_title.lower().replace("_", " ") in ("on vocal", "off vocal"):
        part_title = part_title.lower().replace("_", " ")
    return {
        "videos": [{"filename": video.stem, "title": part_title, "desc": desc, "cid": int(cid)}],
        "cover": args.cover or metadata.get("cover_url") or "",
        "cover43": "",
        "title": title,
        "copyright": args.copyright,
        "tid": args.tid,
        "tag": ",".join(tags),
        "desc_format_id": 9999,
        "desc": desc[:2000],
        "recreate": -1,
        "dynamic": args.dynamic or "",
        "interactive": 0,
        "act_reserve_create": 0,
        "no_disturbance": 1 if args.push_dynamic else 0,
        "no_reprint": 1,
        "subtitle": {"open": 0, "lan": ""},
        "dolby": 0,
        "lossless_music": 0,
        "up_selection_reply": False,
        "up_close_reply": False,
        "up_close_danmu": False,
        "web_os": 3,
        "is_only_self": 1 if args.private else 0,
        "csrf": csrf,
    }


def edit_payload(data: dict, part: str, replacement: dict, args: argparse.Namespace, metadata: dict) -> dict:
    archive = data['archive']
    keys = ('aid', 'title', 'cover', 'cover43', 'copyright', 'tid', 'tag', 'desc',
            'desc_format_id', 'source', 'no_reprint', 'dynamic', 'interactive',
            'is_only_self', 'dtime', 'dolby', 'lossless_music')
    payload = {key: archive[key] for key in keys if key in archive}
    recreate = archive.get('recreate', -1)
    subtitle = data.get('subtitle') or {}
    payload.update(recreate=recreate.get('switch', -1) if isinstance(recreate, dict) else recreate,
                   subtitle={'open': int(subtitle.get('allow', subtitle.get('open', 0))),
                             'lan': subtitle.get('lan', '')},
                   no_disturbance=data.get('no_disturbance', 0))
    for key in ('title', 'cover'):
        if getattr(args, key, None) is not None:
            payload[key] = getattr(args, key)
    if args.description is not None:
        payload['desc'] = args.description
    if args.update_source:
        url = metadata.get('source_url')
        if not url:
            raise ValueError('Metadata has no source_url')
        pattern = r'(?m)^片源\s*[:：].*$'
        credit = '片源：' + url
        payload['desc'] = re.sub(pattern, lambda _: credit, payload['desc']) if re.search(pattern, payload['desc']) else payload['desc'] + '\n' + credit
    if len(payload['title']) > 80:
        raise ValueError('Title exceeds 80 characters')
    videos = [{k: v.get(k, '') for k in ('filename', 'cid', 'title', 'desc')} for v in data['videos']]
    matches = [i for i, v in enumerate(videos) if re.search(rf'\b{part}[ _-]vocal\b', v['title'], re.I)]
    if len(matches) > 1:
        raise ValueError('Ambiguous replacement: multiple matching part titles')
    replacement = {**replacement, 'title': part + ' vocal', 'desc': ''}
    if matches:
        videos[matches[0]] = replacement
    else:
        videos.insert(0 if part == 'on' else len(videos), replacement)
    payload['videos'] = videos
    return payload


def replace_part(args: argparse.Namespace, video: Path, metadata: dict) -> int:
    session, cookies = make_session(args)
    data = json_request(session, 'GET', f'{MEMBER}/x/vupre/web/archive/view', params={'aid': args.aid})['data']
    receipt_path = args.receipt or args.metadata.parent / f'edit_{args.aid}_{args.replace_part}.json'
    receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
    preview = edit_payload(data, args.replace_part,
                           {'filename': video.stem, 'cid': '<upload-biz-id>'}, args, metadata)
    if not args.submit:
        print(json.dumps({'operation': 'edit', 'payload': preview}, ensure_ascii=False, indent=2))
        print('dry-run: read-only archive lookup; --submit uploads/replaces only the selected part')
        return 0
    digest = hashlib.sha256()
    with video.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(block)
    identity = {'aid': args.aid, 'part': args.replace_part, 'sha256': digest.hexdigest()}
    if receipt and any(receipt.get(k) != v for k, v in identity.items()):
        raise ValueError('Receipt belongs to another file/operation; choose a new --receipt')

    def save():
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = receipt_path.with_name(receipt_path.name + '.tmp')
        temporary.write_text(json.dumps(receipt, ensure_ascii=False, indent=2))
        temporary.replace(receipt_path)

    if not receipt:
        info, cid = upload_file(session, video)
        receipt = {**identity, 'filename': Path(info['upos_uri']).stem, 'cid': int(cid), 'state': 'uploaded'}
        save()
    if receipt.get('response') or any(v['cid'] == receipt['cid'] for v in data['videos']):
        print(json.dumps({'already_submitted': True, 'archive': data['archive']['state_desc'],
                          'part_present': any(v['cid'] == receipt['cid'] for v in data['videos']),
                          'cid': receipt['cid']}, ensure_ascii=False))
        return 0
    if receipt.get('state') == 'submitting':
        raise RuntimeError('Previous edit result is uncertain; inspect archive before retrying')
    payload = edit_payload(data, args.replace_part,
                           {k: receipt[k] for k in ('filename', 'cid')}, args, metadata)
    csrf = cookies.get('bili_jct') or session.cookies.get('bili_jct')
    payload['csrf'] = csrf
    receipt['state'] = 'submitting'
    save()
    result = json_request(session, 'POST', f'{MEMBER}/x/vu/web/edit',
                          params={'csrf': csrf, 'ts': int(time.time() * 1000)}, json=payload)
    receipt.update(state='submitted', response=result)
    save()
    readback = json_request(session, 'GET', f'{MEMBER}/x/vupre/web/archive/view', params={'aid': args.aid})['data']
    receipt['readback'] = {'state': readback['archive']['state_desc'], 'videos': readback['videos']}
    save()
    if not any(v['cid'] == receipt['cid'] for v in readback['videos']):
        raise RuntimeError('Edit accepted but new CID not yet visible; inspect archive instead of resubmitting')
    print(json.dumps({'result': result, 'readback': receipt['readback']}, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metadata", type=Path, help="source_metadata.json")
    parser.add_argument("--video", type=Path, help="video to upload; defaults to sibling input.mp4 or *_ON_VOCAL.mp4")
    parser.add_argument("--off-video", type=Path, help="verified OFF VOCAL video; submit as the second part of one archive")
    parser.add_argument("--cookie-file", help="local JSON cookie file (default: ~/.config/jpkara/bilibili_cookie.json)")
    parser.add_argument("--qr-login", action="store_true", help="force QR login and print the scan URL")
    parser.add_argument("--submit", action="store_true", help="actually upload and submit; default is dry-run")
    parser.add_argument("--title")
    parser.add_argument("--description")
    parser.add_argument("--subtitle-engine", help="Actual user-selected alignment engine, e.g. FA-KARA or YOHANE")
    parser.add_argument("--lyrics-split-source", help="Actual lyric/speaker split source, e.g. 萌娘百科")
    parser.add_argument("--part-title", help="Part title; ON/OFF VOCAL is normalized to lowercase")
    parser.add_argument("--cover")
    parser.add_argument("--tid", type=int, default=130, help="Bilibili music subcategory (default: 130; override if needed)")
    parser.add_argument("--copyright", type=int, choices=(1, 2), default=1, help="1=self-made, 2=repost (default: 1 for this user's KTV submissions)")
    parser.add_argument("--dynamic", help="dynamic post text")
    parser.add_argument("--push-dynamic", action="store_true")
    parser.add_argument("--private", action="store_true", help="submit as only-visible-to-self")
    parser.add_argument("--no-source-note", action="store_true")
    parser.add_argument('--aid', type=int, help='existing archive aid; requires --replace-part')
    parser.add_argument('--replace-part', choices=('on', 'off'), help='replace/add only this part in an existing archive')
    parser.add_argument('--receipt', type=Path, help='persist upload CID, file identity and edit response for safe retries')
    parser.add_argument('--update-source', action='store_true', help='update existing archive source credit from metadata')
    args = parser.parse_args()
    metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
    video = args.video or next(iter(sorted(args.metadata.parent.glob("*_ON_VOCAL.mp4"))), None)
    if not video or not video.is_file():
        parser.error("找不到已渲染的 ON 视频，请用 --video 指定成片")
    if bool(args.aid) != bool(args.replace_part):
        parser.error('--aid and --replace-part must be supplied together')
    if (args.receipt or args.update_source) and not args.replace_part:
        parser.error('--receipt/--update-source require --aid and --replace-part')
    if args.replace_part:
        if args.off_video or args.part_title or args.aid <= 0 or not args.video:
            parser.error('Part replacement requires positive --aid and an explicit single --video')
        return replace_part(args, video, metadata)
    if args.off_video and not args.off_video.is_file():
        parser.error("找不到 --off-video 指定的 OFF 成片")
    if args.off_video and args.off_video.resolve() == video.resolve():
        parser.error("ON 和 OFF 必须是不同的已验证成片")
    if args.off_video and args.part_title:
        parser.error("双分 P 投稿会固定使用 on vocal/off vocal，不能同时指定 --part-title")
    if args.qr_login and not args.submit:
        make_session(args)
        print("二维码登录完成；本次未上传视频。")
        return 0
    try:
        preview = metadata_payload(metadata, video, "0", args, "<csrf>")
    except ValueError as exc:
        parser.error(str(exc))
    if args.off_video:
        preview["videos"][0]["title"] = "on vocal"
        preview["videos"].append({**preview["videos"][0], "filename": args.off_video.stem,
                                  "title": "off vocal"})
    if not args.submit:
        for part in preview["videos"]:
            part["cid"] = "<upload-biz-id>"
        print(json.dumps({"video": str(video), "payload": preview}, ensure_ascii=False, indent=2))
        print("dry-run：加 --submit 才会上传；没有读取或打印任何 token。")
        return 0
    session, cookies = make_session(args)
    csrf = cookies.get("bili_jct") or session.cookies.get("bili_jct")
    payload = metadata_payload(metadata, video, "0", args, str(csrf))
    videos = [video] + ([args.off_video] if args.off_video else [])
    payload["videos"] = []
    for part_video, part_title in zip(videos, ("on vocal", "off vocal") if args.off_video else (preview["videos"][0]["title"],)):
        info, cid = upload_file(session, part_video)
        payload["videos"].append({"filename": Path(info["upos_uri"]).stem,
                                  "title": part_title, "desc": payload["desc"], "cid": int(cid)})
    result = json_request(session, "POST", f"{MEMBER}/x/vu/web/add/v3", params={"ts": int(time.time() * 1000), "csrf": csrf}, json=payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
