import os
import logging
import json
from datetime import datetime
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import PicklePersistence
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GOOGLE_SHEETS_CREDENTIALS = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
AUTHORIZED_USER_ID = int(os.getenv('AUTHORIZED_USER_ID'))

# Configure Gemini API
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

# Configure Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_CREDENTIALS, scope)
client = gspread.authorize(creds)

# Open the spreadsheet by ID
spreadsheet = client.open_by_key(SPREADSHEET_ID)
sheet = spreadsheet.sheet1  # Use the first sheet

# Store the spreadsheet URL for sharing
SPREADSHEET_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"

def is_authorized(user_id):
    """Check if the user is authorized to use the bot."""
    return str(user_id) == str(AUTHORIZED_USER_ID)

async def sheet_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Check authorization
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ Maaf, Anda tidak memiliki akses untuk menggunakan bot ini.")
        return
    
    user_name = update.effective_user.first_name
    
    # Create a message with the link
    message = (
        f"📊 *Link Google Sheet Keuangan Anda*\n\n"
        f"Halo {user_name}, berikut adalah link untuk melihat data keuangan Anda:\n\n"
        f"[Buka Google Sheet]({SPREADSHEET_URL})\n\n"
        "Anda dapat melihat semua transaksi dan mengunduh data dalam format Excel/CSV."
    )
    
    # Create button to open the link
    keyboard = [[InlineKeyboardButton("Buka Google Sheet", url=SPREADSHEET_URL)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        message, 
        parse_mode='Markdown',
        reply_markup=reply_markup,
        disable_web_page_preview=True
    )

async def delete_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    # Create keyboard with deletion options
    keyboard = [
        [InlineKeyboardButton("Hapus Transaksi Terakhir", callback_data="delete_last")],
        [InlineKeyboardButton("Hapus Transaksi Tertentu", callback_data="delete_specific")],
        [InlineKeyboardButton("Hapus Berdasarkan Tanggal", callback_data="delete_date")],
        [InlineKeyboardButton("Hapus Semua Data", callback_data="delete_all")],
        [InlineKeyboardButton("❌ Batal", callback_data="delete_cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🗑️ *Hapus Data Keuangan*\n\n"
        f"Halo {user_name}, pilih opsi penghapusan data:\n\n"
        "⚠️ *Perhatian:* Data yang dihapus tidak dapat dikembalikan!",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    
async def delete_transaction_messages(context: ContextTypes.DEFAULT_TYPE):
    """Delete transaction-related messages after a delay."""
    job_data = context.job.data
    chat_id = job_data['chat_id']
    user_id = job_data['user_id']
    
    # Get the user data
    user_data = context.application.user_data.get(user_id, {})
    
    # Check if message deletion is enabled
    if not user_data.get('delete_messages', True):
        return
    
    # Get the list of message IDs to delete
    messages_to_delete = user_data.get('messages_to_delete', [])
    
    if not messages_to_delete:
        return
    
    # Delete each message
    for message_id in messages_to_delete:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception as e:
            logger.error(f"Error deleting message {message_id}: {e}")
    
    # Clear the list of messages to delete
    context.application.user_data[user_id]['messages_to_delete'] = []

async def toggle_delete_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Check authorization
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ Maaf, Anda tidak memiliki akses untuk menggunakan bot ini.")
        return
    
    # Toggle the setting
    if 'delete_messages' not in context.user_data:
        context.user_data['delete_messages'] = True
    else:
        context.user_data['delete_messages'] = not context.user_data['delete_messages']
    
    # Inform the user of the current setting
    status = "AKTIF" if context.user_data['delete_messages'] else "NONAKTIF"
    
    await update.message.reply_text(
        f"🗑️ Penghapusan pesan otomatis: {status}\n\n"
        f"{'Pesan akan dihapus otomatis setelah transaksi dicatat.' if context.user_data['delete_messages'] else 'Pesan tidak akan dihapus otomatis.'}"
    )

async def delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    
    # Check authorization
    if not is_authorized(user_id):
        await query.answer("Anda tidak memiliki akses untuk menggunakan bot ini.", show_alert=True)
        return
    
    await query.answer()
    action = query.data.split("_")[1]
    
    
    if action == "cancel":
        await query.edit_message_text("❌ Penghapusan data dibatalkan.")
        return
    
    elif action == "last":
        # Delete the last transaction for this user
        all_records = sheet.get_all_records()
        user_records = [record for record in all_records if str(record.get('User ID')) == str(user_id)]
        
        if not user_records:
            await query.edit_message_text("❌ Tidak ada transaksi untuk dihapus.")
            return
        
        # Find the last transaction's row
        last_record = user_records[-1]
        all_values = sheet.get_all_values()
        header = all_values[0]  # First row is header
        
        # Find the row index of the last transaction
        row_index = None
        for i, row in enumerate(all_values[1:], start=2):  # Start from 2 because row 1 is header
            record = dict(zip(header, row))
            if (str(record.get('User ID')) == str(user_id) and 
                record.get('Timestamp') == last_record.get('Timestamp')):
                row_index = i
                break
        
        if row_index:
            # Delete the row
            sheet.delete_rows(row_index)
            
            # Show confirmation with details of deleted transaction
            amount = float(last_record.get('Amount', 0))
            transaction_type = "Pemasukan" if amount > 0 else "Pengeluaran"
            
            await query.edit_message_text(
                "✅ Transaksi terakhir berhasil dihapus!\n\n"
                f"Jenis: {transaction_type}\n"
                f"Jumlah: Rp {abs(amount):,.0f}\n"
                f"Kategori: {last_record.get('Category', 'Lainnya')}\n"
                f"Deskripsi: {last_record.get('Description', '')}\n"
                f"Tanggal: {last_record.get('Date', '')}"
            )
        else:
            await query.edit_message_text("❌ Tidak dapat menemukan transaksi terakhir.")
    
    elif action == "specific":
        # Show recent transactions for selection
        all_records = sheet.get_all_records()
        user_records = [record for record in all_records if str(record.get('User ID')) == str(user_id)]
        
        if not user_records:
            await query.edit_message_text("❌ Tidak ada transaksi untuk dihapus.")
            return
        
        # Get the last 5 transactions (or fewer if there aren't 5)
        recent_transactions = user_records[-5:] if len(user_records) >= 5 else user_records
        
        # Create buttons for each transaction
        keyboard = []
        for i, transaction in enumerate(recent_transactions):
            amount = float(transaction.get('Amount', 0))
            transaction_type = "➕" if amount > 0 else "➖"
            date = transaction.get('Date', '')
            description = transaction.get('Description', '')
            # Truncate description if too long
            if len(description) > 20:
                description = description[:17] + "..."
            
            # Create a button with transaction info
            label = f"{date}: {transaction_type} Rp{abs(amount):,.0f} - {description}"
            # Truncate label if too long
            if len(label) > 64:  # Telegram button label limit
                label = label[:61] + "..."
            
            keyboard.append([InlineKeyboardButton(label, callback_data=f"del_specific_{i}")])
        
        # Add a cancel button
        keyboard.append([InlineKeyboardButton("❌ Batal", callback_data="delete_cancel")])
        
        # Store the transactions in context for later reference
        context.user_data['recent_transactions'] = recent_transactions
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "Pilih transaksi yang ingin dihapus:",
            reply_markup=reply_markup
        )
    
    elif action == "date":
        # Ask for date range
        context.user_data['delete_state'] = 'awaiting_start_date'
        
        await query.edit_message_text(
            "📅 *Hapus Berdasarkan Tanggal*\n\n"
            "Masukkan tanggal awal (format: YYYY-MM-DD):\n"
            "Contoh: 2023-05-01",
            parse_mode='Markdown'
        )
    
    elif action == "all":
        # Ask for confirmation before deleting all
        keyboard = [
            [InlineKeyboardButton("✅ Ya, Hapus Semua", callback_data="confirm_delete_all")],
            [InlineKeyboardButton("❌ Tidak, Batalkan", callback_data="delete_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⚠️ *PERINGATAN*\n\n"
            "Anda akan menghapus SEMUA data keuangan Anda.\n"
            "Tindakan ini TIDAK DAPAT DIBATALKAN.\n\n"
            "Apakah Anda yakin ingin melanjutkan?",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
async def process_multiple_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE, transactions):
    """Process multiple transactions and ask for confirmation."""
    user_id = update.effective_user.id
    
    # Create a summary of the transactions
    confirmation_message = f"📝 *{len(transactions)} Transaksi Terdeteksi*\n\n"
    
    # Make a deep copy of the transactions to avoid reference issues
    processed_transactions = []
    
    for i, transaction in enumerate(transactions, 1):
        # Create a new dictionary for each transaction to avoid reference issues
        processed_transaction = {
            'amount': float(transaction.get('amount', 0)),  # Ensure amount is a float
            'category': str(transaction.get('category', 'Lainnya')),  # Ensure category is a string
            'description': str(transaction.get('description', f'Transaksi {i}')),  # Ensure description is a string
            'date': str(transaction.get('date', datetime.now().strftime("%Y-%m-%d")))  # Ensure date is a string
        }
        
        # Add to processed transactions
        processed_transactions.append(processed_transaction)
        
        # Transaction type for display
        transaction_type = "Pemasukan" if processed_transaction['amount'] > 0 else "Pengeluaran"
        
        # Format the date for display
        try:
            display_date = datetime.strptime(processed_transaction['date'], "%Y-%m-%d").strftime("%d/%m/%Y")
        except:
            display_date = processed_transaction['date']
        
        confirmation_message += f"*Transaksi {i}:*\n"
        confirmation_message += f"Tanggal: {display_date}\n"
        confirmation_message += f"Jenis: {transaction_type}\n"
        confirmation_message += f"Jumlah: Rp {abs(processed_transaction['amount']):,.0f}\n"
        confirmation_message += f"Kategori: {processed_transaction['category']}\n"
        confirmation_message += f"Deskripsi: {processed_transaction['description']}\n\n"
    
    confirmation_message += "Apakah semua transaksi ini benar?"
    
    # Print for debugging
    print(f"Storing {len(processed_transactions)} transactions in context")
    for i, t in enumerate(processed_transactions):
        print(f"Transaction {i+1}: {t}")
    
    # Save processed transactions in context with a clear key
    context.user_data['pending_multiple_transactions'] = processed_transactions.copy()
    
    # Create confirmation buttons
    keyboard = [
        [InlineKeyboardButton("✅ Benar Semua", callback_data="confirm_all_yes"),
         InlineKeyboardButton("❌ Batal", callback_data="confirm_all_no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send confirmation message and store its ID
    conf_message = await update.message.reply_text(
        confirmation_message, 
        reply_markup=reply_markup, 
        parse_mode='Markdown'
    )
    
    # Add the confirmation message ID to the list for deletion
    if 'messages_to_delete' not in context.user_data:
        context.user_data['messages_to_delete'] = []
    context.user_data['messages_to_delete'].append(conf_message.message_id)
    
async def multiple_transactions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle confirmation for multiple transactions."""
    query = update.callback_query
    user_id = update.effective_user.id
    
    # Check authorization
    if not is_authorized(user_id):
        await query.answer("Anda tidak memiliki akses untuk menggunakan bot ini.", show_alert=True)
        return
    
    await query.answer()
    
    if query.data == "confirm_all_yes":
        # Get the pending transactions
        transactions = context.user_data.get('pending_multiple_transactions', [])
        
        if not transactions:
            await query.edit_message_text("❌ Terjadi kesalahan. Tidak ada transaksi untuk disimpan.")
            return
        
        # Show processing message
        processing_message = await query.edit_message_text(f"⏳ Menyimpan {len(transactions)} transaksi...")
        
        # Record all transactions to the sheet
        success_count = 0
        for transaction in transactions:
            try:
                # Prepare row data
                row_data = [
                    transaction.get('date', datetime.now().strftime("%Y-%m-%d")),
                    transaction.get('amount', 0),
                    transaction.get('category', 'Lainnya'),
                    transaction.get('description', ''),
                    user_id,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ]
                
                # Append to Google Sheet
                sheet.append_row(row_data)
                success_count += 1
                
                # Add a small delay between insertions
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Error recording transaction: {e}", exc_info=True)
        
        # Clear the pending transactions
        context.user_data.pop('pending_multiple_transactions', None)
        
        # Send confirmation message
        confirmation_message = await query.edit_message_text(
            f"✅ {success_count} dari {len(transactions)} transaksi berhasil dicatat!\n\n"
            f"Gunakan /laporan untuk melihat ringkasan keuangan Anda."
        )
        
        # Store the message ID for deletion
        if 'messages_to_delete' not in context.user_data:
            context.user_data['messages_to_delete'] = []
        
        # Add the confirmation message ID to the list
        context.user_data['messages_to_delete'].append(confirmation_message.message_id)
        
        # Schedule message deletion after 5 seconds
        context.job_queue.run_once(
            delete_transaction_messages, 
            5,  # 5 seconds delay
            data={'chat_id': update.effective_chat.id, 'user_id': user_id}
        )
    
    elif query.data == "confirm_all_no":
        # Clear the pending transactions
        context.user_data.pop('pending_multiple_transactions', None)
        
        await query.edit_message_text(
            "❌ Pencatatan transaksi dibatalkan."
        )

async def delete_specific_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Extract the index from the callback data
    index = int(query.data.split("_")[2])
    
    # Get the transaction from stored context
    if 'recent_transactions' not in context.user_data or index >= len(context.user_data['recent_transactions']):
        await query.edit_message_text("❌ Terjadi kesalahan. Silakan coba lagi.")
        return
    
    transaction = context.user_data['recent_transactions'][index]
    
    # Find the row to delete
    all_values = sheet.get_all_values()
    header = all_values[0]  # First row is header
    
    # Find the row index of the transaction
    row_index = None
    for i, row in enumerate(all_values[1:], start=2):  # Start from 2 because row 1 is header
        record = dict(zip(header, row))
        if (str(record.get('User ID')) == str(user_id) and 
            record.get('Timestamp') == transaction.get('Timestamp')):
            row_index = i
            break
    
    if row_index:
        # Delete the row
        sheet.delete_rows(row_index)
        
        # Show confirmation with details of deleted transaction
        amount = float(transaction.get('Amount', 0))
        transaction_type = "Pemasukan" if amount > 0 else "Pengeluaran"
        
        await query.edit_message_text(
            "✅ Transaksi berhasil dihapus!\n\n"
            f"Jenis: {transaction_type}\n"
            f"Jumlah: Rp {abs(amount):,.0f}\n"
            f"Kategori: {transaction.get('Category', 'Lainnya')}\n"
            f"Deskripsi: {transaction.get('Description', '')}\n"
            f"Tanggal: {transaction.get('Date', '')}"
        )
    else:
        await query.edit_message_text("❌ Tidak dapat menemukan transaksi yang dipilih.")

# Handle date input for deletion
async def handle_date_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message_text = update.message.text.strip()
    
    # Check if we're in the date deletion flow
    if 'delete_state' not in context.user_data:
        return
    
    delete_state = context.user_data['delete_state']
    
    # Validate date format (YYYY-MM-DD)
    import re
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', message_text):
        await update.message.reply_text(
            "❌ Format tanggal tidak valid. Gunakan format YYYY-MM-DD.\n"
            "Contoh: 2023-05-01\n\n"
            "Silakan coba lagi:"
        )
        return
    
    if delete_state == 'awaiting_start_date':
        # Store start date and ask for end date
        context.user_data['start_date'] = message_text
        context.user_data['delete_state'] = 'awaiting_end_date'
        
        await update.message.reply_text(
            "📅 Masukkan tanggal akhir (format: YYYY-MM-DD):\n"
            "Contoh: 2023-05-31"
        )
    
    elif delete_state == 'awaiting_end_date':
        start_date = context.user_data['start_date']
        end_date = message_text
        
        # Validate that end date is after start date
        if end_date < start_date:
            await update.message.reply_text(
                "❌ Tanggal akhir harus setelah tanggal awal.\n"
                "Silakan masukkan tanggal akhir yang valid:"
            )
            return
        
        # Get all records
        all_records = sheet.get_all_records()
        
        # Filter records by user ID and date range
        user_records_in_range = [
            record for record in all_records 
            if str(record.get('User ID')) == str(user_id) and 
               start_date <= record.get('Date', '') <= end_date
        ]
        
        if not user_records_in_range:
            await update.message.reply_text(
                "❌ Tidak ada transaksi dalam rentang tanggal tersebut."
            )
            # Clear delete state
            context.user_data.pop('delete_state', None)
            context.user_data.pop('start_date', None)
            return
        
        # Ask for confirmation
        context.user_data['records_to_delete'] = user_records_in_range
        
        # Create confirmation message
        confirmation_message = (
            f"🗑️ *Konfirmasi Penghapusan*\n\n"
            f"Anda akan menghapus {len(user_records_in_range)} transaksi "
            f"dari {start_date} hingga {end_date}.\n\n"
            "Apakah Anda yakin ingin melanjutkan?"
        )
        
        keyboard = [
            [InlineKeyboardButton("✅ Ya, Hapus", callback_data="confirm_delete_date")],
            [InlineKeyboardButton("❌ Tidak, Batalkan", callback_data="delete_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            confirmation_message,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

async def confirm_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    action = query.data.split("_")[2]  # confirm_delete_all or confirm_delete_date
    
    if action == "all":
        # Delete all transactions for this user
        all_values = sheet.get_all_values()
        header = all_values[0]  # First row is header
        
        # Find all rows to delete (in reverse order to avoid index shifting)
        rows_to_delete = []
        for i, row in enumerate(all_values[1:], start=2):  # Start from 2 because row 1 is header
            record = dict(zip(header, row))
            if str(record.get('User ID')) == str(user_id):
                rows_to_delete.append(i)
        
        # Delete rows in reverse order
        for row_index in sorted(rows_to_delete, reverse=True):
            sheet.delete_rows(row_index)
        
        await query.edit_message_text(
            "✅ Semua transaksi Anda telah dihapus.\n\n"
            f"Total {len(rows_to_delete)} transaksi telah dihapus."
        )
    
    elif action == "date":
        if 'records_to_delete' not in context.user_data:
            await query.edit_message_text("❌ Terjadi kesalahan. Silakan coba lagi.")
            return
        
        records_to_delete = context.user_data['records_to_delete']
        
        # Find all rows to delete (in reverse order)
        all_values = sheet.get_all_values()
        header = all_values[0]  # First row is header
        
        # Find the row indices of the transactions to delete
        rows_to_delete = []
        for record_to_delete in records_to_delete:
            for i, row in enumerate(all_values[1:], start=2):  # Start from 2 because row 1 is header
                record = dict(zip(header, row))
                if (str(record.get('User ID')) == str(user_id) and 
                    record.get('Timestamp') == record_to_delete.get('Timestamp')):
                    rows_to_delete.append(i)
                    break
        
        # Delete rows in reverse order
        for row_index in sorted(rows_to_delete, reverse=True):
            sheet.delete_rows(row_index)
        
        # Clear delete state
        context.user_data.pop('delete_state', None)
        context.user_data.pop('start_date', None)
        context.user_data.pop('records_to_delete', None)
        
        await query.edit_message_text(
            "✅ Transaksi dalam rentang tanggal telah dihapus.\n\n"
            f"Total {len(rows_to_delete)} transaksi telah dihapus."
        )

# Enhanced helper function to parse financial data using Gemini with improved income/expense detection
async def parse_financial_data(text):
    from datetime import datetime, timedelta
    import locale
    
    # Set locale to Indonesian for better date parsing
    try:
        locale.setlocale(locale.LC_TIME, 'id_ID.UTF-7')  # For Linux/Mac
    except:
        try:
            locale.setlocale(locale.LC_TIME, 'Indonesian')  # For Windows
        except:
            pass  # If setting locale fails, continue with default
    
    # Current date for reference
    current_date = datetime.now()
    
    prompt = f"""
    Extract financial information from this Indonesian text: "{text}"
    Today's date is {current_date.strftime("%Y-%m-%d")} ({current_date.strftime("%A, %d %B %Y")}).
    
    Return a JSON object with these fields:
    - amount: the monetary amount (numeric value only, without currency symbols)
    - category: the spending/income category
    - description: brief description of the transaction
    - transaction_type: "income" if this is money received, or "expense" if this is money spent
    - date: the date of the transaction in YYYY-MM-DD format
    - time_context: any time-related information found in the text (e.g., "yesterday", "last Monday", "2 days ago")
    
    For the date field, analyze time expressions carefully:
    
    1. Specific dates:
       - "5 Mei 2023", "05/05/2023", "5 May 2023" → use that exact date
       - "5 Mei", "05/05" → use that date in the current year
    
    2. Relative days:
       - "kemarin", "yesterday" → use yesterday's date ({(current_date - timedelta(days=1)).strftime("%Y-%m-%d")})
       - "hari ini", "today", "sekarang" → use today's date ({current_date.strftime("%Y-%m-%d")})
       - "besok", "tomorrow" → use tomorrow's date ({(current_date + timedelta(days=1)).strftime("%Y-%m-%d")})
       - "lusa", "day after tomorrow" → use the day after tomorrow ({(current_date + timedelta(days=2)).strftime("%Y-%m-%d")})
       - "2 hari yang lalu", "2 days ago" → subtract the specified number of days
       - "minggu lalu", "last week" → subtract 7 days
       - "bulan lalu", "last month" → use the same day in the previous month
    
    3. Day names:
       - "Senin", "Monday" → use the date of the most recent Monday
       - "Senin lalu", "last Monday" → use the date of the previous Monday (not today if today is Monday)
       - "Senin depan", "next Monday" → use the date of the next Monday (not today if today is Monday)
    
    4. Month references:
       - "awal bulan", "beginning of the month" → use the 1st day of the current month
       - "akhir bulan", "end of the month" → use the last day of the current month
       - "pertengahan bulan", "middle of the month" → use the 15th day of the current month
       - "awal bulan lalu", "beginning of last month" → use the 1st day of the previous month
    
    If no date is mentioned, use today's date ({current_date.strftime("%Y-%m-%d")}).
    
    For transaction_type, analyze the context carefully using these rules:
    
    INCOME indicators (set transaction_type to "income"):
    - Words about receiving money: "terima", "dapat", "pemasukan", "masuk", "diterima"
    - Income sources: "gaji", "bonus", "komisi", "dividen", "bunga", "hadiah", "warisan", "penjualan", "refund", "kembalian", "cashback"
    - Phrases like: "dibayar oleh", "transfer dari", "kiriman dari", "diberi", "dikasih"
    
    EXPENSE indicators (set transaction_type to "expense"):
    - Words about spending: "beli", "bayar", "belanja", "pengeluaran", "keluar", "dibayar"
    - Purchase verbs: "membeli", "memesan", "berlangganan", "sewa", "booking"
    - Expense categories: "makanan", "transportasi", "bensin", "pulsa", "tagihan", "biaya", "iuran"
    - Phrases like: "dibayarkan untuk", "transfer ke", "kirim ke"
    
    If the text doesn't clearly indicate transaction type, look at the context:
    - If it mentions purchasing an item or service, it's likely an expense
    - If it mentions receiving money or payment, it's likely income
    
    If still unclear, default to "expense".
    
    For category, try to identify specific categories like:
    - Income categories: "Gaji", "Bonus", "Investasi", "Hadiah", "Penjualan", "Bisnis"
    - Expense categories: "Makanan", "Transportasi", "Belanja", "Hiburan", "Tagihan", "Kesehatan", "Pendidikan"
    
    If any field is unclear, set it to null.
    """
    
    response = model.generate_content(prompt)
    try:
        # Extract JSON from response
        response_text = response.text
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            json_str = response_text.split("```")[1].strip()
        else:
            json_str = response_text.strip()
        
        data = json.loads(json_str)
        
        # Process the date field - if Gemini couldn't determine it, try to parse it ourselves
        if not data.get('date') and data.get('time_context'):
            time_context = data.get('time_context').lower()
            
            # Handle common time expressions
            if any(word in time_context for word in ["kemarin", "yesterday"]):
                data['date'] = (current_date - timedelta(days=1)).strftime("%Y-%m-%d")
            elif any(word in time_context for word in ["besok", "tomorrow"]):
                data['date'] = (current_date + timedelta(days=1)).strftime("%Y-%m-%d")
            elif any(word in time_context for word in ["lusa", "day after tomorrow"]):
                data['date'] = (current_date + timedelta(days=2)).strftime("%Y-%m-%d")
            elif "hari yang lalu" in time_context or "days ago" in time_context:
                try:
                    # Extract number of days
                    import re
                    days_ago = int(re.search(r'(\d+)', time_context).group(1))
                    data['date'] = (current_date - timedelta(days=days_ago)).strftime("%Y-%m-%d")
                except:
                    pass
            elif "minggu lalu" in time_context or "last week" in time_context:
                data['date'] = (current_date - timedelta(days=7)).strftime("%Y-%m-%d")
            
            # Handle day names
            day_names = {
                "senin": 0, "monday": 0,
                "selasa": 1, "tuesday": 1,
                "rabu": 2, "wednesday": 2,
                "kamis": 3, "thursday": 3,
                "jumat": 4, "friday": 4,
                "sabtu": 5, "saturday": 5,
                "minggu": 6, "sunday": 6
            }
            
            for day_name, day_num in day_names.items():
                if day_name in time_context:
                    # Calculate days until the previous occurrence of this day
                    days_diff = (current_date.weekday() - day_num) % 7
                    if days_diff == 0:
                        # If it's the same day and "last" is mentioned, go back a week
                        if "lalu" in time_context or "last" in time_context:
                            days_diff = 7
                    
                    # If "next" is mentioned, calculate days until next occurrence
                    if "depan" in time_context or "next" in time_context:
                        days_diff = (day_num - current_date.weekday()) % 7
                        if days_diff == 0:
                            days_diff = 7
                        data['date'] = (current_date + timedelta(days=days_diff)).strftime("%Y-%m-%d")
                    else:
                        data['date'] = (current_date - timedelta(days=days_diff)).strftime("%Y-%m-%d")
                    
                    break
        
        # If still no date, use today's date
        if not data.get('date'):
            data['date'] = current_date.strftime("%Y-%m-%d")
        
        # Additional processing for amount and transaction type
        if data.get('amount') is not None:
            # Convert amount to float and ensure proper sign
            amount = abs(float(data.get('amount')))
            
            # Apply sign based on transaction type
            if data.get('transaction_type') == 'expense':
                amount = -amount
                
            data['amount'] = amount
        
        # Remove time_context from final data as it's just a helper field
        data.pop('time_context', None)
        
        return data
    except Exception as e:
        logger.error(f"Error parsing Gemini response: {e}")
        # If parsing fails, return a basic structure with today's date
        return {
            "amount": None, 
            "category": None, 
            "description": None, 
            "transaction_type": None,
            "date": current_date.strftime("%Y-%m-%d")
        }

def parse_date_from_text(text):
    """Attempt to extract a date from text using various methods."""
    from datetime import datetime, timedelta
    import re
    
    # Current date for reference
    current_date = datetime.now()
    
    # Try to find date patterns in the text
    text = text.lower()
    
    # Check for "yesterday", "today", "tomorrow"
    if "kemarin" in text or "yesterday" in text:
        return (current_date - timedelta(days=1)).strftime("%Y-%m-%d")
    elif "hari ini" in text or "today" in text:
        return current_date.strftime("%Y-%m-%d")
    elif "besok" in text or "tomorrow" in text:
        return (current_date + timedelta(days=1)).strftime("%Y-%m-%d")
    elif "lusa" in text or "day after tomorrow" in text:
        return (current_date + timedelta(days=2)).strftime("%Y-%m-%d")
    
    # Check for "X days ago"
    days_ago_match = re.search(r'(\d+)\s+hari\s+(?:yang\s+)?lalu', text) or re.search(r'(\d+)\s+days\s+ago', text)
    if days_ago_match:
        days = int(days_ago_match.group(1))
        return (current_date - timedelta(days=days)).strftime("%Y-%m-%d")
    
    # Check for date formats like DD/MM/YYYY or DD-MM-YYYY
    date_patterns = [
        r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})',  # DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY
        r'(\d{4})[/.-](\d{1,2})[/.-](\d{1,2})'   # YYYY/MM/DD or YYYY-MM-DD or YYYY.MM.DD
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            groups = match.groups()
            if len(groups[0]) == 4:  # YYYY/MM/DD format
                year, month, day = groups
            else:  # DD/MM/YYYY format
                day, month, year = groups
            
            try:
                # Validate and format the date
                date_obj = datetime(int(year), int(month), int(day))
                return date_obj.strftime("%Y-%m-%d")
            except ValueError:
                # Invalid date, continue to next pattern
                continue
    
    # If no date found, return today's date
    return current_date.strftime("%Y-%m-%d")
    
# Function to parse multiple transactions from multi-line input
async def parse_multiple_transactions(text):
    """Parse multiple transactions from text separated by newlines."""
    # Split the text by newlines and filter out empty lines
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    print(f"Parsing {len(lines)} lines")
    
    if not lines:
        return []
    
    # Process each line as a separate transaction
    transactions = []
    for i, line in enumerate(lines):
        try:
            print(f"Parsing line {i+1}: {line}")
            transaction_data = await parse_financial_data(line)
            print(f"Parsed data: {transaction_data}")
            
            # Only include transactions where an amount could be determined
            if transaction_data.get('amount') is not None:
                transactions.append(transaction_data)
                print(f"Added transaction {i+1}")
            else:
                print(f"Skipping line {i+1} - no amount detected")
        except Exception as e:
            print(f"Error parsing line {i+1}: {e}")
            logger.error(f"Error parsing transaction line '{line}': {e}")
            # Continue with other lines even if one fails
            continue
    
    print(f"Returning {len(transactions)} parsed transactions")
    return transactions

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Check authorization
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ Maaf, Anda tidak memiliki akses untuk menggunakan bot ini.")
        return
    
    # Original handler code
    await update.message.reply_text(
        "👋 Selamat datang di Bot Pencatatan Keuangan!\n\n"
        "Gunakan bot ini untuk mencatat keuangan Anda. Data akan disimpan di Google Sheets.\n\n"
        "Perintah:\n"
        "/catat - Catat transaksi baru\n"
        "/laporan - Lihat laporan keuangan\n"
        "/sheet - Dapatkan link Google Sheet\n"
        "/hapus - Hapus data keuangan\n"
        "/help - Bantuan lengkap\n\n"
        "Atau cukup kirim pesan seperti:\n"
        "• 'Beli makan siang 50000' (pengeluaran)\n"
        "• 'Terima gaji bulan ini 5000000' (pemasukan)\n\n"
        "Bot akan otomatis mendeteksi apakah itu pemasukan atau pengeluaran."
    )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Check authorization
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ Maaf, Anda tidak memiliki akses untuk menggunakan bot ini.")
        return
    
    # Check if we're in delete state or processing a financial message
    if 'delete_state' in context.user_data:
        await handle_date_input(update, context)
    else:
        message_text = update.message.text
        print(f"Received message: {message_text}")
        
        # Split by newlines and filter out empty lines
        lines = [line.strip() for line in message_text.split('\n') if line.strip()]
        print(f"Detected {len(lines)} lines")
        
        # If we have multiple lines, process as multiple transactions
        if len(lines) > 1:
            await update.message.reply_text("🔍 Menganalisis transaksi Anda...")
            transactions = await parse_multiple_transactions(message_text)
            print(f"Parsed {len(transactions)} transactions")
            
            if not transactions:
                await update.message.reply_text(
                    "❌ Saya tidak dapat mengenali transaksi dari pesan Anda.\n"
                    "Pastikan setiap baris berisi informasi transaksi yang lengkap."
                )
                return
            
            # Process multiple transactions
            await process_multiple_transactions(update, context, transactions)
        else:
            # Single transaction processing
            await process_financial_message(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🔍 *Cara Menggunakan Bot Keuangan*\n\n"
        "*Mencatat Transaksi:*\n"
        "Cukup kirim pesan yang menjelaskan transaksi Anda. Bot akan otomatis mendeteksi apakah itu pemasukan atau pengeluaran.\n\n"
        "*Contoh Pemasukan:*\n"
        "• Terima gaji bulan ini 5000000\n"
        "• Dapat bonus kerja 1500000\n"
        "• Penjualan barang 250000\n"
        "• Kiriman dari ibu 500000\n\n"
        "*Contoh Pengeluaran:*\n"
        "• Beli makan siang 50000\n"
        "• Bayar tagihan listrik 350000\n"
        "• Belanja bulanan di supermarket 750000\n"
        "• Isi bensin motor 25000\n\n"
        "*Input Multi-Transaksi:*\n"
        "Anda dapat mencatat beberapa transaksi sekaligus dengan mengirimkan pesan dengan format:\n\n"
        "Transaksi 1\n"
        "Transaksi 2\n"
        "Transaksi 3\n\n"
        "Contoh:\n"
        "Beli makan siang kemarin 50000\n"
        "Bayar listrik hari ini 350000\n"
        "Terima gaji 5000000\n\n"
        "Bot akan menganalisis setiap baris sebagai transaksi terpisah."
        "*Perintah Lain:*\n"
        "/catat - Mulai mencatat transaksi baru\n"
        "/laporan - Lihat laporan keuangan Anda\n"
        "/help - Tampilkan bantuan ini"
        "*Pengaturan Bot:*\n"
        "/hapuspesan - Aktifkan/nonaktifkan penghapusan pesan otomatis\n\n"
    )
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def record_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Silakan kirim detail transaksi Anda.\n"
        "Format: [deskripsi] [jumlah]\n"
        "Contoh: 'Beli makan siang 50000' atau 'Gaji bulan ini 5000000'"
    )

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Check authorization
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ Maaf, Anda tidak memiliki akses untuk menggunakan bot ini.")
        return
    
    await update.message.reply_text("📊 Mengambil data laporan keuangan Anda...")
    
    try:
        # Get all records directly from the sheet
        all_records = sheet.get_all_records()
        
        # Filter records for this user
        user_records = [record for record in all_records if str(record.get('User ID')) == str(user_id)]
        
        if not user_records:
            await update.message.reply_text("❌ Anda belum memiliki catatan keuangan.")
            return
        
        # Calculate summary
        total_income = sum(float(record['Amount']) for record in user_records if float(record['Amount']) > 0)
        total_expense = sum(abs(float(record['Amount'])) for record in user_records if float(record['Amount']) < 0)
        balance = total_income - total_expense
        
        # Create report message
        report_message = f"📊 *Laporan Keuangan*\n\n"
        report_message += f"Total Pemasukan: Rp {total_income:,.0f}\n"
        report_message += f"Total Pengeluaran: Rp {total_expense:,.0f}\n"
        report_message += f"Saldo: Rp {balance:,.0f}\n\n"
        
        # Add category breakdown for expenses
        expense_by_category = {}
        for record in user_records:
            amount = float(record['Amount'])
            if amount < 0:  # It's an expense
                category = record.get('Category', 'Lainnya')
                if category in expense_by_category:
                    expense_by_category[category] += abs(amount)
                else:
                    expense_by_category[category] = abs(amount)
        
        if expense_by_category:
            report_message += "*Pengeluaran per Kategori:*\n"
            for category, amount in sorted(expense_by_category.items(), key=lambda x: x[1], reverse=True):
                percentage = (amount / total_expense) * 100 if total_expense > 0 else 0
                report_message += f"• {category}: Rp {amount:,.0f} ({percentage:.1f}%)\n"
            
            report_message += "\n"
        
        # Add recent transactions
        report_message += "*Transaksi Terakhir:*\n"
        
        # Sort transactions by date (newest first)
        sorted_records = sorted(user_records, key=lambda x: x.get('Timestamp', ''), reverse=True)
        
        # Take the 5 most recent transactions
        recent_transactions = sorted_records[:5]
        
        for record in recent_transactions:
            try:
                amount = float(record['Amount'])
                symbol = "+" if amount >= 0 else "-"
                date = record.get('Date', '')
                category = record.get('Category', 'Lainnya')
                description = record.get('Description', '')
                
                # Truncate description if too long
                if len(description) > 20:
                    description = description[:17] + "..."
                
                report_message += f"• {date} | {symbol} Rp {abs(amount):,.0f} | {category} | {description}\n"
            except Exception as e:
                # Skip this record if there's an error
                continue
        
        # Send the report
        await update.message.reply_text(report_message, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        await update.message.reply_text(
            "❌ Terjadi kesalahan saat mengambil laporan keuangan Anda. "
            "Silakan coba lagi nanti."
        )

# Fallback function to detect transaction type from text
def detect_transaction_type(text):
    text = text.lower()
    
    # Income indicators
    income_words = [
        "terima", "dapat", "pemasukan", "masuk", "diterima", 
        "gaji", "bonus", "komisi", "dividen", "bunga", "hadiah", 
        "warisan", "penjualan", "refund", "kembalian", "cashback",
        "dibayar oleh", "transfer dari", "kiriman dari", "diberi", "dikasih"
    ]
    
    # Expense indicators
    expense_words = [
        "beli", "bayar", "belanja", "pengeluaran", "keluar", "dibayar",
        "membeli", "memesan", "berlangganan", "sewa", "booking",
        "makanan", "transportasi", "bensin", "pulsa", "tagihan", "biaya", "iuran",
        "dibayarkan untuk", "transfer ke", "kirim ke"
    ]
    
    # Count matches
    income_score = sum(1 for word in income_words if word in text)
    expense_score = sum(1 for word in expense_words if word in text)
    
    # Determine type based on score
    if income_score > expense_score:
        return "income"
    else:
        return "expense"  # Default to expense if tied or no matches

# Message handler for financial data with improved detection
async def process_financial_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Store the user's message ID for later deletion
    if 'messages_to_delete' not in context.user_data:
        context.user_data['messages_to_delete'] = []
    
    # Add the user's message ID to the list
    context.user_data['messages_to_delete'].append(update.message.message_id)
    
    # Authorization is already checked in the message_handler
    
    message_text = update.message.text
    
    # Split by newlines and filter out empty lines
    lines = [line.strip() for line in message_text.split('\n') if line.strip()]
    
    # If we have multiple lines, process as multiple transactions
    if len(lines) > 1:
        # Send analyzing message and store its ID
        analyzing_message = await update.message.reply_text("🔍 Menganalisis transaksi Anda...")
        context.user_data['messages_to_delete'].append(analyzing_message.message_id)
        
        transactions = await parse_multiple_transactions(message_text)
        
        if not transactions:
            error_message = await update.message.reply_text(
                "❌ Saya tidak dapat mengenali transaksi dari pesan Anda.\n"
                "Pastikan setiap baris berisi informasi transaksi yang lengkap."
            )
            context.user_data['messages_to_delete'].append(error_message.message_id)
            return
        
        # Process multiple transactions
        await process_multiple_transactions(update, context, transactions)
    else:
        # Send analyzing message and store its ID
        analyzing_message = await update.message.reply_text("🔍 Menganalisis pesan Anda...")
        context.user_data['messages_to_delete'].append(analyzing_message.message_id)
        
        # Single transaction processing
        parsed_data = await parse_financial_data(message_text)
    
    # If Gemini couldn't determine a date, try our fallback parser
    if not parsed_data.get('date'):
        parsed_data['date'] = parse_date_from_text(message_text)
    
    # If parsing failed or incomplete, ask for clarification
    if not parsed_data.get('amount'):
        keyboard = [
            [InlineKeyboardButton("Pemasukan", callback_data="type_income"),
             InlineKeyboardButton("Pengeluaran", callback_data="type_expense")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        context.user_data['pending_message'] = message_text
        # Store the detected date for later use
        context.user_data['detected_date'] = parsed_data.get('date')
        
        await update.message.reply_text(
            "Saya tidak dapat menentukan jumlah transaksi. Apakah ini pemasukan atau pengeluaran?",
            reply_markup=reply_markup
        )
        return
    
    # Create confirmation message with parsed data
    amount = parsed_data.get('amount', 0)
    transaction_type = "Pemasukan" if amount > 0 else "Pengeluaran"
    category = parsed_data.get('category', 'Lainnya')
    description = parsed_data.get('description', message_text)
    date = parsed_data.get('date')
    
    # Format the date for display (YYYY-MM-DD to DD/MM/YYYY)
    try:
        from datetime import datetime
        display_date = datetime.strptime(date, "%Y-%m-%d").strftime("%d/%m/%Y")
    except:
        display_date = date
    
    confirmation_message = f"📝 *Detail Transaksi*\n\n"
    confirmation_message += f"Tanggal: {display_date}\n"
    confirmation_message += f"Jenis: {transaction_type}\n"
    confirmation_message += f"Jumlah: Rp {abs(amount):,.0f}\n"
    confirmation_message += f"Kategori: {category}\n"
    confirmation_message += f"Deskripsi: {description}\n\n"
    confirmation_message += "Apakah data ini benar?"
    
    # Save data temporarily
    context.user_data['pending_transaction'] = {
        'date': date,
        'amount': amount,
        'category': category,
        'description': description
    }
    
    # Create confirmation buttons
    keyboard = [
        [InlineKeyboardButton("✅ Benar", callback_data="confirm_yes"),
         InlineKeyboardButton("❌ Salah", callback_data="confirm_no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(confirmation_message, reply_markup=reply_markup, parse_mode='Markdown')

# Callback query handler
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    
    # Check authorization
    if not is_authorized(user_id):
        await query.answer("Anda tidak memiliki akses untuk menggunakan bot ini.", show_alert=True)
        return
    
    await query.answer()
    
    if query.data.startswith("type_"):
        transaction_type = query.data.split("_")[1]
        message_text = context.user_data.get('pending_message', '')
        
        # Get the detected date if available, otherwise use today's date
        detected_date = context.user_data.get('detected_date', datetime.now().strftime("%Y-%m-%d"))
        
        # Ask for amount
        context.user_data['transaction_type'] = transaction_type
        context.user_data['description'] = message_text
        context.user_data['date'] = detected_date  # Store the date
        
        # Format the date for display
        try:
            display_date = datetime.strptime(detected_date, "%Y-%m-%d").strftime("%d/%m/%Y")
        except:
            display_date = detected_date
        
        await query.edit_message_text(
            f"Tanggal: {display_date}\n\n"
            f"Berapa jumlah {'pemasukan' if transaction_type == 'income' else 'pengeluaran'} untuk '{message_text}'?",
        )
        return
    
    if query.data.startswith("confirm_"):
        is_confirmed = query.data.split("_")[1] == "yes"
        
        if is_confirmed:
            # Get transaction data
            transaction = context.user_data.get('pending_transaction', {})
            
            # Prepare row data
            row_data = [
                transaction.get('date', datetime.now().strftime("%Y-%m-%d")),  # Use the date from parsed data
                transaction.get('amount', 0),
                transaction.get('category', 'Lainnya'),
                transaction.get('description', ''),
                user_id,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ]
            
            # Append to Google Sheet
            sheet.append_row(row_data)
            
            # Determine transaction type for display
            amount = transaction.get('amount', 0)
            transaction_type = "Pemasukan" if amount > 0 else "Pengeluaran"
            
            # Send confirmation message
            confirmation_message = await query.edit_message_text(
                "✅ Transaksi berhasil dicatat!\n\n"
                f"Tanggal: {transaction.get('date', datetime.now().strftime('%Y-%m-%d'))}\n"
                f"Jenis: {transaction_type}\n"
                f"Jumlah: Rp {abs(float(amount)):,.0f}\n"
                f"Kategori: {transaction.get('category', 'Lainnya')}\n"
                f"Deskripsi: {transaction.get('description', '')}"
            )
            
            # Store the message ID for deletion
            if 'messages_to_delete' not in context.user_data:
                context.user_data['messages_to_delete'] = []
            
            # Add the confirmation message ID to the list
            context.user_data['messages_to_delete'].append(confirmation_message.message_id)
            
            # Schedule message deletion after 5 seconds
            context.job_queue.run_once(
                delete_transaction_messages, 
                5,  # 5 seconds delay
                data={'chat_id': update.effective_chat.id, 'user_id': user_id}
            )
        else:
            # If not confirmed, ask for manual input
            keyboard = [
                [InlineKeyboardButton("Pemasukan", callback_data="type_income"),
                 InlineKeyboardButton("Pengeluaran", callback_data="type_expense")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "Silakan pilih jenis transaksi:",
                reply_markup=reply_markup
            )

# Handle amount input after transaction type selection
async def handle_amount_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'transaction_type' not in context.user_data:
        return
    
    try:
        # Parse amount from message
        amount_text = update.message.text.replace(',', '').replace('.', '')
        amount = float(amount_text)
        
        # Adjust sign based on transaction type
        if context.user_data['transaction_type'] == 'expense':
            amount = -abs(amount)  # Make negative for expenses
        else:
            amount = abs(amount)   # Make positive for income
        
        description = context.user_data.get('description', '')
        
        # Ask for category
        context.user_data['amount'] = amount
        
        # Suggest categories based on transaction type
        if context.user_data['transaction_type'] == 'income':
            categories = ["Gaji", "Bonus", "Investasi", "Hadiah", "Lainnya"]
        else:
            categories = ["Makanan", "Transportasi", "Belanja", "Hiburan", "Tagihan", "Lainnya"]
        
        keyboard = [[InlineKeyboardButton(cat, callback_data=f"cat_{cat}")] for cat in categories]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"Pilih kategori untuk {'pemasukan' if amount > 0 else 'pengeluaran'} ini:",
            reply_markup=reply_markup
        )
    except ValueError:
        await update.message.reply_text("Mohon masukkan jumlah yang valid (angka saja).")

# Handle category selection
async def category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("cat_"):
        category = query.data.split("_")[1]
        user_id = update.effective_user.id
        
        # Get transaction data
        amount = context.user_data.get('amount', 0)
        description = context.user_data.get('description', '')
        
        # Prepare row data
        today = datetime.now().strftime("%Y-%m-%d")
        row_data = [
            today,
            amount,  # Already has correct sign (positive for income, negative for expense)
            category,
            description,
            user_id,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ]
        
        # Append to Google Sheet
        sheet.append_row(row_data)
        
        # Determine transaction type for display
        transaction_type = "Pemasukan" if amount > 0 else "Pengeluaran"
        
        await query.edit_message_text(
            "✅ Transaksi berhasil dicatat!\n\n"
            f"Jenis: {transaction_type}\n"
            f"Jumlah: Rp {abs(float(amount)):,.0f}\n"
            f"Kategori: {category}\n"
            f"Deskripsi: {description}"
        )
        
        # Clear user data
        context.user_data.clear()

def main():
    # Create application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Create persistence object
    persistence = PicklePersistence(filepath="bot_data.pickle")
    
    # Create application with persistence
    application = Application.builder().token(TELEGRAM_TOKEN).persistence(persistence).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("catat", record_command))
    application.add_handler(CommandHandler("laporan", report))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("sheet", sheet_link))
    application.add_handler(CommandHandler("hapus", delete_data))
    application.add_handler(CommandHandler("hapuspesan", toggle_delete_messages))
    
    # Add callback handlers
    application.add_handler(CallbackQueryHandler(multiple_transactions_callback, pattern="^confirm_all_"))
    application.add_handler(CallbackQueryHandler(delete_callback, pattern="^delete_"))
    application.add_handler(CallbackQueryHandler(delete_specific_callback, pattern="^del_specific_"))
    application.add_handler(CallbackQueryHandler(confirm_delete_callback, pattern="^confirm_delete_"))
    application.add_handler(CallbackQueryHandler(button_callback, pattern="^(confirm_|type_)"))
    application.add_handler(CallbackQueryHandler(category_callback, pattern="^cat_"))
    
    # Add message handler
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        message_handler
    ))
    
    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main()