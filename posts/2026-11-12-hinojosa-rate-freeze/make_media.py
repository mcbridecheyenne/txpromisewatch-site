"""Build the Hinojosa rate-freeze graphic (1080x1350) and reel scenes (1080x1920), then the MP4s.
Every scene is drawn whole at full size: no crops or zooms, so no words get cut off.
Text is wrapped to fit inside safe margins, and the script fails if any line would spill out.
FB reel: 4.5 s per picture with a soft original ambient pad. TikTok reel: 7.5 s per picture
(+3 s, per Cheyenne 2026-11-11) plus the 6 s end card, silent so the TikTok CML track is the only music.
Usage: python3 make_media.py outdir"""
import os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "media")
F = lambda n, s: ImageFont.truetype(os.path.join(HERE, "fonts", n), s)
OSW, OSW5 = "oswald-latin-700-normal.woff", "oswald-latin-500-normal.woff"
INT5, INT6, INT7 = "inter-latin-500-normal.woff", "inter-latin-600-normal.woff", "inter-latin-700-normal.woff"
NAVY, PANEL, GOLD, CREAM, GREY = (5, 21, 41), (38, 55, 86), (243, 182, 41), (250, 244, 232), (150, 160, 178)
RED, BLUE = (200, 70, 60), (70, 130, 200)


class Page:
    def __init__(self, w, h, margin=64, top=0, bottom=0):
        self.im = Image.new("RGB", (w, h), NAVY)
        self.d = ImageDraw.Draw(self.im)
        self.w, self.h, self.m, self.bottom = w, h, margin, h - bottom
        self.y = top

    def wrap(self, text, font, width):
        words, lines, cur = text.split(), [], ""
        for wd in words:
            t = (cur + " " + wd).strip()
            if font.getlength(t) <= width: cur = t
            else:
                if not cur: raise SystemExit(f"word too wide: {wd}")
                lines.append(cur); cur = wd
        lines.append(cur)
        return lines

    def text(self, text, font, fill=CREAM, x=None, width=None, gap=1.12, after=0, center=False):
        x = self.m if x is None else x
        width = (self.w - x - self.m) if width is None else width
        adv = round(font.getbbox("Hg")[3] * gap)
        for ln in self.wrap(text, font, width):
            lw = font.getlength(ln)
            xx = x + (width - lw) / 2 if center else x
            bb = self.d.textbbox((xx, self.y), ln, font=font)
            assert bb[0] >= 0 and bb[2] <= self.w and bb[3] <= self.bottom, f"text out of frame: {ln!r} {bb}"
            self.d.text((xx, self.y), ln, font=font, fill=fill)
            self.y += adv
        self.y += after

    def measure(self, text, font, width, gap=1.12):
        return len(self.wrap(text, font, width)) * round(font.getbbox("Hg")[3] * gap)

    def box(self, x0, y0, x1, y1, fill=None, outline=None, wdt=4, r=14):
        self.d.rounded_rectangle((x0, y0, x1, y1), r, fill=fill, outline=outline, width=wdt)

    def check(self):
        assert self.y <= self.bottom, f"content runs past the bottom: {self.y} > {self.bottom}"


# ---------------- copy (VERIFIED by Fact-Checker) ----------------
KICKER = "TEXAS PROMISE WATCH · WILL IT CHANGE WHAT YOU PAY?"
HEAD = "HINOJOSA'S PROMISE: FREEZE HOME POWER RATES"
QUOTE = "“On Day One as governor, I’ll freeze residential electricity rates and make corporations finally pay their fair share.”"
QUOTE_BY = "Gina Hinojosa, Texas governor-elect"
HOUR = "She told the Texas Tribune she would declare a “high-cost emergency” within an hour of taking the oath on Jan. 19."
NOW = ("15.91¢", "per kWh, average Texas home price, Aug. 2026. U.S. average: 18.16¢.")
PLAN = "Have the state utility commission freeze home rates until new laws make data centers and other big users pay their own way."
CATCH = ["Most Texans buy power from competing retail companies. The state doesn't set those prices, so how a freeze would work isn't clear yet.",
         "Lasting changes need the Legislature. Republicans still hold the Texas Senate."]
PRO = "Data centers are pushing up household bills, and families need relief now."
CON = "Capping prices in a competitive market could scare off new power plants and will likely end up in court."
STATUS = "NOT STARTED"
STATUS_SUB = "She takes office Jan. 19, 2027. We'll track whether the freeze happens and holds up."
SOURCES = "Sources: Texas Tribune interview via Fox News & Energy Choice Matters · Hinojosa campaign site · U.S. EIA"


def side_by_side(p, y, labels, bodies, colors, h=None, font=None):
    font = font or F(INT5, 34)
    gap, x0 = 24, p.m
    cw = (p.w - 2 * p.m - gap) // 2
    hs = [p.measure(b, font, cw - 48) for b in bodies]
    h = h or max(hs) + 96
    for i, (lab, body, col) in enumerate(zip(labels, bodies, colors)):
        x = x0 + i * (cw + gap)
        p.box(x, y, x + cw, y + h, fill=PANEL)
        p.d.rectangle((x, y, x + cw, y + 10), fill=col)
        p.y = y + 30
        p.text(lab, F(OSW, 40), fill=col, x=x + 24, width=cw - 48, gap=0.95, after=4)
        p.text(body, font, x=x + 24, width=cw - 48)
    p.y = y + h
    return h


def status_ring(p, cx, cy, r, pct=0):
    p.d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=PANEL, width=22)
    if pct: p.d.arc((cx - r, cy - r, cx + r, cy + r), -90, -90 + 360 * pct, fill=GOLD, width=22)
    f = F(OSW, int(r * 0.55))
    t = f"{int(pct*100)}%"
    p.d.text((cx - f.getlength(t) / 2, cy - f.size * 0.75), t, font=f, fill=CREAM)


# ---------------- static graphic 1080x1350 ----------------
def graphic():
    p = Page(1080, 1350, margin=56, top=40, bottom=28)
    p.text(KICKER, F(OSW5, 30), fill=GOLD, center=True, gap=0.95, after=4)
    p.text(HEAD, F(OSW, 82), gap=0.9, after=6)
    p.box(p.m, p.y, p.w - p.m, p.y + p.measure(QUOTE, F(INT6, 31), p.w - 2 * p.m - 60) + 70, outline=GOLD, wdt=3)
    y0 = p.y; p.y += 20
    p.text(QUOTE, F(INT6, 31), x=p.m + 30, width=p.w - 2 * p.m - 60)
    p.text("— " + QUOTE_BY, F(INT5, 24), fill=GOLD, x=p.m + 30, width=p.w - 2 * p.m - 60)
    p.y += 26
    side_by_side(p, p.y, ["NOW", "HER PLAN"], [NOW[0] + " " + NOW[1], PLAN], [GOLD, GOLD], font=F(INT5, 28))
    p.y += 22
    p.text("THE CATCH", F(OSW, 38), fill=GOLD, gap=0.95, after=0)
    for c in CATCH: p.text("• " + c, F(INT5, 27), after=6)
    p.y += 14
    side_by_side(p, p.y, ["SUPPORTERS SAY", "CRITICS SAY"], [PRO, CON], [BLUE, RED], font=F(INT5, 27))
    p.y += 18
    p.text(SOURCES, F(INT5, 21), fill=GREY, gap=1.25)
    p.check()
    return p.im


# ---------------- reel scenes 1080x1920 (safe area: top 220, bottom 420 for app buttons/captions) ----------------
SAFE_TOP, SAFE_BOTTOM = 230, 1920 - 420


def scene(build):
    p = Page(1080, 4000, margin=80, top=0, bottom=0)
    p.text("TEXAS PROMISE WATCH", F(OSW5, 38), fill=GOLD, center=True, after=40)
    build(p)
    content = p.im.crop((0, 0, 1080, p.y))  # full width, full content height: nothing trimmed
    assert p.y <= SAFE_BOTTOM - SAFE_TOP, f"scene too tall for the safe area: {p.y}"
    im = Image.new("RGB", (1080, 1920), NAVY)
    im.paste(content, (0, SAFE_TOP + (SAFE_BOTTOM - SAFE_TOP - p.y) // 2))
    return im


def s1(p):
    p.text("WILL IT CHANGE WHAT YOU PAY?", F(OSW, 120), gap=1.0, center=True, after=50)
    p.text("Texas Gov.-elect Gina Hinojosa promises to freeze home electricity rates.", F(INT6, 56), center=True, gap=1.2, after=40)
    p.text("Here's what we could confirm.", F(INT6, 46), fill=GOLD, center=True)


def s2(p):
    p.text("THE PROMISE", F(OSW, 96), fill=GOLD, gap=1.0, after=20)
    p.text(QUOTE, F(INT6, 56), gap=1.2, after=20)
    p.text("\u2014 " + QUOTE_BY, F(INT5, 40), fill=GOLD, after=60)
    p.text(HOUR, F(INT5, 46), gap=1.25)


def s3(p):
    p.text("NOW", F(OSW, 96), fill=GOLD, gap=1.0, after=10)
    p.text(NOW[0] + " per kWh", F(OSW, 130), gap=1.0, after=16)
    p.text("What the average Texas home paid in August 2026. U.S. average: 18.16\u00a2 (U.S. EIA).", F(INT5, 46), gap=1.25, after=70)
    p.text("HER PLAN", F(OSW, 96), fill=GOLD, gap=1.0, after=10)
    p.text(PLAN, F(INT6, 50), gap=1.22)


def s4(p):
    p.text("THE CATCH", F(OSW, 96), fill=GOLD, gap=1.0, after=30)
    for c in CATCH: p.text(c, F(INT5, 52), gap=1.22, after=50)
    p.text("Critics expect legal challenges.", F(INT6, 52), fill=GOLD)


def s5(p):
    p.text("HOW EACH SIDE SEES IT", F(OSW, 90), fill=GOLD, gap=1.0, after=40)
    p.text("SUPPORTERS SAY", F(OSW, 64), fill=BLUE, gap=1.0, after=10)
    p.text(PRO, F(INT5, 52), gap=1.22, after=60)
    p.text("CRITICS SAY", F(OSW, 64), fill=RED, gap=1.0, after=10)
    p.text(CON, F(INT5, 52), gap=1.22)


def s6(p):
    p.text("PROMISE STATUS", F(OSW, 96), fill=GOLD, center=True, gap=1.0, after=30)
    cy = p.y + 170; status_ring(p, p.w // 2, cy, 160); p.y = cy + 200
    p.text(STATUS, F(OSW, 110), center=True, gap=1.0, after=24)
    p.text(STATUS_SUB, F(INT5, 48), center=True, gap=1.22, after=50)
    p.text("Should a governor be able to freeze rates? Tell us in the comments.", F(INT6, 46), fill=GOLD, center=True, gap=1.22)


HOLD_FB, HOLD_TT, END_HOLD, FADE = 4.5, 7.5, 6.0, 0.4


def build(imgs, holds, dst, audio):
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for im, d in zip(imgs, holds): cmd += ["-loop", "1", "-t", str(d), "-framerate", "30", "-i", im]
    total = sum(holds)
    if audio:  # original soft A-major pad; no license needed
        cmd += ["-f", "lavfi", "-t", str(total), "-i",
                "sine=f=220:sample_rate=44100,volume=0.25[a];sine=f=277.18:sample_rate=44100,volume=0.18[b];"
                "sine=f=329.63:sample_rate=44100,volume=0.15[c];[a][b][c]amix=inputs=3,tremolo=f=0.25:d=0.5,"
                f"lowpass=f=900,afade=t=in:d=2,afade=t=out:st={total-2.5}:d=2.5,volume=14"]
    else:
        cmd += ["-f", "lavfi", "-t", str(total), "-i", "anullsrc=r=44100:cl=stereo"]
    n = len(imgs)
    # setsar only: images are already 1080x1920, so nothing is scaled, zoomed or cropped
    f = ";".join(f"[{i}:v]setsar=1,format=yuv420p,fade=t=in:st=0:d={FADE}[v{i}]" for i in range(n))
    f += ";" + "".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[v]"
    cmd += ["-filter_complex", f, "-map", "[v]", "-map", f"{n}:a", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "128k", "-shortest",
            "-movflags", "+faststart", dst]
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    graphic().save(f"{OUT}/graphic.png")
    scenes = []
    for i, fn in enumerate([s1, s2, s3, s4, s5, s6], 1):
        pth = f"{OUT}/scene{i}.png"; scene(fn).save(pth); scenes.append(pth)
    end = f"{OUT}/endcard.png"
    assert Image.open(end).size == (1080, 1920)
    build(scenes, [HOLD_FB] * len(scenes), f"{OUT}/reel_facebook.mp4", audio=True)
    build(scenes + [end], [HOLD_TT] * len(scenes) + [END_HOLD], f"{OUT}/reel_tiktok.mp4", audio=False)
    print("built", OUT)
