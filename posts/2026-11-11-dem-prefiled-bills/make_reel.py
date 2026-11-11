"""Build reel scenes (1080x1920) from the Canva graphic, then the MP4s.
Usage: python3 make_reel.py graphic.png endcard.png outdir
No zoom or pan, and every scene's content sits inside the safe box (70 px left, 140 px right,
150 px top, 380 px bottom clear) so no words are cut off or hidden under app buttons (Cheyenne 2026-11-11).
Facebook holds each picture 5.5 s; TikTok holds it 3 s longer (8.5 s) and adds the social-handles end card. Facebook reel gets a soft generated ambient pad (original, royalty-free);
the TikTok cut stays silent so its TikTok Commercial Music Library track is the only music."""
import subprocess, sys
from PIL import Image
g_path, end_path, out = sys.argv[1:4]
G = Image.open(g_path).convert("RGB").resize((1080, 1440))
bg = G.getpixel((8, 8))
W, H = 1080, 1920
SAFE = (70, 150, W - 140, H - 380)  # left, top, right, bottom
SW, SH = SAFE[2] - SAFE[0], SAFE[3] - SAFE[1]
def canvas(): return Image.new("RGB", (W, H), bg)
def fit(parts, gap=40):
    """Stack image parts vertically, scale the stack to fit the safe box, center it there."""
    tw = max(p.width for p in parts); th = sum(p.height for p in parts) + gap * (len(parts) - 1)
    stack = Image.new("RGB", (tw, th), bg); y = 0
    for p in parts: stack.paste(p, ((tw - p.width) // 2, y)); y += p.height + gap
    k = min(SW / tw, SH / th); stack = stack.resize((round(tw * k), round(th * k)), Image.LANCZOS)
    c = canvas(); c.paste(stack, (SAFE[0] + (SW - stack.width) // 2, SAFE[1] + (SH - stack.height) // 2)); return c
# Scene 1: headline + callout (the hook)
s1 = fit([G.crop((0, 0, 1080, 410)), G.crop((0, 1100, 1080, 1350))], gap=120)
# Scene 2: kicker + the bill rows
s2 = fit([G.crop((0, 20, 1080, 100)), G.crop((0, 425, 1080, 1055))], gap=60)
# Scene 3: the full graphic with source line
s3 = fit([G])
scenes = []
for i, s in enumerate([s1, s2, s3], 1):
    p = f"{out}/scene{i}.png"; s.save(p); scenes.append(p)
E = Image.open(end_path).convert("RGB")
if E.size != (W, H):
    e = Image.new("RGB", (W, H), (5, 21, 41)); E.thumbnail((W, H)); e.paste(E, ((W - E.width) // 2, 120)); E = e
# the stock end card runs edge to edge; shrink its content into the safe box too
bg_end = E.getpixel((8, 8)); E = E.crop((0, 120, W, 1530))
_bg = bg; bg = bg_end; E = fit([E]); bg = _bg
E.save(f"{out}/endcard.png")
FB_HOLD = 5.5; TT_HOLD = FB_HOLD + 3; END_HOLD = 6.0; FADE = 0.4
def build(imgs, holds, dst, audio):
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for im, d in zip(imgs, holds): cmd += ["-loop", "1", "-t", str(d), "-framerate", "30", "-i", im]
    total = sum(holds)
    if audio:
        # gentle A-major pad: three sines, slow tremolo, fades; original sound, no license needed
        cmd += ["-f", "lavfi", "-t", str(total), "-i",
                "sine=f=220:sample_rate=44100,volume=0.25[a];sine=f=277.18:sample_rate=44100,volume=0.18[b];"
                "sine=f=329.63:sample_rate=44100,volume=0.15[c];[a][b][c]amix=inputs=3,tremolo=f=0.25:d=0.5,"
                f"lowpass=f=900,afade=t=in:d=2,afade=t=out:st={total-2.5}:d=2.5,volume=14"]
    else:
        cmd += ["-f", "lavfi", "-t", str(total), "-i", "anullsrc=r=44100:cl=stereo"]
    n = len(imgs)
    f = ";".join(f"[{i}:v]scale=1080:1920,setsar=1,format=yuv420p,fade=t=in:st=0:d={FADE}[v{i}]" for i in range(n))
    f += ";" + "".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[v]"
    cmd += ["-filter_complex", f, "-map", "[v]", "-map", f"{n}:a", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "128k", "-shortest",
            "-movflags", "+faststart", dst]
    subprocess.run(cmd, check=True)
build(scenes, [FB_HOLD] * 3, f"{out}/reel_facebook.mp4", audio=True)
build(scenes + [f"{out}/endcard.png"], [TT_HOLD] * 3 + [END_HOLD], f"{out}/reel_tiktok.mp4", audio=False)
print("built", out)
