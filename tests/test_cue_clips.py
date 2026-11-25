import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import cue_clips  # noqa: E402

NAMES = ["intro", "inhale", "hold", "exhale", "finish"]


def make_take(path, lead=0.5, tones=(0.6,), gap=0.5, tail=0.5):
    # `lead` s of silence, the tones separated by `gap` s of silence (a pause inside one line), then `tail` s.
    pieces = [f"anullsrc=r=24000:cl=mono:d={lead}"]
    for i, tone in enumerate(tones):
        pieces.append(f"sine=f=440:r=24000:d={tone}")
        pieces.append(f"anullsrc=r=24000:cl=mono:d={gap if i < len(tones) - 1 else tail}")
    args = ["ffmpeg", "-y", "-loglevel", "error"]
    for p in pieces:
        args += ["-f", "lavfi", "-i", p]
    args += ["-filter_complex", "".join(f"[{i}:a]" for i in range(len(pieces))) + f"concat=n={len(pieces)}:v=0:a=1",
             str(path)]
    subprocess.run(args, check=True)
    return path


def duration(path):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]))


def codec(path):
    return subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                                    "stream=codec_name", "-of", "csv=p=0", str(path)]).decode().strip()


class CueClipsTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def takes(self, count=5):
        return [make_take(self.dir / f"chunk_{n:02d}.wav") for n in range(count)]

    def test_the_span_drops_silence_at_both_ends(self):
        start, end = cue_clips.spoken_span(make_take(self.dir / "one.wav", lead=0.5, tones=(0.6,), tail=0.7))
        self.assertAlmostEqual(start, 0.5, delta=0.05)
        self.assertAlmostEqual(end, 1.1, delta=0.05)

    def test_a_pause_inside_a_line_is_kept(self):
        start, end = cue_clips.spoken_span(make_take(self.dir / "two.wav", lead=0.5, tones=(0.6, 0.6), gap=0.6))
        self.assertAlmostEqual(end - start, 1.8, delta=0.08)

    def test_clips_are_trimmed_m4a_named_after_the_cues(self):
        clips = cue_clips.write_clips(self.takes(), NAMES, self.dir / "clips")
        self.assertEqual([c.stem for c in clips], NAMES)
        for clip in clips:
            self.assertEqual(clip.suffix, ".m4a")
            self.assertEqual(codec(clip), "aac")
            self.assertLessEqual(duration(clip), 0.6 + 2 * cue_clips.EDGE_PAD + 0.05)

    def test_a_missing_take_stops_without_writing(self):
        sources = self.takes(4) + [self.dir / "chunk_04.wav"]
        out = self.dir / "clips"
        with self.assertRaises(SystemExit) as stop:
            cue_clips.write_clips(sources, NAMES, out)
        self.assertIn("chunk_04.wav", str(stop.exception))
        self.assertFalse(out.exists())

    def test_a_failed_run_keeps_the_previous_clips(self):
        out = self.dir / "clips"
        cue_clips.write_clips(self.takes(), NAMES, out)
        before = sorted(p.name for p in out.iterdir())
        (self.dir / "chunk_02.wav").unlink()
        with self.assertRaises(SystemExit):
            cue_clips.write_clips([self.dir / f"chunk_{n:02d}.wav" for n in range(5)], NAMES, out)
        self.assertEqual(sorted(p.name for p in out.iterdir()), before)


if __name__ == "__main__":
    unittest.main()
