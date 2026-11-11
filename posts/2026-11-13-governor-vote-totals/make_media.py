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


# ---------------- copy (VERIFIED by Fact-Checker, see checks.md) ----------------
RED_R, BLUE_D = (214, 78, 66), (74, 138, 214)
# (year, label, [(candidate, party, votes, pct or None)])
DATA = [
    ("2018", "2018", [("Abbott", "R", 4656196, None), ("Valdez", "D", 3546615, None)]),
    ("2022", "2022", [("Abbott", "R", 4437099, None), ("O'Rourke", "D", 3553656, None)]),
    ("2026", "2026 · UNOFFICIAL", [("Abbott", "R", 4524955, "45.7%"), ("Hinojosa", "D", 5230929, "52.8%")]),
]
KICKER = "TEXAS PROMISE WATCH · BY THE NUMBERS"
HEAD = "ABBOTT HELD STEADY. DEMOCRATS ADDED 1.7 MILLION VOTES."
SUB = "Votes for Texas governor in the last three elections."
CH_R = ("ABBOTT", "+88,000 votes from 2022 to 2026 (+2%)")
CH_D = ("DEMOCRATIC NOMINEE", "+1.68 million votes from 2022 to 2026 (+47%)")
TOTALS = "All votes for governor: 8.34M in 2018, 8.10M in 2022, 9.90M in 2026 (unofficial)."
UNOFF = ("2026 numbers are UNOFFICIAL. Texas doesn't make the governor's race official until the "
         "Legislature canvasses the returns after it meets Jan. 12, 2027.")
NEUTRAL = "This chart shows vote totals only. It doesn't tell us why they changed."
SOURCES = "Sources: Texas Secretary of State certified results (2018, 2022) · 2026 unofficial AP count via KSAT & Ballotpedia"
MAXV = 6_000_000


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



def m(v): return f"{v/1e6:.2f}M"


def bars(p, years, bar_h, name_font, val_font, year_font, gap_bar=12, gap_year=30, label_w=250):
    """Horizontal bars drawn whole inside the page margins."""
    x0, x1 = p.m + label_w, p.w - p.m - 10
    for key, ylab, rows in years:
        p.text(ylab, year_font, fill=GOLD, gap=1.0, after=6)
        for name, party, v, pct in rows:
            col = RED_R if party == "R" else BLUE_D
            y = p.y
            p.d.text((p.m, y + (bar_h - name_font.size) / 2 - 4), f"{name} ({party})", font=name_font, fill=CREAM)
            p.d.rounded_rectangle((x0, y, x1, y + bar_h), 8, fill=PANEL)
            bw = (x1 - x0) * v / MAXV
            p.d.rounded_rectangle((x0, y, x0 + bw, y + bar_h), 8, fill=col)
            t = m(v) + (f"  {pct}" if pct else "")
            tx = x0 + bw + 14
            if tx + val_font.getlength(t) > x1: tx = x0 + bw - 14 - val_font.getlength(t)
            p.d.text((tx, y + (bar_h - val_font.size) / 2 - 4), t, font=val_font, fill=CREAM)
            assert tx >= x0 and tx + val_font.getlength(t) <= x1, ("bar label out of box", t)
            assert p.d.textbbox((p.m, y), f"{name} ({party})", font=name_font)[2] < x0 - 8, ("name too wide", name)
            p.y = y + bar_h + gap_bar
        p.y += gap_year


# ---------------- static graphic 1080x1350 ----------------
def graphic():
    p = Page(1080, 1350, margin=56, top=34, bottom=28)
    p.text(KICKER, F(OSW5, 30), fill=GOLD, center=True, gap=0.95, after=6)
    p.text("ABBOTT HELD STEADY.", F(OSW, 60), gap=0.98, after=0)
    p.text("DEMOCRATS ADDED 1.7 MILLION VOTES.", F(OSW, 60), gap=0.98, after=6)
    p.text(SUB, F(INT5, 27), fill=GREY, after=12)
    bars(p, DATA, 46, F(INT6, 28), F(OSW5, 30), F(OSW, 32), gap_bar=10, gap_year=10, label_w=230)
    p.y += 4
    side_by_side(p, p.y, [CH_R[0], CH_D[0]], [CH_R[1], CH_D[1]], [RED_R, BLUE_D], font=F(INT6, 28))
    p.y += 12
    p.text(TOTALS, F(INT5, 25), after=8)
    h = p.measure(UNOFF, F(INT6, 25), p.w - 2 * p.m - 48) + 36
    p.box(p.m, p.y, p.w - p.m, p.y + h, outline=GOLD, wdt=3)
    y0 = p.y; p.y += 16
    p.text(UNOFF, F(INT6, 25), x=p.m + 24, width=p.w - 2 * p.m - 48)
    p.y = y0 + h + 12
    p.text(NEUTRAL, F(INT5, 25), fill=GOLD, after=4)
    p.text(SOURCES, F(INT5, 20), fill=GREY, gap=1.25)
    p.check()
    return p.im


# ---------------- reel scenes 1080x1920 (safe area: top 230, bottom 420 for app buttons/captions) ----------------
SAFE_TOP, SAFE_BOTTOM = 170, 1920 - 400


SAFE_L, SAFE_R = 70, 1080 - 140   # memory rule: 70 px left, 140 px right, 150 top, 380 bottom


def scene(build):
    W = SAFE_R - SAFE_L + 30          # content drawn 900 px wide with 15 px inner margin: text spans x 70..940
    p = Page(W, 4000, margin=15, top=0, bottom=0)
    p.text("TEXAS PROMISE WATCH", F(OSW5, 38), fill=GOLD, center=True, after=40)
    build(p)
    print("scene height", p.y); assert p.y <= SAFE_BOTTOM - SAFE_TOP, f"scene too tall for the safe area: {p.y}"
    content = p.im.crop((0, 0, W, p.y))  # whole content block, nothing trimmed (canvas is taller than content)
    im = Image.new("RGB", (1080, 1920), NAVY)
    im.paste(content, (SAFE_L - 15, SAFE_TOP + (SAFE_BOTTOM - SAFE_TOP - p.y) // 2))
    return im


def fit_endcard(src, dst):
    """Stock end card runs edge to edge: crop its empty top/bottom bands, then SHRINK the whole card into the safe box."""
    im = Image.open(src).convert("RGB").crop((0, 120, 1080, 1530))
    bw, bh = SAFE_R - SAFE_L, 1920 - 380 - 150
    k = min(bw / im.width, bh / im.height)
    im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    out = Image.new("RGB", (1080, 1920), im.getpixel((5, 5)))
    out.paste(im, (SAFE_L + (bw - im.width) // 2, 150 + (bh - im.height) // 2))
    out.save(dst)


def s1(p):
    p.text("ABBOTT'S VOTE TOTAL BARELY MOVED.", F(OSW, 104), gap=1.0, center=True, after=40)
    p.text("The Democratic total jumped by 1.7 million.", F(INT6, 60), fill=GOLD, center=True, gap=1.2, after=40)
    p.text("Texas governor's race, 2018 to 2026", F(INT5, 44), center=True)


def s2(p):
    p.text("THE LAST TWO RACES", F(OSW, 92), fill=GOLD, gap=1.0, after=30)
    bars(p, DATA[:2], 84, F(INT6, 38), F(OSW5, 46), F(OSW, 60), gap_bar=16, gap_year=30, label_w=260)
    p.text("Certified results, Texas Secretary of State", F(INT5, 38), fill=GREY)


def s3(p):
    p.text("2026: UNOFFICIAL COUNT", F(OSW, 92), fill=GOLD, gap=1.0, after=30)
    bars(p, [("2026", "Nov. 3, 2026", DATA[2][2])], 110, F(INT6, 42), F(OSW5, 48), F(OSW, 64), gap_bar=22, gap_year=30, label_w=300)
    p.text("AP count. Not final yet.", F(INT5, 44), fill=GREY)


def s4(p):
    p.text("WHAT CHANGED SINCE 2022", F(OSW, 84), fill=GOLD, gap=1.0, after=40)
    p.text("ABBOTT", F(OSW, 58), fill=RED_R, gap=1.0, after=4)
    p.text("+88,000 votes (+2%)", F(OSW, 84), gap=1.0, after=40)
    p.text("DEMOCRATIC NOMINEE", F(OSW, 58), fill=BLUE_D, gap=1.0, after=4)
    p.text("+1.68 million votes (+47%)", F(OSW, 84), gap=1.0, after=40)
    p.text("All votes for governor: 8.10M in 2022, 9.90M in 2026.", F(INT5, 46), gap=1.22)


def s5(p):
    p.text("NOT OFFICIAL YET", F(OSW, 104), fill=GOLD, gap=1.0, after=30)
    p.text("Texas makes the governor's race official only after the Legislature canvasses the returns. It meets Jan. 12, 2027.", F(INT5, 50), gap=1.22, after=50)
    p.text(NEUTRAL, F(INT6, 50), fill=GOLD, gap=1.22)


def s6(p):
    p.text("WHAT STANDS OUT TO YOU?", F(OSW, 104), fill=GOLD, center=True, gap=1.0, after=40)
    p.text("Tell us in the comments.", F(INT6, 56), center=True, gap=1.2, after=60)
    p.text("We track whether Texas winners keep their campaign promises.", F(INT5, 46), center=True, gap=1.22)


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
    end = f"{OUT}/endcard_fit.png"
    fit_endcard(f"{OUT}/endcard.png", end)
    assert Image.open(end).size == (1080, 1920)
    build(scenes, [HOLD_FB] * len(scenes), f"{OUT}/reel_facebook.mp4", audio=True)
    build(scenes + [end], [HOLD_TT] * len(scenes) + [END_HOLD], f"{OUT}/reel_tiktok.mp4", audio=False)
    print("built", OUT)
