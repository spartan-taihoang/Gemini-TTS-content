# Turn any background recording into a seamless loop at the shared level, so tts_episode.py can loop it without a click.
# Usage: python3 sleepfit/shared_ambience/make_seamless.py <in.mp4|mp3|wav|flac> <out.flac>   (needs ffmpeg)
# The last XF seconds are crossfaded (equal power) into the start and dropped, so the output is XF seconds shorter.
# Output is normalized to -19 dB RMS like every loop here, so "volume_db": -5 gives the same balance under a voice.
import array, math, subprocess, sys

src, out = sys.argv[1], sys.argv[2]
SR, XF = 44100, 4.0
raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", src, "-map", "0:a:0", "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
                     check=True, capture_output=True).stdout
x = array.array("f"); x.frombytes(raw)
n, xf = len(x) // 2, int(XF * SR)
if n < 4 * xf:
    sys.exit(f"{src}: too short for a {XF:.0f} s crossfade")
m = n - xf
y = x[:2 * m]
for i in range(xf):
    a = i / xf
    gi, go = math.sin(a * math.pi / 2), math.cos(a * math.pi / 2)
    for c in (0, 1):
        y[2 * i + c] = x[2 * i + c] * gi + x[2 * (m + i) + c] * go

rms = math.sqrt(sum(v * v for v in y) / len(y))
g = 10 ** (-19 / 20) / rms
pk = max(abs(v) for v in y) * g
if pk > 10 ** (-3 / 20):
    g *= 10 ** (-3 / 20) / pk
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                "-af", f"volume={g:.6f}", "-c:a", "flac", "-sample_fmt", "s16", out],
               input=y.tobytes(), check=True)
print(f"wrote {out}: {m / SR:.1f} s, gain {20 * math.log10(g):+.1f} dB")
