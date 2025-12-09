import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient

# ================== LOAD ENV ==================
load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")
SESSION_NAME = os.getenv("SESSION_NAME", "vanz_farming")

VIU_BOT = os.getenv("VIU_BOT", "@generateviupawbot")
AM_BOT = os.getenv("AM_BOT", "@pawalightmotionbot")

VIU_INTERVAL_MINUTES = int(os.getenv("VIU_INTERVAL_MINUTES", "20"))
AM_INTERVAL_MINUTES = int(os.getenv("AM_INTERVAL_MINUTES", "20"))

# Flow khusus VIU
VIU_PAKET_KEYWORD = os.getenv("VIU_PAKET_KEYWORD", "Lifetime")
VIU_DOMAIN = os.getenv("VIU_DOMAIN", "vanzmail.web.id")
VIU_PASSWORD = os.getenv("VIU_PASSWORD", "masuk123")

# Flow khusus AM (Alight Motion)
AM_DURASI_KEYWORD = os.getenv("AM_DURASI_KEYWORD", "1 Tahun")
AM_JUMLAH = os.getenv("AM_JUMLAH", "50")  # klik tombol angka
AM_MODE_EMAIL = os.getenv("AM_MODE_EMAIL", "Otomatis (Cepat)")

# ================== PATH & STOK FILE ==================
BASE = Path(__file__).parent

# Nama file stok DISAMAKAN dengan bot utama
STOK_VIU = BASE / "stok_viu.txt"       # dipakai /P_VIU di bot utama
STOK_ALIGHT = BASE / "stok_alight.txt" # dipakai /P_ALIGHT di bot utama

# Logging optional
HASIL_VIU_LOG = BASE / "hasil_viu_raw.txt"
HASIL_AM_LOG = BASE / "hasil_am_raw.txt"

# ================== TELETHON CLIENT ==================
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)


# ========== HELPER: CARI MESSAGE & BUTTON ==========

async def get_last_message(chat_username):
    msgs = await client.get_messages(chat_username, limit=1)
    return msgs[0] if msgs else None


async def click_button_by_text(chat_username: str, keyword: str, timeout: int = 30):
    """
    Cari message terakhir dari bot yg punya inline keyboard,
    lalu klik button yg teksnya mengandung keyword.
    """
    keyword_low = keyword.lower()
    for _ in range(timeout):
        msg = await get_last_message(chat_username)
        if msg and msg.buttons:
            for row_idx, row in enumerate(msg.buttons):
                for col_idx, btn in enumerate(row):
                    text = (btn.text or "").strip()
                    if keyword_low in text.lower():
                        print(
                            f"[{chat_username}] 👉 Klik button "
                            f"'{text}' (row={row_idx}, col={col_idx})"
                        )
                        await btn.click()
                        return
        await asyncio.sleep(1)

    raise RuntimeError(
        f"[{chat_username}] Gagal nemu button dengan keyword '{keyword}' "
        f"dalam {timeout} detik"
    )


async def wait_text_contains(chat_username: str, keyword: str, timeout: int = 900):
    """
    Tunggu sampe message terakhir dari bot mengandung keyword tertentu.
    Berguna buat nunggu '✅ Generate Berhasil!' atau '✅ Proses Selesai!'
    """
    keyword_low = keyword.lower()
    for _ in range(timeout):
        msg = await get_last_message(chat_username)
        if msg and keyword_low in (msg.text or "").lower():
            print(f"[{chat_username}] ✅ Ketemu text berisi '{keyword}'")
            return msg
        await asyncio.sleep(2)

    raise RuntimeError(
        f"[{chat_username}] Timeout nunggu text mengandung '{keyword}'"
    )


async def wait_last_document(chat_username: str, timeout: int = 300):
    """
    Nunggu sampe ada message baru dari bot yang berisi document (file),
    biasanya hasil akun AM dikirim sebagai .txt.
    """
    print(f"[{chat_username}] ⏳ Nunggu file document hasil...")
    last_id = None
    for _ in range(timeout):
        msgs = await client.get_messages(chat_username, limit=5)
        for msg in msgs:
            if last_id is not None and msg.id <= last_id:
                # sudah dicek sebelumnya
                continue
            if msg.document:
                print(f"[{chat_username}] 📄 Ketemu document: {msg.document.attributes[0].file_name}")
                return msg
        if msgs:
            last_id = msgs[0].id
        await asyncio.sleep(2)

    raise RuntimeError(f"[{chat_username}] Timeout nunggu document hasil.")


# ========== HELPER: STOK WRITER ==========

def append_to_file(path: Path, lines):
    if not lines:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for line in lines:
            f.write(line.rstrip() + "\n")


# ========== PARSER HASIL VIU TEXT ==========

def parse_viu_accounts(raw_text: str):
    """
    Contoh format:

    VIU PREMIUM RESULTS
    Generated at: ...
    ==================================================

    email1@... | pass123 | 95310 Days
    email2@... | pass123 | 95310 Days
    ...
    ==================================================
    File ini akan otomatis terhapus...

    Kita ambil semua line yang di tengah yang ada '@' dan '|'
    """
    lines = [l.strip() for l in (raw_text or "").splitlines()]
    accounts = []
    in_block = False
    for line in lines:
        if "VIU PREMIUM RESULTS" in line:
            in_block = True
            continue
        if "File ini akan otomatis terhapus" in line:
            break
        if not in_block:
            continue
        if not line:
            continue
        if "@" in line and "|" in line:
            # biarin full line, cocok sama format stok: email | pass | days
            accounts.append(line)
    return accounts


# ========== FLOW VIU (generate akun) ==========

async def run_viu_once():
    bot = VIU_BOT
    print(f"[VIU] 🚀 Mulai flow VIU ke {bot}")

    # 1. /start
    print("[VIU] Kirim /start")
    await client.send_message(bot, "/start")
    await asyncio.sleep(3)

    # 2. Klik 'Buat Akun'
    await click_button_by_text(bot, "Buat Akun")

    # 3. Pilih tipe paket (Lifetime / yg lain)
    await asyncio.sleep(3)
    print(f"[VIU] Pilih paket dengan keyword '{VIU_PAKET_KEYWORD}'")
    await click_button_by_text(bot, VIU_PAKET_KEYWORD)

    # 4. Bot minta domain → kirim text
    await asyncio.sleep(3)
    print(f"[VIU] Kirim domain: {VIU_DOMAIN}")
    await client.send_message(bot, VIU_DOMAIN)

    # 5. Bot minta password → kirim text
    await asyncio.sleep(3)
    print(f"[VIU] Kirim password")
    await client.send_message(bot, VIU_PASSWORD)

    # 6. Nunggu sampai "✅ Generate Berhasil!"
    print("[VIU] ⏳ Nunggu '✅ Generate Berhasil!' ...")
    msg_done = await wait_text_contains(bot, "Generate Berhasil", timeout=900)

    raw_text = msg_done.text or ""
    # save raw log (opsional)
    append_to_file(HASIL_VIU_LOG, ["\n\n===== NEW BATCH =====", raw_text])

    # parse ke list akun
    akun_list = parse_viu_accounts(raw_text)
    print(f"[VIU] ✅ Parsed {len(akun_list)} akun dari hasil generate.")

    if not akun_list:
        print("[VIU] ⚠️ Tidak ada akun yang ter-parse dari hasil.")
        return

    # append ke stok_viu.txt (dipakai bot utama)
    append_to_file(STOK_VIU, akun_list)
    print(f"[VIU] 💾 {len(akun_list)} akun ditambahkan ke {STOK_VIU.name}")


async def farm_viu_loop():
    """
    Loop farming VIU tiap X menit (dari env VIU_INTERVAL_MINUTES)
    """
    if not VIU_BOT:
        print("[VIU] ⚠️ VIU_BOT kosong, skip farming VIU.")
        return

    interval = VIU_INTERVAL_MINUTES
    print(f"[VIU] 🔁 Farming VIU aktif, interval {interval} menit.")

    while True:
        try:
            await run_viu_once()
        except Exception as e:
            print(f"[VIU] ❌ Error di run_viu_once: {e}")

        print(f"[VIU] ⏳ Tidur {interval} menit sebelum next run...\n")
        await asyncio.sleep(interval * 60)


# ========== FLOW AM (Alight Motion) ==========

async def run_am_once():
    bot = AM_BOT
    print(f"[AM] 🚀 Mulai flow AM ke {bot}")

    # 1. /start
    print("[AM] Kirim /start")
    await client.send_message(bot, "/start")
    await asyncio.sleep(3)

    # 2. Klik "🚀 Buat Akun AM"
    await click_button_by_text(bot, "Buat Akun AM")

    # 3. Pilih durasi (6 Bulan / 1 Tahun / dll)
    await asyncio.sleep(3)
    print(f"[AM] Pilih durasi dengan keyword '{AM_DURASI_KEYWORD}'")
    await click_button_by_text(bot, AM_DURASI_KEYWORD)

    # 4. Pilih jumlah akun (1–50)
    await asyncio.sleep(3)
    print(f"[AM] Pilih jumlah akun '{AM_JUMLAH}'")
    await click_button_by_text(bot, AM_JUMLAH)

    # 5. Pilih metode input email (Otomatis / Manual)
    await asyncio.sleep(3)
    print(f"[AM] Pilih mode email '{AM_MODE_EMAIL}'")
    await click_button_by_text(bot, AM_MODE_EMAIL)

    # 6. Nunggu "✅ Proses Selesai!"
    print("[AM] ⏳ Nunggu '✅ Proses Selesai!' ...")
    msg_done = await wait_text_contains(bot, "Proses Selesai", timeout=900)
    done_text = msg_done.text or ""
    append_to_file(HASIL_AM_LOG, ["\n\n===== STATUS DONE =====", done_text])

    # 7. Nunggu file hasil (document .txt)
    file_msg = await wait_last_document(bot, timeout=300)
    # download file ke folder script
    download_path = BASE / "hasil_am_last.txt"
    real_path = await client.download_media(file_msg, file=str(download_path))
    print(f"[AM] 💾 File hasil di-download ke: {real_path}")

    # 8. Baca isi file & append ke stok_alight.txt
    try:
        with open(real_path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
    except UnicodeDecodeError:
        # jaga-jaga kalau encoding beda
        with open(real_path, "r", encoding="latin-1") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]

    if not lines:
        print("[AM] ⚠️ File hasil kosong / tidak terbaca.")
        return

    append_to_file(STOK_ALIGHT, lines)
    print(f"[AM] ✅ {len(lines)} akun ditambahkan ke {STOK_ALIGHT.name}")


async def farm_am_loop():
    """
    Loop farming AM tiap X menit (dari env AM_INTERVAL_MINUTES)
    """
    if not AM_BOT:
        print("[AM] ⚠️ AM_BOT kosong, skip farming AM.")
        return

    interval = AM_INTERVAL_MINUTES
    print(f"[AM] 🔁 Farming AM aktif, interval {interval} menit.")

    while True:
        try:
            await run_am_once()
        except Exception as e:
            print(f"[AM] ❌ Error di run_am_once: {e}")

        print(f"[AM] ⏳ Tidur {interval} menit sebelum next run...\n")
        await asyncio.sleep(interval * 60)


# ========== MAIN ==========

async def main():
    print("🔐 Login userbot...")
    await client.start()
    me = await client.get_me()
    print(f"✅ Login sebagai: {me.first_name} (@{me.username}) [id={me.id}]")

    # Jalanin 2 farming bareng (VIU + AM)
    asyncio.create_task(farm_viu_loop())
    asyncio.create_task(farm_am_loop())

    print("🔥 Farming jalan. Tekan CTRL+C di CMD kalau mau stop.")
    # Biar script nggak langsung selesai
    await asyncio.Future()


if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())
