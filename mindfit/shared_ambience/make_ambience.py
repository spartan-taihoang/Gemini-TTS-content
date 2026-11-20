# Original 60 s seamless loop: sparse soft piano (additive synthesis).
# Usage: python3 sleepfit/shared_ambience/make_ambience.py <scratch dir> sleepfit/shared_ambience  (needs ffmpeg)
# Writes ambience_piano.flac at -19 dB RMS like ambience_soft_pad.flac. Rain and crickets now come from CC0 recordings
# (SOURCES.md), not from here. Tweak the chords or note velocities, rerun, and listen; random.Random(7) keeps it reproducible.
import array, math, random, subprocess, sys
from pathlib import Path
W = Path(sys.argv[1]); OUT = Path(sys.argv[2])
SR, LOOP, TAIL = 44100, 60.0, 12.0
N, NT = int(SR * LOOP), int(SR * (LOOP + TAIL))
rnd = random.Random(7)

def ff(*a): subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *a], check=True)
def write_f32(p, a): p.write_bytes(array.array("f", a).tobytes())
def read_f32(p): x = array.array("f"); x.frombytes(p.read_bytes()); return x

# --- piano: mellow additive tone, slightly inharmonic, upper partials die first
cache = {}
def note(midi, vel):
    k = (midi, round(vel, 2))
    if k in cache: return cache[k]
    f0 = 440 * 2 ** ((midi - 69) / 12); dur = 6.0; n = int(SR * dur)
    tau0 = 3.2 * (1.6 if midi < 50 else 1.0)
    out = [0.0] * n
    for h in range(1, 7):
        f = h * f0 * math.sqrt(1 + 0.0004 * h * h)
        if f > 5000: break
        amp = vel / h ** 1.6; tau = tau0 / (1 + 0.7 * (h - 1)); w = 2 * math.pi * f / SR
        c, s = math.cos(w), math.sin(w); x, y = 1.0, 0.0  # rotating phasor: no per-sample sin()
        d = math.exp(-1 / (tau * SR)); e = amp
        for i in range(n):
            out[i] += e * y; x, y = x * c - y * s, x * s + y * c; e *= d
    att = int(0.012 * SR)
    for i in range(att): out[i] *= i / att
    rel = int(0.4 * SR)
    for i in range(rel): out[n - rel + i] *= 1 - i / rel
    cache[k] = out; return out

# Dmaj7 - Bm7 - Gmaj7 - Asus2, 15 s each; bass on the one, then sparse rising notes
chords = [(38, [57, 61, 66, 64, 69]), (35, [54, 57, 62, 61, 66]), (31, [50, 54, 59, 57, 62]), (33, [52, 57, 59, 61, 64])]
events = []
for ci, (bass, tones) in enumerate(chords):
    t0 = ci * 15.0
    events.append((t0 + 0.05, bass, 0.2)); events.append((t0 + 0.05, bass + 12, 0.1))
    t = t0 + 1.6
    for j, m in enumerate(rnd.sample(tones, 4)):
        events.append((t + rnd.uniform(-0.15, 0.15), m, rnd.uniform(0.17, 0.27)))
        t += rnd.uniform(2.2, 3.4)
    if ci % 2 == 1: events.append((t0 + 12.5, tones[-1] + 12, 0.12))  # a high, quiet answer
dry = [0.0] * NT
for t, m, v in events:
    s = note(m, v); o = int(t * SR)
    for i, val in enumerate(s):
        if o + i < NT: dry[o + i] += val
write_f32(W / "dry.f32", dry)

# --- reverb: stereo impulse = decaying noise (different per side for width)
irn = int(3.5 * SR); ir = []
for i in range(irn):
    g = math.exp(-i / (0.9 * SR)); ir += [rnd.gauss(0, 1) * g, rnd.gauss(0, 1) * g]
write_f32(W / "ir.f32", ir)
ff("-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", str(W / "dry.f32"), "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", str(W / "ir.f32"),
   "-filter_complex", "[0:a]lowpass=f=2600,pan=stereo|c0=c0|c1=c0,asplit[d][r];[r][1:a]afir=gtype=none[w];"
   "[d]volume=0.55[dd];[w]volume=0.10[ww];[dd][ww]amix=inputs=2:normalize=0:duration=first",
   "-t", str(LOOP + TAIL), "-f", "f32le", str(W / "piano.f32"))
p = read_f32(W / "piano.f32")
# fold the tail past 60 s back onto the start, so the loop point is seamless
piano = p[:2 * N]
for i in range(2 * N, min(len(p), 2 * NT)): piano[i - 2 * N] += p[i]

def rms(x): return math.sqrt(sum(v * v for v in x) / len(x))
target = 10 ** (-19 / 20)  # same loudness as ambience_soft_pad.flac, so one volume_db works for every loop


def render(name, gp):
    mix = array.array("f", [v * gp for v in piano])
    g = target / rms(mix); pk = max(abs(v) for v in mix) * g
    if pk > 10 ** (-3 / 20): g *= 10 ** (-3 / 20) / pk
    write_f32(W / "mix.f32", [v * g for v in mix])
    # Gentle compression keeps piano attacks from poking out over a voice. Compress three copies and keep the
    # middle one, so the compressor state at the loop point matches and the seam stays click-free.
    ff("-f", "f32le", "-ar", str(SR), "-ac", "2", "-stream_loop", "2", "-i", str(W / "mix.f32"),
       "-af", "acompressor=threshold=-26dB:ratio=3:attack=15:release=500,atrim=start=60:end=120,asetpts=N/SR/TB",
       "-f", "f32le", str(W / "comp.f32"))
    c = read_f32(W / "comp.f32"); g = target / rms(c)
    write_f32(W / "comp.f32", [v * g for v in c])
    ff("-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", str(W / "comp.f32"), "-c:a", "flac", "-sample_fmt", "s16", str(OUT / name))
    print("wrote", OUT / name)


render("ambience_piano.flac", 1.0 / max(rms(piano), 1e-9))
