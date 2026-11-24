from datetime import datetime, timedelta
import pymysql
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.config import settings

Base = declarative_base()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def ensure_database_exists() -> None:
    """Membuat database MySQL secara otomatis jika belum ada."""
    conn = pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        charset="utf8mb4",
    )
    try:
        with conn.cursor() as cursor:
            db_name = settings.db_name.replace("`", "")
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            )
        conn.commit()
    finally:
        conn.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Inisialisasi database, tabel, profil default, dan contoh data awal jika masih kosong."""
    ensure_database_exists()

    from backend.models import UserProfile, Schedule, KnowledgeDocument  # noqa: F401

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        profile = db.query(UserProfile).first()
        if not profile:
            db.add(
                UserProfile(
                    full_name="Karyawan Pribadi",
                    role_title="Staff / Professional",
                    department="Operasional",
                    work_start="08:30",
                    work_end="17:30",
                    timezone="Asia/Jakarta",
                    preferences_note="Prioritaskan deep work di pagi hari dan hindari meeting berturut-turut tanpa jeda.",
                )
            )
            db.commit()

        if db.query(KnowledgeDocument).count() == 0:
            starter_docs = [
                KnowledgeDocument(
                    title="SOP Pengajuan Cuti & Izin Kerja",
                    category="HR & Cuti",
                    filename="sop_cuti_izin.md",
                    content=(
                        "# SOP Pengajuan Cuti & Izin Kerja\n"
                        "1. Cuti Tahunan: Karyawan berhak atas 12 hari cuti tahunan setelah bekerja minimal 12 bulan.\n"
                        "2. Pengajuan cuti tahunan dilakukan minimal H-3 sebelum tanggal cuti melalui atasan langsung dan sistem HR.\n"
                        "3. Izin Sakit: Wajib melampirkan surat keterangan dokter jika sakit lebih dari 1 hari kerja.\n"
                        "4. Cuti Mendadak / Keperluan Keluarga: Segera hubungi atasan sebelum jam 09:00 WIB.\n"
                        "5. Sisa cuti maksimal 4 hari dapat dibawa ke kuartal pertama tahun berikutnya."
                    ),
                ),
                KnowledgeDocument(
                    title="Panduan Jam Kerja, Meeting & Fokus Harian",
                    category="SOP Kerja",
                    filename="panduan_jam_kerja.md",
                    content=(
                        "# Panduan Jam Kerja & Manajemen Waktu\n"
                        "- Jam kerja standar: Senin–Jumat pukul 08:30–17:30 WIB (istirahat 12:00–13:00 WIB).\n"
                        "- Waktu Deep Work ideal: 09:00–11:30 WIB untuk tugas prioritas tinggi tanpa gangguan meeting.\n"
                        "- Standar durasi meeting: 30 menit untuk sinkronisasi cepat, maksimal 60 menit untuk evaluasi proyek.\n"
                        "- Laporan progres harian dikirim paling lambat pukul 17:00 WIB."
                    ),
                ),
            ]
            db.add_all(starter_docs)
            db.commit()

        if db.query(Schedule).count() == 0:
            today = datetime.now().replace(minute=0, second=0, microsecond=0)
            base_day = today.replace(hour=9, minute=0)
            starter_schedules = [
                Schedule(
                    title="Review Prioritas & Rencana Kerja Harian",
                    description="Cek target harian, email penting, dan susun daftar tugas utama.",
                    start_time=base_day,
                    end_time=base_day + timedelta(minutes=45),
                    category="deep_work",
                    priority="high",
                    status="scheduled",
                    location="Meja Kerja",
                    reminder_minutes=15,
                ),
                Schedule(
                    title="Sinkronisasi Progres Mingguan",
                    description="Update progres pekerjaan dan identifikasi kendala bersama tim.",
                    start_time=base_day.replace(hour=10, minute=30),
                    end_time=base_day.replace(hour=11, minute=30),
                    category="meeting",
                    priority="medium",
                    status="scheduled",
                    location="Google Meet",
                    reminder_minutes=15,
                ),
                Schedule(
                    title="Fokus Penyelesaian Tugas Utama",
                    description="Blok waktu khusus tanpa gangguan untuk menyelesaikan deliverable utama.",
                    start_time=base_day.replace(hour=13, minute=30),
                    end_time=base_day.replace(hour=15, minute=30),
                    category="deep_work",
                    priority="high",
                    status="scheduled",
                    location="Workspace",
                    reminder_minutes=10,
                ),
            ]
            db.add_all(starter_schedules)
            db.commit()
    finally:
        db.close()
