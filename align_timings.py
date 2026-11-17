# Usage: python3 align_timings.py <episode.json> <transcript_lines.txt> <chunks_dir> <out.csv>
# Only for audio rendered 6 parts per request (the default mode); chunks_dir holds chunk_00.wav, chunk_01.wav, ...
# Estimate start_seconds per transcript line from existing chunk WAVs, without regenerating audio.
# Chunk starts are exact; inside a chunk, line boundaries snap to detected silences (DP on speech time vs. text length).
import json, re, subprocess, sys, wave, csv
ep_json, lines_txt, parts_dir, out_csv = sys.argv[1:5]
PER = 6

def norm(s): return re.sub(r"[^a-z]", "", re.sub(r"<[^>]+>", "", s).lower())
parts = json.load(open(ep_json))["parts"]
lines = [l.strip() for l in open(lines_txt, encoding="utf-8") if l.strip()]

# map each line to its part by walking the normalized part texts in order
pnorm = [norm(p["text"]) for p in parts]
line_part, pi, pos = [], 0, 0
for l in lines:
    n = norm(l)
    key = n[:25]
    while pi < len(parts):
        k = pnorm[pi].find(key, pos)
        if k >= 0:
            line_part.append(pi); pos = k + len(n); break
        pi += 1; pos = 0
    else:
        sys.exit(f"cannot place line: {l}")

def silences(path):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-af", "silencedetect=n=-40dB:d=0.3", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", err)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
    return list(zip(st, en))

rows, offset = [], 0.0
nchunks = (len(parts) + PER - 1) // PER
for c in range(nchunks):
    path = f"{parts_dir}/chunk_{c:02d}.wav"
    with wave.open(path) as w: dur = w.getnframes() / w.getframerate()
    idx = [i for i, p in enumerate(line_part) if c * PER <= p < (c + 1) * PER]
    sil = [s for s in silences(path) if s[1] < dur - 0.05]
    lead = sil[0][1] if sil and sil[0][0] < 0.01 else 0.0
    cand = [s for s in sil if s[0] > 0.01]              # boundary candidates
    def speech(a, b):                                    # speech time in [a,b)
        return (b - a) - sum(max(0, min(e, b) - max(s, a)) for s, e in sil)
    chars = [len(norm(lines[i])) for i in idx]
    rate = speech(0, dur) / sum(chars)
    # DP: line j starts at cand[k].end; first line starts at lead
    starts_opts = [lead] + [e for _, e in cand]
    M, N = len(starts_opts), len(idx)
    INF = float("inf")
    cost = [[INF] * M for _ in range(N)]; back = [[-1] * M for _ in range(N)]
    cost[0][0] = 0.0
    for j in range(1, N):
        exp = rate * chars[j - 1]
        for k in range(1, M):
            for kp in range(k):
                if cost[j - 1][kp] == INF: continue
                d = speech(starts_opts[kp], starts_opts[k]) - exp
                v = cost[j - 1][kp] + d * d / max(exp, 0.5)
                if v < cost[j][k]: cost[j][k], back[j][k] = v, kp
    # close the last line at chunk end
    best, bk = INF, -1
    exp = rate * chars[-1]
    for k in range(M):
        if cost[N - 1][k] == INF: continue
        d = speech(starts_opts[k], dur) - exp
        v = cost[N - 1][k] + d * d / max(exp, 0.5)
        if v < best: best, bk = v, k
    ks = [bk]
    for j in range(N - 1, 0, -1): ks.append(back[j][ks[-1]])
    ks.reverse()
    for j, i in enumerate(idx):
        rows.append({"line": i + 1, "start_seconds": round(offset + starts_opts[ks[j]], 1),
                     "exact": "yes" if j == 0 else "", "text": lines[i]})
    offset += dur

with open(out_csv, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["line", "start_seconds", "exact", "text"]); w.writeheader(); w.writerows(rows)
print(len(rows), "lines; total", round(offset, 2), "s")
