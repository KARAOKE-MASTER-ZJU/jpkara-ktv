#!/usr/bin/env python3
"""Download complete Bilibili 1080p DASH tracks, save metadata, and mux offline."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import tempfile
import time
from urllib.parse import parse_qs, urlparse

import requests
import bilibili_metadata as metadata
from render_on_off import probe, run


def api(endpoint: str, params: dict, headers: dict) -> dict | list:
    response = requests.get('https://api.bilibili.com' + endpoint, params=params, headers=headers, timeout=40)
    response.raise_for_status()
    result = response.json()
    if result.get('code') != 0:
        raise RuntimeError(f"{endpoint}: code={result.get('code')}")
    return result['data']


def select_tracks(data: dict) -> tuple[dict, dict]:
    videos = [x for x in data['dash']['video'] if x['id'] == 80]
    if not videos:
        raise ValueError('No actual id=80 1080P track; refusing to downgrade')
    video = max(videos, key=lambda x: (x['codecs'].startswith('avc1'), x['bandwidth']))
    audio = max(data['dash']['audio'], key=lambda x: (x['codecs'].startswith('mp4a'), x['bandwidth']))
    return video, audio


def download_track(name: str, track: dict, destination: Path, headers: dict, refresh) -> None:
    partial = destination.with_suffix('.part')
    for attempt in range(4):
        urls = [track.get('base_url') or track['baseUrl']] + (track.get('backup_url') or track.get('backupUrl') or [])
        try:
            with requests.get(urls[attempt % len(urls)], headers=headers, stream=True, timeout=(20, 45)) as response:
                if response.status_code in (401, 403, 410) and attempt < 3:
                    refreshed = refresh()
                    if (refreshed['id'], refreshed['codecs']) != (track['id'], track['codecs']):
                        raise ValueError('Refreshed DASH track identity changed')
                    track = refreshed
                    continue
                response.raise_for_status()
                expected = int(response.headers.get('Content-Length', 0))
                with partial.open('wb') as stream:
                    for chunk in response.iter_content(1024 * 1024):
                        stream.write(chunk)
            size = partial.stat().st_size
            if not size or (expected and size != expected):
                raise ValueError('Incomplete download')
            partial.replace(destination)
            print(f'{name}: {size} bytes complete', flush=True)
            return
        except Exception as error:
            print(f'{name}: attempt {attempt + 1}/4 failed ({type(error).__name__})', flush=True)
            if attempt == 3:
                raise RuntimeError(f'{name} download failed; partial files retained') from None
            time.sleep(attempt + 1)
    raise RuntimeError(f'{name}: expired URLs could not be refreshed')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', help='BV id or Bilibili URL')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--page', type=int, help='1-based; defaults to URL p= or 1')
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    bv = metadata.bvid_from(args.source)
    page_number = args.page if args.page is not None else int(parse_qs(urlparse(args.source).query).get('p', ['1'])[0])
    output = args.output.resolve()
    sidecar = output.parent / 'source_metadata.json'
    for path in (output, sidecar):
        if path.exists() and not args.overwrite:
            parser.error('Output/metadata exists; use another directory or --overwrite')
    output.parent.mkdir(parents=True, exist_ok=True)
    info = metadata.fetch(bv)
    sidecar.write_text(json.dumps(info, ensure_ascii=False, indent=2))
    headers = {'User-Agent': 'Mozilla/5.0', 'Referer': f'https://www.bilibili.com/video/{bv}'}
    pages = api('/x/player/pagelist', {'bvid': bv}, {'User-Agent': 'Mozilla/5.0'})
    if not 1 <= page_number <= len(pages):
        parser.error('Requested page does not exist')
    page = pages[page_number - 1]

    def tracks():
        return select_tracks(api('/x/player/playurl', {'bvid': bv, 'cid': page['cid'], 'qn': 80,
            'fnval': 4048, 'fnver': 0, 'fourk': 0, 'try_look': 1}, headers))

    video, audio = tracks()
    work = Path(tempfile.mkdtemp(prefix='ktv-download-', dir=output.parent))
    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(download_track, name, track, work / f'{name}.m4s', headers,
                               lambda i=index: tracks()[i])
                   for index, (name, track) in enumerate([('video', video), ('audio', audio)])]
        for future in futures:
            future.result()
    merged = work / 'merged.mp4'
    run(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-i', str(work/'video.m4s'), '-i', str(work/'audio.m4s'),
         '-map', '0:v:0', '-map', '1:a:0', '-c', 'copy', '-movflags', '+faststart', str(merged)])
    media = probe(merged)
    if len(media['streams']) != 2 or any(abs(float(s['duration']) - page['duration']) > 2 for s in media['streams']):
        raise RuntimeError('Downloaded streams do not match page duration; partial files retained')
    actual_video = next(s for s in media['streams'] if s['codec_type'] == 'video')
    if (actual_video['width'], actual_video['height']) != (video['width'], video['height']):
        raise RuntimeError('Downloaded video dimensions differ from selected DASH track')
    info.update(cid=page['cid'], duration_seconds=page['duration'],
                source_url=f'https://www.bilibili.com/video/{bv}/?p={page_number}',
                video={k: video.get(k) for k in ('id', 'width', 'height', 'codecs')},
                audio={k: audio.get(k) for k in ('id', 'codecs')})
    info['video']['quality_id'] = info['video'].pop('id')
    info['audio']['quality_id'] = info['audio'].pop('id')
    info['video']['codec'] = info['video'].pop('codecs')
    info['audio']['codec'] = info['audio'].pop('codecs')
    sidecar.write_text(json.dumps(info, ensure_ascii=False, indent=2))
    merged.replace(output)
    shutil.rmtree(work)
    print('Complete 1080P input and actual-track source_metadata.json saved')


if __name__ == '__main__':
    main()
