# Original 60 s seamless loop: warm sustained pad (D major, additive sine synthesis, no noise source).
# Usage: python3 sleepfit/shared_ambience/make_pad.py <out.flac>   (needs ffmpeg)
# Every frequency and every swell is a whole number of cycles per 60 s, so the loop has no click at the seam, and
# there is nothing above ~900 Hz, so there is no hiss. Output is -19 dB RMS like every loop here, so one volume_db
# works for all of them. Tweak the notes or swells, rerun and listen.
import array, math, subprocess, sys

out = sys.argv[1]
SR, LOOP = 44100, 60
NOTES = [(73.42, 0.9), (110.0, 0.8), (146.83, 1.0), (185.0, 0.55), (220.0, 0.8), (293.66, 0.6), (329.63, 0.3), (440.0, 0.35)]


def cycles(f):
    return round(f * LOOP) / LOOP  # frequency with a whole number of cycles per loop


terms = {0: [], 1: []}  # channel -> expression parts
for i, (f, amp) in enumerate(NOTES):
    for ch, detune in ((0, -0.15), (1, 0.15)):  # slow beating between the two ears: gentle width
        fr = cycles(f) + detune
        swell = (i % 3) + 1  # 1-3 slow swells per loop, each note on its own rhythm
        ph = i * 1.3 + ch * 0.9
        terms[ch].append(f"{amp:.3f}*(0.7+0.3*sin(2*PI*{swell}*t/{LOOP}+{ph:.3f}))*sin(2*PI*{fr:.4f}*t+{ph * 2:.3f})")
expr = "|".join("+".join(terms[ch]) for ch in (0, 1))
raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i",
                      f"aevalsrc='{expr}':s={SR}:d={LOOP}:c=stereo", "-f", "f32le", "-"],
                     check=True, capture_output=True).stdout
x = array.array("f"); x.frombytes(raw)
rms = math.sqrt(sum(v * v for v in x) / len(x))
g = 10 ** (-19 / 20) / rms
pk = max(abs(v) for v in x) * g
if pk > 10 ** (-3 / 20):
    g *= 10 ** (-3 / 20) / pk
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                "-af", f"volume={g:.6f}", "-c:a", "flac", "-sample_fmt", "s16", out], input=x.tobytes(), check=True)
print(f"wrote {out}: {len(x) / 2 / SR:.1f} s, gain {20 * math.log10(g):+.1f} dB")
