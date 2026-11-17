# Usage: python3 align_timings.py <episode.json> <transcript_lines.txt> <chunks_dir> <out.csv>
# chunks_dir holds chunk_00.wav, chunk_01.wav, ... (e.g. <name>_parts/n12); the parts-per-chunk count is read from its name.
# Estimate start_seconds per transcript line from existing chunk WAVs, without regenerating audio.
# Chunk starts are exact; inside a chunk, line boundaries snap to detected silences (DP on speech time vs. text length).
import json, re, subprocess, sys, wave, csv
ep_json, lines_txt, parts_dir, out_csv = sys.argv[1:5]
# Parts per chunk must match the run that made the audio: tts_episode.py stores chunks in <name>_parts/n<N>/.
# Chunks directly in <name>_parts/ come from older runs, which always used 6.
m = re.search(r"(?:^|/)n(\d+)/?$", parts_dir)
PER = int(m.group(1)) if m else 6

def norm(s): return re.sub(r"[^a-z]", "", re.sub(r"<[^>]+>", "", s).lower())
parts = json.load(open(ep_json))["parts"]
lines = [l.strip() for l in open(lines_txt, encoding="utf-8") if l.strip()]

# Normalized part text plus, per normalized char, its index in the raw text (to see which tag follows a line).
def norm_map(raw):
    clean = re.sub(r"<[^>]+>", lambda m: "\0" * len(m.group(0)), raw)
    chars, where = [], []
    for i, ch in enumerate(clean.lower()):
        if "a" <= ch <= "z": chars.append(ch); where.append(i)
    return "".join(chars), where

# map each line to its part by walking the normalized part texts in order,
# and note the pause the script asks for after it: 2 = <long pause> or end of part, 1 = <short pause>, 0 = none
pmaps = [norm_map(p["text"]) for p in parts]
line_part, line_pause, pi, pos = [], [], 0, 0
for l in lines:
    n = norm(l)
    key = n[:25]
    while pi < len(parts):
        k = pmaps[pi][0].find(key, pos)
        if k >= 0:
            pnorm, where = pmaps[pi]
            pos = min(k + len(n), len(pnorm))
            if pos >= len(pnorm):
                pause = 2
            else:
                gap = parts[pi]["text"][where[pos - 1] + 1:where[pos]]
                pause = 2 if "<long pause>" in gap else 1 if "<short pause>" in gap else 0
            line_part.append(pi); line_pause.append(pause); break
        pi += 1; pos = 0
    else:
        sys.exit(f"cannot place line: {l}")

# Silence lengths that tagged pauses produce; a boundary that lands on a much shorter silence is penalized.
MIN_SIL = {2: 1.1, 1: 0.6, 0: 0.0}
PAUSE_WEIGHT = 20.0

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
    sil_len = [0.0] + [e - st for st, e in cand]
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
                short = max(0.0, MIN_SIL[line_pause[idx[j - 1]]] - sil_len[k])
                v = cost[j - 1][kp] + d * d / max(exp, 0.5) + PAUSE_WEIGHT * short * short
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

# Flag lines whose span is far shorter than their text suggests: likely snapped to the wrong silence.
# Long spans are not flagged: a short line followed by an intended <long pause> is normal.
total_chars = sum(len(norm(r["text"])) for r in rows)
ends = [r["start_seconds"] for r in rows[1:]] + [offset]
for r, end in zip(rows, ends):
    expected = offset * len(norm(r["text"])) / total_chars
    r["check"] = "listen" if not r["exact"] and (end - r["start_seconds"]) < 0.55 * expected else ""
with open(out_csv, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["line", "start_seconds", "exact", "check", "text"]); w.writeheader(); w.writerows(rows)
print(len(rows), "lines; total", round(offset, 2), "s")
