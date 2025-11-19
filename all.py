import os
import json
import asyncio
from pathlib import Path
from datetime import datetime, timedelta, date

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ======================================
# CONFIG
# ======================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN wajib diisi di environment variable!")

# GANTI KE ID TELEGRAM LU SENDIRI
ADMIN_IDS = {7321522905}  # contoh: {123456789}

# Limit global per user per hari (gabungan semua produk)
MAX_PER_DAY = 100

BASE = Path(__file__).parent
PREMIUM_FILE = BASE / "premium.json"
HISTORY_FILE = BASE / "history.json"

# File stok per produk
STOK_CANVA = BASE / "stok_canva.txt"
STOK_CAPCUT = BASE / "stok_capcut.txt"
STOK_SCRIBD = BASE / "stok_scribd.txt"
STOK_VIU = BASE / "stok_viu.txt"
STOK_VIDIO = BASE / "stok_vidio.txt"

# Display nama produk
PRODUCTS = {
    "CANVA": "Canva Kosongan",
    "CAPCUT": "CapCut Kosongan",
    "SCRIBD": "Scribd Kosongan",
    "VIU": "Viu Premium 1 Tahun",
    "VIDIO": "Vidio Platinum 1 TV",
}


# ======================================
# JSON HELPERS
# ======================================

def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path: Path, data):
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ======================================
# PREMIUM SYSTEM
# ======================================

def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


def get_premium_db():
    return load_json(PREMIUM_FILE, {})


def save_premium_db(db):
    save_json(PREMIUM_FILE, db)


def is_premium(uid: int) -> bool:
    db = get_premium_db()
    rec = db.get(str(uid))
    if not rec:
        return False
    exp = rec.get("expire_at")
    if not exp:
        return False
    try:
        exp_date = datetime.strptime(exp, "%Y-%m-%d").date()
    except ValueError:
        return False
    return date.today() <= exp_date


def get_sisa_sewa(uid: int) -> int:
    db = get_premium_db()
    rec = db.get(str(uid), {})
    exp = rec.get("expire_at")
    if not exp:
        return 0
    try:
        exp_date = datetime.strptime(exp, "%Y-%m-%d").date()
    except ValueError:
        return 0
    return max((exp_date - date.today()).days, 0)


def update_quota(uid: int):
    today = date.today().strftime("%Y-%m-%d")
    db = get_premium_db()
    rec = db.get(str(uid), {
        "expire_at": None,
        "today_date": today,
        "today_count": 0,
        "total_generated": 0,
    })

    # reset harian kalau ganti tanggal
    if rec.get("today_date") != today:
        rec["today_date"] = today
        rec["today_count"] = 0

    db[str(uid)] = rec
    save_premium_db(db)
    return rec


def increment_quota(uid: int):
    db = get_premium_db()
    rec = db.get(str(uid))
    if not rec:
        return
    rec["today_count"] = rec.get("today_count", 0) + 1
    rec["total_generated"] = rec.get("total_generated", 0) + 1
    db[str(uid)] = rec
    save_premium_db(db)


# ======================================
# HISTORY SYSTEM
# ======================================

def get_history(uid: int):
    db = load_json(HISTORY_FILE, {})
    return db.get(str(uid), [])


def add_history(uid: int, akun: str, produk: str):
    db = load_json(HISTORY_FILE, {})
    lst = db.get(str(uid), [])
    lst.append({"akun": akun, "produk": produk})
    db[str(uid)] = lst
    save_json(HISTORY_FILE, db)


# ======================================
# STOK HANDLER
# ======================================

def get_stok_file(produk_key: str) -> Path:
    if produk_key == "CANVA":
        return STOK_CANVA
    if produk_key == "CAPCUT":
        return STOK_CAPCUT
    if produk_key == "SCRIBD":
        return STOK_SCRIBD
    if produk_key == "VIU":
        return STOK_VIU
    if produk_key == "VIDIO":
        return STOK_VIDIO
    # default fallback
    return STOK_CAPCUT


def ambil_satu_akun(produk_key: str):
    stok_file = get_stok_file(produk_key)
    if not stok_file.exists():
        return None

    lines = [l.strip() for l in stok_file.read_text().splitlines() if l.strip()]
    if not lines:
        return None

    akun = lines[0]
    sisa = lines[1:]

    with stok_file.open("w", encoding="utf-8") as f:
        for s in sisa:
            f.write(s + "\n")

    return akun


# ======================================
# UI KEYBOARD
# ======================================

def main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎨 Canva Kosongan", callback_data="P_CANVA"),
            InlineKeyboardButton("🎬 CapCut Kosongan", callback_data="P_CAPCUT"),
        ],
        [
            InlineKeyboardButton("📚 Scribd Kosongan", callback_data="P_SCRIBD"),
            InlineKeyboardButton("🎵 Viu Premium 1 Tahun", callback_data="P_VIU"),
        ],
        [
            InlineKeyboardButton("📺 Vidio Platinum 1 TV", callback_data="P_VIDIO"),
        ],
        [
            InlineKeyboardButton("📦 Riwayat Akun", callback_data="SAVED"),
            InlineKeyboardButton("⏳ Sisa Sewa", callback_data="SEWA"),
        ],
        [
            InlineKeyboardButton("🆘 Bantuan", callback_data="HELP"),
        ],
    ])


# ======================================
# HANDLER /START
# ======================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    nama = user.first_name or (user.username or "User")

    text = (
        "🌌 <b>VANZSTORE.ID — Multi Generator Bot</b> 🚀\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Welcome, <b>{nama}</b>!\n\n"
        "Bot otomatis untuk generate berbagai akun fresh & premium:\n"
        "• 🎨 Canva Kosongan\n"
        "• 🎬 CapCut Kosongan\n"
        "• 📚 Scribd Kosongan\n"
        "• 🎵 Viu Premium 1 Tahun\n"
        "• 📺 Vidio Platinum 1 TV\n\n"
        "⚙️ <b>Fitur Bot:</b>\n"
        f"• Limit global <b>{MAX_PER_DAY} akun / hari</b>\n"
        "• Multi produk dalam 1 bot\n"
        "• Riwayat akun tersimpan otomatis\n"
        "• Anti-spam & proses cepat\n\n"
        "📲 <b>Cara pakai:</b>\n"
        "1. Pilih dulu produk yang mau digenerate\n"
        "2. Pilih jumlah (10 atau 20 akun)\n"
        "3. Akun keluar & bisa dicek ulang di menu <b>Riwayat Akun</b>\n\n"
        "Silakan pilih produk di bawah:"
    )

    await update.message.reply_text(
        text,
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )


# ======================================
# CALLBACK HANDLER (BUTTONS)
# ======================================

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    data = q.data

    # STEP 1: pilih produk
    if data.startswith("P_"):
        produk_key = data.split("_", 1)[1]  # P_CANVA -> CANVA
        produk_nama = PRODUCTS.get(produk_key, produk_key)
        await show_quantity_menu(q, produk_key, produk_nama)
        return

    # STEP 2: pilih jumlah setelah pilih produk
    if data.startswith("Q_"):
        # format: Q_CANVA_10
        try:
            _, produk_key, qty_str = data.split("_", 2)
            jumlah = int(qty_str)
        except Exception:
            await q.message.reply_text("Format tombol tidak dikenal. Coba /start lagi.")
            return

        produk_nama = PRODUCTS.get(produk_key, produk_key)
        await generate_multiple(q, uid, produk_key, produk_nama, jumlah)
        return

    # tombol lain
    if data == "SAVED":
        await show_saved(q, uid)
    elif data == "SEWA":
        await show_sewa(q, uid)
    elif data == "HELP":
        await show_help(q)
    elif data == "BACK_HOME":
        await q.message.edit_text(
            "Kembali ke menu utama.\n\n"
            "Silakan pilih produk yang ingin kamu generate:",
            reply_markup=main_keyboard(),
            parse_mode="HTML",
        )


# ======================================
# MENU PILIH JUMLAH
# ======================================

async def show_quantity_menu(q, produk_key: str, produk_nama: str):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔟 Generate 10 akun", callback_data=f"Q_{produk_key}_10"),
            InlineKeyboardButton("2️⃣0️⃣ Generate 20 akun", callback_data=f"Q_{produk_key}_20"),
        ],
        [
            InlineKeyboardButton("⬅️ Kembali ke menu utama", callback_data="BACK_HOME"),
        ],
    ])

    await q.message.edit_text(
        f"✨ Kamu memilih: <b>{produk_nama}</b>\n\n"
        "Pilih berapa banyak akun yang mau kamu generate:",
        reply_markup=keyboard,
        parse_mode="HTML",
    )


# ======================================
# GENERATE MULTI AKUN
# ======================================

async def generate_multiple(q, uid: int, produk_key: str, produk_nama: str, jumlah_awal: int):
    # cek akses premium / admin
    if not (is_admin(uid) or is_premium(uid)):
        await q.message.reply_text(
            "🚫 Akses premium belum aktif untuk akun kamu.\n"
            "Silakan hubungi admin untuk aktivasi."
        )
        return

    rec = update_quota(uid)
    jumlah = jumlah_awal

    # cek limit harian global (kecuali admin)
    if not is_admin(uid):
        sisa = MAX_PER_DAY - rec.get("today_count", 0)
        if sisa <= 0:
            await q.message.reply_text(
                "❌ Limit harian kamu sudah tercapai.\n"
                "Kamu bisa generate lagi besok."
            )
            return
        if jumlah > sisa:
            jumlah = sisa

    # notif proses
    proses_msg = await q.message.reply_text(
        f"🔄 <b>Generator {produk_nama}</b>\n"
        f"⏳ Menyiapkan <b>{jumlah}</b> akun untuk kamu...\n\n"
        "Mohon tunggu, sistem sedang memproses.",
        parse_mode="HTML",
    )

    hasil = []

    for _ in range(jumlah):
        akun = ambil_satu_akun(produk_key)
        if not akun:
            break
        hasil.append(akun)
        increment_quota(uid)
        add_history(uid, akun, produk_nama)
        # anti-spam delay
        await asyncio.sleep(0.6)

    if not hasil:
        await proses_msg.edit_text(
            f"😿 Stok akun <b>{produk_nama}</b> sedang habis.\n"
            "Silakan hubungi admin untuk isi ulang stok.",
            parse_mode="HTML",
        )
        return

    lines = []
    for i, a in enumerate(hasil, start=1):
        lines.append(f"{i}. <code>{a}</code>")
    daftar = "\n".join(lines)

    await proses_msg.edit_text(
        f"✅ <b>Generate {produk_nama} selesai!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 Jumlah akun di batch ini: <b>{len(hasil)}</b>\n\n"
        f"{daftar}\n\n"
        "🔁 Semua akun ini juga tersimpan di menu <b>Riwayat Akun</b>.",
        parse_mode="HTML",
    )


# ======================================
# RIWAYAT, SEWA, HELP
# ======================================

async def show_saved(q, uid: int):
    hist = get_history(uid)
    if not hist:
        await q.message.reply_text(
            "📦 Riwayat kosong.\n"
            "Kamu belum pernah generate akun dari bot ini."
        )
        return

    lines = [
        f"{i+1}. [{h['produk']}] <code>{h['akun']}</code>"
        for i, h in enumerate(hist)
    ]

    text = (
        "📦 <b>Riwayat Akun Kamu</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Total akun yang pernah kamu ambil: <b>{len(hist)}</b>\n\n"
        + "\n".join(lines)
    )

    await q.message.reply_text(text, parse_mode="HTML")


async def show_sewa(q, uid: int):
    if is_admin(uid):
        await q.message.reply_text(
            "👑 Kamu adalah admin.\n"
            "Akses generator tidak dibatasi masa sewa."
        )
        return

    if not is_premium(uid):
        await q.message.reply_text(
            "⏳ Akses premium kamu belum aktif.\n"
            "Silakan hubungi admin untuk beli / perpanjang paket."
        )
        return

    sisa = get_sisa_sewa(uid)
    db = get_premium_db()
    rec = db.get(str(uid), {})
    today_cnt = rec.get("today_count", 0)

    await q.message.reply_text(
        "⏳ <b>Status Sewa Premium</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• Sisa masa aktif: <b>{sisa} hari</b>\n"
        f"• Limit harian: <b>{MAX_PER_DAY} akun / hari</b>\n"
        f"• Pemakaian hari ini: <b>{today_cnt}/{MAX_PER_DAY}</b>",
        parse_mode="HTML",
    )


async def show_help(q):
    await q.message.reply_text(
        "🆘 <b>Panduan Singkat</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣ /start → pilih produk (Canva, CapCut, Scribd, Viu, Vidio)\n"
        "2️⃣ Pilih jumlah generate (10 atau 20 akun)\n"
        "3️⃣ Tunggu proses, akun muncul + auto tersimpan di Riwayat\n\n"
        f"Limit generate per user: <b>{MAX_PER_DAY} akun / hari</b>.\n"
        "Untuk pembelian / perpanjang akses premium, silakan hubungi admin.",
        parse_mode="HTML",
    )


# ======================================
# ADMIN COMMANDS
# ======================================

async def addpremium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if len(context.args) < 2:
        await update.message.reply_text("Format: /addpremium <user_id> <hari>")
        return

    try:
        uid = int(context.args[0])
        hari = int(context.args[1])
    except ValueError:
        await update.message.reply_text("User ID dan hari harus berupa angka.")
        return

    db = get_premium_db()
    today = date.today()

    old = db.get(str(uid), {})
    if old.get("expire_at"):
        try:
            old_exp = datetime.strptime(old["expire_at"], "%Y-%m-%d").date()
        except ValueError:
            old_exp = today
    else:
        old_exp = today

    new_expire = max(old_exp, today) + timedelta(days=hari)

    db[str(uid)] = {
        "expire_at": new_expire.strftime("%Y-%m-%d"),
        "today_date": today.strftime("%Y-%m-%d"),
        "today_count": 0,
        "total_generated": old.get("total_generated", 0),
    }

    save_premium_db(db)

    await update.message.reply_text(
        f"✅ Premium user {uid} aktif sampai {new_expire}"
    )


async def delpremium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("Format: /delpremium <user_id>")
        return

    uid_str = context.args[0]
    db = get_premium_db()
    if uid_str in db:
        db.pop(uid_str)
        save_premium_db(db)
        await update.message.reply_text("✅ User tersebut dihapus dari premium.")
    else:
        await update.message.reply_text("User tidak ditemukan di list premium.")


async def listpremium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    db = get_premium_db()
    if not db:
        await update.message.reply_text("Belum ada user premium.")
        return

    lines = []
    for uid, rec in db.items():
        exp = rec.get("expire_at", "-")
        total = rec.get("total_generated", 0)
        lines.append(f"• {uid} | exp: {exp} | total: {total}")

    text = "👑 <b>Daftar User Premium</b>\n" \
           "━━━━━━━━━━━━━━━━━━━━━━━\n\n" + "\n".join(lines)
    await update.message.reply_text(text, parse_mode="HTML")


# ======================================
# FALLBACK & MAIN
# ======================================

async def fallback_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Halo 👋\n"
        "Gunakan /start untuk membuka menu utama bot ya."
    )


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addpremium", addpremium))
    app.add_handler(CommandHandler("delpremium", delpremium))
    app.add_handler(CommandHandler("listpremium", listpremium))

    app.add_handler(CallbackQueryHandler(handle_buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback_msg))

    app.run_polling()


if __name__ == "__main__":
    main()
