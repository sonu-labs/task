#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TaskHub Global — Telegram Bot
Post Task • Do Task • Earn • Guide + Screenshot Proof

BOT_TOKEN hardcoded hai — @BotFather se token leke niche paste karo
Run:  python telegram_bot.py  (polling mode, 24x7 chalta rahega)
"""

import os
import json
import uuid
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)

# ================== CONFIG - TOKEN HARDCODED ==================
# BotFather se liya hua token hardcoded hai — yahan direct pada hai
BOT_TOKEN = "8857611106:AAGnI9_myVw2mItmLYslUClFGZ8t00DnmLE"  # hardcoded token
# Admin user id (full access)
ADMIN_ID = 8907752103
ADMIN_IDS = [8907752103]

# Env override bhi support hai (optional)
BOT_TOKEN = os.environ.get("BOT_TOKEN", BOT_TOKEN)
ADMIN_ID = int(os.environ.get("ADMIN_ID", ADMIN_ID))

DATA_FILE = "tasks_data.json"
CATEGORIES = ["Design","Coding","Writing","Marketing","Video","Data Entry","Research","Testing","AI Training","Translation","Other"]
DIFFICULTIES = ["Easy","Medium","Hard"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)

# ====== Data helpers (same file as web) ======
MOCK_TASKS = None  # web wale mock ko reuse karenge, file na ho to wahi load hoga

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE,'r',encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log.error(f"load fail {e}")
    # fallback - web ka mock
    from main import MOCK_TASKS as MT
    return {"tasks": MT, "users": []}

def save_data(data):
    with open(DATA_FILE,'w',encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user_telegram(u):
    """telegram user se hamara user dict"""
    return {"id": f"tg{u.id}", "name": u.full_name or u.first_name, "avatar": (u.first_name[:2].upper() if u.first_name else "TG"), "tg_id": u.id, "username": u.username}

def find_task(tid, data):
    return next((t for t in data["tasks"] if t["id"]==tid), None)

def format_task_short(t, idx=None):
    prefix = f"{idx}. " if idx else ""
    status_emoji = {"open":"🟢 OPEN","claimed":"🟡 CLAIMED","submitted":"🔵 REVIEW","completed":"✅ DONE"}.get(t["status"],"⚪")
    guide = f" | 📋 {len(t['guide'])} steps" if t.get('guide') else ""
    return f"{prefix}{status_emoji} *{t['title']}*\n🏷️ {t['category']} • {t['difficulty']} • ₹{t['reward']}{guide}\n👤 {t['postedBy']['name']} • ⏳ {format_deadline(t['deadline'])}\n🆔 `{t['id']}`"

def format_deadline(iso):
    try:
        d=datetime.fromisoformat(iso)
        diff=(d-datetime.now()).days
        if diff<0: return "Expired"
        if diff==0: return "Today"
        if diff==1: return "Tomorrow"
        return f"{diff}d left"
    except: return "?"

def task_detail_text(t):
    status_line = {"open":"🟢 *OPEN* — koi bhi claim kar sakta hai","claimed":f"🟡 *CLAIMED* by {t['claimedBy']['name'] if t['claimedBy'] else '?'}","submitted":"🔵 *UNDER REVIEW* — poster check karega","completed":"✅ *COMPLETED & PAID*"}
    txt = f"*{t['title']}*\n"
    txt += f"{status_line.get(t['status'], t['status'])}\n\n"
    txt += f"🏷️ *Category:* {t['category']}  |  💰 *Reward:* ₹{t['reward']}  |  ⭐ *{t['difficulty']}*\n"
    txt += f"⏰ *Deadline:* {datetime.fromisoformat(t['deadline']).strftime('%d %b %Y')} ({format_deadline(t['deadline'])})\n"
    txt += f"👤 *Posted by:* {t['postedBy']['name']}  •  🆔 `{t['id']}`\n"
    txt += f"🏷️ Tags: {', '.join('#'+x for x in t['tags']) if t['tags'] else '—'}\n\n"
    txt += f"📝 *Description:*\n{t['description']}\n\n"
    txt += f"📋 *Step-by-Step Guide ({len(t['guide'])} steps):*\n"
    for i,s in enumerate(t['guide'],1):
        txt += f"{i}. {s}\n"
    if t.get('proof'):
        txt += f"\n📸 *Submitted Proof:*\n{t['proof'].get('note','—')}\n"
        if t['proof'].get('submittedAt'):
            txt += f"_Submitted: {t['proof']['submittedAt'][:16]}_\n"
    return txt

def main_keyboard():
    return ReplyKeyboardMarkup([
        ["🌍 Browse Tasks", "➕ Post Task"],
        ["📋 My Tasks", "🏆 Leaderboard"],
        ["ℹ️ Help"]
    ], resize_keyboard=True)

def categories_keyboard(prefix="cat"):
    rows=[]
    for i in range(0, len(CATEGORIES), 2):
        row=[]
        for c in CATEGORIES[i:i+2]:
            row.append(InlineKeyboardButton(c, callback_data=f"{prefix}:{c}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("All", callback_data=f"{prefix}:All"), InlineKeyboardButton("❌ Cancel", callback_data="cancel_cat")])
    return InlineKeyboardMarkup(rows)

# ====== Conversation states for posting ======
P_TITLE, P_DESC, P_CAT, P_REWARD, P_DIFF, P_GUIDE, P_TAGS, P_CONFIRM = range(8)
# Submit proof states
S_PHOTO, S_NOTE = range(2)

user_post_draft = {}  # user_id -> draft
user_submit_draft = {}  # user_id -> {task_id}

# ============ HANDLERS ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    is_adm = is_admin(u.id)
    admin_badge = "\n👑 *Admin access granted* — /admin se panel kholo\n" if is_adm else ""
    await update.message.reply_text(
        f"👋 *Namaste {u.first_name}!* — TaskHub Global me swagat hai\n\n"
        "🌍 *Global Task Marketplace*\n"
        "• Koi bhi kaam *post karo* — Design, Coding, Writing, Testing, AI Training… sab chalega\n"
        "• Dusron ka task *claim karke* guide follow karo, *screenshot* bhejo, *₹ earn* karo\n"
        "• Har task me *step-by-step guide + screenshot proof* mandatory hai"
        f"{admin_badge}\n"
        "👇 Neeche buttons se shuru karo:",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )
    await update.message.reply_text(
        "⚡ *Quick Commands:*\n"
        "/tasks — Browse global tasks\n"
        "/post — Naya task post karo\n"
        "/mytasks — Tumhare posted / claimed tasks\n"
        "/leaderboard — Top workers\n"
        "/help — Full help" + ("\n/admin — Admin panel" if is_adm else ""),
        parse_mode="Markdown"
    )
    # Auto notify admin about new user (optional)
    try:
        if not is_adm:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"👤 New user started bot:\n{u.full_name} (@{u.username}) ID:{u.id}\nLang:{u.language_code}")
    except:
        pass

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🆘 *TaskHub Bot Help*\n\n"
        "*User kya kar sakta hai:*\n"
        "1️⃣ /post — Naya task post karo (title, desc, guide, reward)\n"
        "2️⃣ /tasks — Global tasks dekho, Claim karo\n"
        "3️⃣ Task open karke *Guide* padho → Claim → Kaam karo → 📸 Screenshot bhejo\n"
        "4️⃣ Poster Approve karega → ₹ Reward milega\n\n"
        "*Bot Commands:*\n"
        "/start — Welcome + menu\n"
        "/tasks [category] — Filter: /tasks Coding\n"
        "/mytasks — Posted / Claimed / Review / Completed\n"
        "/leaderboard — Top earners\n"
        "/cancel — Current action cancel\n\n"
        "*Flow:* Post → Claim → Guide follow → Screenshot Proof → Review → Paid ✅\n\n"
        "🌐 *Web App bhi hai:* http://0.0.0.0:5000  (same data)\n"
        "Token hardcoded hai `telegram_bot.py` me `BOT_TOKEN` variable me.",
        parse_mode="Markdown"
    )

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS or user_id == ADMIN_ID

async def leaderboard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lb = [
        ("🥇 Rohan Dev", 42, 12400),
        ("🥈 Aap (Demo)", 18, 5600),
        ("🥉 Priya Writes", 15, 4800),
        ("  4. Vikas Tester", 12, 3600),
        ("  5. Sneha K", 9, 2700),
    ]
    txt="🏆 *Top Workers — This Week*\n\n"
    for name, comp, earn in lb:
        txt+=f"{name} — {comp} tasks • ₹{earn}\n"
    txt+="\n_Tum Rank #2 pe ho — 18 tasks done!_"
    await update.message.reply_text(txt, parse_mode="Markdown")

# ---------- Admin Panel ----------
async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Ye command sirf Admin ke liye hai.")
        return
    data=load_data()
    total=len(data["tasks"])
    open_c=len([t for t in data["tasks"] if t["status"]=="open"])
    claimed=len([t for t in data["tasks"] if t["status"]=="claimed"])
    submitted=len([t for t in data["tasks"] if t["status"]=="submitted"])
    completed=len([t for t in data["tasks"] if t["status"]=="completed"])
    txt=(
        f"👑 *Admin Panel* — ID: `{ADMIN_ID}`\n\n"
        f"📊 *Stats:*\n"
        f"Total: {total} | Open: {open_c} | Claimed: {claimed} | Review: {submitted} | Done: {completed}\n\n"
        f"*Admin Commands:*\n"
        f"/admin_stats — Full stats + data dump\n"
        f"/admin_tasks — Saare tasks list (admin view)\n"
        f"/admin_approve <id> — Koi bhi task force approve\n"
        f"/admin_delete <id> — Koi bhi task delete\n"
        f"/broadcast <msg> — Sab users ko broadcast (next update me)\n\n"
        f"Bot Token: `{BOT_TOKEN[:6]}...{BOT_TOKEN[-4:]}` (hardcoded)\n"
    )
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Stats", callback_data="admin:stats"), InlineKeyboardButton("📋 All Tasks", callback_data="admin:tasks")],
        [InlineKeyboardButton("🔄 Refresh", callback_data="admin:refresh")],
    ])
    await update.message.reply_text(txt, parse_mode="Markdown", reply_markup=kb)

async def admin_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        await q.answer("Not admin", show_alert=True)
        return
    data=load_data()
    # show all tasks raw summary
    txt="📊 *Admin Stats — Detailed*\n\n"
    for t in data["tasks"][:10]:
        txt+=f"`{t['id']}` {t['status']} • {t['category']} • ₹{t['reward']} • {t['title'][:30]}\n"
    if len(data["tasks"])>10:
        txt+=f"\n...and {len(data['tasks'])-10} more\n"
    await q.message.reply_text(txt, parse_mode="Markdown")

async def admin_tasks_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        return
    data=load_data()
    # show with admin controls
    for t in data["tasks"][:8]:
        kb=InlineKeyboardMarkup([
            [InlineKeyboardButton("👁️ View", callback_data=f"view:{t['id']}"), InlineKeyboardButton("🗑️ Delete", callback_data=f"admin_del:{t['id']}")],
            [InlineKeyboardButton("✅ Force Approve", callback_data=f"admin_approve:{t['id']}")]
        ])
        await q.message.reply_text(format_task_short(t), parse_mode="Markdown", reply_markup=kb)

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        await q.answer("Not admin", show_alert=True)
        return
    data_str=q.data
    if data_str=="admin:stats":
        await admin_stats_callback(update, context)
    elif data_str=="admin:tasks":
        await admin_tasks_callback(update, context)
    elif data_str=="admin:refresh":
        await q.message.reply_text("🔄 Refreshed — /admin dobara bhejo")
    elif data_str.startswith("admin_del:"):
        tid=data_str.split(":")[1]
        data=load_data()
        data["tasks"]=[x for x in data["tasks"] if x["id"]!=tid]
        save_data(data)
        await q.edit_message_text(f"🗑️ Deleted {tid} (by admin)")
    elif data_str.startswith("admin_approve:"):
        tid=data_str.split(":")[1]
        data=load_data()
        t=find_task(tid, data)
        if t:
            t["status"]="completed"
            save_data(data)
            await q.edit_message_text(f"✅ Force approved {tid} — {t['title']}")

async def admin_delete_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /admin_delete t1")
        return
    tid=context.args[0]
    data=load_data()
    before=len(data["tasks"])
    data["tasks"]=[x for x in data["tasks"] if x["id"]!=tid]
    if len(data["tasks"])==before:
        await update.message.reply_text("Not found")
    else:
        save_data(data)
        await update.message.reply_text(f"🗑️ Deleted {tid} (admin)")

async def admin_approve_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /admin_approve t1")
        return
    tid=context.args[0]
    data=load_data()
    t=find_task(tid, data)
    if not t:
        await update.message.reply_text("Not found")
        return
    t["status"]="completed"
    save_data(data)
    await update.message.reply_text(f"✅ Force approved {tid}")

# ---------- Browse tasks ----------
async def tasks_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /tasks  or /tasks Coding
    cat = "All"
    if context.args:
        arg = " ".join(context.args).strip()
        # match case-insensitive
        for c in CATEGORIES:
            if c.lower()==arg.lower():
                cat=c
                break
        if cat=="All" and arg.lower()!="all":
            await update.message.reply_text(f"Category `{arg}` nahi mila. Categories: {', '.join(CATEGORIES)}", parse_mode="Markdown")
            return
    await send_tasks_page(update, cat, page=0, is_callback=False)

async def browse_via_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ReplyKeyboard button
    await update.message.reply_text("🏷️ *Category chuno:*", parse_mode="Markdown", reply_markup=categories_keyboard("browse"))

async def send_tasks_page(update_or_query, category, page=0, is_callback=True):
    data=load_data()
    tasks=data["tasks"]
    if category!="All":
        tasks=[t for t in tasks if t["category"]==category]
    tasks=sorted(tasks, key=lambda x: x["createdAt"], reverse=True)
    per_page=5
    total_pages=(len(tasks)+per_page-1)//per_page
    if total_pages==0:
        txt=f"🔍 *{category}* me koi task nahi mila.\nPost karo: /post"
        if is_callback:
            await update_or_query.edit_message_text(txt, parse_mode="Markdown")
        else:
            await update_or_query.message.reply_text(txt, parse_mode="Markdown")
        return
    page=max(0, min(page, total_pages-1))
    chunk=tasks[page*per_page:(page+1)*per_page]

    txt=f"🌍 *Global Tasks — {category}*  (Page {page+1}/{total_pages})  Total: {len(tasks)}\n\n"
    for i,t in enumerate(chunk, start=page*per_page+1):
        txt+=format_task_short(t, i)+"\n\n"

    # inline buttons for each task
    rows=[]
    for t in chunk:
        rows.append([InlineKeyboardButton(f"👁️ {t['id']} — {t['title'][:28]}", callback_data=f"view:{t['id']}")])
    nav=[]
    if page>0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"page:{category}:{page-1}"))
    if page<total_pages-1:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"page:{category}:{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("🏷️ Change Category", callback_data="change_cat")])
    kb=InlineKeyboardMarkup(rows)
    if is_callback:
        try:
            await update_or_query.edit_message_text(txt, parse_mode="Markdown", reply_markup=kb)
        except:
            await update_or_query.message.reply_text(txt, parse_mode="Markdown", reply_markup=kb)
    else:
        await update_or_query.message.reply_text(txt, parse_mode="Markdown", reply_markup=kb)

# ---------- View single task ----------
async def view_task_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query=update.callback_query
    await query.answer()
    data_str=query.data  # view:t1  or page:All:1 etc
    if data_str.startswith("page:"):
        _, cat, pg = data_str.split(":")
        await send_tasks_page(query, cat, int(pg), is_callback=True)
        return
    if data_str=="change_cat":
        await query.edit_message_text("🏷️ Category chuno:", reply_markup=categories_keyboard("browse"))
        return
    if data_str.startswith("browse:"):
        cat=data_str.split(":",1)[1]
        await send_tasks_page(query, cat, 0, is_callback=True)
        return
    if data_str.startswith("cat:"):
        # for posting flow - handled elsewhere
        return
    if not data_str.startswith("view:"):
        return
    tid=data_str.split(":",1)[1]
    data=load_data()
    t=find_task(tid, data)
    if not t:
        await query.edit_message_text("❌ Task not found.")
        return
    txt=task_detail_text(t)
    # build action buttons based on status and user
    tg_user=get_user_telegram(query.from_user)
    is_owner = t["postedBy"]["id"]==tg_user["id"]
    is_claimer = t.get("claimedBy") and t["claimedBy"]["id"]==tg_user["id"]
    rows=[]
    if t["status"]=="open" and not is_owner:
        rows.append([InlineKeyboardButton("🤝 Claim & Start", callback_data=f"claim:{tid}")])
    elif t["status"]=="open" and is_owner:
        rows.append([InlineKeyboardButton("🗑️ Delete Task", callback_data=f"delete:{tid}")])
    elif t["status"]=="claimed" and is_claimer:
        rows.append([InlineKeyboardButton("📸 Submit Proof (Screenshot)", callback_data=f"submit:{tid}")])
        rows.append([InlineKeyboardButton("🚪 Abandon Task", callback_data=f"abandon:{tid}")])
    elif t["status"]=="submitted" and is_owner:
        rows.append([InlineKeyboardButton(f"✅ Approve & Pay ₹{t['reward']}", callback_data=f"approve:{tid}"), InlineKeyboardButton("❌ Reject", callback_data=f"reject:{tid}")])
    elif t["status"]=="submitted":
        rows.append([InlineKeyboardButton("⏳ Under Review", callback_data="noop")])
    elif t["status"]=="completed":
        rows.append([InlineKeyboardButton("✅ Completed", callback_data="noop")])
    else:
        if t["status"]=="claimed":
            rows.append([InlineKeyboardButton(f"Claimed by {t['claimedBy']['name']}", callback_data="noop")])

    rows.append([InlineKeyboardButton("⬅️ Back to List", callback_data="back_list")])
    # handle long text: if >4000 split
    kb=InlineKeyboardMarkup(rows)
    try:
        # if proof has image url/base64, we already show text; for tg file_id we show later
        if t.get('proof') and t['proof'].get('screenshot','').startswith('AgAC'):  # file_id
            await query.message.reply_photo(photo=t['proof']['screenshot'], caption=txt[:1024], parse_mode="Markdown", reply_markup=kb)
            await query.delete_message()
        else:
            await query.edit_message_text(txt, parse_mode="Markdown", reply_markup=kb)
    except Exception as e:
        # fallback without markdown
        log.error(e)
        await query.message.reply_text(txt, reply_markup=kb)

async def back_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    await q.answer()
    await send_tasks_page(q, "All", 0, True)

# ---------- Claim / Abandon / Verify ----------
async def claim_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    await q.answer()
    tid=q.data.split(":",1)[1]
    data=load_data()
    t=find_task(tid, data)
    if not t:
        await q.edit_message_text("❌ Not found")
        return
    if t["status"]!="open":
        await q.answer("Already claimed/completed", show_alert=True)
        return
    tg_user=get_user_telegram(q.from_user)
    if tg_user["id"]==t["postedBy"]["id"]:
        await q.answer("Apna hi task claim nahi kar sakte!", show_alert=True)
        return
    t["status"]="claimed"
    t["claimedBy"]={"id":tg_user["id"], "name":tg_user["name"], "avatar":tg_user["avatar"]}
    save_data(data)
    await q.edit_message_text(
        f"🎉 *Claimed!* — `{t['title']}`\n\n"
        f"📋 *Guide follow karo:*\n" + "\n".join(f"{i}. {s}" for i,s in enumerate(t['guide'],1)) +
        f"\n\n📸 Kaam complete karke *Screenshot bhejo* → niche button dabao:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📸 Submit Proof", callback_data=f"submit:{tid}")],[InlineKeyboardButton("👁️ View Task", callback_data=f"view:{tid}")]])
    )

async def abandon_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    await q.answer()
    tid=q.data.split(":",1)[1]
    data=load_data()
    t=find_task(tid, data)
    if t:
        t["status"]="open"
        t["claimedBy"]=None
        t["proof"]=None
        save_data(data)
        await q.edit_message_text("🚪 Task abandoned — ab open hai, koi aur claim kar sakta hai.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🌍 Browse", callback_data="back_list")]]))

async def delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    await q.answer()
    tid=q.data.split(":",1)[1]
    data=load_data()
    tg_user=get_user_telegram(q.from_user)
    t=find_task(tid, data)
    if t and t["postedBy"]["id"]==tg_user["id"]:
        data["tasks"]=[x for x in data["tasks"] if x["id"]!=tid]
        save_data(data)
        await q.edit_message_text("🗑️ Task deleted.")
    else:
        await q.answer("Not authorized", show_alert=True)

async def verify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    await q.answer()
    action, tid = q.data.split(":")
    data=load_data()
    t=find_task(tid, data)
    if not t:
        await q.edit_message_text("Not found")
        return
    if action=="approve":
        t["status"]="completed"
        save_data(data)
        await q.edit_message_text(f"✅ *Approved & Paid!* ₹{t['reward']} worker ko de diya gaya.\nTask: {t['title']}", parse_mode="Markdown")
        # notify worker if possible
        try:
            if t.get("claimedBy") and t["claimedBy"].get("tg_id"):
                await context.bot.send_message(chat_id=t["claimedBy"]["tg_id"], text=f"🎉 Tumhara task *{t['title']}* approve ho gaya! ₹{t['reward']} earned!\n🆔 {tid}", parse_mode="Markdown")
        except: pass
    elif action=="reject":
        t["status"]="claimed"
        t["proof"]=None
        save_data(data)
        await q.edit_message_text(f"❌ Rejected — worker ko wapas bhej diya. Worker guide follow karke dobara submit karega.\n🆔 {tid}")

# ---------- My Tasks ----------
async def mytasks_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data=load_data()
    tg_user=get_user_telegram(update.effective_user)
    posted=[t for t in data["tasks"] if t["postedBy"]["id"]==tg_user["id"]]
    claimed=[t for t in data["tasks"] if t.get("claimedBy") and t["claimedBy"]["id"]==tg_user["id"]]
    submitted=[t for t in data["tasks"] if t["status"]=="submitted" and (t["postedBy"]["id"]==tg_user["id"] or (t.get("claimedBy") and t["claimedBy"]["id"]==tg_user["id"]))]
    txt=f"📋 *My Tasks — {tg_user['name']}*\n\n"
    txt+=f"📌 *Posted ({len(posted)}):*\n"
    if posted:
        for t in posted[:5]:
            txt+=f"• {t['id']} — {t['title'][:40]} [{t['status']}]\n"
    else: txt+="— koi posted task nahi\n"
    txt+=f"\n🤝 *Claimed ({len(claimed)}):*\n"
    if claimed:
        for t in claimed[:5]:
            txt+=f"• {t['id']} — {t['title'][:40]} [{t['status']}]\n"
    else: txt+="— koi claimed task nahi\n"
    txt+=f"\n🔵 *Review me ({len(submitted)}):*\n"
    if submitted:
        for t in submitted:
            txt+=f"• {t['id']} — {t['title'][:40]}\n"
    # buttons
    rows=[]
    for t in posted[:3]:
        rows.append([InlineKeyboardButton(f"📌 {t['id']}", callback_data=f"view:{t['id']}")])
    for t in claimed[:3]:
        rows.append([InlineKeyboardButton(f"🤝 {t['id']}", callback_data=f"view:{t['id']}")])
    if not rows:
        rows=[[InlineKeyboardButton("🌍 Browse Tasks", callback_data="back_list")]]
    await update.message.reply_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(rows))

# ========== POST TASK CONVERSATION ==========
async def post_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_post_draft[update.effective_user.id] = {}
    await update.message.reply_text(
        "➕ *Post New Task — Step 1/6*\n\n"
        "✍️ *Task Title bhejo:*\n"
        "Example: `Logo Design for Coffee Shop`\n\n"
        "Type /cancel to stop.",
        parse_mode="Markdown"
    )
    return P_TITLE

async def p_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft=user_post_draft.get(update.effective_user.id, {})
    draft["title"]=update.message.text.strip()
    user_post_draft[update.effective_user.id]=draft
    await update.message.reply_text(
        "📝 *Step 2/6 — Description bhejo:*\n"
        "Detail me likho kya chahiye, kaise chahiye...\n"
        "Example: `Minimal logo, 2 concepts, blue/black, source file chahiye`",
        parse_mode="Markdown"
    )
    return P_DESC

async def p_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft=user_post_draft[update.effective_user.id]
    draft["description"]=update.message.text.strip()
    # ask category via inline
    await update.message.reply_text("🏷️ *Step 3/6 — Category chuno:*", parse_mode="Markdown", reply_markup=categories_keyboard("p_cat"))
    return P_CAT

async def p_cat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    await q.answer()
    if q.data=="cancel_cat":
        user_post_draft.pop(q.from_user.id, None)
        await q.edit_message_text("❌ Cancelled.")
        return ConversationHandler.END
    cat=q.data.split(":",1)[1]
    draft=user_post_draft.get(q.from_user.id, {})
    draft["category"]=cat
    user_post_draft[q.from_user.id]=draft
    await q.edit_message_text(f"✅ Category: *{cat}*\n\n💰 *Step 4/6 — Reward bhejo (₹):*\nExample: `500`  (min 50)", parse_mode="Markdown")
    return P_REWARD

# For message-based category fallback
async def p_cat_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt=update.message.text.strip()
    if txt in CATEGORIES:
        draft=user_post_draft.get(update.effective_user.id, {})
        draft["category"]=txt
        await update.message.reply_text(f"✅ Category: {txt}\n\n💰 *Step 4/6 — Reward bhejo (₹):*", parse_mode="Markdown")
        return P_REWARD
    else:
        await update.message.reply_text(f"Category inme se chuno: {', '.join(CATEGORIES)}", reply_markup=categories_keyboard("p_cat"))
        return P_CAT

async def p_reward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        val=int(update.message.text.strip().replace("₹","").replace(",",""))
        if val<50: raise ValueError
    except:
        await update.message.reply_text("❌ Valid amount bhejo, min ₹50. Example: 500")
        return P_REWARD
    draft=user_post_draft[update.effective_user.id]
    draft["reward"]=val
    await update.message.reply_text(
        "⭐ *Step 5/6 — Difficulty chuno:*\nReply: `Easy` / `Medium` / `Hard`",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([["Easy","Medium","Hard"]], one_time_keyboard=True, resize_keyboard=True)
    )
    return P_DIFF

async def p_diff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt=update.message.text.strip().capitalize()
    if txt not in DIFFICULTIES:
        await update.message.reply_text("Easy / Medium / Hard me se chuno")
        return P_DIFF
    draft=user_post_draft[update.effective_user.id]
    draft["difficulty"]=txt
    await update.message.reply_text(
        "📋 *Step 6/6 — Guide bhejo (har line ek step):*\n"
        "Example:\n"
        "`Brief padho\nReference dekho\nDesign banao\nExport + screenshot lo`\n\n"
        "Har line ek step ban jayegi. Kam se kam 2 steps likho.",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([["/cancel"]], resize_keyboard=True)
    )
    return P_GUIDE

async def p_guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines=[l.strip() for l in update.message.text.strip().split("\n") if l.strip()]
    if len(lines)<2:
        await update.message.reply_text("Kam se kam 2 steps likho, har line ek step. Dobara bhejo.")
        return P_GUIDE
    draft=user_post_draft[update.effective_user.id]
    draft["guide"]=lines
    await update.message.reply_text(
        "🏷️ *Tags bhejo (comma se):*\n"
        "Example: `logo, figma, branding`\n"
        "Ya `skip` likho agar nahi chahiye.",
        parse_mode="Markdown"
    )
    return P_TAGS

async def p_tags(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt=update.message.text.strip()
    draft=user_post_draft[update.effective_user.id]
    if txt.lower()=="skip":
        draft["tags"]=[]
    else:
        draft["tags"]=[t.strip() for t in txt.split(",") if t.strip()]
    # confirm
    preview = (
        f"👀 *Preview:*\n\n"
        f"*{draft['title']}*\n"
        f"🏷️ {draft['category']} • ⭐ {draft.get('difficulty','Medium')} • 💰 ₹{draft['reward']}\n"
        f"📝 {draft['description'][:120]}...\n"
        f"📋 Guide ({len(draft['guide'])} steps):\n" + "\n".join(f"{i}. {s}" for i,s in enumerate(draft['guide'],1)) + "\n"
        f"🏷️ Tags: {', '.join(draft['tags']) if draft['tags'] else '—'}\n\n"
        f"Publish karu?"
    )
    await update.message.reply_text(preview, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Publish Globally", callback_data="p_publish"), InlineKeyboardButton("❌ Cancel", callback_data="p_cancel")]]))
    return P_CONFIRM

async def p_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    await q.answer()
    if q.data=="p_cancel":
        user_post_draft.pop(q.from_user.id, None)
        await q.edit_message_text("❌ Cancelled.")
        await q.message.reply_text("Menu:", reply_markup=main_keyboard())
        return ConversationHandler.END
    # publish
    draft=user_post_draft.pop(q.from_user.id, None)
    if not draft:
        await q.edit_message_text("Session expired, dobara /post karo")
        return ConversationHandler.END
    data=load_data()
    tg_user=get_user_telegram(q.from_user)
    new_task={
        "id": "t"+uuid.uuid4().hex[:6],
        "title": draft["title"],
        "description": draft["description"],
        "category": draft["category"],
        "reward": int(draft["reward"]),
        "deadline": (datetime.now()+timedelta(days=3)).isoformat(),
        "guide": draft["guide"],
        "tags": draft["tags"],
        "status": "open",
        "postedBy": {"id": tg_user["id"], "name": tg_user["name"], "avatar": tg_user["avatar"], "tg_id": tg_user["tg_id"]},
        "claimedBy": None,
        "proof": None,
        "createdAt": datetime.now().isoformat(),
        "difficulty": draft.get("difficulty","Medium")
    }
    data["tasks"].insert(0, new_task)
    save_data(data)
    await q.edit_message_text(f"🚀 *Published!* — `{new_task['id']}`\n*{new_task['title']}* — ₹{new_task['reward']}\nAb global workers dekhenge. /tasks se check karo.", parse_mode="Markdown")
    await q.message.reply_text("Menu:", reply_markup=main_keyboard())
    # notify channel? maybe
    return ConversationHandler.END

async def cancel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_post_draft.pop(update.effective_user.id, None)
    await update.message.reply_text("❌ Cancelled.", reply_markup=main_keyboard())
    return ConversationHandler.END

# ========== SUBMIT PROOF CONVERSATION ==========
async def submit_entry_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    await q.answer()
    tid=q.data.split(":",1)[1]
    data=load_data()
    t=find_task(tid, data)
    tg_user=get_user_telegram(q.from_user)
    if not t or t["status"]!="claimed" or not t.get("claimedBy") or t["claimedBy"]["id"]!=tg_user["id"]:
        await q.answer("Not authorized / not in claimed state", show_alert=True)
        return ConversationHandler.END
    user_submit_draft[q.from_user.id]={"task_id": tid}
    await q.message.reply_text(
        f"📸 *Submit Proof — {t['title']}*\n\n"
        "1️⃣ Pehle *screenshot/photo bhejo* (kaam ka proof)\n"
        "2️⃣ Phir ek note bhejo kya kiya\n\n"
        "Photo bhejo 👇  (/cancel to stop)",
        parse_mode="Markdown"
    )
    return S_PHOTO

async def s_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # expect photo
    if not update.message.photo:
        await update.message.reply_text("❌ Photo bhejo — screenshot of your work. Ya /cancel")
        return S_PHOTO
    # highest res photo
    file_id=update.message.photo[-1].file_id
    draft=user_submit_draft.get(update.effective_user.id, {})
    draft["photo"]=file_id
    user_submit_draft[update.effective_user.id]=draft
    await update.message.reply_text(
        "✅ Photo mil gaya!\n\n✍️ Ab ek *short note* bhejo — kya kiya, kaise kiya? (2-3 lines)\nExample: `Logo ke 2 variations banaye, PNG + AI ready hai`",
        parse_mode="Markdown"
    )
    return S_NOTE

# also allow document
async def s_photo_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # if document image
    if update.message.document:
        file_id=update.message.document.file_id
        draft=user_submit_draft.get(update.effective_user.id, {})
        draft["photo"]=file_id
        user_submit_draft[update.effective_user.id]=draft
        await update.message.reply_text("✅ File mil gaya! Ab note bhejo 👇", parse_mode="Markdown")
        return S_NOTE
    return S_PHOTO

async def s_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    note=update.message.text.strip()
    draft=user_submit_draft.pop(update.effective_user.id, None)
    if not draft:
        await update.message.reply_text("Session expired, dobara submit karo")
        return ConversationHandler.END
    tid=draft["task_id"]
    photo=draft["photo"]
    data=load_data()
    t=find_task(tid, data)
    if not t:
        await update.message.reply_text("Task not found")
        return ConversationHandler.END
    t["status"]="submitted"
    t["proof"]={"screenshot": photo, "note": note, "submittedAt": datetime.now().isoformat()}
    # store tg_id for notification
    save_data(data)
    await update.message.reply_text(
        f"✅ *Proof submitted!* — `{tid}`\nPoster review karega aur approve karte hi ₹{t['reward']} milega.\n/task {tid} se status dekho.",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )
    # notify poster
    try:
        poster_tg = t["postedBy"].get("tg_id")
        if poster_tg:
            await context.bot.send_message(chat_id=poster_tg, text=f"🔔 *New Submission!* — {t['title']} (₹{t['reward']})\nWorker: {update.effective_user.full_name}\nReview ke liye /mytasks ya task dekho: /task {tid}", parse_mode="Markdown")
            await context.bot.send_photo(chat_id=poster_tg, photo=photo, caption=f"📝 Note: {note}\n🆔 {tid}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Approve", callback_data=f"approve:{tid}"), InlineKeyboardButton("❌ Reject", callback_data=f"reject:{tid}")],[InlineKeyboardButton("👁️ View", callback_data=f"view:{tid}")]]))
    except Exception as e:
        log.error(f"notify fail {e}")
    return ConversationHandler.END

async def cancel_submit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_submit_draft.pop(update.effective_user.id, None)
    await update.message.reply_text("❌ Cancelled.", reply_markup=main_keyboard())
    return ConversationHandler.END

# ---------- Generic text handler for reply keyboard ----------
async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt=update.message.text.strip()
    if txt=="🌍 Browse Tasks":
        await browse_via_button(update, context)
    elif txt=="➕ Post Task":
        # trigger post conversation manually
        await update.message.reply_text("➕ /post command se naya task post karo — ab start karte hain...")
        # we can't directly enter conversation, so instruct to use /post
        # but we can call post_entry
        return await post_entry(update, context)
    elif txt=="📋 My Tasks":
        await mytasks_cmd(update, context)
    elif txt=="🏆 Leaderboard":
        await leaderboard_cmd(update, context)
    elif txt=="ℹ️ Help":
        await help_cmd(update, context)
    else:
        # maybe task id search?
        if txt.startswith("/task"):
            parts=txt.split()
            if len(parts)>1:
                tid=parts[1].strip()
                data=load_data()
                t=find_task(tid, data)
                if t:
                    await update.message.reply_text(task_detail_text(t), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👁️ View + Actions", callback_data=f"view:{tid}")]]))
                else:
                    await update.message.reply_text("Task not found")
            return

# ---------- task direct command ----------
async def task_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /task t1  — task id bhejo\nExample: /task t1")
        return
    tid=context.args[0]
    data=load_data()
    t=find_task(tid, data)
    if not t:
        await update.message.reply_text("❌ Task not found")
        return
    await update.message.reply_text(task_detail_text(t), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👁️ Open Actions", callback_data=f"view:{tid}")]]))

# ========== MAIN ==========
def main():
    if BOT_TOKEN=="YOUR_TELEGRAM_BOT_TOKEN_HERE" or not BOT_TOKEN or len(BOT_TOKEN)<20:
        print("="*60)
        print("⚠️  BOT_TOKEN nahi mila!")
        print(" telegram_bot.py ke upar BOT_TOKEN variable me apna token paste karo")
        print(" Ya env set karo:  export BOT_TOKEN='1234:ABC...'")
        print(" Token @BotFather se milega -> /newbot")
        print("="*60)
        # still try to run? exit
        log.warning("Starting without valid token — bot will fail to poll. Please set BOT_TOKEN.")
    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("tasks", tasks_cmd))
    app.add_handler(CommandHandler("mytasks", mytasks_cmd))
    app.add_handler(CommandHandler("leaderboard", leaderboard_cmd))
    app.add_handler(CommandHandler("task", task_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("admin_stats", admin_cmd))
    app.add_handler(CommandHandler("admin_tasks", admin_tasks_callback))
    app.add_handler(CommandHandler("admin_delete", admin_delete_cmd))
    app.add_handler(CommandHandler("admin_approve", admin_approve_cmd))

    # Post conversation
    post_conv = ConversationHandler(
        entry_points=[CommandHandler("post", post_entry), MessageHandler(filters.Regex("^➕ Post Task$"), post_entry)],
        states={
            P_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, p_title)],
            P_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, p_desc)],
            P_CAT: [
                CallbackQueryHandler(p_cat_callback, pattern=r"^p_cat:"),
                CallbackQueryHandler(p_cat_callback, pattern=r"^cancel_cat$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, p_cat_msg)
            ],
            P_REWARD: [MessageHandler(filters.TEXT & ~filters.COMMAND, p_reward)],
            P_DIFF: [MessageHandler(filters.TEXT & ~filters.COMMAND, p_diff)],
            P_GUIDE: [MessageHandler(filters.TEXT & ~filters.COMMAND, p_guide)],
            P_TAGS: [MessageHandler(filters.TEXT & ~filters.COMMAND, p_tags)],
            P_CONFIRM: [CallbackQueryHandler(p_confirm_callback, pattern=r"^p_(publish|cancel)$")],
        },
        fallbacks=[CommandHandler("cancel", cancel_post), MessageHandler(filters.Regex("^/cancel"), cancel_post)],
        per_user=True
    )
    app.add_handler(post_conv)

    # Submit proof conversation (entry via callback)
    submit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(submit_entry_callback, pattern=r"^submit:")],
        states={
            S_PHOTO: [MessageHandler(filters.PHOTO, s_photo), MessageHandler(filters.Document.IMAGE, s_photo_doc)],
            S_NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, s_note)],
        },
        fallbacks=[CommandHandler("cancel", cancel_submit)],
        per_user=True,
        per_message=False
    )
    app.add_handler(submit_conv)

    # Admin callbacks
    app.add_handler(CallbackQueryHandler(admin_callback_handler, pattern=r"^admin:"))
    app.add_handler(CallbackQueryHandler(admin_callback_handler, pattern=r"^admin_(del|approve):"))

    # Callbacks for browsing/viewing
    app.add_handler(CallbackQueryHandler(view_task_callback, pattern=r"^(view:|page:|change_cat$|browse:)"))
    app.add_handler(CallbackQueryHandler(claim_callback, pattern=r"^claim:"))
    app.add_handler(CallbackQueryHandler(abandon_callback, pattern=r"^abandon:"))
    app.add_handler(CallbackQueryHandler(delete_callback, pattern=r"^delete:"))
    app.add_handler(CallbackQueryHandler(verify_callback, pattern=r"^(approve|reject):"))
    app.add_handler(CallbackQueryHandler(back_list_callback, pattern=r"^back_list$"))
    app.add_handler(CallbackQueryHandler(lambda u,c: u.callback_query.answer(), pattern=r"^noop$"))
    # catch-all for category browse when not in conversation
    app.add_handler(CallbackQueryHandler(lambda u,c: send_tasks_page(u.callback_query, u.callback_query.data.split(":")[1],0,True), pattern=r"^browse:"))

    # Also handle browse category inline outside conv
    async def browse_cat_handler(update, context):
        q=update.callback_query
        await q.answer()
        cat=q.data.split(":",1)[1]
        await send_tasks_page(q, cat, 0, True)
    # Already handled in view_task_callback for browse:, but keep

    # Text router for ReplyKeyboard
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    # also handle /cancel generally
    app.add_handler(CommandHandler("cancel", cancel_post))

    print(f"✅ TaskHub Bot starting... Token: {BOT_TOKEN[:10]}...")
    print("📡 Polling shuru — Ctrl+C se band karo")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__=="__main__":
    main()
