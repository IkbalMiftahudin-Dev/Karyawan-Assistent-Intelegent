# KaryawanAI — Personal Intelligent Employee & Scheduling Assistant

Sistem asisten pribadi cerdas untuk karyawan berbasis **Python (FastAPI) + Web Frontend + MySQL (XAMPP) + Google Gemini API**.

## Fitur Utama
- **Smart Scheduling System**: Manajemen jadwal kerja (Meeting, Deep Work, Deadline, Personal, Reminder), kalender bulanan interaktif, deteksi bentrok otomatis, pencarian slot waktu kosong sesuai jam kerja, dan **AI Daily Briefing**.
- **AI Chat Assistant (Gemini API + Function Calling)**: Kelola jadwal langsung lewat bahasa sehari-hari (buat, ubah, hapus, cek jadwal & jam kosong) serta tanya jawab SOP/dokumen kerja.
- **Knowledge Base SOP**: Upload file `.pdf`, `.txt`, `.md` atau simpan catatan manual agar bisa dibaca otomatis oleh AI.
- **Auto Database Setup**: Database MySQL `karyawan_assistant` dan seluruh tabel dibuat otomatis saat server pertama kali dijalankan.

## Cara Menjalankan
1. Pastikan **MySQL di XAMPP** aktif.
2. Jalankan script:
   ```powershell
   .\run.ps1
   ```
3. Buka browser ke `http://127.0.0.1:8000` (Dokumentasi Swagger API di `http://127.0.0.1:8000/docs`).
4. Masuk ke menu **Profil & Pengaturan** (atau edit file `.env`) untuk memasukkan `GEMINI_API_KEY` dari [Google AI Studio](https://aistudio.google.com/apikey).
