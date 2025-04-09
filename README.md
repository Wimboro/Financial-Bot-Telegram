# Bot Keuangan Telegram

Bot Telegram ini membantu Anda mencatat keuangan pribadi. Dengan bot ini, Anda dapat mencatat transaksi, melihat laporan keuangan, dan mengelola data yang tersimpan di Google Sheets.

## Fitur

- **Catat Transaksi**: Tambahkan transaksi pemasukan atau pengeluaran langsung melalui Telegram.
- **Integrasi Google Sheets**: Semua data disimpan di Google Sheets untuk memudahkan akses dan berbagi.
- **Laporan Keuangan**: Lihat ringkasan pemasukan, pengeluaran, dan saldo Anda.
- **Input Multi-Transaksi**: Catat beberapa transaksi sekaligus dalam satu pesan.
- **Pengelolaan Data**: Hapus transaksi berdasarkan tanggal, kategori, atau semua data sekaligus.
- **Otorisasi Pengguna**: Hanya pengguna yang diotorisasi yang dapat menggunakan bot ini.

## Persyaratan

- Python 3.9 atau versi lebih baru
- Token bot Telegram (dapatkan dari [BotFather](https://core.telegram.org/bots#botfather))
- Kredensial API Google Sheets
- Kredensial Gemini API
- File `.env` untuk konfigurasi variabel lingkungan

## Instalasi

1. Clone repositori ini:
   ```bash
   git clone https://github.com/Wimboro/financial-bot-telegram.git
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

4. Buat kredensial untuk mengaktifkan Google Sheets API dan Google Drive API:
   - Masuk ke [Google Cloud Console](https://console.cloud.google.com/apis/credentials).
   - Klik **Create Credentials**, pilih **Service Account**, dan isi informasi yang diminta.
   - Pilih peran sebagai **Owner** atau **Editor**, lalu klik **Done**.

5. Unduh file JSON kredensial:
   - Kembali ke halaman **Credentials**, pilih **Service Account** yang telah dibuat.
   - Pada tab **Keys**, klik **Add Key**, pilih **Create New Key**, dan pilih format **JSON**.
   - File JSON akan diunduh secara otomatis. Ubah nama file menjadi `credentials.json` dan simpan di direktori utama bot.

6. Buat Gemini API Key:
   - Masuk ke [AI Studio Google](https://aistudio.google.com/apikey).
   - Klik **Create API Key**, pilih proyek yang ada, lalu klik **Create API Key**.
   - Salin API Key yang dihasilkan.

7. Jalankan bot:
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
- `/hapuspesan`: Mengaktifkan atau menonaktifkan penghapusan pesan otomatis.

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
