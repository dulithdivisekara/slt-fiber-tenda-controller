#!/usr/bin/env python3
"""
Generates an engineering-grade GitHub Social Preview (1280x640) for slt-fiber-tenda-controller.

Author: Dulith Divisekara
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

WIDTH = 1280
HEIGHT = 640

REPO_ROOT = Path(__file__).resolve().parent.parent

# Typography
FONT_BOLD = "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf"
FONT_MED = "/usr/share/fonts/truetype/ubuntu/Ubuntu-M.ttf"
FONT_REG = "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf"

title_font = ImageFont.truetype(FONT_BOLD, 58)
subtitle_font = ImageFont.truetype(FONT_MED, 25)
card_title_font = ImageFont.truetype(FONT_BOLD, 22)
card_desc_font = ImageFont.truetype(FONT_REG, 16)
badge_font = ImageFont.truetype(FONT_BOLD, 15)
footer_font = ImageFont.truetype(FONT_REG, 15)
footer_bold_font = ImageFont.truetype(FONT_BOLD, 15)


def generate_social_preview(output_path: Path) -> None:
    # 1. Base Canvas with Deep Gradient
    img = Image.new("RGBA", (WIDTH, HEIGHT), (10, 14, 26, 255))
    draw = ImageDraw.Draw(img)

    for y in range(HEIGHT):
        factor = y / HEIGHT
        r = int(9 + 7 * factor)
        g = int(13 + 9 * factor)
        b = int(24 + 18 * factor)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b, 255))

    # Subtle radial optical glow centered behind title area
    glow_center_x, glow_center_y = 640, 210
    glow_radius = 540
    glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    for r in range(glow_radius, 0, -5):
        alpha = int(38 * (1.0 - (r / glow_radius) ** 2))
        glow_draw.ellipse(
            [glow_center_x - r, glow_center_y - r, glow_center_x + r, glow_center_y + r],
            fill=(6, 182, 212, alpha),
        )
    glow = glow.filter(ImageFilter.GaussianBlur(radius=40))
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)

    # Subtle grid pattern (dots)
    dot_color = (255, 255, 255, 14)
    for gx in range(40, WIDTH, 40):
        for gy in range(40, HEIGHT, 40):
            draw.ellipse([gx - 1, gy - 1, gx + 1, gy + 1], fill=dot_color)

    # Outer framing container
    frame_x0 = 52
    frame_y0 = 38
    frame_x1 = WIDTH - 52
    frame_y1 = HEIGHT - 38

    frame = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    frame_draw = ImageDraw.Draw(frame)
    frame_draw.rounded_rectangle(
        [frame_x0, frame_y0, frame_x1, frame_y1],
        radius=24,
        fill=(15, 23, 42, 235),
        outline=(42, 60, 92, 255),
        width=2,
    )
    img = Image.alpha_composite(img, frame)
    draw = ImageDraw.Draw(img)

    # 2. Header: Logo on left, Badges on right
    logo_path = REPO_ROOT / "assets" / "tenda-logo.png"
    logo = Image.open(logo_path)
    logo_w, logo_h = 245, 70
    logo_scaled = logo.resize((logo_w, logo_h), Image.Resampling.LANCZOS)

    header_y = frame_y0 + 34
    img.paste(logo_scaled, (frame_x0 + 48, header_y), logo_scaled)

    def draw_badge(draw_ctx, text, x_right, y_center, bg_color, border_color, text_color=(255, 255, 255)):
        bbox = badge_font.getbbox(text)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        pad_h = 22
        pad_v = 10
        bw = tw + pad_h * 2
        bh = th + pad_v * 2
        bx0 = x_right - bw
        by0 = y_center - bh // 2
        draw_ctx.rounded_rectangle(
            [bx0, by0, x_right, by0 + bh],
            radius=bh // 2,
            fill=bg_color,
            outline=border_color,
            width=1,
        )
        draw_ctx.text((bx0 + bw // 2, y_center), text, fill=text_color, font=badge_font, anchor="mm")
        return bx0

    badges_y_center = header_y + logo_h // 2
    bx = frame_x1 - 48
    bx = draw_badge(draw, "v1.2.0 STABLE", bx, badges_y_center, (6, 78, 59, 240), (16, 185, 129, 220), (167, 243, 208)) - 14
    bx = draw_badge(draw, "SLT-MOBITEL FIBER", bx, badges_y_center, (88, 28, 135, 240), (168, 85, 247, 220), (233, 213, 255)) - 14
    draw_badge(draw, "GPON ONT HG7", bx, badges_y_center, (30, 58, 138, 240), (59, 130, 246, 220), (191, 219, 254))

    # 3. Hero Title & Subtitle
    title_text = "SLT Fiber Tenda HG7 Controller"
    title_y = header_y + logo_h + 20
    draw.text((frame_x0 + 48, title_y), title_text, fill=(255, 255, 255), font=title_font)

    subtitle_text = "Autonomous AI Agent Ecosystem  •  FastMCP Server  •  Engineering CLI"
    subtitle_y = title_y + 70
    draw.text((frame_x0 + 48, subtitle_y), subtitle_text, fill=(56, 189, 248), font=subtitle_font)

    # 4. Feature Cards: 2x2 Grid with balanced spacing & punchy typography
    gap_between_cols = 24
    inner_width = (frame_x1 - 48) - (frame_x0 + 48)
    pill_w = (inner_width - gap_between_cols) // 2
    pill_h = 92
    pill_y0 = subtitle_y + 60

    features = [
        (
            "FastMCP AI Integration",
            "12 structured tools for autonomous agents (Antigravity & Claude)",
            (14, 165, 233),
        ),
        (
            "GPON Optical Diagnostics",
            "Real-time laser Rx/Tx power (dBm), bias current & ONU state O5",
            (16, 185, 129),
        ),
        (
            "Dual-Band Wi-Fi Automation",
            "Programmatic 2.4GHz / 5GHz SSID & WPA2 passphrase mutation",
            (245, 158, 11),
        ),
        (
            "Strict ISP Safety Guardrails",
            "Hardcoded write protection on SLT WAN VLANs, VoIP & TR-069",
            (168, 85, 247),
        ),
    ]

    for idx, (ft_title, ft_desc, dot_col) in enumerate(features):
        col = idx % 2
        row = idx // 2
        px0 = frame_x0 + 48 + col * (pill_w + gap_between_cols)
        py0 = pill_y0 + row * (pill_h + 16)
        px1 = px0 + pill_w
        py1 = py0 + pill_h

        draw.rounded_rectangle(
            [px0, py0, px1, py1],
            radius=14,
            fill=(20, 28, 46, 235),
            outline=(45, 65, 96, 255),
            width=1,
        )

        dot_cy = py0 + 32
        draw.ellipse([px0 + 22, dot_cy - 6, px0 + 34, dot_cy + 6], fill=dot_col)

        draw.text((px0 + 46, py0 + 20), ft_title, fill=(248, 250, 252), font=card_title_font)
        draw.text((px0 + 46, py0 + 52), ft_desc, fill=(160, 178, 202), font=card_desc_font)

    # 5. Footer (Aligned baselines via anchors)
    footer_y = frame_y1 - 36

    draw.text((frame_x0 + 48, footer_y), "github.com/", fill=(100, 116, 139), font=footer_font, anchor="lm")
    pfx_bbox = footer_font.getbbox("github.com/")
    pfx_w = pfx_bbox[2] - pfx_bbox[0]
    draw.text((frame_x0 + 48 + pfx_w, footer_y), "dulithdivisekara/slt-fiber-tenda-controller", fill=(226, 232, 240), font=footer_bold_font, anchor="lm")

    right_text = "Python 3.10+  •  MIT License  •  Realtek RTL960x  •  Boa 0.95.15"
    draw.text((frame_x1 - 48, footer_y), right_text, fill=(100, 116, 139), font=footer_font, anchor="rm")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG", optimize=True)
    print(f"Generated {output_path} successfully ({WIDTH}x{HEIGHT})")


if __name__ == "__main__":
    out = REPO_ROOT / "assets" / "social-preview.png"
    generate_social_preview(out)
