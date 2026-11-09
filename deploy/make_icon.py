"""WMFree App 图标生成 v2:全部半透明元素用独立图层 alpha_composite,避免直写失效。"""
from PIL import Image, ImageDraw, ImageFilter

W = 1024
c1 = (10, 16, 46)
c2 = (24, 42, 110)
c3 = (124, 77, 255)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# 1. 对角渐变背景
small = Image.new("RGB", (256, 256))
px = small.load()
for y in range(256):
    for x in range(256):
        t = (x + y) / 510.0
        tt = t if t < 0.55 else 0.55 + (t - 0.55)
        px[x, y] = lerp(c1, c2, t / 0.55) if t < 0.55 else lerp(c2, c3, (t - 0.55) / 0.45)
img = small.resize((W, W), Image.LANCZOS).convert("RGBA")

# 2. 柔光层
glow = Image.new("RGBA", (W, W), (0, 0, 0, 0))
gd = ImageDraw.Draw(glow)
gd.ellipse([-120, -140, 480, 260], fill=(90, 168, 255, 55))
gd.ellipse([560, 620, 1180, 1240], fill=(124, 77, 255, 65))
glow = glow.filter(ImageFilter.GaussianBlur(60))
img.alpha_composite(glow)

# 3. 玻璃卡层(半透白填充 + 白描边,独立图层)
card = Image.new("RGBA", (W, W), (0, 0, 0, 0))
cd = ImageDraw.Draw(card)
cd.rounded_rectangle([190, 190, 834, 834], radius=150, fill=(255, 255, 255, 34))
card = card.filter(ImageFilter.GaussianBlur(1))
img.alpha_composite(card)

outline = Image.new("RGBA", (W, W), (0, 0, 0, 0))
od = ImageDraw.Draw(outline)
od.rounded_rectangle([190, 190, 834, 834], radius=150,
                     outline=(255, 255, 255, 150), width=6)
img.alpha_composite(outline)

# 4. 卡内顶部高光(玻璃反光)
hl = Image.new("RGBA", (W, W), (0, 0, 0, 0))
hd = ImageDraw.Draw(hl)
hd.rounded_rectangle([225, 215, 800, 400], radius=95, fill=(255, 255, 255, 45))
hl = hl.filter(ImageFilter.GaussianBlur(45))
img.alpha_composite(hl)

# 5. 播放三角(白,圆角,不透明层直接画在主图)
d = ImageDraw.Draw(img, "RGBA")
tri = [(404, 372), (404, 652), (646, 512)]
d.line(tri + [tri[0]], fill=(255, 255, 255, 255), width=58, joint="curve")
# line 起止端点无 cap,补三个顶点圆消掉缺口
for pt in tri:
    d.ellipse([pt[0] - 29, pt[1] - 29, pt[0] + 29, pt[1] + 29], fill="white")
d.polygon([(428, 412), (428, 612), (600, 512)], fill=(255, 255, 255, 255))

# 6. 去水印徽章:深色底圈 + 蓝圆 + 白水滴 + 白斜杠
bx, by, br = 724, 326, 120
d.ellipse([bx - br - 12, by - br - 12, bx + br + 12, by + br + 12],
          fill=(10, 16, 46, 220))
d.ellipse([bx - br, by - br, bx + br, by + br], fill=(91, 124, 250, 255))
cx, cy = bx, by + 4
r = 54
d.pieslice([cx - r, cy - r + 12, cx + r, cy + r + 12], 0, 360, fill="white")
d.polygon([(cx, cy - 64), (cx - r + 4, cy + 4), (cx + r - 4, cy + 4)], fill="white")
# 单条白斜杠(禁用符号)
d.line([(bx - 80, by + 80), (bx + 80, by - 80)], fill=(255, 255, 255, 255), width=26)

out = r"D:/y700/1212/wmfree/ios/WMFree/Assets.xcassets/AppIcon.appiconset/icon_1024.png"
import os
os.makedirs(os.path.dirname(out), exist_ok=True)
img.convert("RGB").save(out, "PNG")
print("ICON_SAVED", os.path.getsize(out), "bytes")
