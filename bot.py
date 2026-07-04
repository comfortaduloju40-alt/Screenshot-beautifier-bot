import os
import io
import logging
from PIL import Image, ImageDraw, ImageFilter
import telebot
from telebot import types

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
bot = telebot.TeleBot(BOT_TOKEN)

THEMES = {
    "macOS": {
        "gradient": [(30, 30, 46), (49, 50, 68)],
        "padding": 60,
        "radius": 14,
        "shadow_color": (0, 0, 0, 140),
        "titlebar": True,
        "titlebar_color": (50, 50, 65),
        "dot_colors": [(255, 95, 87), (255, 189, 46), (39, 201, 63)],
    },
    "Gradient": {
        "gradient": [(102, 126, 234), (118, 75, 162)],
        "padding": 60,
        "radius": 14,
        "shadow_color": (0, 0, 0, 120),
        "titlebar": False,
        "titlebar_color": None,
        "dot_colors": [],
    },
    "Sunset": {
        "gradient": [(255, 94, 58), (255, 195, 113)],
        "padding": 60,
        "radius": 14,
        "shadow_color": (0, 0, 0, 100),
        "titlebar": False,
        "titlebar_color": None,
        "dot_colors": [],
    },
    "Midnight": {
        "gradient": [(15, 12, 41), (48, 43, 99), (36, 36, 62)],
        "padding": 60,
        "radius": 14,
        "shadow_color": (0, 0, 0, 180),
        "titlebar": True,
        "titlebar_color": (30, 28, 60),
        "dot_colors": [(255, 95, 87), (255, 189, 46), (39, 201, 63)],
    },
    "Ocean": {
        "gradient": [(2, 117, 216), (0, 200, 183)],
        "padding": 60,
        "radius": 14,
        "shadow_color": (0, 0, 0, 110),
        "titlebar": False,
        "titlebar_color": None,
        "dot_colors": [],
    },
}

user_sessions = {}


def make_gradient(size, colors):
    w, h = size
    base = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(base)
    if len(colors) == 2:
        r1, g1, b1 = colors[0]
        r2, g2, b2 = colors[1]
        for y in range(h):
            t = y / h
            r = int(r1 + (r2 - r1) * t)
            g = int(g1 + (g2 - g1) * t)
            b = int(b1 + (b2 - b1) * t)
            draw.line([(0, y), (w, y)], fill=(r, g, b))
    elif len(colors) >= 3:
        r1, g1, b1 = colors[0]
        r2, g2, b2 = colors[1]
        r3, g3, b3 = colors[2]
        half = h // 2
        for y in range(half):
            t = y / half
            r = int(r1 + (r2 - r1) * t)
            g = int(g1 + (g2 - g1) * t)
            b = int(b1 + (b2 - b1) * t)
            draw.line([(0, y), (w, y)], fill=(r, g, b))
        for y in range(half, h):
            t = (y - half) / (h - half)
            r = int(r2 + (r3 - r2) * t)
            g = int(g2 + (g3 - g2) * t)
            b = int(b2 + (b3 - b2) * t)
            draw.line([(0, y), (w, y)], fill=(r, g, b))
    return base


def rounded_mask(size, radius):
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), (size[0] - 1, size[1] - 1)], radius=radius, fill=255)
    return mask


def beautify(img_bytes, theme_name):
    theme = THEMES[theme_name]
    screenshot = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    sw, sh = screenshot.size

    pad = theme["padding"]
    tb_h = 38 if theme["titlebar"] else 0

    cw = sw + pad * 2
    ch = sh + pad * 2 + tb_h

    canvas = make_gradient((cw, ch), theme["gradient"]).convert("RGBA")

    # Shadow
    shadow = Image.new("RGBA", (sw + 20, sh + tb_h + 20), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        [(0, 0), (sw + 19, sh + tb_h + 19)],
        radius=theme["radius"],
        fill=theme["shadow_color"],
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=16))
    canvas.alpha_composite(shadow, dest=(pad - 6, pad + tb_h - 6))

    # Card
    card = Image.new("RGBA", (sw, sh + tb_h), (255, 255, 255, 255))

    if theme["titlebar"]:
        tb = Image.new("RGBA", (sw, tb_h), theme["titlebar_color"] + (255,))
        tb_draw = ImageDraw.Draw(tb)
        dot_y = tb_h // 2
        for i, dc in enumerate(theme["dot_colors"]):
            cx = 16 + i * 20
            tb_draw.ellipse([(cx - 6, dot_y - 6), (cx + 6, dot_y + 6)], fill=dc)
        card.paste(tb, (0, 0))

    card.paste(screenshot, (0, tb_h))
    card.putalpha(rounded_mask((sw, sh + tb_h), theme["radius"]))
    canvas.alpha_composite(card, dest=(pad, pad))

    out = io.BytesIO()
    canvas.convert("RGB").save(out, format="PNG", optimize=True)
    out.seek(0)
    return out.read()


@bot.message_handler(commands=["start", "help"])
def cmd_start(message):
    bot.send_message(
        message.chat.id,
        "👋 *Screenshot Beautifier*\n\nSend me any screenshot and I'll wrap it in a beautiful frame!\n\n📸 Just send a photo or file to begin.",
        parse_mode="Markdown",
    )


@bot.message_handler(content_types=["photo", "document"])
def handle_image(message):
    cid = message.chat.id
    try:
        if message.content_type == "photo":
            file_id = message.photo[-1].file_id
        else:
            if not message.document.mime_type.startswith("image/"):
                bot.send_message(cid, "⚠️ Please send an image file.")
                return
            file_id = message.document.file_id

        file_info = bot.get_file(file_id)
        downloaded = bot.download_file(file_info.file_path)
        user_sessions[cid] = {"image_bytes": downloaded}

        markup = types.InlineKeyboardMarkup(row_width=3)
        markup.add(
            types.InlineKeyboardButton("🖥 macOS", callback_data="theme:macOS"),
            types.InlineKeyboardButton("🌈 Gradient", callback_data="theme:Gradient"),
            types.InlineKeyboardButton("🌅 Sunset", callback_data="theme:Sunset"),
            types.InlineKeyboardButton("🌙 Midnight", callback_data="theme:Midnight"),
            types.InlineKeyboardButton("🌊 Ocean", callback_data="theme:Ocean"),
        )
        bot.send_message(cid, "✨ Choose a theme:", reply_markup=markup)

    except Exception as e:
        logger.exception("Error handling image")
        bot.send_message(cid, f"❌ Error: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("theme:"))
def handle_theme(call):
    cid = call.message.chat.id
    theme_name = call.data.split(":")[1]

    if cid not in user_sessions:
        bot.answer_callback_query(call.id, "Session expired. Send your image again.")
        return

    bot.answer_callback_query(call.id, f"Applying {theme_name}…")
    bot.edit_message_text("⏳ Processing…", cid, call.message.message_id)

    try:
        result = beautify(user_sessions[cid]["image_bytes"], theme_name)
        bot.send_photo(cid, result, caption=f"✅ *{theme_name}* theme applied!", parse_mode="Markdown")
        bot.delete_message(cid, call.message.message_id)
    except Exception as e:
        logger.exception("Beautify error")
        bot.send_message(cid, f"❌ Failed: {e}")


if __name__ == "__main__":
    logger.info("Bot starting…")
    bot.infinity_polling()
