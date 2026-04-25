import os
import asyncio
import logging
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiohttp import web
import firebase_admin
from firebase_admin import credentials, firestore

# --- Configuration & Logging ---
logging.basicConfig(level=logging.INFO)
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))

# --- Firebase Setup ---
try:
    # পরিবেশ ভেরিয়েবল থেকে JSON স্ট্রিংটি লোড করা হচ্ছে
    service_account_info = json.loads(os.getenv('FIREBASE_SERVICE_ACCOUNT'))
    cred = credentials.Certificate(service_account_info)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ Firebase Connected Successfully!")
except Exception as e:
    print(f"❌ Firebase Connection Error: {e}")
    exit(1)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- FSM States (প্রসেস কন্ট্রোল করার জন্য) ---
class AdminStates(StatesGroup):
    set_welcome = State()
    set_help = State()
    set_support = State()
    set_referral = State()
    add_cat_name = State()
    add_prod_name = State()
    add_prod_price = State()
    add_prod_cat_id = State()
    add_prod_content = State()
    broadcast = State()
    del_cat_id = State()
    del_prod_id = State()

class UserStates(StatesGroup):
    submitting_trx = State()

# --- Keyboards ---

def user_main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛒 Products"), KeyboardButton(text="📦 My Orders")],
        [KeyboardButton(text="🎁 Referral"), KeyboardButton(text="💬 Support")],
        [KeyboardButton(text="ℹ️ Help")]
    ], resize_keyboard=True)

def admin_main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Add Category"), KeyboardButton(text="➕ Add Product")],
        [KeyboardButton(text="📂 View Categories"), KeyboardButton(text="🗑 Delete Category")],
        [KeyboardButton(text="🗑 Delete Product"), KeyboardButton(text="📝 Edit Texts")],
        [KeyboardButton(text="📢 Broadcast"), KeyboardButton(text="📊 Stats")],
        [KeyboardButton(text="🔙 Back to User Menu")]
    ], resize_keyboard=True)

def cancel_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Cancel/Back")]], resize_keyboard=True)

# --- Helper Functions ---

async def initialize_db():
    """বট চালু হওয়ার সময় ডাটাবেস চেক করবে"""
    print("⚙️ Initializing Database...")
    settings_ref = db.collection('settings')
    defaults = {
        'welcome': "👋 স্বাগতম! আমাদের ডিজিটাল শপে আপনাকে স্বাগতম।\nনিচের মেনু থেকে অপশন সিলেক্ট করুন:",
        'help': "ℹ️ Help: Select product and pay via Bkash/Nagad.",
        'support': "💬 Support: Contact @AdminUsername",
        'referral': "🎁 Referral: Invite friends using your link!"
    }
    for key, text in defaults.items():
        if not settings_ref.document(key).get().exists:
            settings_ref.document(key).set({'text': text})
    print("✅ Database Ready!")

async def get_setting(key):
    doc = db.collection('settings').document(key).get()
    return doc.to_dict()['text'] if doc.exists else ""

# --- Handlers: User Side ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_ref = db.collection('users').document(str(message.from_user.id))
    user_ref.set({'username': message.from_user.username, 'id': message.from_user.id}, merge=True)
    
    welcome_text = await get_setting('welcome')
    if message.from_user.id == ADMIN_ID:
        await message.answer("👑 Welcome Admin!", reply_markup=admin_main_menu())
    else:
        await message.answer(welcome_text, reply_markup=user_main_menu())

@dp.message(F.text == "🛒 Products")
async def show_categories(message: types.Message):
    cats_ref = db.collection('categories').stream()
    buttons = []
    found = False
    for doc in cats_ref:
        found = True
        buttons.append([InlineKeyboardButton(text=doc.to_dict()['name'], callback_data=f"cat_{doc.id}")])
    
    if not found:
        await message.answer("দুঃখিত, বর্তমানে কোনো ক্যাটাগরি নেই।")
        return
    await message.answer("ক্যাটেগরি সিলেক্ট করুন:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("cat_"))
async def show_products(callback_query: types.CallbackQuery):
    cat_id = callback_query.data.split("_")[1]
    prods_ref = db.collection('products').where("category_id", "==", cat_id).stream()
    buttons = []
    found = False
    for doc in prods_ref:
        found = True
        p = doc.to_dict()
        buttons.append([InlineKeyboardButton(text=f"{p['name']} - {p['price']}৳", callback_data=f"buy_{doc.id}")])
    
    if not found:
        await callback_query.answer("এই ক্যাটাগরিতে কোনো প্রোডাক্ট নেই!", show_alert=True)
    else:
        await callback_query.message.edit_text("প্রোডাক্ট সিলেক্ট করুন:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("buy_"))
async def buy_process(callback_query: types.CallbackQuery, state: FSMContext):
    prod_id = callback_query.data.split("_")[1]
    prod_doc = db.collection('products').document(prod_id).get()
    if not prod_doc.exists: return
    p = prod_doc.to_dict()
    await state.update_data(target_prod_id=prod_id, target_prod_name=p['name'], target_prod_price=p['price'])
    
    instr = (f"💳 **Payment Instruction**\n\nProduct: {p['name']}\nAmount: {p['price']}৳\n\n"
             f"Bkash/Nagad: `01XXXXXXXXX`\n\n"
             f"✅ পেমেন্ট করার পর আপনার **Transaction ID** লিখে এখানে পাঠান।")
    await callback_query.message.answer(instr, parse_mode="Markdown")
    await callback_query.answer()
    await state.set_state(UserStates.submitting_trx)

@dp.message(UserStates.submitting_trx)
async def handle_trx(message: types.Message, state: FSMContext):
    data = await state.get_data()
    trx_id = message.text
    order_data = {
        "user_id": message.from_user.id, "user_name": message.from_user.full_name,
        "product_id": data['target_prod_id'], "product_name": data['target_prod_name'],
        "price": data['target_prod_price'], "trx_id": trx_id, "status": "pending"
    }
    new_order = db.collection('orders').add(order_data)
    await message.answer("⏳ পেমেন্ট যাচাই হচ্ছে...")
    
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Approve", callback_data=f"app_{new_order[1].id}"),
         InlineKeyboardButton(text="❌ Reject", callback_data=f"rej_{new_order[1].id}")]
    ])
    await bot.send_message(ADMIN_ID, f"🆕 **New Order!**\n\n👤 User: {message.from_user.full_name}\n📦 Product: {data['target_prod_name']}\n💰 Price: {data['target_prod_price']}৳\n🧾 TRX ID: {trx_id}", reply_markup=admin_kb, parse_mode="Markdown")
    await state.clear()

@dp.message(F.text == "📦 My Orders")
async def my_orders(message: types.Message):
    orders_ref = db.collection('orders').where("user_id", "==", message.from_user.id).stream()
    text = "📦 **আপনার অর্ডারের তালিকা:**\n\n"
    found = False
    for doc in orders_ref:
        found = True
        o = doc.to_dict()
        emoji = "✅" if o['status']=='approved' else "⏳" if o['status']=='pending' else "❌"
        text += f"{emoji} {o['product_name']} - {o['status']}\n"
    await message.answer(text if found else "কোনো অর্ডার নেই।" , parse_mode="Markdown")

@dp.message(F.text == "🎁 Referral")
async def show_referral(message: types.Message):
    ref_link = f"https://t.me/YourBotUsername?start={message.from_user.id}"
    txt = await get_setting('referral')
    await message.answer(f"{txt}\n\n🔗 {ref_link}")

@dp.message(F.text == "💬 Support")
async def show_support(message: types.Message):
    await message.answer(await get_setting('support'))

@dp.message(F.text == "ℹ️ Help")
async def show_help(message: types.Message):
    await message.answer(await get_setting('help'))

# --- Handlers: Admin Side ---

@dp.callback_query(F.data.startswith("app_"))
async def admin_approve(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID: return
    order_id = callback_query.data.split("_")[1]
    order_ref = db.collection('orders').document(order_id)
    order = order_ref.get()
    if not order.exists: return
    order_data = order.to_dict()
    prod_doc = db.collection('products').document(order_data['product_id']).get()
    content = prod_doc.to_dict()['content']
    order_ref.update({"status": "approved"})
    await bot.send_message(order_data['user_id'], f"✅ **Payment Confirmed!**\n\n📦 Product: {order_data['product_name']}\n🔗 Content: `{content}`", parse_mode="Markdown")
    await callback_query.message.edit_text(f"✅ Order {order_id} Approved!")

@dp.callback_query(F.data.startswith("rej_"))
async def admin_reject(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID: return
    order_id = callback_query.data.split("_")[1]
    order_ref = db.collection('orders').document(order_id)
    order = order_ref.get()
    if not order.exists: return
    order_ref.update({"status": "rejected"})
    await bot.send_message(order['user_id'], "❌ আপনার পেমেন্টটি রিজেক্ট করা হয়েছে।")
    await callback_query.message.edit_text(f"❌ Order {order_id} Rejected!")

@dp.message(F.text == "➕ Add Category")
async def admin_add_cat_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("নতুন ক্যাটাগরির নাম লিখুন:", reply_markup=cancel_kb())
    await state.set_state(AdminStates.add_cat_name)

@dp.message(AdminStates.add_cat_name)
async def save_cat(message: types.Message, state: FSMContext):
    res = db.collection('categories').add({'name': message.text})
    await message.answer(f"✅ ক্যাটাগরি তৈরি হয়েছে!\n🆔 ID: {res[1].id}", reply_markup=admin_main_menu())
    await state.clear()

@dp.message(F.text == "📂 View Categories")
async def admin_view_cats(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    cats_ref = db.collection('categories').stream()
    msg = "📂 **Current Categories & IDs:**\n\n"
    found = False
    for doc in cats_ref:
        found = True
        msg += f"🔹 {doc.to_dict()['name']} ➔ `{doc.id}`\n"
    if not found: await message.answer("কোনো ক্যাটাগরি নেই।"); return
    await message.answer(msg, parse_mode="Markdown")

@dp.message(F.text == "🗑 Delete Category")
async def admin_del_cat_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    cats_ref = db.collection('categories').stream()
    buttons = []
    for doc in cats_ref:
        buttons.append([InlineKeyboardButton(text=f"❌ {doc.to_dict()['name']}", callback_data=f"delcat_{doc.id}")])
    if not buttons: await message.answer("কোনো ক্যাটাগরি নেই।"); return
    await message.answer("যে ক্যাটাগরি ডিলিট করতে চান সেটি সিলেক্ট করুন:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("delcat_"))
async def perform_del_cat(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID: return
    db.collection('categories').document(callback_query.data.split("_")[1]).delete()
    await callback_query.message.edit_text("✅ ক্যাটাগরি ডিলিট হয়েছে!")

@dp.message(F.text == "➕ Add Product")
async def admin_add_prod_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("প্রোডাক্টের নাম লিখুন:", reply_markup=cancel_kb())
    await state.set_state(AdminStates.add_prod_name)

@dp.message(AdminStates.add_prod_name)
async def proc_p_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("দাম লিখুন (শুধু সংখ্যা):")
    await state.set_state(AdminStates.add_prod_price)

@dp.message(AdminStates.add_prod_price)
async def proc_p_price(message: types.Message, state: FSMContext):
    await state.update_data(price=message.text)
    await message.answer("ক্যাটাগরির ID লিখুন (অথবা লিস্ট দেখতে 'List' লিখুন):")
    await state.set_state(AdminStates.add_prod_cat_id)

@dp.message(AdminStates.add_prod_cat_id)
async def proc_p_cat(message: types.Message, state: FSMContext):
    if message.text.lower() == 'list':
        cats_ref = db.collection('categories').stream()
        msg = "📂 **Current Categories & IDs:**\n\n"
        for doc in cats_ref:
            msg += f"🔹 {doc.to_dict()['name']} ➔ `{doc.id}`\n"
        await message.answer(msg, parse_mode="Markdown")
        await proc_p_cat(message, state)
        return
    await state.update_data(cat_id=message.text)
    await message.answer("ডেলিভারি কন্টেন্ট (লিঙ্ক বা টেক্সট) লিখুন:")
    await state.set_state(AdminStates.add_prod_content)

@dp.message(AdminStates.add_prod_content)
async def proc_p_content(message: types.Message, state: FSMContext):
    data = await state.get_data()
    res = db.collection('products').add({
        'name': data['name'], 'price': data['price'], 'category_id': data['cat_id'], 'content': message.text
    })
    await message.answer(f"✅ প্রোডাক্ট যোগ হয়েছে!\n🆔 ID: {res[1].id}", reply_markup=admin_main_menu())
    await state.clear()

@dp.message(F.text == "🗑 Delete Product")
async def admin_del_prod_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    prods_ref = db.collection('products').stream()
    buttons = []
    for doc in prods_ref:
        p = doc.to_dict()
        buttons.append([InlineKeyboardButton(text=f"❌ {p['name']}", callback_data=f"delprod_{doc.id}")])
    if not buttons: await message.answer("কোনো প্রোডাক্ট নেই।"); return
    await message.answer("যে প্রোডাক্ট ডিলিট করতে চান সেটি সিলেক্ট করুন:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("delprod_"))
async def perform_del_prod(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID: return
    db.collection('products').document(callback_query.data.split("_")[1]).delete()
    await callback_query.message.edit_text("✅ প্রোডাক্ট ডিলিট হয়েছে!")

@dp.message(F.text == "📝 Edit Texts")
async def admin_edit_menu(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Set Welcome", callback_data="edit_welcome")],
        [InlineKeyboardButton(text="Set Help", callback_data="edit_help")],
        [InlineKeyboardButton(text="Set Support", callback_data="edit_support")],
        [InlineKeyboardButton(text="Set Referral", callback_data="edit_referral")]
    ])
    await message.answer("কোনটি পরিবর্তন করবেন?", reply_markup=kb)

@dp.callback_query(F.data.startswith("edit_"))
async def admin_edit_start(callback_query: types.CallbackQuery, state: FSMContext):
    key = callback_query.data.split("_")[1]
    await callback_query.message.answer(f"নতুন {key} টেক্সটটি লিখুন:", reply_markup=cancel_kb())
    await state.update_data(edit_key=key)
    await state.set_state(AdminStates.set_welcome)

@dp.message(AdminStates.set_welcome)
async def save_edited_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    key = data.get('edit_key')
    if not key: return
    db.collection('settings').document(key).set({'text': message.text})
    await message.answer(f"✅ {key} আপডেট হয়েছে!", reply_markup=admin_main_menu())
    await state.clear()

@dp.message(F.text == "📢 Broadcast")
async def admin_broadcast_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("সব ইউজারকে যে মেসেজটি পাঠাতে চান সেটি লিখুন:", reply_markup=cancel_kb())
    await state.set_state(AdminStates.broadcast)

@dp.message(AdminStates.broadcast)
async def send_broadcast(message: types.Message, state: FSMContext):
    users_ref = db.collection('users').stream()
    count = 0
    for user in users_ref:
        try:
            await bot.send_message(user.id, message.text)
            count += 1
        except: pass
    await message.answer(f"✅ Broadcast Sent to {count} users!", reply_markup=admin_main_menu())
    await state.clear()

@dp.message(F.text == "📊 Stats")
async def admin_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    try:
        u_count = db.collection('users').count().get()[0].value
        o_count = db.collection('orders').count().get()[0].value
        await message.answer(f"📊 **Bot Statistics**\n\n👥 Total Users: {u_count}\n📦 Total Orders: {o_count}", parse_mode="Markdown", reply_markup=admin_main_menu())
    except Exception as e:
        await message.answer(f"❌ Error: {e}", reply_markup=admin_main_menu())

@dp.message(F.text == "🔙 Back to User Menu")
async def back_to_user(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Switching to User View...", reply_markup=user_main_menu())

# --- Render Web Server ---
async def start_web_server():
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="Bot is Alive!"))
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    await web.TCPSite(runner, '0.0.0.0', port).start()

async def main():
    await initialize_db()
    await start_web_server()
    print("🚀 Bot is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
