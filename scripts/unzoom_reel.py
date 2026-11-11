"""Rebuild a slideshow reel with NO zoom and every word inside the safe box.
Usage: python3 unzoom_reel.py in.mp4 out.mp4 [--extra 0] [--endcard card.png] [--sheet dir/name]
Finds the crossfades, grabs each picture at its least-zoomed moment, shrinks any picture whose
content spills outside the safe box (never crops words), then rebuilds the video as still
pictures with the same 0.4 s crossfades. --extra adds seconds to every picture (TikTok);
--endcard replaces the last picture (the stock end card) with an already-safe image."""
import argparse, json, os, subprocess, sys, tempfile
import numpy as np
from PIL import Image

W, H, FPS, XF = 1080, 1920, 30, 0.4
SAFE = (70, 150, W - 140, H - 380)  # left, top, right, bottom
SW, SH = SAFE[2] - SAFE[0], SAFE[3] - SAFE[1]

def probe(path):
    r = subprocess.run(["ffprobe", "-v", "0", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height:format=duration", "-of", "json", path],
                       capture_output=True, text=True, check=True)
    return float(json.loads(r.stdout)["format"]["duration"])

def find_cuts(src, dur):
    w, h, L = 72, 128, 15
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-vf", f"fps={FPS},scale={w}:{h},format=gray",
                          "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)
    d = np.array([np.abs(fr[i + L] - fr[i]).mean() for i in range(len(fr) - L)])
    base = np.median(d); thr = max(base * 4, base + 0.5)
    cuts, i = [], 0
    while i < len(d):
        if d[i] > thr:
            j = i
            while j < len(d) and d[j] > thr: j += 1
            c = (i + int(np.argmax(d[i:j])) + L / 2) / FPS
            if not cuts or c - cuts[-1] > 1.0: cuts.append(c)
            i = j
        else:
            i += 1
    return [c for c in cuts if 2.0 < c < dur - 1.0]

def grab(src, t, path):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", src, "-frames:v", "1",
                    "-vf", f"scale={W}:{H}", path], check=True)
    return np.asarray(Image.open(path).convert("RGB")).astype(np.int16)

def row_bg(a):
    edge = np.concatenate([a[:, :8], a[:, -8:]], axis=1)
    return np.median(edge, axis=1)  # (H, 3)

def content_box(a):
    bg = row_bg(a)
    m = (np.abs(a - bg[:, None, :]).max(axis=2) > 28)
    ys, xs = np.where(m)
    if len(xs) == 0: return None, 0
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1), int(m.sum())

def make_safe(a):
    """Return (image, box, shrunk?)."""
    box, _ = content_box(a)
    if box is None: return Image.fromarray(a.astype(np.uint8)), box, False
    x0, y0, x1, y1 = box
    if x0 >= SAFE[0] and y0 >= SAFE[1] and x1 <= SAFE[2] and y1 <= SAFE[3]:
        return Image.fromarray(a.astype(np.uint8)), box, False
    p = 12
    x0, y0, x1, y1 = max(0, x0 - p), max(0, y0 - p), min(W, x1 + p), min(H, y1 + p)
    bg = row_bg(a).astype(np.uint8)
    canvas = Image.fromarray(np.repeat(bg[:, None, :], W, axis=1))
    part = Image.fromarray(a.astype(np.uint8)).crop((x0, y0, x1, y1))
    k = min(SW / part.width, SH / part.height, 1.0)
    part = part.resize((max(1, int(part.width * k)), max(1, int(part.height * k))), Image.LANCZOS)
    cx = SAFE[0] + (SW - part.width) // 2; cy = SAFE[1] + (SH - part.height) // 2
    canvas.paste(part, (cx, cy))
    return canvas, box, True

def build(imgs, holds, dst):
    """holds = seconds each picture is on screen (cut to cut); crossfades centred on the cuts."""
    n = len(imgs); total = sum(holds)
    cmd = ["ffmpeg", "-v", "error", "-y"]
    for k, im in enumerate(imgs):
        L = holds[k] + (XF / 2 if k > 0 else 0) + (XF / 2 if k < n - 1 else 0)
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", f"{L:.3f}", "-i", im]
    cmd += ["-f", "lavfi", "-t", f"{total:.3f}", "-i", "anullsrc=r=44100:cl=stereo"]
    f = [f"[{k}:v]scale={W}:{H},setsar=1,fps={FPS},format=yuv420p[s{k}]" for k in range(n)]
    last, t = "s0", 0.0
    for k in range(1, n):
        t += holds[k - 1]
        f.append(f"[{last}][s{k}]xfade=transition=fade:duration={XF}:offset={t - XF / 2:.3f}[x{k}]")
        last = f"x{k}"
    cmd += ["-filter_complex", ";".join(f), "-map", f"[{last}]", "-map", f"{n}:a", "-c:v", "libx264",
            "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac",
            "-shortest", "-movflags", "+faststart", dst]
    subprocess.run(cmd, check=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--extra", type=float, default=0.0)
    ap.add_argument("--endcard"); ap.add_argument("--sheet")
    a = ap.parse_args()
    dur = probe(a.src); cuts = find_cuts(a.src, dur)
    if not cuts: sys.exit(f"no picture changes found in {a.src}")
    edges = [0.0] + cuts + [dur]
    holds = [edges[k + 1] - edges[k] for k in range(len(edges) - 1)]
    tmp = tempfile.mkdtemp()
    imgs, info = [], []
    for k in range(len(holds)):
        if k == len(holds) - 1 and a.endcard:
            imgs.append(a.endcard); info.append({"pic": k, "endcard": True}); continue
        late = grab(a.src, edges[k + 1] - 0.3, f"{tmp}/late{k}.png")
        if k == 0:
            early = grab(a.src, 0.05, f"{tmp}/early{k}.png")
            # an intro that animates in leaves the first frame emptier: use the late frame then
            pick = early if content_box(early)[1] >= 0.9 * content_box(late)[1] else late
        else:
            pick = grab(a.src, edges[k] + XF / 2 + 0.05, f"{tmp}/early{k}.png")
        img, box, shrunk = make_safe(pick)
        p = f"{tmp}/pic{k}.png"; img.save(p); imgs.append(p)
        info.append({"pic": k, "box": box, "shrunk": shrunk})
    holds = [h + a.extra for h in holds]
    build(imgs, holds, a.dst)
    out_dur = probe(a.dst)
    if a.sheet:
        mids, t = [], 0.0
        for h in holds: mids.append(t + h / 2); t += h
        for k, m in enumerate(mids):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{m:.2f}", "-i", a.dst, "-frames:v", "1",
                            "-vf", f"drawbox=x={SAFE[0]}:y={SAFE[1]}:w={SW}:h={SH}:color=red@0.8:t=3,scale=270:480",
                            f"{tmp}/mid{k}.png"], check=True)
        sheet = Image.new("RGB", (270 * len(mids), 480))
        for k in range(len(mids)): sheet.paste(Image.open(f"{tmp}/mid{k}.png"), (270 * k, 0))
        sheet.save(a.sheet, quality=85)
    print(json.dumps({"src": a.src, "in_s": round(dur, 2), "pictures": len(holds),
                      "cuts": [round(c, 2) for c in cuts], "out_s": round(out_dur, 2), "pics": info}))

if __name__ == "__main__":
    main()
