"""Render the Proof headlines as a branded 1080x1350 PNG card (Pillow). No em dashes anywhere in copy."""
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

BG, CARD, GOLD, TEXT, MUTED, GREEN, ORANGE = "#0B0B0C", "#161618", "#C9A962", "#FFFFFF", "#9A9A9E", "#34C759", "#FF9500"
FONT_DIR = "/usr/share/fonts/truetype/liberation/"


def _font(size: int, bold: bool = False):
    try:
        return ImageFont.truetype(FONT_DIR + ("LiberationSans-Bold.ttf" if bold else "LiberationSans-Regular.ttf"), size)
    except Exception:
        return ImageFont.load_default()


def _wrap(draw, text: str, font, max_w: int) -> list:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def render_proof_card(proof: dict, store_name: str) -> bytes:
    W, H, PAD = 1080, 1350, 64
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # header
    d.text((PAD, PAD), "i'M ON SOCIAL", font=_font(28, True), fill=GOLD)
    d.text((PAD, PAD + 40), (store_name or "Internet lead results")[:40], font=_font(44, True), fill=TEXT)
    d.text((PAD, PAD + 100), f"Internet leads, last {proof.get('days', 90)} days", font=_font(28), fill=MUTED)

    # stat tiles
    y = PAD + 170
    rep = proof.get("reply", {}) or {}
    def pct(g):
        return f"{g.get('close_rate')}%" if g and g.get("leads") and g.get("close_rate") is not None else "--"
    tiles = [
        (f"{proof.get('close_rate') or 0}%", "CLOSE RATE", GOLD),
        (pct(rep.get("replied")), "REPLIED CLOSED", GREEN),
        (pct(rep.get("silent")), "SILENT CLOSED", ORANGE),
    ]
    tw = (W - 2 * PAD - 2 * 20) // 3
    for i, (val, label, color) in enumerate(tiles):
        x = PAD + i * (tw + 20)
        d.rounded_rectangle([x, y, x + tw, y + 170], radius=24, fill=CARD)
        f = _font(64, True)
        d.text((x + tw / 2 - d.textlength(val, font=f) / 2, y + 30), val, font=f, fill=color)
        f2 = _font(22, True)
        d.text((x + tw / 2 - d.textlength(label, font=f2) / 2, y + 118), label, font=f2, fill=MUTED)
    y += 170 + 44

    # headlines
    d.text((PAD, y), "WHAT THE DATA SAYS", font=_font(24, True), fill=GOLD)
    y += 48
    body = _font(34)
    for h in (proof.get("headlines") or [])[:5]:
        lines = _wrap(d, h, body, W - 2 * PAD - 60)
        d.ellipse([PAD, y + 12, PAD + 18, y + 30], fill=GREEN)
        for ln in lines:
            d.text((PAD + 40, y), ln, font=body, fill=TEXT)
            y += 44
        y += 18
        if y > H - 260:
            break
    if not proof.get("headlines"):
        for ln in _wrap(d, "Headlines appear once sold leads exist in both groups being compared. Keep snapping sold photos.", body, W - 2 * PAD):
            d.text((PAD, y), ln, font=body, fill=MUTED)
            y += 44

    # footer
    fy = H - 150
    d.line([PAD, fy, W - PAD, fy], fill="#2A2A2E", width=2)
    tts = (proof.get("time_to_sold") or {}).get("avg_days")
    foot = f"{proof.get('leads', 0)} leads · {proof.get('sold', 0)} sold" + (f" · {tts} days lead to sold" if tts is not None else "")
    d.text((PAD, fy + 28), foot, font=_font(28), fill=MUTED)
    d.text((PAD, fy + 72), "Speed, texts and calls tracked automatically in the iMOS app · imonsocial.com", font=_font(24), fill=GOLD)

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
