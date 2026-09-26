# Bilibili DASH 下载与离线合并

Use this procedure for a Bilibili BV URL, BV ID, or `b23.tv` short URL. It is an offline downloader: fetch the DASH video and audio resources completely, then mux them into a local MP4. It does not implement real-time mixing.

## 1. Resolve the BV ID and target page

- Accept a `BV...` ID or a `b23.tv` short URL.
- For a short URL, follow redirects with a normal HTTP client and extract the `BV[0-9A-Za-z]+` token from the final URL. Do not log the complete redirected URL if it contains query parameters.
- The page index is zero-based: web `p=1` means `index=0`.
- Reject an invalid or ambiguous page index instead of silently choosing another page.

## 2. Read the page `cid` and duration

Send an anonymous request with only this identifying header:

```text
GET https://api.bilibili.com/x/player/pagelist?bvid={bvid}
User-Agent: Mozilla/5.0
```

Do not send cookies. Require JSON `code == 0`, then read:

```text
data[index].cid
data[index].duration
```

Retain the page duration for the later completeness check. A failure, empty `data`, missing `cid`, or invalid page index is a hard error.

## 3. Request the 1080P DASH tracks

Use the existing anonymous request parameters exactly:

```text
GET https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&qn=80&fnval=4048&fnver=0&fourk=0&try_look=1
User-Agent: Mozilla/5.0
Referer: https://www.bilibili.com/video/{bvid}
```

Do not send cookies. `qn=80` requests ordinary 1080P. Keep `fnval=4048` and `try_look=1`. Do not use `data.quality` as proof that 1080P was returned; inspect the actual DASH arrays:

- Video candidates are `data.dash.video` entries with `id == 80`.
- Prefer a video whose `codecs` starts with `avc1` (H.264). Within the same codec class, choose the greatest `bandwidth`.
- If there is no `id == 80` video candidate, fail clearly. Do not silently downgrade to another quality.
- Audio candidates come from `data.dash.audio`; choose the greatest `bandwidth`. When MP4 playback compatibility is important, prefer an audio codec beginning with `mp4a`, then apply the bandwidth rule.

For each selected track retain, at minimum:

```text
base_url or baseUrl
backup_url or backupUrl (optional)
id, width, height, codecs, bandwidth
```

Log the non-secret track metadata, not the complete signed URL. `try_look=1` does not guarantee that the content is fully authorized or complete; only the finished download and duration checks establish success.

## 4. Download both resources completely

Save the selected resources as `video.m4s` and `audio.m4s`. The URLs represent complete media resources, including their initialization data; download from the beginning and do not reconstruct initialization segments yourself.

Every media request must include:

```text
User-Agent: Mozilla/5.0
Referer: https://www.bilibili.com/video/{bvid}
```

Implementation requirements:

- Stream response chunks directly to disk; never load the full resource into memory.
- Download video and audio concurrently when practical, with connection timeout, read-idle timeout, finite retries, and bounded backoff.
- Write to `video.m4s.part` and `audio.m4s.part`; rename to the final names only after the individual download passes its checks.
- If resuming is implemented, request `Range: bytes={existing_size}-` and accept append only when the response is `206` with a matching `Content-Range`. If the server returns `200`, truncate/rewrite from byte zero; never append a full response to an existing partial file.
- Try `backup_url` when the primary URL fails. If a signed URL is expired or returns an access failure, request playurl again and verify that the refreshed track still matches the selected identity (`id`, codec family, and relevant dimensions/bandwidth) before retrying.
- Log track metadata, byte counts, elapsed time, and concise errors. Never log cookies or complete signed URLs.

At minimum, reject zero-byte files and failed HTTP responses. Where the container/parser supports it, inspect each `.m4s` with `ffprobe` and compare its duration with the page duration. The final MP4 duration check remains mandatory.

## 5. Lossless offline merge

After both tracks are complete, merge without re-encoding:

```bash
ffmpeg -nostdin \
  -i video.m4s \
  -i audio.m4s \
  -map 0:v:0 \
  -map 1:a:0 \
  -c copy \
  -movflags +faststart \
  output.mp4
```

Do not add `-shortest` by default. It can hide an incomplete track by truncating the final file to the shorter stream. Use a temporary output and keep `video.m4s`/`audio.m4s` until validation succeeds.

## 6. Validate before cleanup

Inspect the final file with:

```bash
ffprobe -v error \
  -show_entries stream=index,codec_type,codec_name,width,height,duration:format=duration,size \
  -of json output.mp4
```

Acceptance checks:

- Both a video stream and an audio stream exist.
- Standard landscape 1080P is normally 1920×1080, but accept portrait and unusual aspect ratios when the selected track metadata explains them.
- Video and audio durations are close to the page duration and are not merely the first few seconds.
- Spot-check the beginning, middle, and end for decodability and audio/video synchronization.
- An audio stream existing does not prove it contains sound. If required, decode samples and inspect audio energy or silence intervals.
- Delete intermediate `.m4s` and `.part` files only after all checks pass. Preserve them and report the failure when validation does not pass.

`BV1dqj16aECG` may be used as a historical anonymous-1080P test sample, but it is not a guarantee of current network/API behavior and must not be described as freshly verified without rerunning the request.
