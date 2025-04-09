# Bot Keuangan Telegram

Bot Telegram untuk membantu mencatat keuangan pribadi Anda. Bot ini memungkinkan pengguna untuk mencatat transaksi, melihat laporan keuangan, dan mengelola data yang disimpan di Google Sheets.

## Fitur

- **Catat Transaksi**: Tambahkan transaksi pemasukan atau pengeluaran langsung melalui pesan Telegram.
- **Integrasi Google Sheets**: Semua data disimpan di Google Sheets untuk kemudahan akses dan berbagi.
- **Laporan Keuangan**: Lihat ringkasan pemasukan, pengeluaran, dan saldo.
- **Input Multi-Transaksi**: Catat beberapa transaksi sekaligus dalam satu pesan.
- **Pengelolaan Data**: Hapus transaksi berdasarkan tanggal, kategori, atau semua data sekaligus.
- **Otorisasi Pengguna**: Hanya pengguna yang diotorisasi yang dapat menggunakan bot ini.

## Persyaratan

- Python 3.9 atau lebih baru
- Token bot Telegram (dapatkan dari [BotFather](https://core.telegram.org/bots#botfather))
- Kredensial API Google Sheets
- Kredensial Gemini API
- File `.env` untuk konfigurasi variabel lingkungan

## Instalasi

1. Clone repositori ini:
   ```bash
   git clone https://github.com/username/financial-bot-telegram.git
   cd financial-bot-telegram
   ```

2. Instal dependensi:
   ```bash
   pip install -r requirements.txt
   ```

3. Buat file `.env` dan tambahkan variabel berikut:
   ```env
   TELEGRAM_TOKEN=token-bot-telegram-anda
   GEMINI_API_KEY=api-key-gemini-anda
   GOOGLE_SHEETS_CREDENTIALS=path-ke-google-sheets-credentials.json
   SPREADSHEET_ID=id-google-spreadsheet-anda
   AUTHORIZED_USER_ID=id-user-telegram-anda
   ```

4. Pastikan kredensial Google Sheets API Anda sudah diatur. Ikuti [Panduan Google Sheets API](https://developers.google.com/sheets/api/quickstart/python) untuk membuat dan mengunduh file `credentials.json`.

5. Jalankan bot:
   ```bash
   python main.py
   ```

## Cara Menggunakan

### Perintah

- `/start`: Memulai bot dan menampilkan pesan selamat datang.
- `/catat`: Mencatat transaksi baru.
- `/laporan`: Melihat laporan keuangan.
- `/sheet`: Mendapatkan tautan ke Google Sheet Anda.
- `/hapus`: Menghapus data keuangan.
- `/help`: Menampilkan panduan penggunaan.
- `/hapuspesan`: Mengaktifkan/nonaktifkan penghapusan pesan otomatis.

### Contoh Transaksi

Kirim pesan seperti berikut untuk mencatat transaksi:

- **Pemasukan**: `Terima gaji bulan ini 5000000`
- **Pengeluaran**: `Beli makan siang 50000`
- **Multi-Transaksi**:
  ```
  Beli makan siang kemarin 50000
  Bayar listrik hari ini 350000
  Terima gaji 5000000
  ```

### Integrasi Google Sheets

Semua transaksi disimpan di Google Sheets. Gunakan perintah `/sheet` untuk mendapatkan tautan ke spreadsheet Anda.

## Lisensi

Proyek ini dilisensikan di bawah [Lisensi MIT](LICENSE).

## Kontribusi

Kontribusi sangat diterima! Silakan buka issue atau kirim pull request.

## Penghargaan

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [Google Sheets API](https://developers.google.com/sheets/api)
- [Gemini API](https://developers.google.com/gemini)
- [dotenv](https://pypi.org/project/python-dotenv/)
