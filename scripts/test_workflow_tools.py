"""Behavior checks; all media is synthetic and uploads are mocked."""
import argparse
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

import bilibili_download as download
import bilibili_submit as submit
from fix_countdown_spacing import fix_spacing
from render_on_off import merge_ass, packet_md5, probe


FORMAT = 'Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding'


def style(name, size, margin):
    return f'Style: {name},sans-serif,{size},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,3,0,1,84,28,{margin},1'


def ass(text='TEST', style_name='K1'):
    return ('[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\n'
            '[V4+ Styles]\nFormat: ' + FORMAT + '\n' +
            '\n'.join([style('K1', 84, 245), style('K1-furigana', 34, 245),
                       style('Intro', 50, 298)]) + '\n[Events]\n'
            'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'
            'Comment: 0,0:00:00.00,0:00:00.00,K1,,0,0,0,code once,remember("furigana_offset", -10)\n'
            f'Dialogue: 0,0:00:00.00,0:00:01.00,{style_name},,0,0,0,,{text}\n')


class WorkflowTests(unittest.TestCase):
    def test_countdown_preserves_events_and_is_idempotent(self):
        original = ass()
        fixed, report = fix_spacing(original)
        self.assertGreaterEqual(report['protected_effect_top_estimate'] - report['countdown_bottom_estimate'], 24)
        self.assertEqual([x for x in fixed.splitlines() if x.startswith('Dialogue:')],
                         [x for x in original.splitlines() if x.startswith('Dialogue:')])
        self.assertEqual(fix_spacing(fixed)[0], fixed)
        with self.assertRaises(ValueError):
            fix_spacing(original.replace(',0,,TEST', ',0,fx,TEST'))

    def test_merge_and_reject_conflicts(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            a, b, out = p/'a.ass', p/'b.ass', p/'merged.ass'
            a.write_text(ass('MAIN'))
            b.write_text(ass('HARMONY'))
            merge_ass(a, b, out)
            self.assertEqual(out.read_text(encoding='utf-8-sig').count('Dialogue:'), 2)
            b.write_text(ass().replace('sans-serif,84', 'sans-serif,90'))
            with self.assertRaises(ValueError):
                merge_ass(a, b, out)

    def test_download_selects_actual_1080_avc(self):
        d = {'dash': {'video': [dict(id=120, codecs='avc1', bandwidth=999),
                               dict(id=80, codecs='hev1', bandwidth=888),
                               dict(id=80, codecs='avc1', bandwidth=123)],
                      'audio': [dict(id=1, codecs='mp4a', bandwidth=90)]}}
        self.assertEqual(download.select_tracks(d)[0]['bandwidth'], 123)
        d['dash']['video'] = d['dash']['video'][:1]
        with self.assertRaises(ValueError):
            download.select_tracks(d)

    def test_download_retries_without_appending_partial_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)/'audio.m4s'
            first = Mock()
            first.__enter__ = Mock(return_value=first)
            first.__exit__ = Mock(return_value=False)
            first.status_code = 200
            first.headers = {'Content-Length': '6'}
            first.iter_content.return_value = iter([b'bad'])
            second = Mock()
            second.__enter__ = Mock(return_value=second)
            second.__exit__ = Mock(return_value=False)
            second.status_code = 200
            second.headers = {'Content-Length': '6'}
            second.iter_content.return_value = iter([b'abcdef'])
            with patch.object(download.requests, 'get', side_effect=[first, second]), patch.object(download.time, 'sleep'):
                download.download_track('audio', {'base_url': 'https://example.invalid/media'}, target, {}, None)
            self.assertEqual(target.read_bytes(), b'abcdef')

    @staticmethod
    def archive():
        return {'archive': {'aid': 1, 'title': 'SONG', 'cover': 'original-cover', 'copyright': 1,
                            'desc': '片源：old', 'state_desc': 'processing', 'recreate': {'switch': -1}},
                'subtitle': {'allow': False, 'lan': ''},
                'videos': [{'cid': 7, 'filename': 'off-upload', 'title': 'off vocal', 'desc': ''}]}

    def test_edit_preserves_other_parts_and_does_not_resubmit(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            video = p/'on.mp4'
            video.write_bytes(b'synthetic upload fixture')
            args = argparse.Namespace(aid=1, replace_part='on', receipt=p/'receipt.json', submit=True,
                title=None, cover=None, description=None, update_source=False, metadata=p/'metadata.json')
            before = self.archive()
            original = copy.deepcopy(before)
            after = copy.deepcopy(before)
            after['videos'].insert(0, {'cid': 8, 'filename': 'new-upload', 'title': 'on vocal', 'desc': ''})
            response = {'code': 0, 'data': {'aid': 1}}
            with patch.object(submit, 'make_session', return_value=(Mock(), {'bili_jct': 'test-only'})), \
                 patch.object(submit, 'upload_file', return_value=({'upos_uri': 'upos://new-upload.mp4'}, '8')) as upload, \
                 patch.object(submit, 'json_request', side_effect=[{'data': before}, response, {'data': after}, {'data': after}]) as request, \
                 contextlib.redirect_stdout(io.StringIO()):
                submit.replace_part(args, video, {})
                submit.replace_part(args, video, {})
            self.assertEqual(upload.call_count, 1)
            self.assertEqual(sum(c.args[1] == 'POST' for c in request.call_args_list), 1)
            payload = request.call_args_list[1].kwargs['json']
            self.assertEqual(payload['videos'][1], before['videos'][0])
            self.assertEqual(payload['cover'], 'original-cover')
            self.assertEqual(before, original)
            self.assertNotIn('test-only', args.receipt.read_text())

    def test_uncertain_edit_stops_before_upload_or_post(self):
        with tempfile.TemporaryDirectory() as temp:
            import hashlib
            p = Path(temp)
            video = p/'on.mp4'
            video.write_bytes(b'fixture')
            receipt = p/'receipt.json'
            receipt.write_text(json.dumps({'aid': 1, 'part': 'on', 'sha256': hashlib.sha256(b'fixture').hexdigest(),
                                           'filename': 'pending', 'cid': 8, 'state': 'submitting'}))
            args = argparse.Namespace(aid=1, replace_part='on', receipt=receipt, submit=True,
                title=None, cover=None, description=None, update_source=False, metadata=p/'metadata.json')
            with patch.object(submit, 'make_session', return_value=(Mock(), {})), \
                 patch.object(submit, 'upload_file') as upload, \
                 patch.object(submit, 'json_request', return_value={'data': self.archive()}) as request:
                with self.assertRaises(RuntimeError):
                    submit.replace_part(args, video, {})
                upload.assert_not_called()
                self.assertEqual(request.call_count, 1)

    def test_real_ffmpeg_on_off_and_non_aac(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            def run(*command):
                subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            source = p/'source.mp4'
            run('ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=size=320x180:rate=24',
                '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000', '-t', '1',
                '-c:v', 'libx264', '-threads', '2', '-c:a', 'aac', '-ac', '2', str(source))
            main, harmony = p/"main's 字幕.ass", p/'harmony.ass'
            main.write_text(ass())
            harmony.write_text(ass('HARMONY'))
            script = str(Path(__file__).with_name('render_on_off.py'))
            common = ['python', script, '--video', str(source), '--ass', str(main),
                      '--encoder', 'libx264', '--preset', 'ultrafast', '--threads', '2', '--verify', 'full']
            run(*common, '--harmony-ass', str(harmony), '--instrumental', str(source),
                '--width', '160', '--height', '90', '--output-prefix', str(p/'pair'))
            on, off = p/'pair_ON_VOCAL.mp4', p/'pair_OFF_VOCAL.mp4'
            self.assertEqual(packet_md5(source), packet_md5(on))
            self.assertTrue(off.exists())
            self.assertEqual(probe(on)['streams'][0]['width'], 160)
            non_aac = p/'fullmix.flac'
            run('ffmpeg', '-v', 'error', '-i', str(source), '-vn', '-c:a', 'flac', str(non_aac))
            run(*common, '--mode', 'on', '--full-mix', str(non_aac), '--output-prefix', str(p/'solo'))
            self.assertEqual(probe(p/'solo_ON_VOCAL.mp4')['streams'][1]['codec_name'], 'aac')
            self.assertFalse((p/'solo_OFF_VOCAL.mp4').exists())
            self.assertEqual(json.loads((p/'solo_render.json').read_text())['on_audio'], 'aac')
            run(*common, '--mode', 'off', '--instrumental', str(non_aac), '--output-prefix', str(p/'off'))
            self.assertTrue((p/'off_OFF_VOCAL.mp4').exists())
            self.assertFalse((p/'off_ON_VOCAL.mp4').exists())


if __name__ == '__main__':
    unittest.main()
