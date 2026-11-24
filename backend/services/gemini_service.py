import json
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Tuple
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models import UserProfile, ChatMessage
from backend.services import schedule_service, knowledge_service

HARI_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
FALLBACK_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
]


def _generate_with_fallback(client, primary_model: str, contents, config=None):
    """Mencoba model utama, dan otomatis fallback ke model lain jika 503/404/429."""
    candidates = [primary_model] + [m for m in FALLBACK_MODELS if m != primary_model]
    last_err = None
    for model_name in candidates:
        try:
            kwargs = {"model": model_name, "contents": contents}
            if config is not None:
                kwargs["config"] = config
            return client.models.generate_content(**kwargs), model_name
        except Exception as exc:
            last_err = exc
            msg = str(exc)
            if any(code in msg for code in ("503", "UNAVAILABLE", "404", "NOT_FOUND", "429", "RESOURCE_EXHAUSTED")):
                continue
            raise
    raise last_err


def _parse_dt(val: str) -> datetime:
    cleaned = (val or "").strip().replace("Z", "")
    for fmt in (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return datetime.fromisoformat(cleaned)


def _format_schedule(s) -> dict:
    return {
        "id": s.id,
        "title": s.title,
        "start_time": s.start_time.strftime("%Y-%m-%d %H:%M"),
        "end_time": s.end_time.strftime("%Y-%m-%d %H:%M"),
        "category": s.category,
        "priority": s.priority,
        "status": s.status,
        "location": s.location or "",
        "description": s.description or "",
    }


def _build_system_prompt(db: Session) -> str:
    now = datetime.now()
    hari = HARI_ID[now.weekday()]
    profile = db.query(UserProfile).first()

    profile_txt = ""
    if profile:
        profile_txt = (
            f"Profil Karyawan:\n"
            f"- Nama: {profile.full_name}\n"
            f"- Jabatan: {profile.role_title} ({profile.department})\n"
            f"- Jam Kerja Default: {profile.work_start} - {profile.work_end} ({profile.timezone})\n"
            f"- Preferensi Kerja: {profile.preferences_note or '-'}\n"
        )

    return (
        "Anda adalah Asisten Pribadi Cerdas untuk Karyawan (Karyawan Assistant Intelligent).\n"
        f"Waktu saat ini: {hari}, {now.strftime('%Y-%m-%d %H:%M')} WIB.\n"
        f"{profile_txt}\n"
        "Tugas utama Anda:\n"
        "1. Membantu penjadwalan harian/mingguan karyawan secara cerdas menggunakan tools yang tersedia "
        "(cek jadwal, buat jadwal baru, ubah/selesaikan jadwal, hapus jadwal, cari jam kosong).\n"
        "2. Menjawab pertanyaan seputar SOP, kebijakan HR, dan dokumen kerja dengan memanggil tool "
        "`search_knowledge_base` sebelum menjawab agar jawaban akurat dan menyertakan nama dokumen sumbernya.\n"
        "3. Selalu perhatikan potensi bentrok jadwal. Jika `create_schedule` atau `update_schedule` melaporkan "
        "ada bentrok, beri tahu karyawan dengan jelas dan tawarkan alternatif jam kosong.\n"
        "4. Gunakan Bahasa Indonesia yang ramah, ringkas, profesional, dan terstruktur (gunakan bullet points/bold bila perlu).\n"
        "5. Saat membuat jadwal tanpa durasi eksplisit, gunakan durasi default 60 menit (atau 30 menit untuk reminder/sync singkat).\n"
    )


def _execute_tool(db: Session, name: str, args: Dict[str, Any]) -> Tuple[dict, dict, bool]:
    """Menjalankan tool lokal dan mengembalikan (result_for_model, action_log, schedules_modified)."""
    try:
        if name == "get_schedules":
            d_from = _parse_dt(args["date_from"]) if args.get("date_from") else None
            d_to = _parse_dt(args["date_to"]) if args.get("date_to") else None
            if d_to and len(str(args.get("date_to", "")).strip()) == 10:
                d_to = d_to.replace(hour=23, minute=59, second=59)
            items = schedule_service.list_schedules(
                db,
                date_from=d_from,
                date_to=d_to,
                status=args.get("status") or None,
                category=args.get("category") or None,
                search=args.get("search") or None,
            )
            data = [_format_schedule(x) for x in items]
            return (
                {"count": len(data), "schedules": data},
                {"tool": name, "summary": f"Membaca {len(data)} jadwal", "data": {"count": len(data)}},
                False,
            )

        if name == "create_schedule":
            start_dt = _parse_dt(args["start_time"])
            end_dt = _parse_dt(args["end_time"]) if args.get("end_time") else start_dt + timedelta(hours=1)
            item, conflicts = schedule_service.create_schedule(
                db=db,
                title=args["title"],
                start_time=start_dt,
                end_time=end_dt,
                description=args.get("description", ""),
                category=args.get("category", "meeting"),
                priority=args.get("priority", "medium"),
                location=args.get("location", ""),
                reminder_minutes=int(args.get("reminder_minutes", 15)),
            )
            conflict_list = [_format_schedule(c) for c in conflicts]
            summary = f"Jadwal dibuat: {item.title} ({item.start_time.strftime('%d/%m %H:%M')})"
            if conflict_list:
                summary += f" [Peringatan: {len(conflict_list)} bentrok]"
            return (
                {
                    "created": _format_schedule(item),
                    "has_conflict": len(conflict_list) > 0,
                    "conflicts": conflict_list,
                },
                {"tool": name, "summary": summary, "data": _format_schedule(item)},
                True,
            )

        if name == "update_schedule":
            sid = int(args["schedule_id"])
            updates: Dict[str, Any] = {}
            for k in ("title", "description", "category", "priority", "status", "location"):
                if k in args and args[k] is not None:
                    updates[k] = args[k]
            if args.get("start_time"):
                updates["start_time"] = _parse_dt(args["start_time"])
            if args.get("end_time"):
                updates["end_time"] = _parse_dt(args["end_time"])
            item, conflicts = schedule_service.update_schedule(db, sid, updates)
            if not item:
                return (
                    {"error": f"Jadwal dengan ID {sid} tidak ditemukan."},
                    {"tool": name, "summary": f"Jadwal #{sid} tidak ditemukan"},
                    False,
                )
            conflict_list = [_format_schedule(c) for c in conflicts]
            return (
                {
                    "updated": _format_schedule(item),
                    "has_conflict": len(conflict_list) > 0,
                    "conflicts": conflict_list,
                },
                {"tool": name, "summary": f"Jadwal diperbarui: {item.title} ({item.status})", "data": _format_schedule(item)},
                True,
            )

        if name == "delete_schedule":
            sid = int(args["schedule_id"])
            ok = schedule_service.delete_schedule(db, sid)
            return (
                {"deleted": ok, "schedule_id": sid},
                {"tool": name, "summary": f"Jadwal #{sid} {'dihapus' if ok else 'tidak ditemukan'}"},
                ok,
            )

        if name == "find_free_slots":
            raw_date = args.get("date") or date.today().isoformat()
            target = _parse_dt(raw_date).date()
            duration = int(args.get("duration_minutes", 60))
            slots = schedule_service.find_free_slots(db, target, duration)
            formatted = [
                {
                    "start_time": s["start_time"].strftime("%Y-%m-%d %H:%M"),
                    "end_time": s["end_time"].strftime("%Y-%m-%d %H:%M"),
                    "duration_minutes": s["duration_minutes"],
                }
                for s in slots
            ]
            return (
                {"date": target.isoformat(), "min_duration_minutes": duration, "free_slots": formatted},
                {"tool": name, "summary": f"Ditemukan {len(formatted)} slot kosong pada {target.isoformat()}"},
                False,
            )

        if name == "search_knowledge_base":
            query = args.get("query", "")
            docs = knowledge_service.search_documents(db, query, limit=4)
            return (
                {"count": len(docs), "documents": docs},
                {"tool": name, "summary": f"Mencari SOP/dokumen: '{query}' ({len(docs)} hasil)"},
                False,
            )

        return (
            {"error": f"Tool tidak dikenal: {name}"},
            {"tool": name, "summary": f"Tool tidak dikenal: {name}"},
            False,
        )
    except Exception as exc:
        return (
            {"error": str(exc)},
            {"tool": name, "summary": f"Gagal menjalankan {name}: {exc}"},
            False,
        )


def _get_gemini_tools():
    from google.genai import types

    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_schedules",
                description="Melihat daftar jadwal karyawan dalam rentang tanggal, status, kategori, atau kata kunci tertentu.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "date_from": types.Schema(type=types.Type.STRING, description="Tanggal/waktu awal format YYYY-MM-DD atau YYYY-MM-DD HH:MM"),
                        "date_to": types.Schema(type=types.Type.STRING, description="Tanggal/waktu akhir format YYYY-MM-DD atau YYYY-MM-DD HH:MM"),
                        "status": types.Schema(type=types.Type.STRING, description="Filter status: scheduled, done, atau cancelled"),
                        "category": types.Schema(type=types.Type.STRING, description="Filter kategori: meeting, deep_work, deadline, personal, reminder"),
                        "search": types.Schema(type=types.Type.STRING, description="Kata kunci pencarian judul/deskripsi/lokasi"),
                    },
                ),
            ),
            types.FunctionDeclaration(
                name="create_schedule",
                description="Membuat jadwal/kegiatan baru ke database dan otomatis memeriksa bentrok dengan jadwal lain.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    required=["title", "start_time", "end_time"],
                    properties={
                        "title": types.Schema(type=types.Type.STRING, description="Judul jadwal/kegiatan"),
                        "start_time": types.Schema(type=types.Type.STRING, description="Waktu mulai format YYYY-MM-DD HH:MM"),
                        "end_time": types.Schema(type=types.Type.STRING, description="Waktu selesai format YYYY-MM-DD HH:MM"),
                        "category": types.Schema(type=types.Type.STRING, description="meeting, deep_work, deadline, personal, atau reminder"),
                        "priority": types.Schema(type=types.Type.STRING, description="high, medium, atau low"),
                        "location": types.Schema(type=types.Type.STRING, description="Lokasi fisik atau link meeting"),
                        "description": types.Schema(type=types.Type.STRING, description="Catatan tambahan"),
                        "reminder_minutes": types.Schema(type=types.Type.INTEGER, description="Menit pengingat sebelum mulai, default 15"),
                    },
                ),
            ),
            types.FunctionDeclaration(
                name="update_schedule",
                description="Mengubah jadwal yang sudah ada (waktu, judul, prioritas, lokasi, atau status seperti menandai selesai 'done' / batal 'cancelled').",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    required=["schedule_id"],
                    properties={
                        "schedule_id": types.Schema(type=types.Type.INTEGER, description="ID jadwal yang akan diubah"),
                        "title": types.Schema(type=types.Type.STRING),
                        "start_time": types.Schema(type=types.Type.STRING, description="Format YYYY-MM-DD HH:MM"),
                        "end_time": types.Schema(type=types.Type.STRING, description="Format YYYY-MM-DD HH:MM"),
                        "category": types.Schema(type=types.Type.STRING),
                        "priority": types.Schema(type=types.Type.STRING),
                        "status": types.Schema(type=types.Type.STRING, description="scheduled, done, atau cancelled"),
                        "location": types.Schema(type=types.Type.STRING),
                        "description": types.Schema(type=types.Type.STRING),
                    },
                ),
            ),
            types.FunctionDeclaration(
                name="delete_schedule",
                description="Menghapus jadwal berdasarkan ID.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    required=["schedule_id"],
                    properties={
                        "schedule_id": types.Schema(type=types.Type.INTEGER, description="ID jadwal yang akan dihapus"),
                    },
                ),
            ),
            types.FunctionDeclaration(
                name="find_free_slots",
                description="Mencari slot jam kosong yang tersedia pada tanggal tertentu berdasarkan jam kerja karyawan.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    required=["date"],
                    properties={
                        "date": types.Schema(type=types.Type.STRING, description="Tanggal target format YYYY-MM-DD"),
                        "duration_minutes": types.Schema(type=types.Type.INTEGER, description="Durasi minimum dalam menit, default 60"),
                    },
                ),
            ),
            types.FunctionDeclaration(
                name="search_knowledge_base",
                description="Mencari informasi pada dokumen SOP, kebijakan HR, panduan kerja, dan catatan pribadi yang tersimpan.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    required=["query"],
                    properties={
                        "query": types.Schema(type=types.Type.STRING, description="Kata kunci atau topik yang dicari"),
                    },
                ),
            ),
        ]
    )


def _offline_fallback_reply(db: Session, message: str) -> Tuple[str, List[dict]]:
    """Jawaban lokal cerdas saat GEMINI_API_KEY belum diisi."""
    lower = message.lower()
    actions: List[dict] = []

    if any(k in lower for k in ("kosong", "free", "luang", "slot")):
        target = date.today() + timedelta(days=1) if "besok" in lower else date.today()
        slots = schedule_service.find_free_slots(db, target, 30)
        actions.append({"tool": "find_free_slots", "summary": f"Cek slot kosong ({target.isoformat()})"})
        if slots:
            lines = [f"- **{s['start_time'].strftime('%H:%M')} – {s['end_time'].strftime('%H:%M')}** ({s['duration_minutes']} menit)" for s in slots]
            body = f"Berikut slot waktu kosong pada **{target.strftime('%d %B %Y')}**:\n" + "\n".join(lines)
        else:
            body = f"Tidak ada slot waktu kosong pada **{target.strftime('%d %B %Y')}**."
    elif any(k in lower for k in ("jadwal", "agenda", "meeting", "hari ini", "besok")):
        target = date.today() + timedelta(days=1) if "besok" in lower else date.today()
        start = datetime(target.year, target.month, target.day, 0, 0)
        end = datetime(target.year, target.month, target.day, 23, 59, 59)
        items = schedule_service.list_schedules(db, date_from=start, date_to=end)
        actions.append({"tool": "get_schedules", "summary": f"Membaca {len(items)} jadwal ({target.isoformat()})"})
        if items:
            lines = [
                f"- **{x.start_time.strftime('%H:%M')}–{x.end_time.strftime('%H:%M')}** — {x.title} (`{x.priority}` / `{x.status}`)"
                for x in items
            ]
            body = f"Jadwal pada **{target.strftime('%d %B %Y')}**:\n" + "\n".join(lines)
        else:
            body = f"Belum ada jadwal tercatat pada **{target.strftime('%d %B %Y')}**."
    else:
        docs = knowledge_service.search_documents(db, message, limit=2)
        if docs:
            actions.append({"tool": "search_knowledge_base", "summary": f"Menemukan {len(docs)} dokumen SOP terkait"})
            parts = [f"**{d['title']}** ({d['category']}):\n{d['snippet']}" for d in docs]
            body = "Saya menemukan dokumen yang relevan di Knowledge Base:\n\n" + "\n\n---\n\n".join(parts)
        else:
            body = (
                "Saya saat ini berjalan di **Mode Lokal** karena `GEMINI_API_KEY` belum diisi.\n"
                "Anda tetap bisa menanyakan *jadwal hari ini*, *slot kosong besok*, atau mencari kata kunci dari dokumen SOP."
            )

    note = (
        "\n\n> **Tips:** Masukkan `GEMINI_API_KEY` di menu **Pengaturan** (atau file `.env`) untuk mengaktifkan "
        "percakapan AI penuh & pembuatan jadwal otomatis lewat bahasa sehari-hari."
    )
    return body + note, actions


def chat_with_assistant(
    db: Session,
    user_message: str,
    session_id: str = "default",
) -> dict:
    # Simpan pesan user
    user_row = ChatMessage(session_id=session_id, role="user", content=user_message)
    db.add(user_row)
    db.commit()

    api_key = settings.gemini_api_key
    tool_actions: List[dict] = []
    schedules_modified = False
    ai_powered = False

    if not api_key:
        reply_text, tool_actions = _offline_fallback_reply(db, user_message)
    else:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            system_prompt = _build_system_prompt(db)
            tool_def = _get_gemini_tools()

            # Ambil 10 pesan terakhir sebagai konteks percakapan
            history_rows = (
                db.query(ChatMessage)
                .filter(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.id.desc())
                .limit(12)
                .all()
            )
            history_rows.reverse()

            contents: List[types.Content] = []
            for row in history_rows:
                role = "user" if row.role == "user" else "model"
                contents.append(types.Content(role=role, parts=[types.Part.from_text(text=row.content)]))

            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=[tool_def],
                temperature=0.4,
            )

            reply_text = ""
            active_model = settings.gemini_model
            for _ in range(6):
                response, active_model = _generate_with_fallback(
                    client=client,
                    primary_model=active_model,
                    contents=contents,
                    config=config,
                )

                candidate = response.candidates[0] if response.candidates else None
                if not candidate or not candidate.content:
                    reply_text = response.text or "Maaf, saya tidak menerima respons dari Gemini."
                    break

                parts = candidate.content.parts or []
                fn_calls = [p.function_call for p in parts if getattr(p, "function_call", None)]

                if not fn_calls:
                    reply_text = response.text or "Selesai diproses."
                    break

                # Tambahkan respons model (yang berisi function call) ke contents
                contents.append(candidate.content)

                fn_response_parts = []
                for fc in fn_calls:
                    fc_name = fc.name
                    fc_args = dict(fc.args) if fc.args else {}
                    result_payload, action_log, modified = _execute_tool(db, fc_name, fc_args)
                    tool_actions.append(action_log)
                    if modified:
                        schedules_modified = True
                    fn_response_parts.append(
                        types.Part.from_function_response(
                            name=fc_name,
                            response=result_payload,
                        )
                    )

                contents.append(types.Content(role="user", parts=fn_response_parts))

            ai_powered = True
            if not reply_text:
                reply_text = "Aksi telah selesai dijalankan. Silakan cek jadwal Anda."
        except Exception as exc:
            reply_text = (
                f"Terjadi kendala saat menghubungi Gemini API: `{exc}`\n\n"
                "Pastikan `GEMINI_API_KEY` dan nama model di menu **Pengaturan** sudah benar dan koneksi internet aktif."
            )
            ai_powered = False

    assistant_row = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=reply_text,
        tool_actions_json=json.dumps(tool_actions, ensure_ascii=False) if tool_actions else None,
    )
    db.add(assistant_row)
    db.commit()
    db.refresh(assistant_row)

    return {
        "reply": reply_text,
        "tool_actions": tool_actions,
        "schedules_modified": schedules_modified,
        "ai_powered": ai_powered,
        "message_id": assistant_row.id,
    }


def generate_daily_briefing(db: Session) -> dict:
    today = date.today()
    day_start = datetime(today.year, today.month, today.day, 0, 0, 0)
    day_end = datetime(today.year, today.month, today.day, 23, 59, 59)
    today_schedules = schedule_service.list_schedules(db, date_from=day_start, date_to=day_end)
    free_slots = schedule_service.find_free_slots(db, today, duration_minutes=30)
    profile = db.query(UserProfile).first()

    hari = HARI_ID[today.weekday()]
    sched_data = [_format_schedule(s) for s in today_schedules]
    slot_data = [
        f"{s['start_time'].strftime('%H:%M')}-{s['end_time'].strftime('%H:%M')} ({s['duration_minutes']}m)"
        for s in free_slots
    ]

    if settings.gemini_api_key:
        try:
            from google import genai

            client = genai.Client(api_key=settings.gemini_api_key)
            prompt = (
                f"Buatkan Daily Briefing pagi yang singkat, hangat, dan actionable dalam Bahasa Indonesia untuk "
                f"{profile.full_name if profile else 'Karyawan'} ({profile.role_title if profile else ''}).\n"
                f"Hari/Tanggal: {hari}, {today.strftime('%d %B %Y')}.\n"
                f"Daftar jadwal hari ini: {json.dumps(sched_data, ensure_ascii=False)}\n"
                f"Slot waktu kosong: {json.dumps(slot_data, ensure_ascii=False)}\n"
                f"Preferensi kerja: {profile.preferences_note if profile else '-'}\n\n"
                "Format singkat: 1) Ringkasan agenda utama, 2) Sorotan prioritas tertinggi / potensi padat, "
                "3) Rekomendasi pemanfaatan jam kosong (maksimal 180 kata)."
            )
            resp, _used_model = _generate_with_fallback(
                client=client,
                primary_model=settings.gemini_model,
                contents=prompt,
            )
            return {
                "date": today.isoformat(),
                "briefing": resp.text or "",
                "ai_powered": True,
                "schedule_count": len(today_schedules),
            }
        except Exception:
            pass

    # Fallback briefing terstruktur tanpa API key
    pending = [s for s in today_schedules if s.status == "scheduled"]
    high = [s for s in pending if s.priority == "high"]
    lines = [
        f"**Daily Briefing — {hari}, {today.strftime('%d %B %Y')}**",
        f"Halo **{profile.full_name if profile else 'Karyawan'}**! Hari ini Anda memiliki **{len(pending)} agenda aktif** ({len(high)} prioritas tinggi).",
    ]
    if high:
        lines.append("**Prioritas Utama:** " + ", ".join(f"{x.title} ({x.start_time.strftime('%H:%M')})" for x in high))
    if slot_data:
        lines.append("**Slot Waktu Kosong:** " + ", ".join(slot_data[:3]))
    else:
        lines.append("**Catatan:** Jadwal hari ini cukup padat, pastikan tetap menyisipkan jeda istirahat.")

    return {
        "date": today.isoformat(),
        "briefing": "\n\n".join(lines),
        "ai_powered": False,
        "schedule_count": len(today_schedules),
    }
