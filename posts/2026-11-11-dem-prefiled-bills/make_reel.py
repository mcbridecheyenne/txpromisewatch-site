"""Build reel scenes (1080x1920) from the Canva graphic, then the MP4s.
Usage: python3 make_reel.py graphic.png endcard.png outdir
Each picture holds 7 s (the old 4 s plus 3 s, per Cheyenne 2026-11-11). The TikTok cut adds the
social-handles end card. Facebook reel gets a soft generated ambient pad (original, royalty-free);
the TikTok cut stays silent so its TikTok Commercial Music Library track is the only music."""
import subprocess, sys
from PIL import Image
g_path, end_path, out = sys.argv[1:4]
G = Image.open(g_path).convert("RGB").resize((1080, 1440))
bg = G.getpixel((8, 8))
W, H = 1080, 1920
def canvas(): return Image.new("RGB", (W, H), bg)
# Scene 1: headline + callout (the hook)
s1 = canvas(); s1.paste(G.crop((0, 0, 1080, 410)), (0, 330)); s1.paste(G.crop((0, 1100, 1080, 1350)), (0, 900))
# Scene 2: the bill rows, slightly enlarged
rows = G.crop((20, 425, 1060, 1055)); rows = rows.resize((1080, round(rows.height * 1080 / rows.width)))
s2 = canvas(); s2.paste(G.crop((0, 0, 1080, 105)), (0, 330)); s2.paste(rows, (0, (H - rows.height) // 2))
# Scene 3: the full graphic with source line
s3 = canvas(); s3.paste(G, (0, (H - 1440) // 2))
scenes = []
for i, s in enumerate([s1, s2, s3], 1):
    p = f"{out}/scene{i}.png"; s.save(p); scenes.append(p)
E = Image.open(end_path).convert("RGB")
if E.size != (W, H):
    e = Image.new("RGB", (W, H), (5, 21, 41)); E.thumbnail((W, H)); e.paste(E, ((W - E.width) // 2, 120)); E = e
E.save(f"{out}/endcard.png")
HOLD = 7.0; END_HOLD = 6.0; FADE = 0.4
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
build(scenes, [HOLD] * 3, f"{out}/reel_facebook.mp4", audio=True)
build(scenes + [f"{out}/endcard.png"], [HOLD] * 3 + [END_HOLD], f"{out}/reel_tiktok.mp4", audio=False)
print("built", out)
