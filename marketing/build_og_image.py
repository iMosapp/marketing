"""Build the Open Graph / iMessage link-preview card for imonsocial.com (1200x630).
run: cd /app/marketing && python3 build_og_image.py
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1200, 630
BG = (14, 15, 18)
GOLD = (201, 169, 98)
WHITE = (255, 255, 255)
GRAY = (170, 173, 180)
FONT_DIR = "/tmp/inter/extras/ttf/"


def font(name, size):
    return ImageFont.truetype(f"{FONT_DIR}Inter-{name}.ttf", size)


img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

# soft gold glow top-left, blue glow bottom-right
glow = Image.new("RGB", (W, H), BG)
gd = ImageDraw.Draw(glow)
gd.ellipse((-250, -300, 550, 500), fill=(52, 44, 26))
gd.ellipse((750, 300, 1500, 1000), fill=(16, 32, 56))
glow = glow.filter(ImageFilter.GaussianBlur(160))
img = Image.blend(img, glow, 0.9)
d = ImageDraw.Draw(img)

# subtle grid texture
for x in range(0, W, 60):
    d.line((x, 0, x, H), fill=(22, 23, 27), width=1)
for y in range(0, H, 60):
    d.line((0, y, W, y), fill=(22, 23, 27), width=1)

# gold accent bar
d.rounded_rectangle((0, 0, W, 8), fill=GOLD)

# logo card (white rounded tile so the colorful mark stays crisp)
logo = Image.open("/app/marketing/build/imos-logo.png").convert("RGBA")
tile = 300
pad = 26
tile_box = (84, (H - tile) // 2 - 10, 84 + tile, (H - tile) // 2 - 10 + tile)
d.rounded_rectangle(tile_box, radius=48, fill=(250, 250, 252))
logo_size = tile - pad * 2
logo = logo.resize((logo_size, logo_size), Image.LANCZOS)
img.paste(logo, (tile_box[0] + pad, tile_box[1] + pad), logo)

# text
x = 84 + tile + 64
d.text((x, 138), "THE RELATIONSHIP OS FOR SALES TEAMS", font=font("Bold", 22), fill=GOLD)
d.text((x, 180), "Your CRM remembers", font=font("ExtraBold", 56), fill=WHITE)
d.text((x, 243), "the deal.", font=font("ExtraBold", 56), fill=WHITE)
d.text((x, 322), "i'M On Social", font=font("ExtraBold", 56), fill=GOLD)
d.text((x, 385), "remembers the person.", font=font("ExtraBold", 56), fill=GOLD)

d.text((x, 470), "Texts, calls, reviews, digital cards and", font=font("Medium", 23), fill=GRAY)
d.text((x, 500), "AI follow-up, all in one app.", font=font("Medium", 23), fill=GRAY)

# footer url pill
url = "imonsocial.com"
f = font("SemiBold", 26)
tw = d.textlength(url, font=f)
d.rounded_rectangle((x, 552, x + tw + 44, 552 + 46), radius=23, outline=GOLD, width=2)
d.text((x + 22, 552 + 9), url, font=f, fill=WHITE)

img.save("/app/marketing/build/og-image.png", optimize=True)
img.save("/app/marketing/public/og-image.png", optimize=True)
print("wrote og-image.png", img.size)
