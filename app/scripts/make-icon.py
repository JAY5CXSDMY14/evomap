#!/usr/bin/env python3
"""画 Evo 的应用图标「调度球」，出 Resources/AppIcon.png（1024）和 Resources/AppIcon.icns（全套尺寸）。

原创矢量风格（老板 2026-10-21 选定方向）：暖奶油色 macOS 圆角方块，一个珊瑚橙色的软圆球从右下角探进来，
球左上部两只略微倾斜的竖椭圆黑眼睛（带一点高光），好奇地朝左上看。纯代码画（numpy + Pillow），不用任何外部图片。

用法（在 app/ 目录）：python3 scripts/make-icon.py      依赖：pip install pillow numpy
结果提交进仓库，构建时 assemble-app.sh 直接拷 AppIcon.icns，CI 不用装 Python 包。
"""
import io
import math
import os
import struct
import sys

import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..", "Resources")
SS = 2                      # 超采样倍数
N = 1024 * SS               # 画布边长


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def rounded_rect_mask(xx, yy, x0, y0, x1, y1, r, aa):
    """圆角矩形（近似 macOS 连续圆角：用 superellipse 角）。返回 0..1 覆盖率。"""
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    hw, hh = (x1 - x0) / 2, (y1 - y0) / 2
    dx = np.maximum(np.abs(xx - cx) - (hw - r), 0)
    dy = np.maximum(np.abs(yy - cy) - (hh - r), 0)
    n = 5.0                                      # superellipse 指数，比圆角更顺
    d = (dx ** n + dy ** n) ** (1 / n) - r
    inside_box = np.maximum(np.abs(xx - cx) - hw, np.abs(yy - cy) - hh)
    d = np.where((dx > 0) & (dy > 0), d, inside_box)
    return 1 - smoothstep(-aa, aa, d)


def ellipse_mask(xx, yy, cx, cy, rx, ry, angle_deg, aa):
    a = math.radians(angle_deg)
    x, y = xx - cx, yy - cy
    u = x * math.cos(a) + y * math.sin(a)
    v = -x * math.sin(a) + y * math.cos(a)
    d = np.sqrt((u / rx) ** 2 + (v / ry) ** 2)
    # 距离近似到像素：乘短半轴
    return 1 - smoothstep(1 - aa / min(rx, ry), 1 + aa / min(rx, ry), d)


def over(dst_rgb, dst_a, src_rgb, src_a):
    """premultiplied-free 的 source-over 合成。"""
    out_a = src_a + dst_a * (1 - src_a)
    safe = np.where(out_a > 0, out_a, 1)
    out_rgb = (src_rgb * src_a[..., None] + dst_rgb * (dst_a * (1 - src_a))[..., None]) / safe[..., None]
    return out_rgb, out_a


def render():
    aa = 1.2 * SS
    ys, xs = np.mgrid[0:N, 0:N].astype(np.float32) + 0.5
    rgb = np.zeros((N, N, 3), np.float32)
    alpha = np.zeros((N, N), np.float32)

    # ---- 方块（Apple 图标网格：1024 画布里 824 的圆角方块，四周留 100）----
    t0, t1 = 100 * SS, 924 * SS
    T = t1 - t0
    radius = 186 * SS

    # 投影：方块下方柔和阴影
    shadow = rounded_rect_mask(xs, ys - 12 * SS, t0, t0, t1, t1, radius, aa)
    sh_img = Image.fromarray((shadow * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(18 * SS))
    sh = np.asarray(sh_img, np.float32) / 255 * 0.28
    rgb, alpha = over(rgb, alpha, np.zeros_like(rgb), sh)

    tile = rounded_rect_mask(xs, ys, t0, t0, t1, t1, radius, aa)
    ty = (ys - t0) / T
    tx = (xs - t0) / T
    top = np.array([0.985, 0.955, 0.885]); bot = np.array([0.955, 0.895, 0.780])
    g = np.clip(ty * 0.85 + tx * 0.15, 0, 1)[..., None]
    bg = top * (1 - g) + bot * g
    # 方块顶部一圈细微的内高光
    rim = (1 - smoothstep(0, 10 * SS, ys - t0)) * 0.03
    bg = np.clip(bg + rim[..., None], 0, 1)

    # ---- 调度球：从右下角探进来，超出方块的部分被裁掉 ----
    bcx, bcy, br = t0 + 0.70 * T, t0 + 0.74 * T, 0.50 * T
    d = np.sqrt((xs - bcx) ** 2 + (ys - bcy) ** 2)
    ball = 1 - smoothstep(br - aa, br + aa, d)
    nx, ny = (xs - bcx) / br, (ys - bcy) / br
    nz = np.sqrt(np.clip(1 - nx ** 2 - ny ** 2, 0, 1))
    # 光从左上偏上来；漫反射 + 柔和高光 + 边缘环境遮蔽
    L = np.array([-0.35, -0.75, 0.56]); L = L / np.linalg.norm(L)
    diff = np.clip(nx * L[0] + ny * L[1] + nz * L[2], 0, 1)
    H = L + np.array([0, 0, 1.0]); H = H / np.linalg.norm(H)
    spec = np.clip(nx * H[0] + ny * H[1] + nz * H[2], 0, 1) ** 18
    shade = 0.42 + 0.55 * diff + 0.10 * spec
    edge = smoothstep(0.80, 1.0, np.sqrt(nx ** 2 + ny ** 2))
    shade = shade - 0.12 * edge
    base = np.array([1.0, 0.56, 0.38])
    cool = np.array([0.80, 0.30, 0.18])
    s = np.clip(shade, 0, 1)[..., None]
    ball_rgb = cool * (1 - s) + base * s
    # 球落在方块上的一圈暗影（让球更「立」起来）
    halo = (smoothstep(br + 36 * SS, br, d) * (1 - ball)) * 0.16
    bg = bg * (1 - halo[..., None])

    layer = bg * (1 - ball[..., None]) + ball_rgb * ball[..., None]

    # ---- 眼睛：球的左上部，两只竖椭圆，顶端略向左倾，朝左上看 ----
    eye_ang = -20
    eyes = [(t0 + 0.505 * T, t0 + 0.555 * T), (t0 + 0.655 * T, t0 + 0.505 * T)]
    rx, ry = 0.044 * T, 0.092 * T
    for ex, ey in eyes:
        m = ellipse_mask(xs, ys, ex, ey, rx, ry, eye_ang, aa)
        eye_col = np.array([0.07, 0.07, 0.08])
        layer = layer * (1 - m[..., None]) + eye_col * m[..., None]
        # 小高光：眼睛左上角一点
        hl = ellipse_mask(xs, ys, ex - 0.35 * rx, ey - 0.55 * ry, 0.28 * rx, 0.20 * ry, eye_ang, aa) * 0.85
        layer = layer * (1 - hl[..., None]) + np.array([1.0, 1.0, 1.0]) * hl[..., None]

    rgb, alpha = over(rgb, alpha, layer, tile)

    img = np.dstack([np.clip(rgb, 0, 1), np.clip(alpha, 0, 1)])
    im = Image.fromarray((img * 255 + 0.5).astype(np.uint8), "RGBA")
    return im.resize((1024, 1024), Image.LANCZOS)


def png_bytes(im, size):
    b = io.BytesIO()
    (im if im.size[0] == size else im.resize((size, size), Image.LANCZOS)).save(b, "PNG", optimize=True)
    return b.getvalue()


def write_icns(im, path):
    # PNG 负载的 icns 条目（macOS 10.7+ 都认）
    entries = [("icp4", 16), ("icp5", 32), ("icp6", 64), ("ic07", 128), ("ic08", 256), ("ic09", 512),
               ("ic10", 1024), ("ic11", 32), ("ic12", 64), ("ic13", 256), ("ic14", 512)]
    body = b""
    for typ, size in entries:
        data = png_bytes(im, size)
        body += typ.encode() + struct.pack(">I", len(data) + 8) + data
    with open(path, "wb") as f:
        f.write(b"icns" + struct.pack(">I", len(body) + 8) + body)


def main():
    im = render()
    os.makedirs(RES, exist_ok=True)
    png = os.path.join(RES, "AppIcon.png")
    icns = os.path.join(RES, "AppIcon.icns")
    im.save(png, "PNG", optimize=True)
    write_icns(im, icns)
    print(png); print(icns, os.path.getsize(icns), "bytes")


if __name__ == "__main__":
    sys.exit(main())
