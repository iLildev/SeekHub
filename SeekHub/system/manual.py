"""
system/manual.py
================
Interactive inline manual — navigable sections inside the bot.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

# ── Section content ────────────────────────────────────────────────────────────

SECTIONS = {
    "home": {
        "title": "📖 SeekHub Manual",
        "text": (
            "Welcome to the SeekHub Manual\\.\n\n"
            "SeekHub is the deepest connected Telegram database — "
            "it indexes users, groups, and channels through a network of Mirror bots\\.\n\n"
            "*Choose a section to get started:*\n\n"
            "🔍 *What is SeekHub?* — overview & how it works\n"
            "🤖 *Mirrors* — create and manage your mirror bot\n"
            "🛡️ *Privacy Plans* — hide yourself from search\n"
            "💎 *Crystals* — earn and spend crystals\n"
            "🌟 *Aura* — reputation system\n"
            "❓ *FAQ* — common questions"
        ),
        "buttons": [
            [
                InlineKeyboardButton("🔍 What is SeekHub?", callback_data="manual:what"),
                InlineKeyboardButton("🤖 Mirrors",          callback_data="manual:mirrors"),
            ],
            [
                InlineKeyboardButton("🛡️ Privacy Plans",   callback_data="manual:privacy"),
                InlineKeyboardButton("💎 Crystals",         callback_data="manual:crystals"),
            ],
            [
                InlineKeyboardButton("🌟 Aura",             callback_data="manual:aura"),
                InlineKeyboardButton("❓ FAQ",               callback_data="manual:faq"),
            ],
        ],
    },

    "what": {
        "title": "🔍 What is SeekHub?",
        "text": (
            "*🔍 What is SeekHub?*\n\n"
            "SeekHub is a Telegram intelligence network — a system that passively indexes "
            "public Telegram users, groups, and channels through a fleet of Mirror bots\\.\n\n"
            "*How it works:*\n"
            "① Mirror bots are added to groups and channels\n"
            "② They silently collect public data \\(names, usernames, activity\\)\n"
            "③ All data flows into the SeekHub database\n"
            "④ You can search, track, and analyse from this bot\n\n"
            "*What you can do:*\n"
            "• Search any user, group, or channel\n"
            "• Track when someone was last online\n"
            "• Monitor username changes\n"
            "• Export data \\(Pro/Elite plans\\)\n\n"
            "*What SeekHub is NOT:*\n"
            "• It only indexes *public* data\n"
            "• It cannot read private messages\n"
            "• The only official bot is @SeekHubBot"
        ),
    },

    "mirrors": {
        "title": "🤖 Mirrors",
        "text": (
            "*🤖 Mirror Bots*\n\n"
            "A Mirror is a Telegram bot you own that connects to SeekHub and collects data "
            "from groups and channels it's added to\\.\n\n"
            "*Setting up your mirror:*\n"
            "① Create a bot via @BotFather\n"
            "② Copy the bot token\n"
            "③ Use /token in SeekHub to register it\n"
            "④ Add your mirror bot to any group or channel\n"
            "⑤ It starts collecting automatically\n\n"
            "*Commands:*\n"
            "• /mirror — view your mirror status\n"
            "• /token — register or change your mirror bot\n"
            "• /mset — configure mirror settings\n"
            "• /mystats — see what your mirror has collected\n\n"
            "*Limits by plan:*\n"
            "• 👻 Ghost — 1 mirror\n"
            "• 🌑 Shadow — 3 mirrors\n"
            "• 🕵️ Spy — unlimited mirrors\n\n"
            "💡 Submit a group with /submit and earn *\\+8 crystals*"
        ),
    },

    "privacy": {
        "title": "🛡️ Privacy Plans",
        "text": (
            "*🛡️ Privacy Plans*\n\n"
            "Hide your presence from SeekHub's search results\\. "
            "All plans are billed monthly via Telegram Stars \\(⭐\\)\\.\n\n"
            "👻 *Ghost — ⭐250/mo \\(~\\$4\\.99\\)*\n"
            "• Your username is hidden from all search results\n"
            "• Profile still appears but username is masked\n"
            "• Ideal for basic privacy\n\n"
            "🌑 *Shadow — ⭐400/mo \\(~\\$7\\.99\\)*\n"
            "• Completely removed from all search results\n"
            "• No one can find you by username or name\n"
            "• Full invisibility\n\n"
            "🕵️ *Spy — ⭐750/mo \\(~\\$14\\.99\\)*\n"
            "• Everything in Shadow, plus:\n"
            "• Get notified when someone searches for you\n"
            "• See who's looking for you\n\n"
            "To subscribe: use /plan"
        ),
    },

    "crystals": {
        "title": "💎 Crystals",
        "text": (
            "*💎 Crystals*\n\n"
            "Crystals are SeekHub's internal currency\\. "
            "Earn them for free by contributing to the network\\.\n\n"
            "*How to earn:*\n"
            "• 🎁 Join SeekHub — *\\+4 crystals*\n"
            "• 👥 Refer a friend — *\\+10 crystals* per new user\n"
            "• 📢 Submit a group/channel — *\\+8 crystals*\n\n"
            "*How to spend:*\n"
            "• 🔍 Queries cost crystals based on your plan\n"
            "• 🤖 Unlock mirror features\n\n"
            "*Check your balance:*\n"
            "Use /points or tap 💎 Points in the main menu\n\n"
            "*Referral link:*\n"
            "Share your personal link from /points — "
            "every new user who joins through it gives you *\\+10 crystals*"
        ),
    },

    "aura": {
        "title": "🌟 Aura",
        "text": (
            "*🌟 Aura — Reputation System*\n\n"
            "Aura is your public reputation score in the SeekHub network\\.\n\n"
            "*How it works:*\n"
            "• Other users can give you Aura points\n"
            "• Your score is visible on your profile\n"
            "• Top Aura holders appear on the leaderboard\n\n"
            "*Commands:*\n"
            "• /aura — view your score and the top 5 leaderboard\n"
            "• /addaura @username — give Aura to someone\n\n"
            "*Rules:*\n"
            "• You cannot give Aura to yourself\n"
            "• Each user can give Aura once per target per day\n\n"
            "Build your reputation — high Aura users get priority in search results 🏆"
        ),
    },

    "faq": {
        "title": "❓ FAQ",
        "text": (
            "*❓ Frequently Asked Questions*\n\n"
            "*Is SeekHub safe to use?*\n"
            "Yes — SeekHub only indexes *public* Telegram data\\. "
            "Private messages and private groups are never accessed\\.\n\n"
            "*Why is my data in SeekHub?*\n"
            "If you were in a public group that a Mirror bot was added to, "
            "your public profile \\(name, username\\) may have been indexed\\. "
            "Use /plan to hide yourself\\.\n\n"
            "*How do I remove my data?*\n"
            "Subscribe to a Ghost or higher plan — your profile will be "
            "hidden from all search results immediately\\.\n\n"
            "*Is there an official channel?*\n"
            "Yes — @SeekHubBot is the one and only official bot\\. "
            "Any other bot claiming to be SeekHub is fake\\.\n\n"
            "*I found a bug / have a suggestion:*\n"
            "Contact the admin directly through the bot\\."
        ),
    },
}

BACK_ROW = [[InlineKeyboardButton("« Back to Manual", callback_data="manual:home")]]


def _keyboard(section: dict) -> InlineKeyboardMarkup:
    rows = section.get("buttons", [])
    if section != SECTIONS["home"]:
        rows = rows + BACK_ROW
    return InlineKeyboardMarkup(rows)


# ── Handlers ───────────────────────────────────────────────────────────────────

async def cmd_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sec = SECTIONS["home"]
    await update.message.reply_text(
        sec["text"],
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=_keyboard(sec),
    )


async def handle_manual_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    key = query.data.split(":")[1]
    sec = SECTIONS.get(key)
    if not sec:
        return

    await query.edit_message_text(
        sec["text"],
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=_keyboard(sec),
    )
