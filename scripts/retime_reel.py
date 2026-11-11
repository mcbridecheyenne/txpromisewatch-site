"""Hold every picture in a slideshow reel EXTRA seconds longer.
Usage: python3 retime_reel.py in.mp4 out.mp4 [--extra 3] [--sheet sheet.jpg]
Finds the crossfades between pictures, then slows each picture's hold (between fades)
so it lasts EXTRA seconds more. Fades stay 0.4 s. Output: 1080x1920 30 fps H.264 + silent AAC."""
import argparse, json, subprocess, sys
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("dst")
ap.add_argument("--extra", type=float, default=3.0)
ap.add_argument("--sheet")
a = ap.parse_args()

def probe(path):
    r = subprocess.run(["ffprobe", "-v", "0", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height:format=duration", "-of", "json", path],
                       capture_output=True, text=True, check=True)
    j = json.loads(r.stdout)
    return float(j["format"]["duration"]), j["streams"][0]["width"], j["streams"][0]["height"]

dur, W, H = probe(a.src)
FPS, w, h = 30, 72, 128
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", a.src, "-vf", f"fps={FPS},scale={w}:{h},format=gray",
                      "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
fr = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)
n = len(fr)
# difference between frames 0.5 s apart: small inside a picture (slow zoom), big across a fade
L = 15
d = np.array([np.abs(fr[i + L] - fr[i]).mean() for i in range(n - L)])
base = np.median(d)
thr = max(base * 4, base + 0.5)
# peaks = fade centres; a fade spans ~12 frames, the 0.5 s window smears it to ~27 frames
cuts = []
i = 0
while i < len(d):
    if d[i] > thr:
        j = i
        while j < len(d) and d[j] > thr: j += 1
        seg = d[i:j]
        centre = (i + int(np.argmax(seg)) + L / 2) / FPS  # window midpoint
        if not cuts or centre - cuts[-1] > 1.0:
            cuts.append(centre)
        i = j
    else:
        i += 1
cuts = [c for c in cuts if 0.8 < c < dur - 0.8]
if not cuts:
    sys.exit(f"no picture changes found in {a.src}")
F = 0.2  # half a 0.4 s fade
# segments: holds (stretched) and fades (kept)
pts = [0.0]
for c in cuts: pts += [c - F, c + F]
pts.append(dur)
parts = []
for k in range(0, len(pts) - 1):
    s, e = pts[k], pts[k + 1]
    hold = k % 2 == 0
    if e - s <= 0.01: continue
    factor = (e - s + a.extra) / (e - s) if hold else 1.0
    parts.append((s, e, factor))
fc = []
for k, (s, e, f) in enumerate(parts):
    fc.append(f"[0:v]trim=start={s:.4f}:end={e:.4f},setpts=(PTS-STARTPTS)*{f:.6f},fps={FPS}[p{k}]")
fc.append("".join(f"[p{k}]" for k in range(len(parts))) + f"concat=n={len(parts)}:v=1:a=0,format=yuv420p[v]")
new_dur = dur + a.extra * (len(cuts) + 1)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.src, "-f", "lavfi", "-t", f"{new_dur:.3f}",
                "-i", "anullsrc=r=44100:cl=stereo", "-filter_complex", ";".join(fc),
                "-map", "[v]", "-map", "1:a", "-shortest", "-c:v", "libx264", "-preset", "veryfast",
                "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-movflags", "+faststart",
                a.dst], check=True)
out_dur = probe(a.dst)[0]
if a.sheet:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.dst, "-vf", "fps=1,scale=120:-1,tile=12x4",
                    "-frames:v", "1", a.sheet], check=True)
print(json.dumps({"src": a.src, "in_s": round(dur, 2), "pictures": len(cuts) + 1,
                  "cuts": [round(c, 2) for c in cuts], "out_s": round(out_dur, 2)}))
