from __future__ import annotations

import datetime as dt
import base64
import csv
import hashlib
import hmac
import io
import json
import math
import os
import re
import secrets
import sqlite3
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, Field

from politometro_scientific import AXIS_SHORT, CALIBRATION_NOTES, MODEL_VERSION, QUESTIONS, QUICK_QUESTION_IDS, SOCIAL_QUESTION_IDS, SOURCE_REFERENCES, build_model_audit, build_result


app = FastAPI(title="Politometro Custom")

DATA_DIR = Path(os.environ.get("POLITOMETRO_DATA_DIR", "data"))
SQLITE_PATH = Path(os.environ.get("POLITOMETRO_SQLITE_PATH", str(DATA_DIR / "politometro.sqlite3")))
ADMIN_EMAIL = os.environ.get("POLITOMETRO_ADMIN_EMAIL", "").strip().lower()
ADMIN_PASSWORD_HASH = os.environ.get("POLITOMETRO_ADMIN_PASSWORD_HASH", "").strip()
SESSION_SECRET = os.environ.get("POLITOMETRO_SESSION_SECRET", "")
AUTH_COOKIE = "politometro_admin"
AUTH_MAX_AGE_SECONDS = 60 * 60 * 12
COOKIE_SECURE = os.environ.get("POLITOMETRO_COOKIE_SECURE", "").lower() in {"1", "true", "yes", "on"}


class AnswerPayload(BaseModel):
    answers: dict[str, int]
    research_consent: bool = False
    demographics: dict[str, str] = Field(default_factory=dict)
    session_id: str = ""
    mode: str = "deep"


class FeedbackPayload(BaseModel):
    research_consent: bool = False
    session_id: str = ""
    accuracy_rating: int
    self_label: str = ""
    closest_party_self: str = ""
    notes: str = ""
    predicted_ideology: str = ""
    predicted_parties: list[str] = []


class ReportPayload(BaseModel):
    answers: dict[str, int]
    mode: str = "deep"


class AdminLoginPayload(BaseModel):
    email: str
    password: str


class SupportPayload(BaseModel):
    contact_type: str = "supporto"
    email: str
    name: str = ""
    organization: str = ""
    message: str
    consent_contact: bool = False


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return HTML


@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request):
    if not is_admin_request(request):
        return RedirectResponse("/login", status_code=303)
    return ADMIN_HTML


@app.get("/login", response_class=HTMLResponse)
def login_page() -> str:
    return LOGIN_HTML


@app.post("/api/admin/login")
def admin_login(payload: AdminLoginPayload):
    if not admin_auth_configured():
        raise HTTPException(status_code=503, detail="Login admin non configurato: imposta email, password hash e secret nelle variabili ambiente.")
    email = payload.email.strip().lower()
    if email != ADMIN_EMAIL or not verify_password(payload.password, ADMIN_PASSWORD_HASH):
        raise HTTPException(status_code=401, detail="Credenziali non valide.")
    response = JSONResponse({"ok": True, "redirect": "/admin"})
    response.set_cookie(
        AUTH_COOKIE,
        make_auth_token(email),
        max_age=AUTH_MAX_AGE_SECONDS,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    return response


@app.post("/api/admin/logout")
def admin_logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(AUTH_COOKIE, path="/")
    return response


@app.get("/manifest.webmanifest")
def manifest():
    return JSONResponse(
        {
            "name": "Politometro",
            "short_name": "Politometro",
            "description": "Test politico multi-asse con report, mappe e dashboard locale.",
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "display_override": ["standalone", "minimal-ui"],
            "id": "/",
            "orientation": "portrait-primary",
            "background_color": "#f6f8f8",
            "theme_color": "#10242f",
            "categories": ["education", "utilities", "social"],
            "shortcuts": [
                {"name": "Inizia test", "url": "/", "description": "Apri Politometro"},
                {"name": "Dashboard privata", "url": "/admin", "description": "Leggi trend e feedback locali"},
            ],
            "icons": [
                {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
                {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
                {"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any"},
            ],
        },
        media_type="application/manifest+json",
    )


@app.get("/icon.svg")
def icon():
    return Response(
        """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
<defs>
<linearGradient id="g" x1="64" y1="42" x2="450" y2="474" gradientUnits="userSpaceOnUse">
<stop stop-color="#38a3a5"/><stop offset=".46" stop-color="#f2b880"/><stop offset="1" stop-color="#6d597a"/>
</linearGradient>
<radialGradient id="r" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(142 116) rotate(48) scale(410)">
<stop stop-color="#ffffff" stop-opacity=".62"/><stop offset=".46" stop-color="#ffffff" stop-opacity=".08"/><stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
</radialGradient>
</defs>
<rect width="512" height="512" rx="92" fill="#10242f"/>
<rect x="54" y="54" width="404" height="404" rx="76" fill="url(#g)"/>
<rect x="54" y="54" width="404" height="404" rx="76" fill="url(#r)"/>
<circle cx="256" cy="256" r="126" fill="#10242f" fill-opacity=".92"/>
<path d="M256 154 292 228 256 256 220 228Z M358 256 284 292 256 256 284 220Z M256 358 220 284 256 256 292 284Z M154 256 228 220 256 256 228 292Z" fill="#f6f8f8"/>
<circle cx="256" cy="256" r="44" fill="#10242f"/>
<circle cx="256" cy="256" r="20" fill="#f2b880"/>
</svg>""",
        media_type="image/svg+xml",
    )


def generated_icon_png(size: int) -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (size, size), "#10242f")
    draw = ImageDraw.Draw(img)
    margin = int(size * 0.105)
    draw.rounded_rectangle([margin, margin, size - margin, size - margin], radius=int(size * 0.18), fill="#38a3a5")
    draw.pieslice([margin, margin, size - margin, size - margin], 35, 145, fill="#f2b880")
    draw.pieslice([margin, margin, size - margin, size - margin], 145, 265, fill="#6d597a")
    draw.pieslice([margin, margin, size - margin, size - margin], 265, 395, fill="#38a3a5")
    cx = cy = size // 2
    draw.ellipse([cx - int(size * .245), cy - int(size * .245), cx + int(size * .245), cy + int(size * .245)], fill="#10242f")
    outer = int(size * 0.20)
    inner = int(size * 0.070)
    draw.polygon([(cx, cy - outer), (cx + inner, cy - inner), (cx, cy), (cx - inner, cy - inner)], fill="#f6f8f8")
    draw.polygon([(cx + outer, cy), (cx + inner, cy + inner), (cx, cy), (cx + inner, cy - inner)], fill="#f6f8f8")
    draw.polygon([(cx, cy + outer), (cx - inner, cy + inner), (cx, cy), (cx + inner, cy + inner)], fill="#f6f8f8")
    draw.polygon([(cx - outer, cy), (cx - inner, cy - inner), (cx, cy), (cx - inner, cy + inner)], fill="#f6f8f8")
    dot = int(size * 0.074)
    draw.ellipse([cx - dot, cy - dot, cx + dot, cy + dot], fill="#10242f")
    dot2 = int(size * 0.04)
    draw.ellipse([cx - dot2, cy - dot2, cx + dot2, cy + dot2], fill="#f2b880")
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()


@app.get("/icon-192.png")
def icon_192():
    return Response(generated_icon_png(192), media_type="image/png")


@app.get("/icon-512.png")
def icon_512():
    return Response(generated_icon_png(512), media_type="image/png")


@app.get("/sw.js")
def service_worker():
    return Response(
        """
const CACHE = "politometro-v8";
const CORE = ["/", "/manifest.webmanifest", "/icon.svg", "/icon-192.png", "/icon-512.png"];
self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(CORE)));
  self.skipWaiting();
});
self.addEventListener("activate", event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))));
  self.clients.claim();
});
self.addEventListener("fetch", event => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.pathname.startsWith("/api/") || url.pathname === "/admin" || url.pathname.startsWith("/admin/") || url.pathname === "/login" || url.pathname.startsWith("/login/")) return;
  event.respondWith(fetch(request).then(response => {
    if (!response || !response.ok || response.type === "opaque") return response;
    const copy = response.clone();
    caches.open(CACHE).then(cache => cache.put(request, copy));
    return response;
  }).catch(() => caches.match(request).then(cached => cached || caches.match("/"))));
});
""",
        media_type="text/javascript",
    )


def question_payload() -> dict:
    return {
        "model_version": MODEL_VERSION,
        "quick_question_ids": QUICK_QUESTION_IDS,
        "social_question_ids": SOCIAL_QUESTION_IDS,
        "calibration": CALIBRATION_NOTES,
        "questions": [
            {
                "id": q["id"],
                "question": q["question"],
                "options": q["options"],
                "quick": q.get("quick", False),
            }
            for q in QUESTIONS
        ]
    }


@app.get("/api/questions")
def questions():
    return question_payload()


@app.get("/api/audit")
def audit():
    return {"model_version": MODEL_VERSION, "audit": build_model_audit(), "sources": SOURCE_REFERENCES}


@app.get("/api/research-summary")
def research_summary():
    path = DATA_DIR / "research_samples.jsonl"
    rows = []
    if path.exists():
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    rows.append(json.loads(line))

    ideology_counts: dict[str, int] = {}
    demographic_counts: dict[str, dict[str, int]] = {}
    confidence_values = []
    reliability_values = []
    for row in rows:
        ideology = (row.get("ideology") or {}).get("name", "Sconosciuta")
        ideology_counts[ideology] = ideology_counts.get(ideology, 0) + 1
        demographics = row.get("demographics") or {}
        for key, value in demographics.items():
            if not value:
                continue
            demographic_counts.setdefault(key, {})
            demographic_counts[key][value] = demographic_counts[key].get(value, 0) + 1
        if isinstance(row.get("confidence"), (int, float)):
            confidence_values.append(float(row["confidence"]))
        reliability = row.get("reliability") or {}
        if isinstance(reliability.get("score") if isinstance(reliability, dict) else None, (int, float)):
            reliability_values.append(float(reliability["score"]))

    feedback_path = DATA_DIR / "research_feedback.jsonl"
    feedback_rows = []
    if feedback_path.exists():
        with feedback_path.open(encoding="utf-8") as handle:
            feedback_rows = [json.loads(line) for line in handle if line.strip()]

    ratings = [float(row["accuracy_rating"]) for row in feedback_rows if isinstance(row.get("accuracy_rating"), int)]

    support_path = DATA_DIR / "support_contacts.jsonl"
    support_rows = []
    if support_path.exists():
        with support_path.open(encoding="utf-8") as handle:
            support_rows = [json.loads(line) for line in handle if line.strip()]

    return {
        "samples": len(rows),
        "feedback_samples": len(feedback_rows),
        "support_contacts": len(support_rows),
        "model_version": MODEL_VERSION,
        "average_confidence": round(sum(confidence_values) / len(confidence_values), 1) if confidence_values else None,
        "average_reliability": round(sum(reliability_values) / len(reliability_values), 1) if reliability_values else None,
        "average_accuracy_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
        "ideology_counts": ideology_counts,
        "demographic_counts": demographic_counts,
        "storage": str(path),
        "feedback_storage": str(feedback_path),
        "support_storage": str(support_path),
    }


@app.get("/api/private-analytics")
def private_analytics(request: Request):
    if not is_admin_request(request):
        raise HTTPException(status_code=401, detail="Login admin richiesto.")
    return build_private_analytics()


@app.get("/api/admin/export/{kind}")
def admin_export(kind: str, request: Request):
    if not is_admin_request(request):
        raise HTTPException(status_code=401, detail="Login admin richiesto.")
    samples = load_jsonl(DATA_DIR / "research_samples.jsonl")
    feedback_rows = load_jsonl(DATA_DIR / "research_feedback.jsonl")
    support_rows = load_jsonl(DATA_DIR / "support_contacts.jsonl")
    if kind == "samples.csv":
        return csv_download([flatten_sample(row) for row in samples], "politometro-samples.csv")
    if kind == "feedback.csv":
        return csv_download([flatten_feedback(row) for row in feedback_rows], "politometro-feedback.csv")
    if kind == "contacts.csv":
        return csv_download([flatten_support(row) for row in support_rows], "politometro-contatti.csv")
    if kind == "analytics.json":
        return JSONResponse(
            build_private_analytics(),
            headers={"Content-Disposition": 'attachment; filename="politometro-analytics.json"'},
        )
    raise HTTPException(status_code=404, detail="Export non trovato.")


@app.post("/api/result")
def result(payload: AnswerPayload):
    try:
        computed = build_result(payload.answers)
        computed["mode"] = safe_mode(payload.mode)
        if payload.research_consent:
            save_research_sample(payload.answers, computed, payload.demographics, payload.session_id, payload.mode)
        return computed
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/feedback")
def feedback(payload: FeedbackPayload):
    if not payload.research_consent:
        return {"saved": False, "message": "Feedback non salvato per assenza di consenso ricerca."}
    if payload.accuracy_rating < 1 or payload.accuracy_rating > 5:
        raise HTTPException(status_code=400, detail="Valutazione fuori scala.")
    save_research_feedback(payload)
    return {"saved": True}


@app.post("/api/support-contact")
def support_contact(payload: SupportPayload):
    if not payload.consent_contact:
        raise HTTPException(status_code=400, detail="Serve consenso per salvare la richiesta di contatto.")
    save_support_contact(payload)
    return {"saved": True, "message": "Richiesta salvata. Nella versione pubblica andrà collegata a email o CRM."}


@app.post("/api/report-pdf")
def report_pdf(payload: ReportPayload):
    try:
        computed = build_result(payload.answers)
        computed["mode"] = safe_mode(payload.mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    path = create_pdf_report(computed)
    return FileResponse(path, media_type="application/pdf", filename="politometro-report.pdf")


def save_research_sample(answers: dict[str, int], computed: dict, demographics: dict[str, str], session_id: str, mode: str) -> None:
    data_dir = DATA_DIR
    data_dir.mkdir(parents=True, exist_ok=True)
    sample = {
        "timestamp_utc": dt.datetime.now(dt.UTC).isoformat(),
        "consent_version": "2026-05-25-local-research-v1",
        "model_version": computed.get("model_version", MODEL_VERSION),
        "session_id": safe_token(session_id),
        "mode": safe_mode(mode),
        "answers": answers,
        "demographics": sanitize_demographics(demographics),
        "profile": computed.get("profile"),
        "confidence": computed.get("confidence"),
        "self_coherence": computed.get("self_coherence"),
        "reliability": computed.get("reliability"),
        "uncertainty": computed.get("uncertainty"),
        "ideology": computed.get("ideology"),
        "ideologies": computed.get("ideologies"),
        "parties": computed.get("parties"),
        "historical": computed.get("historical"),
        "historical_nemesis": computed.get("historical_nemesis"),
        "contradictions_count": len(computed.get("contradictions", [])),
    }
    with (data_dir / "research_samples.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(sample, ensure_ascii=False) + "\n")
    save_sample_sqlite(sample)


def sanitize_demographics(demographics: dict[str, str]) -> dict[str, str]:
    allowed = {
        "age_range",
        "education",
        "origin_area",
        "country_region",
        "political_interest",
        "political_knowledge",
        "news_frequency",
        "student_worker",
    }
    clean = {}
    for key in allowed:
        value = str(demographics.get(key, "")).strip()
        if value:
            clean[key] = value[:120]
    return clean


def save_research_feedback(payload: FeedbackPayload) -> None:
    data_dir = DATA_DIR
    data_dir.mkdir(parents=True, exist_ok=True)
    sample = {
        "timestamp_utc": dt.datetime.now(dt.UTC).isoformat(),
        "consent_version": "2026-05-25-local-research-v1",
        "model_version": MODEL_VERSION,
        "session_id": safe_token(payload.session_id),
        "accuracy_rating": payload.accuracy_rating,
        "self_label": payload.self_label[:200],
        "closest_party_self": payload.closest_party_self[:200],
        "notes": payload.notes[:1000],
        "predicted_ideology": payload.predicted_ideology[:200],
        "predicted_parties": payload.predicted_parties[:10],
    }
    with (data_dir / "research_feedback.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(sample, ensure_ascii=False) + "\n")
    save_feedback_sqlite(sample)


def save_support_contact(payload: SupportPayload) -> None:
    data_dir = DATA_DIR
    data_dir.mkdir(parents=True, exist_ok=True)
    sample = {
        "timestamp_utc": dt.datetime.now(dt.UTC).isoformat(),
        "contact_type": payload.contact_type[:80],
        "email": payload.email.strip()[:200],
        "name": payload.name.strip()[:160],
        "organization": payload.organization.strip()[:200],
        "message": payload.message.strip()[:3000],
        "consent_contact": bool(payload.consent_contact),
    }
    with (data_dir / "support_contacts.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(sample, ensure_ascii=False) + "\n")
    save_support_sqlite(sample)


def create_pdf_report(computed: dict) -> str:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    path = str(Path(tempfile.gettempdir()) / f"politometro-report-{safe_token(computed.get('model_version', MODEL_VERSION))}.pdf")
    doc = SimpleDocTemplate(path, pagesize=A4, rightMargin=1.5 * cm, leftMargin=1.5 * cm, topMargin=1.4 * cm, bottomMargin=1.4 * cm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Hero", parent=styles["Title"], fontSize=24, leading=28, textColor=colors.HexColor("#10242f"), spaceAfter=8))
    styles.add(ParagraphStyle(name="Muted", parent=styles["Normal"], fontSize=9, leading=12, textColor=colors.HexColor("#60707c")))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], fontSize=14, textColor=colors.HexColor("#22577a"), spaceBefore=12, spaceAfter=8))

    story = [
        Paragraph("Politometro - Report personale", styles["Hero"]),
        Paragraph(f"Modello: {computed.get('model_version')} - Modalita: {computed.get('mode', 'deep')} - Completezza: {computed.get('completion')}% - Confidenza: {computed.get('confidence')}%", styles["Muted"]),
        Spacer(1, 0.25 * cm),
        Paragraph(f"Profilo dominante: {computed['ideology']['name']}", styles["Section"]),
        Paragraph(
            f"{computed['interpretation']['family']}; {computed['interpretation']['culture']}; {computed['interpretation']['geopolitics']}.",
            styles["Normal"],
        ),
        Paragraph("Coerenza interna", styles["Section"]),
        Paragraph(
            f"{computed.get('self_coherence', {}).get('label', 'n/d')} - {computed.get('self_coherence', {}).get('score', 'n/d')}%. "
            f"{computed.get('self_coherence', {}).get('explanation', '')}",
            styles["Normal"],
        ),
        Paragraph("Affidabilità interpretativa", styles["Section"]),
        Paragraph(
            f"{computed.get('reliability', {}).get('label', 'n/d')} - {computed.get('reliability', {}).get('score', 'n/d')}%. "
            f"{computed.get('reliability', {}).get('explanation', '')}",
            styles["Normal"],
        ),
    ]

    axis_rows = [["Asse", "Valore", "Confidenza", "Interpretazione"]]
    for axis in computed["axes"]:
        axis_rows.append([axis["name"], f"{axis['value']:+.2f}", f"{axis['confidence'] * 100:.0f}%", axis["explanation"]])
    axis_table = Table(axis_rows, colWidths=[3.0 * cm, 2.0 * cm, 2.4 * cm, 10.0 * cm])
    axis_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#10242f")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d9e1e7")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f8f8")]),
            ]
        )
    )
    story.extend([Paragraph("Assi politici", styles["Section"]), axis_table])

    def match_table(title: str, items: list[dict]) -> None:
        rows = [["Nome", "Affinita", "Distanza"]]
        for item in items:
            rows.append([item["name"], f"{item.get('affinity', 0):.1f}%", str(item.get("distance", ""))])
        table = Table(rows, colWidths=[10 * cm, 3 * cm, 3 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#22577a")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d9e1e7")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f8f8")]),
                ]
            )
        )
        story.extend([Paragraph(title, styles["Section"]), table])

    match_table("Partiti più vicini", computed.get("parties", []))
    match_table("Confronti storici comparabili", computed.get("historical", []))
    match_table("Nemesi storica metodologica", computed.get("historical_nemesis", []))

    story.append(Paragraph("Risposte che hanno pesato di più", styles["Section"]))
    for item in computed.get("top_contributions", [])[:8]:
        story.append(Paragraph(f"{item['question']} - risposta {item['answer']} - {item['primary_axis']} ({item['contribution']:+.3f})", styles["Normal"]))

    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Nota metodologica: il report è interpretativo, non diagnostico. Le correlazioni e i confronti diventano più affidabili solo con dati consensuali numerosi e fonti esterne calibrate.", styles["Muted"]))
    doc.build(story)
    return path


def safe_mode(value: str) -> str:
    clean = str(value).strip().lower()
    if clean in {"social", "quick"}:
        return clean
    return "deep"


def safe_token(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "", str(value))[:80]


def admin_auth_configured() -> bool:
    return bool(ADMIN_EMAIL and ADMIN_PASSWORD_HASH and SESSION_SECRET and SESSION_SECRET != "dev-only-change-me")


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, rounds_raw, salt_b64, digest_b64 = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        rounds = int(rounds_raw)
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_b64.encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def make_auth_token(email: str) -> str:
    issued = str(int(dt.datetime.now(dt.UTC).timestamp()))
    nonce = secrets.token_urlsafe(12)
    payload = f"{email}|{issued}|{nonce}"
    signature = hmac.new(SESSION_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}|{signature}".encode("utf-8")).decode("ascii")


def verify_auth_token(token: str) -> bool:
    if not admin_auth_configured() or not token:
        return False
    try:
        decoded = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        email, issued_raw, nonce, signature = decoded.split("|", 3)
        payload = f"{email}|{issued_raw}|{nonce}"
        expected = hmac.new(SESSION_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        issued = int(issued_raw)
        now = int(dt.datetime.now(dt.UTC).timestamp())
        return email == ADMIN_EMAIL and now - issued <= AUTH_MAX_AGE_SECONDS and hmac.compare_digest(signature, expected)
    except Exception:
        return False


def is_admin_request(request: Request) -> bool:
    return verify_auth_token(request.cookies.get(AUTH_COOKIE, ""))


def sqlite_enabled() -> bool:
    return os.environ.get("POLITOMETRO_DISABLE_SQLITE", "").lower() not in {"1", "true", "yes"}


def sqlite_connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(SQLITE_PATH)
    conn.execute("pragma journal_mode = wal")
    conn.execute("pragma foreign_keys = on")
    return conn


def init_sqlite() -> None:
    if not sqlite_enabled():
        return
    with sqlite_connect() as conn:
        conn.executescript(
            """
            create table if not exists research_samples (
              id integer primary key autoincrement,
              timestamp_utc text not null,
              session_id text,
              mode text,
              model_version text,
              confidence real,
              self_coherence real,
              reliability_score real,
              reliability_label text,
              ideology_name text,
              top_party_name text,
              top_historical_name text,
              nemesis_name text,
              raw_json text not null
            );
            create table if not exists research_feedback (
              id integer primary key autoincrement,
              timestamp_utc text not null,
              session_id text,
              accuracy_rating integer,
              predicted_ideology text,
              raw_json text not null
            );
            create table if not exists support_contacts (
              id integer primary key autoincrement,
              timestamp_utc text not null,
              contact_type text,
              email text,
              organization text,
              raw_json text not null
            );
            create index if not exists pm_samples_session_idx on research_samples(session_id);
            create index if not exists pm_samples_time_idx on research_samples(timestamp_utc);
            create index if not exists pm_feedback_session_idx on research_feedback(session_id);
            create index if not exists pm_support_time_idx on support_contacts(timestamp_utc);
            """
        )
        existing = {row[1] for row in conn.execute("pragma table_info(research_samples)")}
        migrations = {
            "reliability_score": "real",
            "reliability_label": "text",
            "top_historical_name": "text",
            "nemesis_name": "text",
        }
        for column, column_type in migrations.items():
            if column not in existing:
                conn.execute(f"alter table research_samples add column {column} {column_type}")


def save_sample_sqlite(sample: dict) -> None:
    if not sqlite_enabled():
        return
    init_sqlite()
    self_coherence = sample.get("self_coherence") or {}
    reliability = sample.get("reliability") or {}
    ideology = sample.get("ideology") or {}
    parties = sample.get("parties") or []
    historical = sample.get("historical") or []
    nemesis = sample.get("historical_nemesis") or []
    with sqlite_connect() as conn:
        conn.execute(
            """
            insert into research_samples (
              timestamp_utc, session_id, mode, model_version, confidence, self_coherence,
              reliability_score, reliability_label, ideology_name, top_party_name,
              top_historical_name, nemesis_name, raw_json
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sample.get("timestamp_utc"),
                sample.get("session_id"),
                sample.get("mode"),
                sample.get("model_version"),
                sample.get("confidence"),
                self_coherence.get("score") if isinstance(self_coherence, dict) else None,
                reliability.get("score") if isinstance(reliability, dict) else None,
                reliability.get("label") if isinstance(reliability, dict) else None,
                ideology.get("name") if isinstance(ideology, dict) else None,
                parties[0].get("name") if parties and isinstance(parties[0], dict) else None,
                historical[0].get("name") if historical and isinstance(historical[0], dict) else None,
                nemesis[0].get("name") if nemesis and isinstance(nemesis[0], dict) else None,
                json.dumps(sample, ensure_ascii=False),
            ),
        )


def save_feedback_sqlite(sample: dict) -> None:
    if not sqlite_enabled():
        return
    init_sqlite()
    with sqlite_connect() as conn:
        conn.execute(
            """
            insert into research_feedback (
              timestamp_utc, session_id, accuracy_rating, predicted_ideology, raw_json
            ) values (?, ?, ?, ?, ?)
            """,
            (
                sample.get("timestamp_utc"),
                sample.get("session_id"),
                sample.get("accuracy_rating"),
                sample.get("predicted_ideology"),
                json.dumps(sample, ensure_ascii=False),
            ),
        )


def save_support_sqlite(sample: dict) -> None:
    if not sqlite_enabled():
        return
    init_sqlite()
    with sqlite_connect() as conn:
        conn.execute(
            """
            insert into support_contacts (
              timestamp_utc, contact_type, email, organization, raw_json
            ) values (?, ?, ?, ?, ?)
            """,
            (
                sample.get("timestamp_utc"),
                sample.get("contact_type"),
                sample.get("email"),
                sample.get("organization"),
                json.dumps(sample, ensure_ascii=False),
            ),
        )


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def mean(values: list[float]) -> float | None:
    clean = [float(value) for value in values if isinstance(value, (int, float))]
    return round(sum(clean) / len(clean), 4) if clean else None


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mx) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - my) ** 2 for y in ys))
    if den_x == 0 or den_y == 0:
        return None
    return round(num / (den_x * den_y), 4)


ORDINAL_MAPS = {
    "age_range": {"meno di 18": 1, "18-24": 2, "25-34": 3, "35-44": 4, "45-54": 5, "55-64": 6, "65+": 7},
    "education": {
        "Scuola media o inferiore": 1,
        "Diploma superiore": 2,
        "Laurea triennale": 3,
        "Laurea magistrale o ciclo unico": 4,
        "Dottorato / master avanzato": 5,
        "Altro percorso": 2,
    },
    "political_interest": {"Molto basso": 1, "Basso": 2, "Medio": 3, "Alto": 4, "Molto alto": 5},
    "political_knowledge": {"Principiante": 1, "Base": 2, "Intermedia": 3, "Avanzata": 4, "Studio/lavoro nel settore": 5},
    "news_frequency": {
        "Quasi mai": 1,
        "Qualche volta al mese": 2,
        "Settimanalmente": 3,
        "Quasi ogni giorno": 4,
        "Ogni giorno da più fonti": 5,
    },
}


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def safe_csv_value(value) -> str | int | float | None:
    if isinstance(value, (str, int, float)) or value is None:
        return value
    return json.dumps(value, ensure_ascii=False)


def csv_download(rows: list[dict], filename: str) -> Response:
    output = io.StringIO()
    fieldnames = sorted({key for row in rows for key in row.keys()}) if rows else ["empty"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: safe_csv_value(row.get(key, "")) for key in fieldnames})
    return Response(
        output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def flatten_sample(row: dict) -> dict:
    demographics = row.get("demographics") or {}
    self_coherence = row.get("self_coherence") or {}
    reliability = row.get("reliability") or {}
    ideology = row.get("ideology") or {}
    parties = row.get("parties") or []
    historical = row.get("historical") or []
    nemesis = row.get("historical_nemesis") or []
    profile = row.get("profile") or []
    out = {
        "timestamp_utc": row.get("timestamp_utc", ""),
        "session_id": row.get("session_id", ""),
        "mode": row.get("mode", ""),
        "model_version": row.get("model_version", ""),
        "confidence": row.get("confidence", ""),
        "self_coherence": self_coherence.get("score", "") if isinstance(self_coherence, dict) else "",
        "reliability": reliability.get("score", "") if isinstance(reliability, dict) else "",
        "reliability_label": reliability.get("label", "") if isinstance(reliability, dict) else "",
        "ideology": ideology.get("name", "") if isinstance(ideology, dict) else "",
        "top_party": parties[0].get("name", "") if parties and isinstance(parties[0], dict) else "",
        "top_party_affinity": parties[0].get("affinity", "") if parties and isinstance(parties[0], dict) else "",
        "top_historical": historical[0].get("name", "") if historical and isinstance(historical[0], dict) else "",
        "nemesis": nemesis[0].get("name", "") if nemesis and isinstance(nemesis[0], dict) else "",
        "contradictions_count": row.get("contradictions_count", ""),
        "answers_json": row.get("answers", {}),
    }
    for key in ["age_range", "education", "origin_area", "country_region", "political_interest", "political_knowledge", "news_frequency", "student_worker"]:
        out[key] = demographics.get(key, "")
    for idx, axis in enumerate(AXIS_SHORT):
        out[f"axis_{normalize_text(axis)}"] = profile[idx] if idx < len(profile) else ""
    return out


def flatten_feedback(row: dict) -> dict:
    return {
        "timestamp_utc": row.get("timestamp_utc", ""),
        "session_id": row.get("session_id", ""),
        "accuracy_rating": row.get("accuracy_rating", ""),
        "self_label": row.get("self_label", ""),
        "closest_party_self": row.get("closest_party_self", ""),
        "predicted_ideology": row.get("predicted_ideology", ""),
        "predicted_parties": row.get("predicted_parties", []),
        "notes": row.get("notes", ""),
    }


def flatten_support(row: dict) -> dict:
    return {
        "timestamp_utc": row.get("timestamp_utc", ""),
        "contact_type": row.get("contact_type", ""),
        "email": row.get("email", ""),
        "name": row.get("name", ""),
        "organization": row.get("organization", ""),
        "message": row.get("message", ""),
        "consent_contact": row.get("consent_contact", ""),
    }


def build_private_analytics() -> dict:
    samples = load_jsonl(DATA_DIR / "research_samples.jsonl")
    feedback = load_jsonl(DATA_DIR / "research_feedback.jsonl")
    support = load_jsonl(DATA_DIR / "support_contacts.jsonl")
    feedback_by_session = {row.get("session_id"): row for row in feedback if row.get("session_id")}
    joined = [row | {"feedback": feedback_by_session[row.get("session_id")]} for row in samples if row.get("session_id") in feedback_by_session]

    summary = research_summary()
    response_gaps = strongest_response_gaps(samples)
    demographic_breakdowns = build_demographic_breakdowns(samples)
    ordinal = build_ordinal_correlations(samples, joined)
    feedback_stats = build_feedback_stats(feedback, joined)
    time_trends = build_time_trends(samples, feedback)
    dataset_health = build_dataset_health(samples, feedback, support, summary)
    auto_insights = build_auto_insights(samples, feedback, ordinal, response_gaps, demographic_breakdowns, dataset_health)

    return {
        "model_version": MODEL_VERSION,
        "privacy": "Dashboard privata. Legge solo dati consensuali locali; online serviranno database, login admin, informativa privacy e controlli di accesso.",
        "minimum_sample_note": "Le correlazioni sono esplorative: sotto 30 campioni totali e 20 per gruppo vanno lette solo come indizi.",
        "dataset_health": dataset_health,
        "auto_insights": auto_insights,
        "summary": summary,
        "time_trends": time_trends,
        "demographic_breakdowns": demographic_breakdowns,
        "strongest_response_gaps": response_gaps,
        "ordinal_correlations": ordinal,
        "feedback": feedback_stats,
    }


def build_dataset_health(samples: list[dict], feedback: list[dict], support: list[dict], summary: dict) -> dict:
    n = len(samples)
    if n >= 1000:
        stage = "scala"
        label = "Pronto per analisi robuste"
        next_goal = "Ricalibrare pesi, percentili e stabilità del modello."
    elif n >= 300:
        stage = "validazione"
        label = "Pronto per analisi fattoriale esplorativa"
        next_goal = "Controllare assi ridondanti, item deboli e bias demografici."
    elif n >= 100:
        stage = "beta"
        label = "Pronto per primi report interni"
        next_goal = "Usare i trend per correggere domande, non per vendere conclusioni forti."
    elif n >= 30:
        stage = "early"
        label = "Prime indicazioni"
        next_goal = "Raccogliere almeno 100 risposte consensuali."
    else:
        stage = "setup"
        label = "Dataset ancora iniziale"
        next_goal = "Testare il flusso e raccogliere i primi campioni con consenso."

    demographic_completion = {}
    for key in ["age_range", "education", "origin_area", "political_interest", "political_knowledge", "news_frequency"]:
        filled = sum(1 for row in samples if (row.get("demographics") or {}).get(key))
        demographic_completion[key] = round(filled / n * 100, 1) if n else 0

    warnings = []
    if n < 100:
        warnings.append("Non vendere ancora correlazioni come insight forti: il campione è troppo piccolo.")
    if feedback and len(feedback) < max(10, n * 0.15):
        warnings.append("Pochi feedback rispetto ai test completati: spingi una domanda finale più semplice sull'accuratezza percepita.")
    if n and demographic_completion.get("education", 0) < 35:
        warnings.append("Pochi dati facoltativi sul titolo di studio: le correlazioni istruzione-risposte saranno fragili.")
    if not support:
        warnings.append("Nessun contatto commerciale/supporto salvato: aggiungi call-to-action più visibili quando lancerai una beta.")

    return {
        "stage": stage,
        "label": label,
        "next_goal": next_goal,
        "samples": n,
        "feedback_samples": len(feedback),
        "support_contacts": len(support),
        "average_confidence": summary.get("average_confidence"),
        "average_reliability": summary.get("average_reliability"),
        "average_accuracy_rating": summary.get("average_accuracy_rating"),
        "demographic_completion": demographic_completion,
        "warnings": warnings,
        "sellable_public_claim": n >= 100,
        "research_claim_ready": n >= 300,
    }


def insight_row(kind: str, title: str, body: str, n: int = 0, strength: float | None = None, caution: bool = True) -> dict:
    return {
        "kind": kind,
        "title": title,
        "body": body,
        "n": n,
        "strength": strength,
        "caution": caution,
    }


def readable_field(field: str) -> str:
    return {
        "age_range": "età",
        "education": "titolo di studio",
        "origin_area": "area di provenienza",
        "political_interest": "interesse politico",
        "political_knowledge": "conoscenza politica dichiarata",
        "news_frequency": "frequenza informativa",
        "student_worker": "condizione studio/lavoro",
    }.get(field, field)


def build_auto_insights(
    samples: list[dict],
    feedback: list[dict],
    ordinal: dict,
    response_gaps: list[dict],
    demographic_breakdowns: dict,
    dataset_health: dict,
) -> list[dict]:
    insights = [
        insight_row(
            "dataset",
            dataset_health["label"],
            f"{dataset_health['samples']} campioni, {dataset_health['feedback_samples']} feedback e {dataset_health['support_contacts']} contatti. Prossimo obiettivo: {dataset_health['next_goal']}",
            n=dataset_health["samples"],
            caution=dataset_health["samples"] < 100,
        )
    ]

    axis_corr = [row for row in ordinal.get("axes", []) if row.get("n", 0) >= 10]
    if axis_corr:
        top = axis_corr[0]
        direction = "cresce" if top["correlation"] > 0 else "diminuisce"
        insights.append(
            insight_row(
                "correlation",
                f"Segnale tra {readable_field(top['field'])} e asse {top['target']}",
                f"Nel campione attuale, all'aumentare di {readable_field(top['field'])} il punteggio su {top['target']} tende a {direction}. È un segnale esplorativo, non una causa.",
                n=top["n"],
                strength=abs(top["correlation"]),
                caution=top["n"] < 30,
            )
        )

    question_corr = [row for row in ordinal.get("questions", []) if row.get("n", 0) >= 10]
    if question_corr:
        top = question_corr[0]
        insights.append(
            insight_row(
                "question",
                f"Domanda sensibile a {readable_field(top['field'])}",
                f"Questa domanda varia parecchio per {readable_field(top['field'])}: “{top['question']}”. Controllala per capire se misura ideologia o anche linguaggio/competenza.",
                n=top["n"],
                strength=abs(top["correlation"]),
                caution=top["n"] < 30,
            )
        )

    if response_gaps:
        gap = response_gaps[0]
        insights.append(
            insight_row(
                "gap",
                f"Differenza forte tra gruppi su {readable_field(gap['field'])}",
                f"La domanda “{gap['question']}” separa {gap['low_group']} e {gap['high_group']} con gap medio {gap['gap']}. Utile per revisione item e segmenti editoriali.",
                n=gap.get("min_group_n", 0),
                strength=abs(gap.get("gap", 0)),
                caution=gap.get("caution", True),
            )
        )

    feedback_ratings = [row.get("accuracy_rating") for row in feedback if isinstance(row.get("accuracy_rating"), int)]
    if feedback_ratings:
        avg = mean(feedback_ratings)
        insights.append(
            insight_row(
                "feedback",
                "Accuratezza percepita dagli utenti",
                f"Il voto medio di accuratezza percepita è {avg}/5. Se scende sotto 3.5, rivedi domande, nomi degli archetipi e spiegazioni finali.",
                n=len(feedback_ratings),
                strength=avg,
                caution=len(feedback_ratings) < 30,
            )
        )

    for field, groups in demographic_breakdowns.items():
        large_groups = [group for group in groups if group.get("n", 0) >= 10]
        if len(large_groups) >= 2:
            top_group = max(large_groups, key=lambda group: group.get("average_confidence") or 0)
            low_group = min(large_groups, key=lambda group: group.get("average_confidence") or 0)
            if top_group.get("average_confidence") is not None and low_group.get("average_confidence") is not None:
                delta = round(top_group["average_confidence"] - low_group["average_confidence"], 2)
                if abs(delta) >= 4:
                    insights.append(
                        insight_row(
                            "confidence",
                            f"Confidenza diversa per {readable_field(field)}",
                            f"La confidenza media è più alta in “{top_group['value']}” rispetto a “{low_group['value']}” di {delta} punti. Può segnalare domande più chiare per alcuni gruppi.",
                            n=min(top_group["n"], low_group["n"]),
                            strength=abs(delta),
                            caution=min(top_group["n"], low_group["n"]) < 30,
                        )
                    )
                    break

    return insights[:8]


def date_bucket(row: dict) -> str:
    raw = str(row.get("timestamp_utc", ""))
    if len(raw) >= 10:
        return raw[:10]
    return "senza-data"


def build_time_trends(samples: list[dict], feedback: list[dict]) -> list[dict]:
    days: dict[str, dict] = {}
    for row in samples:
        day = date_bucket(row)
        bucket = days.setdefault(day, {"date": day, "samples": 0, "feedback": 0, "confidences": [], "reliabilities": [], "ratings": [], "ideologies": {}})
        bucket["samples"] += 1
        if isinstance(row.get("confidence"), (int, float)):
            bucket["confidences"].append(row["confidence"])
        reliability = row.get("reliability") or {}
        if isinstance(reliability.get("score") if isinstance(reliability, dict) else None, (int, float)):
            bucket["reliabilities"].append(reliability["score"])
        ideology = (row.get("ideology") or {}).get("name")
        if ideology:
            bucket["ideologies"][ideology] = bucket["ideologies"].get(ideology, 0) + 1

    for row in feedback:
        day = date_bucket(row)
        bucket = days.setdefault(day, {"date": day, "samples": 0, "feedback": 0, "confidences": [], "reliabilities": [], "ratings": [], "ideologies": {}})
        bucket["feedback"] += 1
        if isinstance(row.get("accuracy_rating"), int):
            bucket["ratings"].append(row["accuracy_rating"])

    out = []
    for day, bucket in sorted(days.items()):
        top = sorted(bucket["ideologies"].items(), key=lambda item: item[1], reverse=True)
        out.append(
            {
                "date": day,
                "samples": bucket["samples"],
                "feedback": bucket["feedback"],
                "average_confidence": mean(bucket["confidences"]),
                "average_reliability": mean(bucket["reliabilities"]),
                "average_accuracy_rating": mean(bucket["ratings"]),
                "top_ideology": top[0][0] if top else "n/d",
            }
        )
    return out[-90:]


def build_demographic_breakdowns(samples: list[dict]) -> dict:
    fields = ["age_range", "education", "origin_area", "political_interest", "political_knowledge", "news_frequency", "student_worker"]
    out = {}
    for field in fields:
        groups: dict[str, list[dict]] = {}
        for row in samples:
            value = (row.get("demographics") or {}).get(field)
            if value:
                groups.setdefault(value, []).append(row)
        out[field] = []
        for value, rows in groups.items():
            ideologies: dict[str, int] = {}
            for row in rows:
                ideology = (row.get("ideology") or {}).get("name", "Sconosciuta")
                ideologies[ideology] = ideologies.get(ideology, 0) + 1
            axis_means = {}
            for idx, axis in enumerate(AXIS_SHORT):
                axis_means[axis] = mean([row.get("profile", [None] * len(AXIS_SHORT))[idx] for row in rows])
            out[field].append(
                {
                    "value": value,
                    "n": len(rows),
                    "average_confidence": mean([row.get("confidence") for row in rows]),
                    "average_reliability": mean([
                        (row.get("reliability") or {}).get("score")
                        for row in rows
                        if isinstance(row.get("reliability") or {}, dict)
                    ]),
                    "axis_means": axis_means,
                    "top_ideologies": sorted(ideologies.items(), key=lambda item: item[1], reverse=True)[:5],
                }
            )
        out[field].sort(key=lambda item: item["n"], reverse=True)
    return out


def strongest_response_gaps(samples: list[dict]) -> list[dict]:
    fields = ["education", "political_knowledge", "news_frequency", "age_range", "origin_area"]
    rows = []
    question_lookup = {q["id"]: q["question"] for q in QUESTIONS}
    for field in fields:
        values = sorted({(sample.get("demographics") or {}).get(field) for sample in samples if (sample.get("demographics") or {}).get(field)})
        if len(values) < 2:
            continue
        for question in QUESTIONS:
            qid = question["id"]
            means = {}
            counts = {}
            for value in values:
                answers = [
                    sample.get("answers", {}).get(qid)
                    for sample in samples
                    if (sample.get("demographics") or {}).get(field) == value and isinstance(sample.get("answers", {}).get(qid), int)
                ]
                if answers:
                    means[value] = sum(answers) / len(answers)
                    counts[value] = len(answers)
            if len(means) < 2:
                continue
            low_group = min(means, key=means.get)
            high_group = max(means, key=means.get)
            gap = means[high_group] - means[low_group]
            rows.append(
                {
                    "field": field,
                    "question_id": qid,
                    "question": question_lookup[qid],
                    "low_group": low_group,
                    "high_group": high_group,
                    "low_mean": round(means[low_group], 3),
                    "high_mean": round(means[high_group], 3),
                    "gap": round(gap, 3),
                    "min_group_n": min(counts.values()),
                    "caution": min(counts.values()) < 20,
                }
            )
    return sorted(rows, key=lambda row: abs(row["gap"]), reverse=True)[:20]


def build_ordinal_correlations(samples: list[dict], joined: list[dict]) -> dict:
    axis_rows = []
    question_rows = []
    feedback_rows = []
    for field, mapping in ORDINAL_MAPS.items():
        paired = [(mapping.get((row.get("demographics") or {}).get(field)), row) for row in samples]
        paired = [(x, row) for x, row in paired if isinstance(x, int)]
        if len(paired) >= 3:
            xs = [float(x) for x, _ in paired]
            for idx, axis in enumerate(AXIS_SHORT):
                ys = [float((row.get("profile") or [0] * len(AXIS_SHORT))[idx]) for _, row in paired]
                corr = pearson(xs, ys)
                if corr is not None:
                    axis_rows.append({"field": field, "target": axis, "correlation": corr, "n": len(xs)})
            for question in QUESTIONS:
                ys = [float(row.get("answers", {}).get(question["id"])) for _, row in paired if isinstance(row.get("answers", {}).get(question["id"]), int)]
                xs_q = [float(x) for x, row in paired if isinstance(row.get("answers", {}).get(question["id"]), int)]
                corr = pearson(xs_q, ys)
                if corr is not None:
                    question_rows.append({"field": field, "question": question["question"], "question_id": question["id"], "correlation": corr, "n": len(xs_q)})

        joined_paired = [(mapping.get((row.get("demographics") or {}).get(field)), row) for row in joined]
        joined_paired = [(x, row) for x, row in joined_paired if isinstance(x, int) and isinstance((row.get("feedback") or {}).get("accuracy_rating"), int)]
        if len(joined_paired) >= 3:
            xs = [float(x) for x, _ in joined_paired]
            ys = [float(row["feedback"]["accuracy_rating"]) for _, row in joined_paired]
            corr = pearson(xs, ys)
            if corr is not None:
                feedback_rows.append({"field": field, "target": "accuracy_rating", "correlation": corr, "n": len(xs)})

    axis_rows.sort(key=lambda row: abs(row["correlation"]), reverse=True)
    question_rows.sort(key=lambda row: abs(row["correlation"]), reverse=True)
    feedback_rows.sort(key=lambda row: abs(row["correlation"]), reverse=True)
    return {"axes": axis_rows[:20], "questions": question_rows[:20], "feedback": feedback_rows[:10]}


def build_feedback_stats(feedback: list[dict], joined: list[dict]) -> dict:
    ratings = [row.get("accuracy_rating") for row in feedback if isinstance(row.get("accuracy_rating"), int)]
    by_predicted: dict[str, list[int]] = {}
    party_alignment = []
    for row in feedback:
        ideology = row.get("predicted_ideology") or "Sconosciuta"
        if isinstance(row.get("accuracy_rating"), int):
            by_predicted.setdefault(ideology, []).append(row["accuracy_rating"])
        self_party = normalize_text(row.get("closest_party_self", ""))
        predicted = [normalize_text(item) for item in row.get("predicted_parties", [])]
        if self_party:
            party_alignment.append(any(self_party in item or item in self_party for item in predicted if item))

    by_predicted_summary = [
        {"ideology": ideology, "n": len(values), "average_rating": mean(values)}
        for ideology, values in by_predicted.items()
    ]
    by_predicted_summary.sort(key=lambda row: row["n"], reverse=True)

    return {
        "average_rating": mean(ratings),
        "ratings_count": len(ratings),
        "party_alignment_rate": round(sum(party_alignment) / len(party_alignment) * 100, 1) if party_alignment else None,
        "party_alignment_n": len(party_alignment),
        "by_predicted_ideology": by_predicted_summary,
        "joined_feedback_samples": len(joined),
    }


LOGIN_HTML = """
<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Login admin - Politometro</title>
  <style>
    :root{--ink:#172026;--muted:#60707c;--line:#d9e1e7;--accent:#22577a;--accent2:#38a3a5;--warm:#f2b880;--danger:#b84a62}
    *{box-sizing:border-box}
    body{margin:0;min-height:100vh;display:grid;place-items:center;padding:20px;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:linear-gradient(120deg,rgba(56,163,165,.16),transparent 30%),linear-gradient(240deg,rgba(242,184,128,.22),transparent 36%),#f6f8f8;color:var(--ink)}
    main{width:min(460px,100%);background:#fff;border:1px solid var(--line);border-radius:8px;padding:24px;box-shadow:0 24px 70px rgba(16,36,47,.14)}
    h1{font-family:Georgia,serif;font-size:36px;line-height:1.04;margin:0 0 8px}
    p{color:var(--muted);line-height:1.45}
    label{display:grid;gap:6px;margin:12px 0;font-weight:800}
    input{width:100%;border:1px solid var(--line);border-radius:8px;padding:12px;font:inherit}
    button{width:100%;min-height:46px;border:0;border-radius:8px;background:linear-gradient(135deg,var(--accent),#17384d);color:white;font-weight:900;cursor:pointer}
    .warning{border-left:4px solid var(--warm);background:#fff8ef;border-radius:8px;padding:12px;color:#5a401f}
    .status{min-height:22px;font-weight:800;color:var(--danger)}
    a{color:var(--accent)}
  </style>
</head>
<body>
  <main>
    <h1>Accesso admin</h1>
    <p>Entra solo per leggere dashboard, campioni consensuali e correlazioni aggregate. Il quiz pubblico deve restare separato dall'area amministrativa.</p>
    <div class="warning"><strong>Password sicura:</strong> non va scritta nel codice. Configurala sul server come hash e cambia qualunque password già condivisa in chat.</div>
    <form id="loginForm">
      <label>Email admin<input id="email" type="email" autocomplete="username" required></label>
      <label>Password<input id="password" type="password" autocomplete="current-password" required></label>
      <button type="submit">Entra nella dashboard</button>
    </form>
    <p class="status" id="status"></p>
    <p><a href="/">Torna al Politometro</a></p>
  </main>
  <script>
    document.getElementById("loginForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      const status = document.getElementById("status");
      status.textContent = "Controllo credenziali...";
      const response = await fetch("/api/admin/login", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          email: document.getElementById("email").value,
          password: document.getElementById("password").value
        })
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        status.textContent = err.detail || "Accesso non riuscito.";
        return;
      }
      location.href = "/admin";
    });
  </script>
</body>
</html>
"""

ADMIN_HTML = """
<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Politometro Admin</title>
  <style>
    :root {
      --ink:#172026; --muted:#60707c; --line:#d9e1e7; --paper:#f6f8f8; --panel:#fff;
      --accent:#22577a; --accent2:#38a3a5; --warm:#f2b880; --danger:#b84a62;
      --purple:#6d597a; --rose:#fde9ed; --deep:#10242f;
      --shadow:0 18px 46px rgba(16,36,47,.10);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    * { box-sizing:border-box; }
    body {
      margin:0;
      background:
        radial-gradient(circle at 8% 8%, rgba(56,163,165,.16), transparent 28%),
        radial-gradient(circle at 88% 4%, rgba(242,184,128,.20), transparent 30%),
        radial-gradient(circle at 82% 92%, rgba(109,89,122,.16), transparent 32%),
        linear-gradient(180deg,#fffdfa,var(--paper));
      color:var(--ink);
    }
    header {
      padding:26px 30px;
      background:
        radial-gradient(circle at 12% 0%, rgba(56,163,165,.38), transparent 30%),
        radial-gradient(circle at 90% 0%, rgba(242,184,128,.24), transparent 32%),
        linear-gradient(135deg,#10242f,#17384d 58%,#3c3447);
      color:white;
      box-shadow:0 18px 44px rgba(16,36,47,.18);
    }
	    header h1 { margin:0; font-size:28px; letter-spacing:0; }
	    header p { margin:8px 0 0; color:#c5d5dc; max-width:900px; }
	    header .top { display:flex; justify-content:space-between; gap:14px; align-items:flex-start; }
	    .logout { border:1px solid rgba(255,255,255,.24); background:rgba(255,255,255,.10); color:#fff; border-radius:10px; padding:10px 12px; cursor:pointer; font-weight:900; }
    main { padding:24px; display:grid; gap:18px; }
    .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:14px; }
    .wide { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:14px; }
    .card {
      background:
        linear-gradient(135deg, rgba(255,255,255,.98), rgba(248,252,252,.94)),
        var(--panel);
      border:1px solid rgba(34,87,122,.13);
      border-radius:12px;
      padding:18px;
      box-shadow:var(--shadow);
      overflow:hidden;
      position:relative;
    }
    .card::before {
      content:"";
      position:absolute;
      inset:0 0 auto;
      height:4px;
      background:linear-gradient(90deg,var(--accent2),var(--warm),var(--purple));
      opacity:.72;
    }
    .metric { font-size:30px; font-weight:900; color:var(--accent); margin-top:8px; }
    h2, h3 { margin:0 0 12px; letter-spacing:0; }
    p { line-height:1.45; }
    .muted { color:var(--muted); font-size:13px; }
    table { width:100%; border-collapse:collapse; font-size:14px; }
    th, td { text-align:left; border-bottom:1px solid var(--line); padding:9px 7px; vertical-align:top; }
    th { color:var(--muted); font-size:12px; text-transform:uppercase; }
    .tag { display:inline-block; padding:5px 8px; border-radius:999px; background:linear-gradient(135deg,#edf3f4,#fff7e8); font-weight:800; font-size:12px; border:1px solid rgba(34,87,122,.10); }
    .actions { display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
    .btn { border:0; border-radius:10px; padding:11px 13px; background:linear-gradient(135deg,#e5ecef,#fff); color:var(--ink); font-weight:900; cursor:pointer; text-decoration:none; box-shadow:0 8px 20px rgba(16,36,47,.07); }
    .btn.primary { background:linear-gradient(135deg,var(--warm),#e4a665,var(--accent2)); color:#10242f; }
    .health { display:grid; grid-template-columns:1.2fr 2fr; gap:14px; align-items:start; }
    .stage { border-radius:12px; padding:16px; color:white; background:linear-gradient(135deg,var(--accent),var(--accent2),var(--purple)); box-shadow:0 12px 28px rgba(34,87,122,.16); }
    .stage strong { display:block; font-size:20px; margin-bottom:6px; }
    .insights { display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:12px; }
    .insight { border:1px solid rgba(34,87,122,.12); border-radius:12px; padding:14px; background:linear-gradient(135deg,rgba(56,163,165,.10),rgba(242,184,128,.13),rgba(109,89,122,.08)),#fff; }
    .insight h3 { font-size:15px; margin-bottom:6px; }
    .insight small { color:var(--muted); font-weight:800; }
    .warn { border-left:4px solid var(--warm); background:linear-gradient(135deg,#fff8ef,var(--rose)); padding:12px; border-radius:10px; }
    .question-bank { display:grid; gap:10px; }
    .question-line { border:1px solid rgba(34,87,122,.12); border-radius:10px; padding:12px; background:#fbfdfd; }
    .question-line strong { display:block; margin-bottom:5px; }
    .question-line span { display:inline-block; margin-right:6px; margin-top:5px; }
    @media (max-width:1000px) { .grid, .wide, .health { grid-template-columns:1fr; } }
  </style>
</head>
<body>
	  <header>
	    <div class="top">
	      <div>
	        <h1>Politometro Admin</h1>
	        <p>Dashboard locale privata: campioni consensuali, feedback, contatti, correlazioni esplorative e segnali su quali domande migliorare. In locale i file sono in data/ e nel database SQLite; online serviranno database e login admin.</p>
	      </div>
	      <button class="logout" id="logoutBtn">Esci</button>
	    </div>
	  </header>
  <main>
    <section class="grid" id="metrics"></section>
    <section class="card warn" id="note"></section>
    <section class="card">
      <h2>Stato dataset</h2>
      <div class="health" id="datasetHealth"></div>
    </section>
    <section class="card">
      <h2>Insight automatici</h2>
      <div class="insights" id="autoInsights"></div>
    </section>
    <section class="card">
      <h2>Banca domande attuale</h2>
      <p class="muted">Qui vedi il modello caricato adesso. Le risposte salvate conservano anche la versione del modello usata, ma le vecchie banche domande non vengono mostrate come archivio separato finché non creiamo uno storico versioni.</p>
      <div id="questionBank" class="question-bank"></div>
    </section>
    <section class="card">
      <h2>Export per analisi e vendita</h2>
      <p class="muted">Scarica dataset e sintesi. Usa questi file solo in forma aggregata e con consenso: niente vendita di dati individuali.</p>
      <div class="actions">
        <button class="btn primary" data-export="analytics.json">Scarica analytics JSON</button>
        <button class="btn" data-export="samples.csv">Campioni CSV</button>
        <button class="btn" data-export="feedback.csv">Feedback CSV</button>
        <button class="btn" data-export="contacts.csv">Contatti CSV</button>
      </div>
    </section>
    <section class="card">
      <h2>Trend nel tempo</h2>
      <table id="trends"></table>
    </section>
    <section class="wide">
      <div class="card">
        <h2>Distribuzione ideologie</h2>
        <table id="ideologies"></table>
      </div>
      <div class="card">
        <h2>Feedback</h2>
        <table id="feedback"></table>
      </div>
    </section>
    <section class="card">
      <h2>Correlazioni: istruzione / informazione / età con assi</h2>
      <table id="axisCorr"></table>
    </section>
    <section class="card">
      <h2>Correlazioni: istruzione / informazione / età con singole domande</h2>
      <table id="questionCorr"></table>
    </section>
    <section class="card">
      <h2>Differenze maggiori tra gruppi demografici</h2>
      <table id="gaps"></table>
    </section>
    <section class="card">
      <h2>Breakdown demografico</h2>
      <div id="breakdowns"></div>
    </section>
  </main>
	  <script>
	    const fmt = (x) => x === null || x === undefined ? "n/d" : x;
	    document.getElementById("logoutBtn").addEventListener("click", async () => {
	      await fetch("/api/admin/logout", {method:"POST"}).catch(() => {});
	      if (location.pathname.endsWith("admin.html")) location.reload();
	      else location.href = "/login";
	    });
    function rows(items, cols) {
      if (!items || !items.length) return `<tr><td class="muted">Ancora nessun dato sufficiente.</td></tr>`;
      return `<tr>${cols.map(c => `<th>${c[0]}</th>`).join("")}</tr>` + items.map(item =>
        `<tr>${cols.map(c => `<td>${c[1](item)}</td>`).join("")}</tr>`
      ).join("");
    }
    async function downloadAdminExport(kind) {
      const response = await fetch(`/api/admin/export/${kind}`);
      if (!response.ok) {
        document.getElementById("note").innerHTML = "<strong>Export non disponibile.</strong><br>Avvia la versione server con login admin, oppure usa la dashboard locale generata dalla PWA.";
        return;
      }
      const blob = await response.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `politometro-${kind}`;
      a.click();
      URL.revokeObjectURL(a.href);
    }
    document.querySelectorAll("[data-export]").forEach((button) => {
      button.addEventListener("click", () => downloadAdminExport(button.dataset.export));
    });
    fetch("/api/questions").then(r => r.json()).then(data => {
      const questions = data.questions || [];
      const quick = new Set(data.quick_question_ids || []);
      const social = new Set(data.social_question_ids || []);
      const preview = questions.slice(0, 10).map((q) => `
        <div class="question-line">
          <strong>${q.question}</strong>
          <span class="tag">${q.id}</span>
          ${quick.has(q.id) ? `<span class="tag">rapida</span>` : ""}
          ${social.has(q.id) ? `<span class="tag">social</span>` : ""}
        </div>
      `).join("");
      document.getElementById("questionBank").innerHTML = `
        <div class="insights">
          <div class="insight"><small>Versione</small><h3>${data.model_version || "n/d"}</h3><p>Modello attualmente servito dal sito.</p></div>
          <div class="insight"><small>Domande</small><h3>${questions.length}</h3><p>${(data.quick_question_ids || []).length} rapide · ${(data.social_question_ids || []).length} social.</p></div>
        </div>
        ${preview}
        <p class="muted">Mostro le prime 10 per tenere leggibile la dashboard. L'elenco completo è disponibile via export tecnico del modello.</p>
      `;
    }).catch(() => {
      document.getElementById("questionBank").innerHTML = `<p class="muted">Non riesco a leggere la banca domande da questa sessione.</p>`;
    });
    fetch("/api/private-analytics").then(r => r.json()).then(data => {
      const s = data.summary;
      document.getElementById("metrics").innerHTML = [
        ["Campioni", s.samples],
        ["Feedback", s.feedback_samples],
        ["Contatti", s.support_contacts],
        ["Confidenza media", fmt(s.average_confidence)],
        ["Affidabilità media", fmt(s.average_reliability)],
        ["Accuratezza media", fmt(s.average_accuracy_rating)]
      ].map(([label, value]) => `<div class="card"><span class="muted">${label}</span><div class="metric">${value}</div></div>`).join("");
      document.getElementById("note").innerHTML = `<strong>${data.model_version}</strong><br>${data.minimum_sample_note}<br>${data.privacy}`;
      const health = data.dataset_health || {};
      document.getElementById("datasetHealth").innerHTML = `
        <div class="stage"><strong>${health.label || "Dataset"}</strong><span>${health.next_goal || ""}</span></div>
        <div>
          <p><strong>Fase:</strong> ${health.stage || "n/d"} · <strong>claim pubblico:</strong> ${health.sellable_public_claim ? "inizia a essere presentabile" : "ancora prudente"} · <strong>ricerca:</strong> ${health.research_claim_ready ? "analisi più serie possibili" : "non ancora"}</p>
          <p class="muted">${(health.warnings || []).join("<br>") || "Nessun avviso critico."}</p>
        </div>`;
      document.getElementById("autoInsights").innerHTML = (data.auto_insights || []).map((item) => `
        <div class="insight">
          <small>${item.kind} · n=${item.n || 0}${item.caution ? " · prudente" : ""}</small>
          <h3>${item.title}</h3>
          <p>${item.body}</p>
        </div>
      `).join("") || `<p class="muted">Servono più risposte consensuali per generare insight automatici.</p>`;
      document.getElementById("trends").innerHTML = rows(data.time_trends, [
        ["Data", x => x.date],
        ["Test", x => x.samples],
        ["Feedback", x => x.feedback],
        ["Confidenza", x => fmt(x.average_confidence)],
        ["Accuratezza", x => fmt(x.average_accuracy_rating)],
        ["Ideologia top", x => x.top_ideology]
      ]);
      const ideologyItems = Object.entries(s.ideology_counts || {}).map(([name, count]) => ({name, count}));
      document.getElementById("ideologies").innerHTML = rows(ideologyItems, [["Ideologia", x => x.name], ["N", x => x.count]]);
      document.getElementById("feedback").innerHTML = rows(data.feedback.by_predicted_ideology, [["Ideologia prevista", x => x.ideology], ["N", x => x.n], ["Rating medio", x => fmt(x.average_rating)]]);
      document.getElementById("axisCorr").innerHTML = rows(data.ordinal_correlations.axes, [["Campo", x => x.field], ["Asse", x => x.target], ["r", x => x.correlation], ["N", x => x.n]]);
      document.getElementById("questionCorr").innerHTML = rows(data.ordinal_correlations.questions, [["Campo", x => x.field], ["Domanda", x => x.question], ["r", x => x.correlation], ["N", x => x.n]]);
      document.getElementById("gaps").innerHTML = rows(data.strongest_response_gaps, [
        ["Campo", x => x.field],
        ["Domanda", x => x.question],
        ["Gruppo basso", x => `${x.low_group} (${x.low_mean})`],
        ["Gruppo alto", x => `${x.high_group} (${x.high_mean})`],
        ["Gap", x => `${x.gap}${x.caution ? " *" : ""}`]
      ]);
      const parts = Object.entries(data.demographic_breakdowns || {}).map(([field, groups]) => `
        <h3>${field}</h3>
        <table>${rows(groups, [["Gruppo", x => x.value], ["N", x => x.n], ["Confidenza", x => fmt(x.average_confidence)], ["Top ideologie", x => (x.top_ideologies || []).map(i => `${i[0]} (${i[1]})`).join(", ")]])}</table>
      `).join("");
      document.getElementById("breakdowns").innerHTML = parts || `<p class="muted">Ancora nessun dato demografico.</p>`;
    });
  </script>
</body>
</html>
"""


HTML = """
<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Politometro</title>
  <link rel="manifest" href="/manifest.webmanifest" />
  <meta name="theme-color" content="#10242f" />
  <meta name="apple-mobile-web-app-capable" content="yes" />
  <meta name="apple-mobile-web-app-title" content="Politometro" />
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
  <style>
    :root {
      color-scheme: light;
      --ink: #172026;
      --muted: #60707c;
      --line: #d9e1e7;
      --paper: #f6f8f8;
      --panel: #ffffff;
      --accent: #22577a;
      --accent-2: #38a3a5;
      --warm: #f2b880;
	      --danger: #b84a62;
	      --good: #4f8f64;
	      --violet: #6d597a;
	      --mint-soft: #e7f6ef;
	      --sky-soft: #e8f3f7;
	      --gold-soft: #fff3d8;
	      --rose-soft: #fde9ed;
	      --shadow: 0 18px 45px rgba(23, 32, 38, .10);
      --shadow-soft: 0 10px 26px rgba(23, 32, 38, .08);
      --display: ui-serif, Georgia, "Times New Roman", serif;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    * { box-sizing: border-box; }
    body {
	      margin: 0;
	      background:
	        linear-gradient(120deg, rgba(56,163,165,.14), transparent 26%),
	        linear-gradient(240deg, rgba(242,184,128,.18), transparent 34%),
	        linear-gradient(315deg, rgba(184,74,98,.08), transparent 38%),
	        linear-gradient(180deg, #fbfcf7 0%, var(--paper) 42%, #eaf4f1 100%);
	      color: var(--ink);
	    }
    button, input, select, textarea { font: inherit; }
    .shell {
      min-height: 100vh;
      display: grid;
      grid-template-columns: 320px minmax(0, 1fr);
    }
    aside {
      background:
        linear-gradient(180deg, rgba(16,36,47,.98), rgba(18,48,59,.98)),
        repeating-linear-gradient(135deg, rgba(255,255,255,.07) 0 1px, transparent 1px 18px);
      color: white;
      padding: 28px;
      position: sticky;
      top: 0;
      height: 100vh;
      display: flex;
      flex-direction: column;
      gap: 22px;
    }
    .brand {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .brand::before {
      content: "";
      width: 54px;
      height: 54px;
      border-radius: 16px;
      background:
        radial-gradient(circle at 50% 50%, #10242f 0 24%, transparent 25%),
        conic-gradient(from 210deg, var(--accent-2), var(--warm), #f7f2e8, var(--accent-2));
      border: 1px solid rgba(255,255,255,.25);
      box-shadow: 0 16px 40px rgba(0,0,0,.22);
    }
    .brand h1 {
      font-family: var(--display);
      font-size: 42px;
      line-height: .95;
      margin: 0;
      letter-spacing: 0;
      text-wrap: balance;
    }
    .brand p {
      margin: 0;
      color: #b9c8d0;
      line-height: 1.45;
    }
    .meter {
      display: grid;
      gap: 10px;
    }
    .meter-top {
      display: flex;
      justify-content: space-between;
      color: #d8e2e8;
      font-size: 14px;
    }
    .track {
      height: 12px;
      border-radius: 999px;
      background: rgba(255,255,255,.16);
      overflow: hidden;
      box-shadow: inset 0 1px 3px rgba(0,0,0,.25);
    }
    .fill {
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, var(--accent-2), var(--warm));
      transition: width .45s cubic-bezier(.2,.8,.2,1);
      position: relative;
    }
    .fill::after {
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(90deg, transparent, rgba(255,255,255,.45), transparent);
      transform: translateX(-100%);
      animation: sheen 2.4s ease-in-out infinite;
    }
    .side-note {
      margin-top: auto;
      color: #b9c8d0;
      font-size: 13px;
      line-height: 1.5;
    }
    main {
      padding: 34px;
      display: grid;
      gap: 22px;
    }
    .topbar {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: center;
    }
    .step-title {
      margin: 0;
      font-family: var(--display);
      font-size: 30px;
      letter-spacing: 0;
    }
    .step-subtitle {
      margin: 6px 0 0;
      color: var(--muted);
    }
    .question-panel {
	      background:
	        linear-gradient(135deg, rgba(56,163,165,.055), rgba(255,255,255,0) 34%),
	        linear-gradient(315deg, rgba(242,184,128,.075), rgba(255,255,255,0) 38%),
	        var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 26px;
      min-height: 460px;
      display: grid;
      grid-template-rows: auto 1fr auto;
      gap: 22px;
      box-shadow: var(--shadow);
      transform-origin: 50% 20%;
      animation: rise .34s cubic-bezier(.2,.8,.2,1) both;
      transition: transform .28s ease, opacity .28s ease, box-shadow .28s ease;
      position: relative;
      overflow: hidden;
    }
    .question-panel::before {
      content: "";
      position: absolute;
      inset: 0 0 auto;
      height: 4px;
      background: linear-gradient(90deg, var(--accent-2), var(--warm), var(--violet), var(--accent-2));
      background-size: 220% 100%;
      animation: colorSlide 7s linear infinite;
    }
    .question-panel.switching {
      opacity: .42;
      transform: translateY(8px) scale(.992);
    }
    @keyframes rise {
      from { opacity: 0; transform: translateY(10px); }
      to { opacity: 1; transform: translateY(0); }
    }
    @keyframes sheen {
      0%, 40% { transform: translateX(-100%); }
      70%, 100% { transform: translateX(100%); }
    }
    @keyframes pop {
      0% { transform: scale(.86); }
      70% { transform: scale(1.08); }
      100% { transform: scale(1); }
    }
    @keyframes colorSlide {
      from { background-position: 0% 50%; }
      to { background-position: 220% 50%; }
    }
    @keyframes orbit {
      from { transform: rotate(0deg); }
      to { transform: rotate(360deg); }
    }
    @keyframes finishPulse {
      0% { transform: scale(.96); opacity: .65; }
      55% { transform: scale(1.04); opacity: 1; }
      100% { transform: scale(1); opacity: 1; }
    }
    .question-text {
      font-size: 28px;
      line-height: 1.16;
      margin: 0;
      text-wrap: balance;
    }
    .options {
      display: grid;
      gap: 10px;
      align-content: start;
    }
    .option {
      border: 1px solid var(--line);
	      background:
	        linear-gradient(90deg, rgba(255,255,255,.92), rgba(247,251,251,.92)),
	        #fbfcfc;
      border-radius: 8px;
      padding: 14px 16px;
      text-align: left;
      cursor: pointer;
      display: flex;
      gap: 12px;
      align-items: flex-start;
      color: var(--ink);
      position: relative;
      overflow: hidden;
      transform: translateY(0);
      transition: transform .18s ease, border-color .18s ease, background .18s ease, box-shadow .18s ease;
    }
    .option:hover {
      border-color: var(--accent-2);
	      background:
	        linear-gradient(90deg, rgba(232,243,247,.86), rgba(255,243,216,.46)),
	        #f4fbfb;
      transform: translateY(-2px);
      box-shadow: var(--shadow-soft);
    }
    .option:active { transform: translateY(0) scale(.995); }
    .option.selected {
      border-color: var(--accent);
	      background:
	        linear-gradient(90deg, rgba(56,163,165,.16), rgba(242,184,128,.16)),
	        #f7fbfb;
      box-shadow: 0 0 0 2px rgba(34, 87, 122, .12), var(--shadow-soft);
    }
    .num {
      flex: 0 0 auto;
      width: 26px;
      height: 26px;
      border-radius: 999px;
      background: #e4ebef;
      display: grid;
      place-items: center;
      color: var(--accent);
      font-weight: 700;
      font-size: 13px;
    }
    .option.selected .num {
      background: var(--accent);
      color: white;
      animation: pop .22s ease both;
    }
    .nav {
      display: flex;
      justify-content: space-between;
      gap: 12px;
    }
    .btn {
      border: 0;
      border-radius: 8px;
      padding: 12px 16px;
      cursor: pointer;
      background: #e5ecef;
      color: var(--ink);
      font-weight: 700;
      min-height: 44px;
      transition: transform .16s ease, box-shadow .16s ease, background .16s ease;
    }
    a.btn {
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }
    .btn:hover:not(:disabled) {
      transform: translateY(-1px);
      box-shadow: var(--shadow-soft);
    }
    .btn:active:not(:disabled) { transform: translateY(0) scale(.99); }
    .btn.primary {
      background: linear-gradient(135deg, var(--accent), #17384d);
      color: white;
    }
    .btn:disabled {
      opacity: .45;
      cursor: not-allowed;
    }
    .results {
      display: none;
      gap: 18px;
    }
    .results.visible { display: grid; }
	    .mode-card {
	      border: 1px solid var(--line);
	      border-radius: 8px;
	      padding: 14px;
	      background:
	        linear-gradient(135deg, rgba(255,255,255,.92), rgba(247,251,251,.92)),
	        #fbfcfc;
	      cursor: pointer;
      position: relative;
      overflow: hidden;
      transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease, background .18s ease;
    }
    .mode-card::before {
      content: "";
      position: absolute;
      inset: 0 auto 0 0;
      width: 4px;
	      background: linear-gradient(180deg, var(--accent-2), var(--warm));
	      opacity: .55;
	    }
	    .mode-card.mode-social { background: linear-gradient(135deg, var(--sky-soft), #fff 58%); }
	    .mode-card.mode-quick { background: linear-gradient(135deg, var(--mint-soft), #fff 58%); }
	    .mode-card.mode-deep { background: linear-gradient(135deg, var(--gold-soft), #fff 58%); }
	    .mode-card.mode-election { background: linear-gradient(135deg, var(--rose-soft), #fff7e8 64%); }
	    .mode-card.mode-social::before { background: linear-gradient(180deg, #22577a, #38a3a5); }
	    .mode-card.mode-quick::before { background: linear-gradient(180deg, #38a3a5, #4f8f64); }
	    .mode-card.mode-deep::before { background: linear-gradient(180deg, #f2b880, #6d597a); }
	    .mode-card.mode-election::before { background: linear-gradient(180deg, #b84a62, #f2b880, #38a3a5); }
    .mode-card:hover {
      transform: translateY(-2px);
      box-shadow: var(--shadow-soft);
      border-color: var(--accent-2);
    }
	    .mode-card.selected {
	      border-color: var(--accent);
	      background:
	        linear-gradient(135deg, rgba(56,163,165,.18), rgba(242,184,128,.18)),
	        #fff;
	      box-shadow: 0 0 0 2px rgba(34, 87, 122, .12);
	    }
    .mode-card.featured {
      background: #fbfcfc;
    }
    .mode-card.locked {
      cursor: default;
      background:
        repeating-linear-gradient(135deg, rgba(34,87,122,.06) 0 9px, rgba(242,184,128,.12) 9px 18px),
        #fff;
      border-style: dashed;
    }
    .mode-card.locked::before {
      width: 100%;
      height: 4px;
      inset: 0 0 auto 0;
      animation: colorSlide 6s linear infinite;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      margin-left: 8px;
      padding: 4px 8px;
      border-radius: 999px;
      background: #10242f;
      color: #fff;
      font-size: 11px;
      font-weight: 900;
      letter-spacing: .02em;
      vertical-align: middle;
    }
    .worksite-mini {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 5px;
      margin-top: 10px;
      max-width: 120px;
    }
    .worksite-mini span {
      height: 6px;
      border-radius: 999px;
      background: var(--warm);
      animation: finishPulse 1.4s ease-in-out infinite;
    }
    .worksite-mini span:nth-child(2) { animation-delay: .16s; background: var(--accent-2); }
    .worksite-mini span:nth-child(3) { animation-delay: .32s; background: var(--violet); }
    .trust-strip {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-top: 14px;
    }
	    .trust-chip {
      min-height: 78px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
	      background:
	        linear-gradient(135deg, rgba(56,163,165,.08), rgba(242,184,128,.08)),
	        linear-gradient(180deg, #fff, #f7fbfb);
      display: grid;
      gap: 5px;
      box-shadow: var(--shadow-soft);
    }
    .trust-chip strong {
      font-size: 13px;
      color: var(--accent);
    }
    .trust-chip span {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.35;
    }
    .partner-panel {
      border: 1px solid rgba(34,87,122,.22);
      border-radius: 8px;
      background:
        linear-gradient(135deg, rgba(56,163,165,.12), transparent 40%),
        linear-gradient(315deg, rgba(242,184,128,.18), transparent 45%),
        #ffffff;
      padding: 16px;
      display: grid;
      gap: 12px;
      position: relative;
      overflow: hidden;
    }
    .partner-panel::before {
      content: "";
      position: absolute;
      inset: 0 0 auto;
      height: 4px;
      background: linear-gradient(90deg, var(--accent), var(--accent-2), var(--warm), var(--accent));
      background-size: 220% 100%;
      animation: colorSlide 8s linear infinite;
    }
    .partner-panel h4 {
      margin: 0;
      font-size: 18px;
    }
    .partner-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
    }
    .partner-card {
      border: 1px solid var(--line);
      background: rgba(255,255,255,.78);
      border-radius: 8px;
      padding: 12px;
      min-height: 112px;
    }
	    .partner-card strong {
	      display: block;
	      margin-bottom: 5px;
	      color: var(--accent);
	    }
	    .startup-grid {
	      display: grid;
	      grid-template-columns: repeat(4, minmax(0, 1fr));
	      gap: 10px;
	    }
	    .startup-card {
	      border: 1px solid rgba(34,87,122,.18);
	      border-radius: 8px;
	      padding: 12px;
	      background:
	        linear-gradient(135deg, rgba(56,163,165,.10), rgba(242,184,128,.12)),
	        rgba(255,255,255,.86);
	      min-height: 126px;
	    }
	    .startup-card strong {
	      display: block;
	      color: var(--accent);
	      margin-bottom: 5px;
	    }
    .ethics-note {
      border-left: 4px solid var(--warm);
      background: rgba(242,184,128,.14);
      border-radius: 8px;
      padding: 12px 14px;
      color: #4f3b22;
      font-size: 13px;
      line-height: 1.45;
    }
    .mode-card h4 {
      margin: 0 0 6px;
      font-size: 17px;
    }
    .hero-badges {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 10px;
    }
    .hero-badge {
      border: 1px solid rgba(34,87,122,.18);
      border-radius: 999px;
      padding: 7px 10px;
      background: rgba(255,255,255,.72);
      color: #24404c;
      font-size: 12px;
      font-weight: 850;
      box-shadow: 0 8px 18px rgba(23,32,38,.05);
    }
    .experience-strip {
      display: grid;
      grid-template-columns: 1.15fr .85fr;
      gap: 12px;
      align-items: stretch;
    }
    .experience-panel {
      border: 1px solid rgba(34,87,122,.18);
      border-radius: 8px;
      padding: 16px;
      background:
        radial-gradient(circle at 12% 10%, rgba(56,163,165,.15), transparent 34%),
        radial-gradient(circle at 92% 8%, rgba(242,184,128,.20), transparent 32%),
        #ffffff;
      box-shadow: var(--shadow-soft);
      min-height: 148px;
      display: grid;
      align-content: center;
      gap: 10px;
      overflow: hidden;
      position: relative;
    }
    .experience-panel::after {
      content: "";
      position: absolute;
      right: -30px;
      bottom: -36px;
      width: 150px;
      height: 150px;
      border-radius: 50%;
      border: 18px solid rgba(34,87,122,.08);
    }
    .experience-panel h4 {
      margin: 0;
      font-family: var(--display);
      font-size: 26px;
      letter-spacing: 0;
    }
    .experience-steps {
      display: grid;
      gap: 8px;
    }
    .experience-step {
      display: grid;
      grid-template-columns: 34px minmax(0, 1fr);
      gap: 9px;
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 9px;
      background: rgba(255,255,255,.82);
      font-size: 13px;
      color: #314653;
      font-weight: 760;
    }
    .experience-step span {
      width: 34px;
      height: 34px;
      border-radius: 50%;
      display: grid;
      place-items: center;
      background: #10242f;
      color: #fff;
      font-weight: 950;
    }
    .setup-details {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      overflow: hidden;
    }
    .setup-details summary {
      cursor: pointer;
      padding: 14px 16px;
      font-weight: 900;
      list-style: none;
    }
    .setup-details summary::-webkit-details-marker { display: none; }
    .setup-details summary::after {
      content: "+";
      float: right;
      color: var(--accent);
      font-weight: 900;
    }
    .setup-details[open] summary::after { content: "−"; }
    .setup-body {
      padding: 0 16px 16px;
    }
    .tabs {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      position: sticky;
      top: 0;
      z-index: 2;
      padding: 8px 0;
      background: rgba(246,248,248,.88);
      backdrop-filter: blur(10px);
    }
    .tab {
      border: 1px solid var(--line);
      background: #fff;
      color: var(--ink);
      border-radius: 8px;
      padding: 10px 12px;
      cursor: pointer;
      font-weight: 800;
      transition: transform .16s ease, background .16s ease, box-shadow .16s ease, border-color .16s ease;
    }
    .tab::before {
      content: attr(data-icon);
      margin-right: 6px;
      font-weight: 900;
      opacity: .78;
    }
    .tab:hover {
      transform: translateY(-1px);
      box-shadow: var(--shadow-soft);
      border-color: var(--accent-2);
    }
    .tab.active {
      background: linear-gradient(135deg, var(--accent), #17384d);
      border-color: var(--accent);
      color: #fff;
    }
    .tab-panel { display: none; }
    .tab-panel.active {
      display: grid;
      gap: 18px;
      animation: rise .24s ease both;
    }
    .result-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.15fr) minmax(300px, .85fr);
      gap: 18px;
    }
	    .block {
	      background:
	        linear-gradient(135deg, rgba(56,163,165,.035), rgba(255,255,255,0) 40%),
	        var(--panel);
	      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 20px;
      box-shadow: 0 1px 0 rgba(255,255,255,.85), var(--shadow-soft);
    }
    .block h2, .block h3 {
      margin: 0 0 12px;
      letter-spacing: 0;
    }
    .hero-result {
      display: grid;
      gap: 12px;
    }
    .surface-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }
    .archetype-card {
      display: grid;
      gap: 10px;
      padding: 18px;
      border-radius: 8px;
      border: 1px solid rgba(56,163,165,.30);
      background:
        linear-gradient(135deg, rgba(34,87,122,.08), rgba(242,184,128,.12)),
        #fff;
    }
    .archetype-card h3 {
      font-family: var(--display);
      font-size: 30px;
      line-height: 1.06;
      margin: 0;
    }
    .dominant-axis {
      display: grid;
      gap: 8px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfc;
    }
    .world-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
    }
    .world-card {
      display: grid;
      gap: 13px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      background:
        linear-gradient(135deg, rgba(56,163,165,.08), rgba(255,255,255,0) 42%),
        #fbfcfc;
      position: relative;
      overflow: hidden;
      transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
    }
    .world-card:hover {
      transform: translateY(-2px);
      box-shadow: var(--shadow-soft);
      border-color: rgba(56,163,165,.55);
    }
    .world-card.nemesi {
      background:
        linear-gradient(135deg, rgba(184,74,98,.08), rgba(242,184,128,.10)),
        #fff;
    }
    .world-head {
      display: flex;
      gap: 12px;
      align-items: center;
      min-width: 0;
    }
    .world-head h4 {
      margin: 0;
      font-size: 18px;
      line-height: 1.15;
    }
    .axis-mini-list {
      display: grid;
      gap: 7px;
    }
    .axis-mini-row {
      border-left: 3px solid rgba(56,163,165,.55);
      padding-left: 9px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.35;
    }
    .world-card.nemesi .axis-mini-row {
      border-left-color: rgba(184,74,98,.55);
    }
    .world-actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
      margin-top: 2px;
    }
    .world-note {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
      margin: 0;
    }
    .advanced-panel {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      overflow: hidden;
    }
    .advanced-panel summary {
      padding: 14px 16px;
      cursor: pointer;
      font-weight: 900;
    }
    .advanced-panel > div {
      padding: 0 16px 16px;
    }
    .interval-row {
      display: grid;
      grid-template-columns: 110px minmax(0, 1fr);
      gap: 10px;
      align-items: center;
      padding: 8px 0;
      border-bottom: 1px solid var(--line);
    }
    .interval-row:last-child { border-bottom: 0; }
    .interval-track {
      height: 8px;
      border-radius: 999px;
      background: #e5ecef;
      position: relative;
    }
    .interval-band {
      position: absolute;
      top: 0;
      bottom: 0;
      border-radius: inherit;
      background: rgba(56,163,165,.45);
    }
    .interval-pin {
      position: absolute;
      top: 50%;
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: var(--accent);
      border: 2px solid #fff;
      transform: translate(-50%, -50%);
      box-shadow: 0 2px 8px rgba(0,0,0,.18);
    }
    .kicker {
      color: var(--muted);
      font-size: 13px;
      text-transform: uppercase;
      font-weight: 800;
    }
    .ideology {
      font-family: var(--display);
      font-size: 42px;
      line-height: 1.05;
      margin: 0;
      text-wrap: balance;
    }
    .chips {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .identity-line {
      display: flex;
      gap: 14px;
      align-items: center;
      min-width: 0;
    }
    .avatar {
      --tone-a: #22577a;
      --tone-b: #38a3a5;
      flex: 0 0 auto;
      width: 46px;
      height: 46px;
      border-radius: 50%;
      display: grid;
      place-items: center;
      color: #fff;
      font-weight: 900;
      border: 2px solid rgba(255,255,255,.9);
      background:
        radial-gradient(circle at 35% 30%, rgba(255,255,255,.35), transparent 28%),
        linear-gradient(135deg, var(--tone-a), var(--tone-b));
      box-shadow: 0 8px 24px rgba(16,36,47,.14);
      transition: transform .22s ease, box-shadow .22s ease;
      position: relative;
      overflow: hidden;
    }
    .avatar img {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      object-fit: cover;
      z-index: 1;
    }
    .avatar.logo {
      background: #fff;
      border-color: rgba(16,36,47,.10);
      color: var(--accent);
    }
    .avatar.logo img {
      object-fit: contain;
      padding: 5px;
      background: #fff;
    }
    .avatar.portrait img {
      filter: saturate(.95) contrast(1.04);
    }
    .avatar.media::after {
      content: "";
      position: absolute;
      inset: 0;
      border-radius: inherit;
      box-shadow: inset 0 0 0 1px rgba(255,255,255,.25);
      z-index: 2;
      pointer-events: none;
    }
    .identity-line:hover .avatar,
    .identity-match:hover .avatar {
      transform: rotate(-3deg) scale(1.04);
      box-shadow: 0 14px 32px rgba(16,36,47,.18);
    }
    .avatar.large {
      width: 72px;
      height: 72px;
      font-size: 24px;
    }
    .avatar.user-photo {
      background-size: cover;
      background-position: center;
      color: transparent;
    }
    .user-strip {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 12px;
      border-radius: 8px;
      background: #f7fbfb;
      border: 1px solid var(--line);
    }
    .user-strip strong {
      display: block;
      font-size: 16px;
    }
    .identity-match {
      align-items: center;
    }
    .identity-main {
      min-width: 0;
      display: flex;
      gap: 10px;
      align-items: center;
    }
    .identity-main strong {
      min-width: 0;
    }
    .chip {
      background: #edf3f4;
      color: #284452;
      border-radius: 999px;
      padding: 7px 10px;
      font-weight: 700;
      font-size: 13px;
      border: 1px solid rgba(34,87,122,.08);
    }
    .axis {
      display: grid;
      gap: 7px;
      padding: 11px 0;
      border-bottom: 1px solid var(--line);
    }
    .axis:last-child { border-bottom: 0; }
    .axis-head {
      display: flex;
      justify-content: space-between;
      gap: 14px;
      font-weight: 800;
    }
    .axisbar {
      height: 12px;
      border-radius: 999px;
      background: linear-gradient(90deg, #3579a8 0%, #edf1f2 50%, #be6d4f 100%);
      position: relative;
      overflow: visible;
    }
    .pin {
      width: 18px;
      height: 18px;
      border-radius: 999px;
      background: var(--ink);
      border: 3px solid white;
      position: absolute;
      top: 50%;
      transform: translate(-50%, -50%);
      box-shadow: 0 2px 8px rgba(0,0,0,.25);
      transition: left .55s cubic-bezier(.2,.8,.2,1);
    }
    .small {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.4;
    }
    .chart-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
      align-items: start;
    }
    .chart-img {
      width: 100%;
      height: auto;
      border-radius: 8px;
      border: 1px solid var(--line);
      background: #111827;
      display: block;
    }
	    .viz-canvas {
      width: 100%;
      min-height: 320px;
      aspect-ratio: 16 / 10;
      border-radius: 8px;
      border: 1px solid var(--line);
	      background:
	        linear-gradient(135deg, rgba(34,87,122,.08), rgba(242,184,128,.10)),
	        #fbfcfc;
      display: block;
      box-shadow: inset 0 1px 0 rgba(255,255,255,.9);
      transition: box-shadow .18s ease, transform .18s ease;
    }
    .viz-canvas:hover {
      box-shadow: inset 0 1px 0 rgba(255,255,255,.9), var(--shadow-soft);
    }
	    .map-wrap {
	      position: relative;
	      padding: 8px;
	      border-radius: 8px;
	      background:
	        repeating-linear-gradient(135deg, rgba(34,87,122,.055) 0 10px, rgba(242,184,128,.08) 10px 20px),
	        linear-gradient(135deg, #f8fbfa, #fff7ec);
	      border: 1px solid rgba(34,87,122,.14);
	    }
	    .map-wrap .viz-canvas {
	      border-color: rgba(34,87,122,.18);
	      box-shadow: inset 0 1px 0 rgba(255,255,255,.9), 0 14px 38px rgba(16,36,47,.10);
	    }
    .tooltip {
      position: absolute;
      pointer-events: none;
      transform: translate(12px, 12px);
      background: #10242f;
      color: white;
      padding: 8px 10px;
      border-radius: 6px;
      font-size: 12px;
      display: none;
	      max-width: 240px;
	      z-index: 3;
	      box-shadow: 0 12px 30px rgba(16,36,47,.25);
	    }
    .poster {
      display: grid;
      gap: 18px;
      max-width: 420px;
      margin: 0 auto;
      padding: 28px;
      border-radius: 8px;
      background:
        linear-gradient(160deg, #10242f 0%, #16384a 58%, #23333a 100%);
      color: #fff;
      border: 1px solid rgba(255,255,255,.12);
      box-shadow: 0 22px 60px rgba(16,36,47,.22);
    }
    .poster-preview {
      display: grid;
      gap: 12px;
      justify-items: center;
    }
    .poster h2 {
      font-family: var(--display);
      font-size: 28px;
      line-height: 1.05;
      margin: 0;
    }
    .poster .avatar {
      border-color: rgba(255,255,255,.25);
      box-shadow: none;
    }
    .mini-axis {
      display: grid;
      gap: 5px;
    }
    .mini-axis span {
      font-size: 12px;
      color: #c5d5dc;
    }
    .mini-track {
      height: 8px;
      border-radius: 999px;
      background: linear-gradient(90deg, #38a3a5 0%, #eef3f5 50%, #f2b880 100%);
      position: relative;
    }
    .mini-pin {
      width: 12px;
      height: 12px;
      border-radius: 999px;
      background: #fff;
      position: absolute;
      top: 50%;
      transform: translate(-50%, -50%);
      transition: left .45s ease;
    }
    .social-img {
      max-width: 360px;
      width: 100%;
      margin: 0 auto;
    }
    .method-hero {
      display: grid;
      gap: 12px;
      padding: 22px;
      border-radius: 8px;
      background:
        linear-gradient(135deg, rgba(34,87,122,.10), rgba(56,163,165,.10)),
        #ffffff;
      border: 1px solid var(--line);
    }
    .method-hero h3 {
      font-family: var(--display);
      font-size: 30px;
      line-height: 1.08;
      margin: 0;
    }
    .method-steps {
      counter-reset: method;
      display: grid;
      gap: 12px;
    }
    .method-step {
      counter-increment: method;
      display: grid;
      grid-template-columns: 42px minmax(0, 1fr);
      gap: 12px;
      align-items: start;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      background: #fbfcfc;
    }
    .method-step::before {
      content: counter(method);
      width: 34px;
      height: 34px;
      border-radius: 999px;
      display: grid;
      place-items: center;
      background: var(--accent);
      color: #fff;
      font-weight: 900;
    }
    .method-step h4 {
      margin: 0 0 5px;
      font-size: 16px;
    }
    .comparison-table {
      width: 100%;
      border-collapse: collapse;
      overflow: hidden;
      border-radius: 8px;
      border: 1px solid var(--line);
      background: #fff;
    }
    .comparison-table th,
    .comparison-table td {
      padding: 12px;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
      text-align: left;
    }
    .comparison-table th {
      background: #10242f;
      color: #fff;
      font-size: 13px;
      text-transform: uppercase;
    }
    .comparison-table tr:last-child td { border-bottom: 0; }
    .share-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }
    .share-grid .btn {
      width: 100%;
      text-align: center;
    }
    .share-link-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 8px;
      align-items: center;
    }
    .share-link-row input,
    .share-copy {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 11px 12px;
      background: #fff;
      color: var(--ink);
    }
    .share-copy {
      min-height: 118px;
      resize: vertical;
    }
    .share-status {
      min-height: 20px;
      color: var(--good);
      font-weight: 800;
    }
    .phone-steps {
      display: grid;
      gap: 8px;
      margin: 0;
      padding: 0;
      list-style: none;
    }
    .phone-steps li {
      padding: 10px 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfc;
    }
    .explain-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }
    .explain {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      background: #fbfcfc;
      transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
    }
    .explain:hover {
      transform: translateY(-2px);
      box-shadow: var(--shadow-soft);
      border-color: rgba(56,163,165,.45);
    }
    .explain h4 {
      margin: 0 0 8px;
      font-size: 16px;
    }
    .explain p { margin: 0; }
    .list {
      display: grid;
      gap: 10px;
    }
    .match {
      display: flex;
      justify-content: space-between;
      gap: 14px;
      padding: 10px 0;
      border-bottom: 1px solid var(--line);
      transition: background .16s ease, padding .16s ease;
    }
    .match:hover {
      background: #f7fbfb;
      padding-left: 8px;
      padding-right: 8px;
      border-radius: 8px;
    }
    .match:last-child { border-bottom: 0; }
    .match strong { display: block; }
    .score {
      font-weight: 900;
      color: var(--accent);
      white-space: nowrap;
    }
    .warning {
      border-left: 4px solid var(--warm);
      padding: 12px;
      background: #fff8ef;
      border-radius: 6px;
      color: #65401d;
    }
    .inline-error {
      margin: 0;
      font-weight: 750;
    }
    .app-notice {
      position: fixed;
      right: 18px;
      top: 18px;
      z-index: 80;
      width: min(390px, calc(100vw - 36px));
      box-shadow: var(--shadow);
      animation: rise .24s ease both;
    }
    .welcome-card,
    .completion-card {
      display: grid;
      gap: 12px;
      justify-items: start;
      border-radius: 8px;
      padding: 18px;
      background:
        linear-gradient(135deg, rgba(56,163,165,.10), rgba(242,184,128,.12)),
        #fbfcfc;
      border: 1px solid var(--line);
    }
    .welcome-sigil,
    .completion-sigil {
      width: 58px;
      height: 58px;
      border-radius: 50%;
      display: grid;
      place-items: center;
      color: #10242f;
      font-weight: 900;
      background: conic-gradient(from 90deg, var(--accent-2), var(--warm), #f7f2e8, var(--accent-2));
      position: relative;
      box-shadow: 0 12px 30px rgba(16,36,47,.12);
    }
    .welcome-sigil::after,
    .completion-sigil::after {
      content: "";
      position: absolute;
      inset: -7px;
      border-radius: 50%;
      border: 1px dashed rgba(34,87,122,.35);
      animation: orbit 9s linear infinite;
    }
    .completion-card {
      min-height: 280px;
      place-content: center;
      justify-items: center;
      text-align: center;
      animation: finishPulse .55s cubic-bezier(.2,.8,.2,1) both;
    }
    .welcome-card {
      grid-template-columns: auto minmax(0, 1fr);
      align-items: center;
    }
    .completion-card h3 {
      font-family: var(--display);
      font-size: 32px;
      margin: 0;
    }
    .coherence-strip {
      display: grid;
      grid-template-columns: 92px minmax(0, 1fr);
      gap: 14px;
      align-items: center;
      margin-bottom: 18px;
    }
    .coherence-ring {
      --score: 0deg;
      width: 92px;
      height: 92px;
      border-radius: 50%;
      background: conic-gradient(var(--accent-2) 0 var(--score), #e5ecef var(--score) 360deg);
      display: grid;
      place-items: center;
      position: relative;
      box-shadow: inset 0 0 0 1px rgba(34,87,122,.08);
    }
    .coherence-ring::after {
      content: "";
      position: absolute;
      width: 68px;
      height: 68px;
      border-radius: 50%;
      background: #fff;
      box-shadow: inset 0 1px 0 rgba(255,255,255,.9);
    }
    .coherence-ring strong {
      position: relative;
      z-index: 1;
      font-size: 20px;
      color: var(--accent);
    }
    .coherence-bars {
      display: grid;
      gap: 7px;
      margin-top: 10px;
    }
    .reliability-card {
      margin: 14px 0 20px;
      padding: 16px;
      border: 1px solid rgba(34,87,122,.12);
      border-radius: var(--radius);
      background: linear-gradient(135deg, rgba(56,163,165,.12), rgba(242,184,128,.18));
      box-shadow: inset 0 1px 0 rgba(255,255,255,.65);
    }
    .reliability-head {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
      margin-bottom: 10px;
    }
    .reliability-head strong {
      color: var(--accent);
    }
    .confidence-meter {
      height: 10px;
      border-radius: 999px;
      overflow: hidden;
      background: rgba(16,36,47,.10);
      margin-bottom: 10px;
    }
    .confidence-meter span {
      display: block;
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, var(--accent-2), var(--gold));
    }
    .coherence-bar {
      display: grid;
      gap: 4px;
    }
    .coherence-bar span {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      font-size: 12px;
      color: var(--muted);
    }
    .coherence-track {
      height: 7px;
      border-radius: 999px;
      background: #e5ecef;
      overflow: hidden;
    }
    .coherence-fill {
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, var(--accent-2), var(--warm));
    }
    .field {
      display: grid;
      gap: 7px;
      margin-bottom: 12px;
    }
    .field label {
      font-weight: 800;
      font-size: 14px;
    }
    .field input, .field select, .field textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 11px 12px;
      background: #fff;
      color: var(--ink);
      transition: border-color .16s ease, box-shadow .16s ease;
    }
    .field input:focus, .field select:focus, .field textarea:focus {
      outline: none;
      border-color: var(--accent-2);
      box-shadow: 0 0 0 3px rgba(56,163,165,.14);
    }
    .field textarea {
      min-height: 90px;
      resize: vertical;
    }
    a { color: var(--accent); }

    /* Visual identity layer: app-like, vivid, still readable. */
    :root {
      --blue-deep: #10242f;
      --blue: #22577a;
      --teal: #38a3a5;
      --gold: #f2b880;
      --purple: #6d597a;
      --rose: #fde9ed;
      --rose-ink: #8f4258;
      --radius: 10px;
      --radius-lg: 12px;
      --shadow: 0 24px 70px rgba(16, 36, 47, .13);
      --shadow-soft: 0 14px 36px rgba(16, 36, 47, .09);
      --shadow-lift: 0 22px 46px rgba(16, 36, 47, .14);
    }
    body {
      min-height: 100vh;
      background:
        radial-gradient(circle at 9% 6%, rgba(56,163,165,.18), transparent 29%),
        radial-gradient(circle at 86% 10%, rgba(242,184,128,.22), transparent 31%),
        radial-gradient(circle at 76% 92%, rgba(109,89,122,.18), transparent 34%),
        linear-gradient(180deg, #fffdfa 0%, #f6f8f8 44%, #eef6f4 100%);
    }
    aside {
      background:
        radial-gradient(circle at 18% 8%, rgba(56,163,165,.42), transparent 30%),
        radial-gradient(circle at 85% 5%, rgba(242,184,128,.30), transparent 28%),
        linear-gradient(178deg, #10242f 0%, #143241 52%, #0c1c26 100%);
      overflow: hidden;
    }
    aside::before {
      content: "";
      position: absolute;
      inset: 0;
      background:
        linear-gradient(130deg, rgba(255,255,255,.08) 0 1px, transparent 1px 16px),
        linear-gradient(40deg, transparent 0 88%, rgba(255,255,255,.10));
      opacity: .38;
      pointer-events: none;
    }
    aside::after {
      content: "";
      position: absolute;
      left: 28px;
      right: 28px;
      bottom: 98px;
      height: 1px;
      background: linear-gradient(90deg, transparent, rgba(242,184,128,.42), rgba(56,163,165,.42), transparent);
      pointer-events: none;
    }
    aside > * { position: relative; z-index: 1; }
    .brand::before {
      width: 62px;
      height: 62px;
      border-radius: 18px;
      background:
        radial-gradient(circle at 50% 50%, #f2b880 0 12%, #10242f 13% 24%, transparent 25%),
        radial-gradient(circle at 50% 50%, #10242f 0 35%, transparent 36%),
        conic-gradient(from 220deg, var(--teal), var(--gold), var(--purple), var(--teal));
      box-shadow: 0 18px 46px rgba(0,0,0,.26), inset 0 0 0 1px rgba(255,255,255,.28);
    }
    .brand h1 {
      text-shadow: 0 8px 28px rgba(0,0,0,.22);
    }
    .track {
      height: 13px;
      background: rgba(255,255,255,.13);
      border: 1px solid rgba(255,255,255,.10);
    }
    .fill {
      background: linear-gradient(90deg, var(--teal), var(--gold), var(--purple));
      box-shadow: 0 0 24px rgba(56,163,165,.42);
    }
    .topbar {
      padding: 4px 0 2px;
    }
    .step-title,
    .ideology,
    .archetype-card h3,
    .experience-panel h4,
    .completion-card h3 {
      letter-spacing: 0;
    }
    .question-panel,
    .block,
    .mode-card,
    .trust-chip,
    .setup-details,
    .advanced-panel,
    .explain,
    .partner-panel,
    .partner-card,
    .startup-card,
    .dominant-axis,
    .welcome-card,
    .completion-card,
    .method-hero,
    .method-step,
    .world-card,
    .poster,
    .viz-canvas,
    .map-wrap {
      border-radius: var(--radius-lg);
    }
    .question-panel {
      border-color: rgba(34,87,122,.16);
      background:
        linear-gradient(135deg, rgba(56,163,165,.085), transparent 34%),
        radial-gradient(circle at 92% 8%, rgba(242,184,128,.14), transparent 28%),
        radial-gradient(circle at 84% 96%, rgba(109,89,122,.10), transparent 34%),
        rgba(255,255,255,.94);
      backdrop-filter: blur(8px);
    }
    .question-panel::before {
      height: 5px;
      background: linear-gradient(90deg, var(--blue), var(--teal), var(--gold), var(--purple), var(--blue));
      background-size: 260% 100%;
    }
    .question-panel::after {
      content: "";
      position: absolute;
      top: 22px;
      right: 22px;
      width: 82px;
      height: 82px;
      border-radius: 999px;
      border: 16px solid rgba(56,163,165,.07);
      pointer-events: none;
    }
    .question-text {
      max-width: 980px;
    }
    .option {
      border-color: rgba(34,87,122,.14);
      background:
        linear-gradient(90deg, rgba(255,255,255,.94), rgba(248,252,252,.90)),
        #fff;
      box-shadow: 0 1px 0 rgba(255,255,255,.9);
    }
    .option::after {
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(90deg, rgba(56,163,165,.13), rgba(242,184,128,.13));
      opacity: 0;
      transition: opacity .18s ease;
      pointer-events: none;
    }
    .option:hover::after,
    .option.selected::after { opacity: 1; }
    .option > * { position: relative; z-index: 1; }
    .option.selected {
      border-color: rgba(56,163,165,.78);
      box-shadow: 0 0 0 3px rgba(56,163,165,.13), var(--shadow-soft);
    }
    .num {
      background: rgba(34,87,122,.10);
      color: var(--blue);
      box-shadow: inset 0 0 0 1px rgba(34,87,122,.08);
    }
    .option.selected .num {
      background: linear-gradient(135deg, var(--blue), var(--teal));
    }
    .btn {
      border-radius: var(--radius);
      background: linear-gradient(135deg, #edf4f5, #dfe9ed);
      box-shadow: 0 1px 0 rgba(255,255,255,.8);
      white-space: normal;
    }
    .btn.primary {
      background: linear-gradient(135deg, var(--blue), #17384d 52%, var(--purple));
      color: #fff;
      box-shadow: 0 14px 28px rgba(34,87,122,.20);
    }
    .surface-actions .btn.primary,
    #nextBtn.btn.primary {
      background: linear-gradient(135deg, var(--gold), #e4a665 44%, var(--teal));
      color: #10242f;
    }
    .btn:hover:not(:disabled) {
      transform: translateY(-2px);
      box-shadow: var(--shadow-soft);
    }
    .welcome-card {
      background:
        radial-gradient(circle at 10% 5%, rgba(56,163,165,.20), transparent 32%),
        radial-gradient(circle at 92% 10%, rgba(242,184,128,.26), transparent 32%),
        linear-gradient(135deg, rgba(255,255,255,.96), rgba(248,252,252,.92));
      border-color: rgba(34,87,122,.15);
      box-shadow: var(--shadow-soft);
    }
    .welcome-sigil,
    .completion-sigil {
      border-radius: 18px;
      background:
        radial-gradient(circle at 50% 50%, #10242f 0 24%, transparent 25%),
        conic-gradient(from 220deg, var(--teal), var(--gold), var(--purple), var(--teal));
      color: transparent;
    }
    .welcome-sigil::before,
    .completion-sigil::before {
      content: "";
      width: 30px;
      height: 30px;
      background: #fff;
      clip-path: polygon(50% 7%, 60% 40%, 93% 50%, 60% 60%, 50% 93%, 40% 60%, 7% 50%, 40% 40%);
      display: block;
    }
    .hero-badge,
    .chip,
    .tag {
      border-color: rgba(34,87,122,.14);
      background: linear-gradient(135deg, rgba(255,255,255,.92), rgba(232,243,247,.72));
    }
    .experience-panel {
      background:
        radial-gradient(circle at 12% 10%, rgba(56,163,165,.22), transparent 33%),
        radial-gradient(circle at 92% 8%, rgba(242,184,128,.26), transparent 34%),
        radial-gradient(circle at 86% 94%, rgba(109,89,122,.16), transparent 34%),
        #ffffff;
    }
    .experience-step {
      border-color: rgba(34,87,122,.12);
      box-shadow: 0 8px 22px rgba(16,36,47,.055);
    }
    .experience-step:nth-child(1) span { background: linear-gradient(135deg, var(--blue), var(--teal)); }
    .experience-step:nth-child(2) span { background: linear-gradient(135deg, var(--teal), var(--gold)); color: #10242f; }
    .experience-step:nth-child(3) span { background: linear-gradient(135deg, var(--purple), var(--rose-ink)); }
    .mode-card {
      --mode-a: var(--blue);
      --mode-b: var(--teal);
      --mode-bg-a: rgba(34,87,122,.12);
      --mode-bg-b: rgba(56,163,165,.10);
      --mode-ring: rgba(34,87,122,.16);
      min-height: 142px;
      padding: 16px 16px 16px 18px;
      border-color: rgba(34,87,122,.14);
      background:
        linear-gradient(135deg, var(--mode-bg-a), var(--mode-bg-b) 58%, #fff);
      box-shadow: 0 10px 28px rgba(16,36,47,.06);
    }
    .mode-card::before {
      width: 5px;
      background: linear-gradient(180deg, var(--mode-a), var(--mode-b));
      opacity: .95;
    }
    .mode-card::after {
      content: "";
      position: absolute;
      width: 96px;
      height: 96px;
      right: -34px;
      bottom: -40px;
      border-radius: 999px;
      background: radial-gradient(circle, var(--mode-bg-b), transparent 68%);
      pointer-events: none;
    }
    .mode-card.mode-social { --mode-a: var(--blue); --mode-b: var(--teal); --mode-bg-a: rgba(34,87,122,.12); --mode-bg-b: rgba(56,163,165,.11); --mode-ring: rgba(34,87,122,.18); }
    .mode-card.mode-quick { --mode-a: var(--teal); --mode-b: var(--gold); --mode-bg-a: rgba(56,163,165,.13); --mode-bg-b: rgba(242,184,128,.16); --mode-ring: rgba(56,163,165,.20); }
    .mode-card.mode-deep { --mode-a: var(--gold); --mode-b: var(--purple); --mode-bg-a: rgba(242,184,128,.18); --mode-bg-b: rgba(109,89,122,.12); --mode-ring: rgba(109,89,122,.18); }
    .mode-card.mode-election { --mode-a: var(--rose-ink); --mode-b: var(--gold); --mode-bg-a: rgba(253,233,237,.86); --mode-bg-b: rgba(242,184,128,.18); --mode-ring: rgba(184,74,98,.16); }
    .mode-card.selected {
      border-color: var(--mode-a);
      background:
        linear-gradient(135deg, var(--mode-bg-a), var(--mode-bg-b)),
        #fff;
      box-shadow: 0 0 0 3px var(--mode-ring), var(--shadow-soft);
    }
    .mode-card.locked {
      border-style: solid;
      background:
        repeating-linear-gradient(135deg, rgba(184,74,98,.08) 0 9px, rgba(242,184,128,.14) 9px 18px),
        linear-gradient(135deg, #fff, #fff7e8);
    }
    .badge {
      background: linear-gradient(135deg, var(--purple), var(--rose-ink));
      box-shadow: 0 7px 18px rgba(109,89,122,.20);
    }
    .trust-chip,
    .setup-details,
    .partner-card,
    .startup-card,
    .explain {
      border-color: rgba(34,87,122,.12);
      background: rgba(255,255,255,.86);
      box-shadow: 0 8px 22px rgba(16,36,47,.045);
    }
    .setup-details[open] {
      box-shadow: var(--shadow-soft);
      border-color: rgba(56,163,165,.28);
    }
    .tabs {
      border: 1px solid rgba(34,87,122,.10);
      border-radius: var(--radius-lg);
      padding: 8px;
      background: rgba(255,255,255,.72);
      box-shadow: 0 10px 32px rgba(16,36,47,.07);
    }
    .tab {
      border-radius: var(--radius);
      background: rgba(255,255,255,.86);
      border-color: rgba(34,87,122,.12);
    }
    .tab.active {
      background: linear-gradient(135deg, var(--blue), var(--teal) 55%, var(--purple));
      box-shadow: 0 12px 24px rgba(34,87,122,.18);
    }
    .results.visible {
      animation: resultReveal .42s cubic-bezier(.2,.8,.2,1) both;
    }
    .block {
      border-color: rgba(34,87,122,.13);
      background:
        linear-gradient(135deg, rgba(255,255,255,.98), rgba(248,252,252,.94)),
        #fff;
    }
    .hero-result,
    .archetype-card {
      position: relative;
      overflow: hidden;
    }
    .hero-result::before,
    .archetype-card::before,
    .world-card::before {
      content: "";
      position: absolute;
      inset: 0 0 auto;
      height: 5px;
      background: linear-gradient(90deg, var(--teal), var(--gold), var(--purple));
      pointer-events: none;
    }
    .archetype-card {
      border-color: rgba(109,89,122,.24);
      background:
        radial-gradient(circle at 8% 8%, rgba(56,163,165,.18), transparent 30%),
        radial-gradient(circle at 94% 12%, rgba(242,184,128,.24), transparent 30%),
        linear-gradient(135deg, rgba(255,255,255,.96), rgba(253,233,237,.48));
      box-shadow: var(--shadow-soft);
    }
    .ideology {
      color: #142936;
    }
    .world-card {
      background:
        radial-gradient(circle at 10% 0%, rgba(56,163,165,.16), transparent 32%),
        linear-gradient(135deg, rgba(255,255,255,.96), rgba(248,252,252,.90));
      box-shadow: 0 10px 28px rgba(16,36,47,.06);
    }
    .world-card:nth-child(2)::before { background: linear-gradient(90deg, var(--gold), var(--purple)); }
    .world-card:nth-child(3)::before { background: linear-gradient(90deg, var(--purple), var(--rose-ink)); }
    .world-card.nemesi {
      border-color: rgba(184,74,98,.20);
      background:
        radial-gradient(circle at 12% 0%, rgba(253,233,237,.72), transparent 36%),
        linear-gradient(135deg, #fff, #fff8ef);
    }
    .coherence-ring {
      background: conic-gradient(var(--teal) 0 var(--score), rgba(242,184,128,.28) var(--score) 360deg);
    }
    .reliability-card {
      border-radius: var(--radius-lg);
      border-color: rgba(56,163,165,.20);
      background:
        radial-gradient(circle at 0% 0%, rgba(56,163,165,.18), transparent 32%),
        linear-gradient(135deg, rgba(255,255,255,.96), rgba(255,243,216,.64));
    }
    .confidence-meter span,
    .coherence-fill {
      background: linear-gradient(90deg, var(--teal), var(--gold), var(--purple));
    }
    .axisbar,
    .mini-track {
      background: linear-gradient(90deg, var(--teal) 0%, #eef3f5 50%, var(--gold) 100%);
    }
    .pin {
      background: linear-gradient(135deg, var(--blue-deep), var(--purple));
    }
    .viz-canvas,
    .map-wrap {
      border-color: rgba(34,87,122,.15);
      background:
        radial-gradient(circle at 12% 10%, rgba(56,163,165,.12), transparent 30%),
        radial-gradient(circle at 90% 10%, rgba(242,184,128,.16), transparent 30%),
        linear-gradient(135deg, #fbfdfd, #fffaf2);
    }
    .poster {
      background:
        radial-gradient(circle at 10% 0%, rgba(56,163,165,.32), transparent 35%),
        radial-gradient(circle at 92% 10%, rgba(242,184,128,.24), transparent 34%),
        linear-gradient(160deg, #10242f 0%, #18384a 48%, #4d4059 100%);
      border-radius: var(--radius-lg);
    }
    .share-grid .btn:nth-child(1) { background: linear-gradient(135deg, var(--teal), var(--blue)); color: #fff; }
    .share-grid .btn:nth-child(2) { background: linear-gradient(135deg, var(--gold), #f7d09d); color: #10242f; }
    .share-grid .btn:nth-child(3) { background: linear-gradient(135deg, var(--purple), #8f6d90); color: #fff; }
    .share-grid .btn:nth-child(4) { background: linear-gradient(135deg, #edf4f5, #fff); }
    .warning {
      border-left-color: var(--gold);
      background: linear-gradient(135deg, rgba(255,248,239,.96), rgba(253,233,237,.60));
      color: #65401d;
    }
    .app-notice {
      border: 1px solid rgba(242,184,128,.32);
    }
    .avatar {
      background:
        radial-gradient(circle at 35% 30%, rgba(255,255,255,.42), transparent 28%),
        linear-gradient(135deg, var(--blue), var(--teal) 45%, var(--purple));
    }
    .field input,
    .field select,
    .field textarea,
    .share-link-row input,
    .share-copy {
      border-color: rgba(34,87,122,.14);
      background: rgba(255,255,255,.94);
    }
    @keyframes resultReveal {
      from { opacity: 0; transform: translateY(16px) scale(.992); }
      to { opacity: 1; transform: translateY(0) scale(1); }
    }
    @media (max-width: 900px) {
      .shell { grid-template-columns: 1fr; }
      aside {
        position: static;
        height: auto;
        padding: 22px;
      }
      .result-grid { grid-template-columns: 1fr; }
	      .chart-grid, .explain-grid, .share-grid, .world-grid, .trust-strip, .partner-grid, .startup-grid, .experience-strip { grid-template-columns: 1fr; }
      .coherence-strip { grid-template-columns: 1fr; }
      .share-link-row { grid-template-columns: 1fr; }
      main { padding: 18px; }
      .question-text { font-size: 22px; }
      .brand h1 { font-size: 36px; }
      .topbar { align-items: flex-start; flex-direction: column; }
      .question-panel { padding: 20px; min-height: 520px; }
      .question-panel::after { width: 58px; height: 58px; border-width: 12px; }
      .option { padding: 14px; }
      .nav { display: grid; grid-template-columns: 1fr 1fr; }
      .btn { width: 100%; min-width: 0; }
      .mode-card { min-height: auto; }
      .ideology { font-size: 34px; }
      .archetype-card h3 { font-size: 26px; }
      .tabs {
        flex-wrap: nowrap;
        overflow-x: auto;
        scrollbar-width: thin;
      }
      .tab { flex: 0 0 auto; }
      .welcome-card { grid-template-columns: 1fr; }
      .surface-actions .btn { flex: 1 1 180px; }
    }
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after {
        animation-duration: .001ms !important;
        animation-iteration-count: 1 !important;
        scroll-behavior: auto !important;
        transition-duration: .001ms !important;
      }
    }
  </style>
</head>
<body>
  <div class="shell">
    <aside>
      <div class="brand">
        <h1>Politometro</h1>
        <p>Test politico multi-asse con modello di confidenza e confronto ideologico.</p>
      </div>
      <div class="meter">
        <div class="meter-top">
          <span id="count">0 / 0</span>
          <span id="percent">0%</span>
        </div>
        <div class="track"><div id="progress" class="fill"></div></div>
      </div>
      <div class="side-note">
        Il risultato non misura una verità definitiva: stima un profilo coerente con le risposte, segnala incertezza e mostra dove il dato è più o meno stabile.
      </div>
    </aside>
    <main>
      <section id="quiz">
        <div class="topbar">
          <div>
            <h2 class="step-title" id="stepTitle">Caricamento</h2>
            <p class="step-subtitle" id="stepSubtitle">Preparo le domande.</p>
          </div>
          <button class="btn" id="resetBtn">↺ Ricomincia</button>
        </div>
        <div class="question-panel">
          <h2 class="question-text" id="questionText"></h2>
          <div class="options" id="options"></div>
          <div class="nav">
            <button class="btn" id="prevBtn">← Indietro</button>
            <button class="btn primary" id="nextBtn">Avanti →</button>
          </div>
        </div>
      </section>
      <section id="results" class="results"></section>
    </main>
  </div>
  <script>
    window.addEventListener("beforeinstallprompt", (event) => {
      event.preventDefault();
      if (window.__politometroState) window.__politometroState.deferredInstallPrompt = event;
    });
    const QUESTION_BOOTSTRAP = "__QUESTION_BOOTSTRAP__";
    const state = {
      questions: [],
      index: 0,
      answers: {},
      researchConsent: false,
      demographics: {},
      started: false,
      lastResult: null,
      sessionId: `local-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      mode: "quick",
      selectedQuestions: [],
      quickQuestionIds: [],
      socialQuestionIds: [],
	      deferredInstallPrompt: null,
	      mapView: { scale: 1, offsetX: 0, offsetY: 0, hover: null },
	      mapPoints: [],
	      mapPulseTimer: null,
	      identity: { nickname: "", avatarMode: "generated", photoDataUrl: "" },
      touchStart: null,
    };
    window.__politometroState = state;
    const el = (id) => document.getElementById(id);

    function showAppNotice(message) {
      const old = document.getElementById("appNotice");
      if (old) old.remove();
      const box = document.createElement("div");
      box.id = "appNotice";
      box.className = "warning app-notice";
      box.textContent = message;
      document.body.appendChild(box);
      window.setTimeout(() => box.remove(), 6200);
    }

    function showInlineError(message) {
      const panel = document.querySelector(".question-panel");
      if (!panel) {
        showAppNotice(message);
        return;
      }
      let box = document.getElementById("inlineError");
      if (!box) {
        box = document.createElement("div");
        box.id = "inlineError";
        box.className = "warning inline-error";
        panel.insertBefore(box, panel.firstElementChild);
      }
      box.textContent = message;
    }

    function clearInlineError() {
      document.getElementById("inlineError")?.remove();
    }

    function applyQuestionPayload(data, source = "pagina") {
      const questions = Array.isArray(data?.questions)
        ? data.questions.filter((q) => q && q.id && q.question && Array.isArray(q.options) && q.options.length)
        : [];
      if (!questions.length) return false;
      const quickIds = Array.isArray(data.quick_question_ids) ? data.quick_question_ids : [];
      const socialIds = Array.isArray(data.social_question_ids) ? data.social_question_ids : [];
      state.questions = questions;
      state.quickQuestionIds = quickIds.length ? quickIds : questions.filter((q) => q.quick).map((q) => q.id);
      state.socialQuestionIds = socialIds.length ? socialIds : state.quickQuestionIds.slice(0, 12);
      if (!state.started) {
        state.selectedQuestions = questions;
        renderConsentIntro();
      } else if (!state.selectedQuestions.length) {
        state.selectedQuestions = selectQuestionSet();
        if (state.selectedQuestions.length) renderQuestionAnimated();
      }
      return true;
    }

    function useEmbeddedQuestions() {
      const ok = applyQuestionPayload(QUESTION_BOOTSTRAP, "pagina");
      if (!ok) {
        el("questionText").textContent = "Non riesco a preparare le domande.";
        el("options").innerHTML = `<div class="warning">Chiudi e riapri il server locale. Se continua, avvisami: il file delle domande non è stato incluso correttamente.</div>`;
        el("nextBtn").disabled = true;
      }
      return ok;
    }

    function answerValue(text) {
      return Number(String(text).trim().slice(0, 1));
    }

    function escapeHtml(value) {
      return String(value || "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;",
      }[char]));
    }

    function updateProgress() {
      const answered = Object.keys(state.answers).length;
      const total = (state.selectedQuestions.length || state.questions.length) || 1;
      const pct = Math.round(answered / total * 100);
      el("count").textContent = `${answered} / ${total}`;
      el("percent").textContent = `${pct}%`;
      el("progress").style.width = `${pct}%`;
    }

    function renderQuestion() {
      const q = state.selectedQuestions[state.index];
      if (!q) {
        el("questionText").textContent = "Non riesco a trovare le domande per questa modalità.";
        el("options").innerHTML = `<div class="warning">Ricarica la pagina. Se il problema continua, usa la modalità profonda.</div>`;
        el("nextBtn").disabled = true;
        return;
      }
      updateProgress();
      el("stepTitle").textContent = `Domanda ${state.index + 1}`;
      const modeLabel = state.mode === "social" ? "social" : state.mode === "quick" ? "rapida" : "profonda";
      el("stepSubtitle").textContent = `${state.selectedQuestions.length - state.index - 1} domande rimanenti · modalità ${modeLabel} · puoi usare anche swipe`;
      el("questionText").textContent = q.question;
      el("options").innerHTML = "";

      q.options.forEach((option) => {
        const value = answerValue(option);
        const button = document.createElement("button");
        button.className = "option";
        if (state.answers[q.id] === value) button.classList.add("selected");
        button.innerHTML = `<span class="num">${value}</span><span>${option.replace(/^\\d\\s*[–-]\\s*/, "")}</span>`;
        button.addEventListener("click", () => {
          clearInlineError();
          state.answers[q.id] = value;
          renderQuestion();
        });
        el("options").appendChild(button);
      });

      el("prevBtn").disabled = state.index === 0;
      const isLast = state.index === state.selectedQuestions.length - 1;
      el("nextBtn").textContent = isLast ? "Calcola risultato →" : "Avanti →";
      el("nextBtn").disabled = !state.answers[q.id];
    }

    function renderQuestionAnimated() {
      const panel = document.querySelector(".question-panel");
      if (!panel || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        renderQuestion();
        return;
      }
      panel.classList.add("switching");
      window.setTimeout(() => {
        renderQuestion();
        panel.classList.remove("switching");
      }, 120);
    }

    function renderCompletionAnimation() {
      updateProgress();
      el("stepTitle").textContent = "Quiz completato";
      el("stepSubtitle").textContent = "Sto leggendo il profilo, le tensioni interne e i confronti.";
      el("questionText").textContent = "";
      el("options").innerHTML = `
        <div class="completion-card">
          <div class="completion-sigil">OK</div>
          <h3>Sto componendo il tuo risultato</h3>
          <p class="small">Peso le risposte, controllo la coerenza interna e preparo grafici, mappa e report.</p>
        </div>
      `;
      el("prevBtn").disabled = true;
      el("nextBtn").disabled = true;
      el("nextBtn").textContent = "Calcolo in corso";
    }

    async function completeAndCalculate() {
      renderCompletionAnimation();
      await new Promise((resolve) => window.setTimeout(resolve, 720));
      await calculate();
    }

    async function calculate() {
      try {
        const response = await fetch("/api/result", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            answers: state.answers,
            research_consent: state.researchConsent,
            demographics: state.researchConsent ? state.demographics : {},
            session_id: state.sessionId,
            mode: state.mode,
          }),
        });
        if (!response.ok) {
          const error = await response.json().catch(() => ({}));
          const message = error.detail || "Risposte incomplete.";
          renderQuestionAnimated();
          window.setTimeout(() => showInlineError(message), 160);
          return;
        }
        const data = await response.json();
        renderResults(data);
      } catch (error) {
        const message = `Non riesco a calcolare il risultato: ${error.message || error}`;
        renderQuestionAnimated();
        window.setTimeout(() => showInlineError(message), 160);
      }
    }

    function axisDirection(value) {
      if (value < -0.15) return "sinistra / libertario / apertura";
      if (value > 0.15) return "destra / autorita / conservazione";
      return "zona bilanciata";
    }

    function renderAxis(axis) {
      const left = Math.max(2, Math.min(98, (axis.value + 1) * 50));
      return `
        <div class="axis">
          <div class="axis-head">
            <span>${axis.name}</span>
            <span>${axis.value >= 0 ? "+" : ""}${axis.value.toFixed(2)}</span>
          </div>
          <div class="axisbar"><span class="pin" style="left:${left}%"></span></div>
          <div class="small">${axisDirection(axis.value)} · confidenza asse ${Math.round(axis.confidence * 100)}%</div>
        </div>
      `;
    }

    function nameHash(text) {
      return Array.from(String(text)).reduce((acc, char) => ((acc << 5) - acc + char.charCodeAt(0)) | 0, 0);
    }

    function initials(name) {
      const words = String(name).replace(/[^\\p{L}\\p{N}\\s]/gu, " ").trim().split(/\\s+/).filter(Boolean);
      return (words[0]?.[0] || "P").toUpperCase() + (words[1]?.[0] || "").toUpperCase();
    }

    function paletteForName(name) {
      const palettes = [
        ["#22577a", "#38a3a5"],
        ["#7d4e57", "#f2b880"],
        ["#2f5d50", "#88b06a"],
        ["#493b73", "#c06c84"],
        ["#40514e", "#d9bf77"],
        ["#6d597a", "#355070"],
      ];
      return palettes[Math.abs(nameHash(name)) % palettes.length];
    }

    function commonsFile(file, width = 220) {
      return `https://commons.wikimedia.org/wiki/Special:FilePath/${encodeURIComponent(file)}?width=${width}`;
    }

    const ENTITY_MEDIA = {
      "PD": { type: "logo", src: commonsFile("PartitoDemocratico logo.png", 180) },
      "Alleanza Verdi e Sinistra": { type: "logo", src: commonsFile("Camera 2022 Alleanza Verdi-Sinistra.svg", 180) },
      "Movimento 5 Stelle": { type: "logo", src: commonsFile("Five Star Movement.svg", 180) },
      "Azione / Italia Viva": { type: "logo", src: commonsFile("Camera 2022 (U) Azione-Italia Viva.svg", 180) },
      "Azione": { type: "logo", src: commonsFile("Azione logo.svg", 180) },
      "Italia Viva": { type: "logo", src: commonsFile("Italia Viva logo.svg", 180) },
      "+Europa": { type: "logo", src: commonsFile("+Europa logo.svg", 180) },
      "Volt Italia": { type: "logo", src: commonsFile("Volt Europa logo.svg", 180) },
      "Sinistra Italiana": { type: "logo", src: commonsFile("Sinistra Italiana logo.svg", 180) },
      "Europa Verde": { type: "logo", src: commonsFile("Europa Verde logo.svg", 180) },
      "Noi Moderati": { type: "logo", src: commonsFile("Noi Moderati logo.svg", 180) },
      "Forza Italia": { type: "logo", src: commonsFile("Forza Italia 2022 electoral logo.png", 180) },
      "Lega": { type: "logo", src: commonsFile("Simbolo di Lega per Salvini Premier.svg", 180) },
      "Fratelli d'Italia": { type: "logo", src: commonsFile("Fratelli d'Italia logo.svg", 180) },
      "Partito Democratico (USA)": { type: "logo", src: commonsFile("US Democratic Party Logo.svg", 180) },
      "Partito Repubblicano (USA)": { type: "logo", src: commonsFile("Republicanlogo.svg", 180) },
      "Labour Party (UK)": { type: "logo", src: commonsFile("Labour Party logo, 1966.svg", 180) },
      "Conservative Party (UK)": { type: "logo", src: commonsFile("British party Conservative.svg", 180) },
      "SPD (GER)": { type: "logo", src: commonsFile("SPD logo.svg", 180) },
      "Karl Marx": { type: "portrait", src: commonsFile("Karl Marx.png", 220) },
      "Franklin D. Roosevelt": { type: "portrait", src: commonsFile("Franklin D. Roosevelt portrait - NARA - 196689.jpg", 220) },
      "John F. Kennedy": { type: "portrait", src: commonsFile("John F Kennedy Official Portrait.jpg", 220) },
      "Abraham Lincoln": { type: "portrait", src: commonsFile("President Abraham Lincoln Portrait.jpg", 220) },
      "George Washington": { type: "portrait", src: commonsFile("George Washington, 1776.jpg", 220) },
      "Winston Churchill": { type: "portrait", src: commonsFile("Winston Churchill's Portrait.jpg", 220) },
      "Margaret Thatcher": { type: "portrait", src: commonsFile("Margaret Thatcher Portrait 1984.jpg", 220) },
      "Ronald Reagan": { type: "portrait", src: commonsFile("Official Portrait of President Ronald Reagan.jpg", 220) },
      "Mahatma Gandhi": { type: "portrait", src: commonsFile("Portrait Gandhi.jpg", 220) },
      "Nelson Mandela": { type: "portrait", src: commonsFile("Nelson Mandela 1994 (2).jpg", 220) },
      "Martin Luther King Jr.": { type: "portrait", src: commonsFile("Martin Luther King, Jr..jpg", 220) },
      "Giuseppe Garibaldi": { type: "portrait", src: commonsFile("Giuseppe Garibaldi (1866).jpg", 220) },
      "Giuseppe Mazzini": { type: "portrait", src: commonsFile("Giuseppe Mazzini.jpg", 220) },
      "Niccolò Machiavelli": { type: "portrait", src: commonsFile("Portrait of Niccolò Machiavelli by Santi di Tito.jpg", 220) },
      "John Locke": { type: "portrait", src: commonsFile("John Locke.jpg", 220) },
      "Thomas Hobbes": { type: "portrait", src: commonsFile("Thomas Hobbes (portrait).jpg", 220) },
      "Luigi Einaudi": { type: "portrait", src: commonsFile("Luigi Einaudi official portrait.jpg", 220) },
      "Alcide De Gasperi": { type: "portrait", src: commonsFile("Alcide De Gasperi 2.jpg", 220) },
      "Norberto Bobbio": { type: "portrait", src: commonsFile("Norberto Bobbio.jpg", 220) },
      "John Maynard Keynes": { type: "portrait", src: commonsFile("Keynes 1933.jpg", 220) },
      "Friedrich Hayek": { type: "portrait", src: commonsFile("Friedrich Hayek portrait.jpg", 220) },
      "Hannah Arendt": { type: "portrait", src: commonsFile("Hannah Arendt 1975 (cropped).jpg", 220) },
      "Alexis de Tocqueville": { type: "portrait", src: commonsFile("Alexis de tocqueville.jpg", 220) },
      "Platone": { type: "portrait", src: commonsFile("Plato Silanion Musei Capitolini MC1377.jpg", 220) },
      "Aristotele": { type: "portrait", src: commonsFile("Aristotle Altemps Inv8575.jpg", 220) },
      "Napoleone Bonaparte": { type: "portrait", src: commonsFile("Jacques-Louis David - The Emperor Napoleon in His Study at the Tuileries - Google Art Project.jpg", 220) },
      "Benito Mussolini": { type: "portrait", src: commonsFile("Benito Mussolini cropped.jpg", 220) },
      "Adolf Hitler": { type: "portrait", src: commonsFile("Hitler portrait crop.jpg", 220) },
      "Josif Stalin": { type: "portrait", src: commonsFile("Stalin 1902.jpg", 220) },
      "Mao Zedong": { type: "portrait", src: commonsFile("Mao Zedong portrait.jpg", 220) },
      "Augusto Pinochet": { type: "portrait", src: commonsFile("Augusto Pinochet 1974.jpg", 220) },
      "Francisco Franco": { type: "portrait", src: commonsFile("Francisco Franco 1969.jpg", 220) },
      "Vladimir Lenin": { type: "portrait", src: commonsFile("Vladimir Lenin.jpg", 220) },
      "Che Guevara": { type: "portrait", src: commonsFile("CheHigh.jpg", 220) },
      "Fidel Castro": { type: "portrait", src: commonsFile("Fidel Castro 1959.jpg", 220) },
      "Maximilien Robespierre": { type: "portrait", src: commonsFile("Maximilien Robespierre.jpg", 220) },
      "Otto von Bismarck": { type: "portrait", src: commonsFile("Bundesarchiv Bild 183-R68588, Otto von Bismarck.jpg", 220) },
      "Milton Friedman": { type: "portrait", src: commonsFile("Milton Friedman 1976.jpg", 220) },
      "Murray Rothbard": { type: "portrait", src: commonsFile("Murray Rothbard.jpg", 220) },
    };

    function renderPortrait(name, size = "") {
      const [a, b] = paletteForName(name);
      const label = initials(name);
      const media = ENTITY_MEDIA[name];
      const mediaMarkup = media
        ? `<img src="${escapeHtml(media.src)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove();this.parentElement.classList.remove('media','logo','portrait');">`
        : "";
      const classes = ["avatar", size, media ? "media" : "", media?.type || ""].filter(Boolean).join(" ");
      return `<span class="${classes}" style="--tone-a:${a};--tone-b:${b};" aria-hidden="true">${label}${mediaMarkup}</span>`;
    }

    function userDisplayName() {
      return state.identity.nickname.trim() || "Tu";
    }

    function userAvatarName(data) {
      if (state.identity.avatarMode === "historical") return data?.historical?.[0]?.name || data?.ideology?.name || userDisplayName();
      if (state.identity.avatarMode === "ideology") return data?.ideology?.name || userDisplayName();
      return userDisplayName();
    }

    function renderUserAvatar(data, size = "large") {
      if (state.identity.avatarMode === "photo" && state.identity.photoDataUrl) {
        return `<span class="avatar ${size} user-photo" style="background-image:url('${state.identity.photoDataUrl.replace(/'/g, "%27")}')" aria-hidden="true"></span>`;
      }
      return renderPortrait(userAvatarName(data), size);
    }

    function renderUserStrip(data) {
      const label = escapeHtml(userDisplayName());
      const sub = state.identity.avatarMode === "historical"
        ? `avatar storico: ${escapeHtml(data?.historical?.[0]?.name || "calcolato dal risultato")}`
        : state.identity.avatarMode === "photo"
          ? "foto personale locale, non salvata nei dati"
          : "avatar generato dal nickname";
      return `<div class="user-strip">${renderUserAvatar(data)}<div><strong>${label}</strong><span class="small">${sub}</span></div></div>`;
    }

    function renderMatches(items) {
      return items.map((item) => `
        <div class="match identity-match">
          <div class="identity-main">
            ${renderPortrait(item.name)}
            <strong>${item.name}<span class="small"> distanza ${item.distance}${item.metadata?.comparability === "extreme_context" ? " · alto rischio interpretativo" : ""}</span></strong>
          </div>
          <span class="score">${item.affinity}%</span>
        </div>
      `).join("");
    }

    function renderCoherence(data) {
      const c = data.self_coherence || { score: 0, label: "n/d", explanation: "Dato non disponibile.", signals: [], groups: [] };
      const score = Number(c.score || 0);
      const groups = (c.groups || []).slice(0, 3);
      return `
        <div class="coherence-strip">
          <div class="coherence-ring" style="--score:${Math.max(0, Math.min(100, score)) * 3.6}deg"><strong>${score.toFixed(0)}%</strong></div>
          <div>
            <span class="kicker">Coerenza interna</span>
            <h3 style="margin:4px 0 6px;">${c.label}</h3>
            <p class="small">${c.explanation}</p>
            <div class="chips">
              <span class="chip">${c.contradiction_count || 0} tensioni forti</span>
              <span class="chip">${c.neutral_answers || 0} risposte centrali</span>
            </div>
          </div>
        </div>
        ${groups.length ? `<div class="coherence-bars">${groups.map((group) => `
          <div class="coherence-bar">
            <span><b>${group.label}</b><b>${group.score}%</b></span>
            <div class="coherence-track"><div class="coherence-fill" style="width:${Math.max(0, Math.min(100, group.score))}%"></div></div>
          </div>
        `).join("")}</div>` : ""}
      `;
    }

    function renderReliability(data) {
      const r = data.reliability || { score: 0, label: "n/d", explanation: "Dato non disponibile.", signals: [], note: "" };
      const score = Number(r.score || 0);
      const signals = (r.signals || []).slice(0, 4);
      return `
        <div class="reliability-card">
          <div class="reliability-head">
            <span class="kicker">Affidabilità del risultato</span>
            <strong>${escapeHtml(r.label)} · ${score.toFixed(0)}%</strong>
          </div>
          <div class="confidence-meter"><span style="width:${Math.max(4, Math.min(100, score))}%"></span></div>
          <p class="small">${escapeHtml(r.explanation || "")}</p>
          ${signals.length ? `<div class="chips">${signals.map((signal) => `<span class="chip">${escapeHtml(signal)}</span>`).join("")}</div>` : ""}
          <p class="small">${escapeHtml(r.note || "")}</p>
        </div>
      `;
    }

    function axisByName(data, name) {
      return (data.axes || []).find((axis) => axis.name === name) || { value: 0, confidence: 0, name };
    }

    function resultArchetype(data) {
      const econ = axisByName(data, "Economia").value;
      const auth = axisByName(data, "Autorità").value;
      const culture = axisByName(data, "Cultura").value;
      const geo = axisByName(data, "Geopolitica").value;
      const env = axisByName(data, "Ambiente").value;
      const tech = axisByName(data, "Tecnologia").value;
      const equality = axisByName(data, "Uguaglianza").value;
      if (env < -0.32 && geo > 0.20) return { name: "Eco-sovranista", line: "transizione verde, identità politica e protezione nazionale nello stesso profilo." };
      if (tech > 0.28 && econ < 0.10 && culture < 0.20) return { name: "Tecno-riformista", line: "innovazione, pragmatismo e riforme con sensibilità sociale." };
      if (econ > 0.28 && culture < -0.20 && geo < 0.15) return { name: "Liberal-internazionalista", line: "mercato, apertura culturale e cooperazione esterna." };
      if (econ < -0.28 && culture < -0.20 && equality < -0.15) return { name: "Progressista redistributivo", line: "welfare, diritti e riduzione delle disuguaglianze." };
      if (auth > 0.28 && culture > 0.24) return { name: "Comunitarista d'ordine", line: "coesione, sicurezza e continuità culturale." };
      if (Math.abs(econ) < .25 && Math.abs(auth) < .25 && Math.abs(culture) < .30) return { name: "Pragmatico civico", line: "posizioni selettive, poco tribali e orientate al compromesso." };
      return { name: data.ideology?.name || "Profilo ibrido", line: data.interpretation?.family || "profilo multidimensionale" };
    }

    function dominantAxis(data) {
      return (data.axes || []).reduce((best, axis) => Math.abs(axis.value) > Math.abs(best.value) ? axis : best, data.axes?.[0] || { name: "n/d", value: 0, explanation: "" });
    }

    function intervalToPct(value) {
      return Math.max(0, Math.min(100, (Number(value) + 1) * 50));
    }

    function renderUncertainty(data, limit = 4) {
      const rows = (data.uncertainty?.axes || []).slice(0, limit);
      if (!rows.length) return `<p class="small">Intervalli non disponibili.</p>`;
      return `
        <div class="list">${rows.map((row) => `
          <div class="interval-row">
            <strong>${row.axis}</strong>
            <div>
              <div class="interval-track">
                <span class="interval-band" style="left:${intervalToPct(row.low)}%;right:${100 - intervalToPct(row.high)}%"></span>
                <span class="interval-pin" style="left:${intervalToPct(row.value)}%"></span>
              </div>
              <p class="small" style="margin:6px 0 0;">${row.low} / ${row.high}</p>
            </div>
          </div>
        `).join("")}</div>
        <p class="small">${data.uncertainty?.note || ""}</p>
      `;
    }

    function jumpToTab(name) {
      activateTab(name);
      window.setTimeout(() => drawVisuals(state.lastResult), 40);
      window.scrollTo({ top: 0, behavior: "smooth" });
    }

    function activateTab(name) {
      document.querySelectorAll(".tab").forEach((tab) => {
        tab.classList.toggle("active", tab.dataset.tab === name);
      });
      document.querySelectorAll(".tab-panel").forEach((panel) => {
        panel.classList.toggle("active", panel.id === `panel-${name}`);
      });
    }

    function selectQuestionSet() {
      if (state.mode === "deep") return state.questions;
      const socialFallback = state.quickQuestionIds.slice(0, 12);
      const buckets = state.mode === "social"
        ? (state.socialQuestionIds.length ? state.socialQuestionIds : socialFallback)
        : (state.quickQuestionIds.length ? state.quickQuestionIds : state.questions.filter((q) => q.quick).map((q) => q.id));
      const byId = Object.fromEntries(state.questions.map((q) => [q.id, q]));
      return buckets.map((id) => byId[id]).filter(Boolean);
    }

    function renderCards(items) {
      return items.map((item) => `
        <div class="explain">
          <h4>${item.title}</h4>
          <p class="small">${item.body}</p>
        </div>
      `).join("");
    }

    function setupCanvas(canvas) {
      const rect = canvas.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.max(1, Math.floor(rect.width * dpr));
      canvas.height = Math.max(1, Math.floor(rect.height * dpr));
      const ctx = canvas.getContext("2d");
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      return { ctx, width: rect.width, height: rect.height };
    }

    function drawRadar(data) {
      const canvas = document.getElementById("radarCanvas");
      if (!canvas) return;
      const { ctx, width, height } = setupCanvas(canvas);
      const axes = data.axes;
      const cx = width / 2;
      const cy = height / 2 + 10;
      const radius = Math.min(width, height) * 0.34;
      ctx.clearRect(0, 0, width, height);
      ctx.strokeStyle = "#d9e1e7";
      ctx.fillStyle = "#60707c";
      ctx.font = "12px system-ui";
      for (let ring = 1; ring <= 4; ring++) {
        ctx.beginPath();
        for (let i = 0; i < axes.length; i++) {
          const angle = -Math.PI / 2 + i * Math.PI * 2 / axes.length;
          const r = radius * ring / 4;
          const x = cx + Math.cos(angle) * r;
          const y = cy + Math.sin(angle) * r;
          if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.closePath();
        ctx.stroke();
      }
      const points = axes.map((axis, i) => {
        const angle = -Math.PI / 2 + i * Math.PI * 2 / axes.length;
        const r = radius * (axis.value + 1) / 2;
        return { x: cx + Math.cos(angle) * r, y: cy + Math.sin(angle) * r, angle };
      });
      ctx.beginPath();
      points.forEach((p, i) => i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y));
      ctx.closePath();
      ctx.fillStyle = "rgba(34, 87, 122, .22)";
      ctx.strokeStyle = "#22577a";
      ctx.lineWidth = 3;
      ctx.fill();
      ctx.stroke();
      axes.forEach((axis, i) => {
        const angle = -Math.PI / 2 + i * Math.PI * 2 / axes.length;
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.lineTo(cx + Math.cos(angle) * radius, cy + Math.sin(angle) * radius);
        ctx.strokeStyle = "#e5ecef";
        ctx.lineWidth = 1;
        ctx.stroke();
        const lx = cx + Math.cos(angle) * (radius + 34);
        const ly = cy + Math.sin(angle) * (radius + 34);
        ctx.fillStyle = "#172026";
        ctx.textAlign = lx < cx - 10 ? "right" : lx > cx + 10 ? "left" : "center";
        ctx.fillText(axis.name, lx, ly);
      });
    }

    function drawBars(data) {
      const canvas = document.getElementById("barCanvas");
      if (!canvas) return;
      const { ctx, width, height } = setupCanvas(canvas);
      ctx.clearRect(0, 0, width, height);
      const axes = data.axes;
      const left = 120;
      const right = width - 30;
      const mid = (left + right) / 2;
      const rowH = (height - 40) / axes.length;
      ctx.font = "13px system-ui";
      axes.forEach((axis, i) => {
        const y = 24 + i * rowH;
        ctx.fillStyle = "#172026";
        ctx.textAlign = "left";
        ctx.fillText(axis.name, 12, y + 5);
        ctx.fillStyle = "#edf3f4";
        ctx.fillRect(left, y - 8, right - left, 16);
        ctx.fillStyle = axis.value >= 0 ? "#be6d4f" : "#3579a8";
        const barW = Math.abs(axis.value) * (right - left) / 2;
        if (axis.value >= 0) ctx.fillRect(mid, y - 8, barW, 16);
        else ctx.fillRect(mid - barW, y - 8, barW, 16);
        ctx.strokeStyle = "#172026";
        ctx.beginPath();
        ctx.moveTo(mid, y - 12);
        ctx.lineTo(mid, y + 12);
        ctx.stroke();
        ctx.fillStyle = "#60707c";
        ctx.textAlign = "right";
        ctx.fillText(`${axis.value >= 0 ? "+" : ""}${axis.value.toFixed(2)}`, width - 8, y + 5);
      });
    }

    function drawMap(data, filter = "all") {
      const canvas = document.getElementById("mapCanvas");
      if (!canvas) return;
      const { ctx, width, height } = setupCanvas(canvas);
      const pca = data.visuals.pca;
      const visible = pca.points.filter((p) => filter === "all" || p.category === filter);
      const points = [...visible, { ...pca.user, category: "user", name: "TU" }];
      const xs = points.map((p) => p.x);
      const ys = points.map((p) => p.y);
      const minX = Math.min(...xs), maxX = Math.max(...xs);
      const minY = Math.min(...ys), maxY = Math.max(...ys);
      const pad = 36;
      const sx0 = (x) => pad + (x - minX) / Math.max(.001, maxX - minX) * (width - pad * 2);
      const sy0 = (y) => height - pad - (y - minY) / Math.max(.001, maxY - minY) * (height - pad * 2);
	      const sx = (x) => (sx0(x) - width / 2) * state.mapView.scale + width / 2 + state.mapView.offsetX;
	      const sy = (y) => (sy0(y) - height / 2) * state.mapView.scale + height / 2 + state.mapView.offsetY;
	      const colors = { partito: "#22577a", ideologia: "#38a3a5", storico: "#b84a62", user: "#f2b880" };
	      ctx.clearRect(0, 0, width, height);
	      const bg = ctx.createLinearGradient(0, 0, width, height);
	      bg.addColorStop(0, "#f8fbfa");
	      bg.addColorStop(.44, "#eef8f6");
	      bg.addColorStop(1, "#fff4df");
	      ctx.fillStyle = bg;
	      ctx.fillRect(0, 0, width, height);
	      ctx.save();
	      ctx.globalAlpha = .55;
	      ctx.strokeStyle = "rgba(34,87,122,.13)";
	      ctx.lineWidth = 1;
	      for (let i = 1; i < 6; i++) {
	        const gx = pad + (width - pad * 2) * i / 6;
	        const gy = pad + (height - pad * 2) * i / 6;
	        ctx.beginPath();
	        ctx.moveTo(gx, pad);
	        ctx.lineTo(gx, height - pad);
	        ctx.moveTo(pad, gy);
	        ctx.lineTo(width - pad, gy);
	        ctx.stroke();
	      }
	      ctx.restore();
	      ctx.strokeStyle = "rgba(16,36,47,.26)";
	      ctx.lineWidth = 1.4;
	      ctx.beginPath();
	      ctx.moveTo(width / 2, pad);
	      ctx.lineTo(width / 2, height - pad);
	      ctx.moveTo(pad, height / 2);
	      ctx.lineTo(width - pad, height / 2);
	      ctx.stroke();
	      ctx.fillStyle = "rgba(16,36,47,.58)";
	      ctx.font = "700 11px system-ui";
	      ctx.fillText("PC1", width - pad - 22, height / 2 - 9);
	      ctx.fillText("PC2", width / 2 + 9, pad + 14);
	      const userPoint = { x: sx(pca.user.x), y: sy(pca.user.y) };
	      const nearest = visible
	        .map((p) => ({ ...p, screenX: sx(p.x), screenY: sy(p.y), d: Math.hypot(p.x - pca.user.x, p.y - pca.user.y) }))
	        .sort((a, b) => a.d - b.d)
	        .slice(0, 8);
	      nearest.forEach((p, i) => {
	        ctx.beginPath();
	        ctx.moveTo(userPoint.x, userPoint.y);
	        ctx.lineTo(p.screenX, p.screenY);
	        ctx.strokeStyle = i < 3 ? "rgba(242,184,128,.45)" : "rgba(34,87,122,.14)";
	        ctx.lineWidth = i < 3 ? 1.8 : 1;
	        ctx.stroke();
	      });
	      ctx.font = "11px system-ui";
	      state.mapPoints = [];
	      visible.forEach((p) => {
	        const x = sx(p.x), y = sy(p.y);
	        const radius = p.category === "storico" ? 4.3 : 5.4;
	        ctx.beginPath();
	        ctx.arc(x, y, radius + 3, 0, Math.PI * 2);
	        ctx.fillStyle = p.high_risk ? "rgba(154,164,170,.20)" : `${colors[p.category]}24`;
	        ctx.fill();
	        ctx.beginPath();
	        ctx.arc(x, y, radius, 0, Math.PI * 2);
	        ctx.fillStyle = p.high_risk ? "#9aa4aa" : colors[p.category];
	        ctx.fill();
	        ctx.strokeStyle = "rgba(255,255,255,.78)";
	        ctx.lineWidth = 1.5;
	        ctx.stroke();
	        state.mapPoints.push({ ...p, screenX: x, screenY: y });
	        if (filter !== "all" || p.category !== "storico") {
	          ctx.fillStyle = "#172026";
	          ctx.fillText(p.name.slice(0, 24), x + 7, y + 4);
	        }
	      });
	      const ux = userPoint.x, uy = userPoint.y;
	      state.mapPoints.push({ name: "TU", category: "user", screenX: ux, screenY: uy });
	      const pulse = 15 + Math.sin(Date.now() / 420) * 2;
	      ctx.beginPath();
	      ctx.arc(ux, uy, pulse, 0, Math.PI * 2);
	      ctx.fillStyle = "rgba(242,184,128,.24)";
	      ctx.fill();
	      ctx.beginPath();
	      ctx.arc(ux, uy, 11, 0, Math.PI * 2);
	      ctx.fillStyle = colors.user;
	      ctx.fill();
	      ctx.strokeStyle = "#172026";
	      ctx.lineWidth = 2;
	      ctx.stroke();
	      ctx.fillStyle = "#172026";
	      ctx.font = "bold 13px system-ui";
	      ctx.fillText("TU", ux + 14, uy + 4);
	      const legend = [
	        ["partiti", colors.partito],
	        ["ideologie", colors.ideologia],
	        ["storici", colors.storico],
	        ["tu", colors.user],
	      ];
	      let lx = 14;
	      const ly = height - 16;
	      ctx.font = "700 11px system-ui";
	      legend.forEach(([label, color]) => {
	        ctx.beginPath();
	        ctx.arc(lx, ly - 3, 4, 0, Math.PI * 2);
	        ctx.fillStyle = color;
	        ctx.fill();
	        ctx.fillStyle = "rgba(16,36,47,.72)";
	        ctx.fillText(label, lx + 8, ly);
	        lx += ctx.measureText(label).width + 32;
	      });
	    }

	    function setupMapInteractions(data) {
	      const canvas = document.getElementById("mapCanvas");
	      const tooltip = document.getElementById("mapTooltip");
	      if (!canvas || !tooltip || canvas.dataset.ready) return;
	      canvas.dataset.ready = "1";
	      if (state.mapPulseTimer) window.clearInterval(state.mapPulseTimer);
	      state.mapPulseTimer = window.setInterval(() => {
	        if (document.getElementById("panel-map")?.classList.contains("active")) {
	          drawMap(data, document.getElementById("mapFilter")?.value || "all");
	        }
	      }, 900);
	      canvas.addEventListener("wheel", (event) => {
        event.preventDefault();
        const delta = event.deltaY < 0 ? 1.12 : 0.88;
        state.mapView.scale = Math.max(0.7, Math.min(4, state.mapView.scale * delta));
        drawMap(data, document.getElementById("mapFilter")?.value || "all");
      });
      let dragging = false;
      let last = null;
      canvas.addEventListener("mousedown", (event) => {
        dragging = true;
        last = { x: event.clientX, y: event.clientY };
      });
      window.addEventListener("mouseup", () => { dragging = false; last = null; });
      canvas.addEventListener("mousemove", (event) => {
        const rect = canvas.getBoundingClientRect();
        if (dragging && last) {
          state.mapView.offsetX += event.clientX - last.x;
          state.mapView.offsetY += event.clientY - last.y;
          last = { x: event.clientX, y: event.clientY };
          drawMap(data, document.getElementById("mapFilter")?.value || "all");
          return;
        }
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;
        const hit = state.mapPoints.find((p) => Math.hypot(p.screenX - x, p.screenY - y) < 12);
        if (hit) {
          tooltip.style.display = "block";
          tooltip.style.left = `${x}px`;
          tooltip.style.top = `${y}px`;
          tooltip.innerHTML = `<strong>${hit.name}</strong><br>${hit.category}`;
        } else {
          tooltip.style.display = "none";
        }
      });
      canvas.addEventListener("mouseleave", () => { tooltip.style.display = "none"; });
    }

    function renderPoster(data) {
      const archetype = resultArchetype(data);
      return `
        <div class="poster">
          <span class="kicker" style="color:#c5d5dc;">Profilo Politometro</span>
          ${state.identity.nickname ? `<div class="user-strip" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);">${renderUserAvatar(data)}<div><strong>${escapeHtml(userDisplayName())}</strong><span class="small" style="color:#c5d5dc;">profilo personale</span></div></div>` : ""}
          <div class="identity-line">
            ${renderPortrait(archetype.name, "large")}
            <h2>${archetype.name}</h2>
          </div>
          <div class="chips">
            <span class="chip">${data.interpretation.family}</span>
            <span class="chip">confidenza ${data.confidence}%</span>
            <span class="chip">coerenza ${data.self_coherence?.score ?? "n/d"}%</span>
            <span class="chip">affidabilità ${data.reliability?.label || "n/d"}</span>
          </div>
          ${data.axes.map((axis) => `
            <div class="mini-axis">
              <span>${axis.name} · ${axis.value >= 0 ? "+" : ""}${axis.value.toFixed(2)}</span>
              <div class="mini-track"><i class="mini-pin" style="left:${Math.max(2, Math.min(98, (axis.value + 1) * 50))}%"></i></div>
            </div>
          `).join("")}
        </div>
      `;
    }

    function renderMethodologyPanel(data) {
      const calibration = data.calibration || {};
      const sources = data.sources || [];
      const steps = [
        ["Domande multi-asse", "Ogni domanda può caricare uno o più assi, ma il peso viene normalizzato: una risposta non deve dominare il profilo solo perché è scritta in modo forte."],
        ["Copertura e confidenza", "Il risultato non mostra solo una posizione: calcola anche quanto ogni asse è coperto, quanto le risposte sono nette e quante tensioni interne compaiono."],
        ["Prototipi confrontabili", "Partiti, ideologie e figure storiche sono trattati come punti nello stesso spazio a 8 assi; la vicinanza è una distanza matematica, non un giudizio morale."],
        ["Audit delle domande", "Il modello espone domande, assi coperti, criticità e prossimi controlli. Questo lo rende ispezionabile e correggibile."],
        ["Validazione con consenso", "I feedback facoltativi permettono di confrontare risultato calcolato, auto-descrizione e partito percepito, separando analisi aggregate e dati personali."],
      ];
      const calibrationCards = [
        { title: "Versione modello", body: data.model_version || "n/d" },
        { title: "Modalità usata", body: data.mode === "social" ? "Social: 12 domande, adatta alla condivisione ma meno precisa." : data.mode === "quick" ? "Rapida: 20 domande bilanciate, confidenza più prudente." : "Profonda: 60 domande, copertura maggiore degli assi." },
        { title: "Domande rapide", body: `${data.model_audit?.quick_question_ids?.length || 20} item scelti per coprire tutti gli assi senza concentrare il peso su un solo tema.` },
        { title: "Limite dichiarato", body: "Non è una diagnosi politica e non pretende neutralità assoluta: è uno strumento trasparente, spiegabile e migliorabile con dati." },
      ];
      return `
        <div class="method-hero">
          <span class="kicker">Metodo del Politometro</span>
          <h3>Perché il risultato è più trasparente di un quiz politico classico</h3>
          <p class="small">La forza del modello non sta nel dire “hai ragione” o “sei davvero X”. Sta nel mostrare come ci arriva: assi separati, pesi espliciti, confidenza, contraddizioni, fonti di calibrazione e confronto tra risultato e feedback volontario.</p>
        </div>
        <div class="result-grid">
          <div class="block">
            <h3>Processo di calcolo</h3>
            <div class="method-steps">${steps.map(([title, body]) => `
              <div class="method-step"><div><h4>${title}</h4><p class="small">${body}</p></div></div>
            `).join("")}</div>
          </div>
          <div class="block">
            <h3>Stato della calibrazione</h3>
            <div class="explain-grid">${renderCards(calibrationCards)}</div>
            <p class="small">${escapeHtml(calibration.summary || "Calibrazione interna orientata a copertura, chiarezza e riduzione dei bias di formulazione.")}</p>
          </div>
        </div>
        <div class="block">
          <h3>Confronto metodologico prudente</h3>
          <table class="comparison-table">
            <tr><th>Aspetto</th><th>Quiz politici classici</th><th>Politometro</th></tr>
            <tr><td>Spazio politico</td><td>Spesso 2 assi o categorie finali poco spiegate.</td><td>8 assi separati con valori, barre, radar e mappa compressa solo come vista secondaria.</td></tr>
            <tr><td>Incertezza</td><td>Il risultato tende a sembrare definitivo.</td><td>Mostra confidenza, copertura, completezza e incoerenze tematiche.</td></tr>
            <tr><td>Spiegabilità</td><td>Di solito vedi il risultato, non quali risposte lo hanno spinto.</td><td>Mostra le domande che hanno pesato di più e il verso del contributo.</td></tr>
            <tr><td>Calibrazione</td><td>Metodologia spesso opaca o non aggiornata per l'utente finale.</td><td>Espone audit, fonti esterne utili e feedback consensuale per correzioni future.</td></tr>
            <tr><td>Limite corretto</td><td>Rischio di far sembrare scientifico ciò che è soprattutto divulgativo.</td><td>Dichiara che diventa più forte solo con validazione, campioni e confronto con dataset esterni.</td></tr>
          </table>
        </div>
        <div class="block">
          <h3>Fonti di calibrazione e controllo</h3>
          <div class="explain-grid">${sources.map((item) => `
            <div class="explain">
              <h4><a href="${item.url}" target="_blank" rel="noreferrer">${item.name}</a></h4>
              <p class="small">${item.use}</p>
            </div>
          `).join("")}</div>
        </div>
      `;
    }

    function renderWorldAxisRows(rows, emptyText) {
      if (!rows?.length) return `<p class="small">${emptyText}</p>`;
      return `
        <div class="axis-mini-list">${rows.map((row) => `
          <div class="axis-mini-row">
            <strong>${escapeHtml(row.axis)}</strong>: ${escapeHtml(row.text)}
          </div>
        `).join("")}</div>
      `;
    }

    function renderWorldEntity(card, title) {
      if (!card) {
        return `
          <div class="world-card">
            <div class="world-head">${renderPortrait(title)}<div><h4>${title}</h4><p class="small">Dato non disponibile.</p></div></div>
          </div>
        `;
      }
      const kind = escapeHtml(card.kind || "");
      return `
        <article class="world-card ${kind}">
          <div class="world-head">
            ${renderPortrait(card.name)}
            <div>
              <span class="kicker">${title}</span>
              <h4>${escapeHtml(card.name)}</h4>
              <p class="small">Affinità ${Number(card.affinity || 0).toFixed(1)}% · distanza ${Number(card.distance || 0).toFixed(2)}</p>
              ${card.high_risk ? `<p class="small" style="color:#7a4a15;font-weight:800;">Alto rischio interpretativo: non è un paragone morale.</p>` : ""}
            </div>
          </div>
          <div>
            <h4>Cosa pensa in breve</h4>
            <p class="small">${escapeHtml(card.brief || "Sintesi non disponibile.")}</p>
            ${card.method_note ? `<p class="small">${escapeHtml(card.method_note)}</p>` : ""}
          </div>
          <div>
            <h4>Dove sei simile</h4>
            ${renderWorldAxisRows(card.similar, "Somiglianze non disponibili.")}
          </div>
          <div>
            <h4>Dove sei diverso</h4>
            ${renderWorldAxisRows(card.different, "Divergenze non disponibili.")}
          </div>
          <div class="world-actions">
            ${card.url ? `<a class="btn" href="${escapeHtml(card.url)}" target="_blank" rel="noreferrer">Approfondisci</a>` : ""}
            <span class="small">${escapeHtml(card.source_label || "Fonte")}</span>
          </div>
        </article>
      `;
    }

    function renderPoliticalWorld(data, compact = false) {
      const world = data.political_world || {};
      const body = `
        <div class="world-grid">
          ${renderWorldEntity(world.ideology, "Ideologia più vicina")}
          ${renderWorldEntity(world.party, "Partito più vicino")}
          ${renderWorldEntity(world.historical, "Personaggio più vicino")}
          ${renderWorldEntity(world.nemesis, "Nemesi metodologica")}
        </div>
        <p class="world-note">${escapeHtml(world.note || "Confronti interpretativi: non sono consigli di voto né equivalenze morali.")}</p>
      `;
      if (compact) {
        return `
          <div class="block">
            <span class="kicker">Nuovo</span>
            <h3>${escapeHtml(world.title || "Il tuo mondo politico")}</h3>
            <p class="small">${escapeHtml(world.summary || "Partito, figura storica e nemesi spiegati sugli 8 assi.")}</p>
            ${body}
          </div>
        `;
      }
      return `
        <div class="block">
          <span class="kicker">Lettura narrativa</span>
          <h3>${escapeHtml(world.title || "Il tuo mondo politico")}</h3>
          <p class="small">${escapeHtml(world.summary || "Partito, figura storica e nemesi spiegati sugli 8 assi.")}</p>
        </div>
        <div class="block">${body}</div>
      `;
    }

    function publicShareUrl() {
      if (location.protocol === "http:" || location.protocol === "https:") return location.href;
      return "";
    }

    function localLinkLabel() {
      const url = publicShareUrl();
      if (url) return url;
      return "Versione offline locale: per un link pubblico va caricata online o aperta da un server.";
    }

    function buildShareText(data) {
      const parties = (data.parties || []).slice(0, 3).map((item) => `${item.name} ${item.affinity}%`).join(", ");
      const historical = (data.historical || []).slice(0, 2).map((item) => `${item.name} ${item.affinity}%`).join(", ");
      const name = userDisplayName();
      const archetype = resultArchetype(data).name;
      const coherence = data.self_coherence ? ` Coerenza interna ${data.self_coherence.score}% (${data.self_coherence.label}).` : "";
      const reliability = data.reliability ? ` Affidabilità ${data.reliability.label}.` : "";
      return `${name} sul Politometro: ${archetype}. ${data.interpretation.family}; confidenza ${data.confidence}%.${coherence}${reliability} Partiti vicini: ${parties}. Confronti storici: ${historical}.`;
    }

    function buildTikTokCaption(data) {
      return `${buildShareText(data)} #politometro #politica #testpolitico`;
    }

    function setShareStatus(message) {
      const status = document.getElementById("shareStatus");
      if (status) status.textContent = message;
    }

    async function copyText(text) {
      try {
        if (navigator.clipboard?.writeText) {
          await navigator.clipboard.writeText(text);
          return;
        }
      } catch (_) {}
      const area = document.createElement("textarea");
      area.value = text;
      area.style.position = "fixed";
      area.style.left = "-9999px";
      document.body.appendChild(area);
      area.focus();
      area.select();
      const copied = document.execCommand("copy");
      area.remove();
      if (!copied) throw new Error("Copia non riuscita");
    }

    async function copyShareText(data, variant = "standard") {
      const text = variant === "tiktok" ? buildTikTokCaption(data) : buildShareText(data);
      await copyText(text);
      setShareStatus(variant === "tiktok" ? "Caption TikTok copiata. Usa anche la card PNG come visual." : "Testo copiato.");
    }

    async function copyShareLink() {
      const url = publicShareUrl();
      if (!url) {
        setShareStatus("Questa copia e offline: per avere un link condivisibile serve pubblicarla online o avviarla da un server raggiungibile.");
        return;
      }
      await copyText(url);
      setShareStatus("Link copiato.");
    }

    async function nativeShare(data) {
      const url = publicShareUrl();
      const payload = { title: "Politometro", text: buildShareText(data) };
      if (url) payload.url = url;
      if (navigator.share) {
        try {
          await navigator.share(payload);
          setShareStatus("Condivisione aperta.");
          return;
        } catch (_) {
          return;
        }
      }
      await copyShareText(data);
      setShareStatus("Il browser non apre il pannello di condivisione: testo copiato.");
    }

    async function openShareTarget(target, data) {
      const text = buildShareText(data);
      const url = publicShareUrl();
      let href = "";
      if (target === "whatsapp") href = `https://wa.me/?text=${encodeURIComponent(url ? `${text} ${url}` : text)}`;
      if (target === "telegram") href = `https://t.me/share/url?text=${encodeURIComponent(text)}${url ? `&url=${encodeURIComponent(url)}` : ""}`;
      if (target === "x") href = `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}${url ? `&url=${encodeURIComponent(url)}` : ""}`;
      if (target === "facebook" || target === "linkedin") {
        if (!url) {
          await copyShareText(data);
          setShareStatus("Per Facebook/LinkedIn serve un link pubblico: intanto ho copiato il testo.");
          return;
        }
        href = target === "facebook"
          ? `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`
          : `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`;
      }
      if (!href) return;
      window.open(href, "_blank", "noopener,noreferrer");
      setShareStatus("Finestra di condivisione aperta.");
    }

    async function openTikTokShare(data) {
      await copyShareText(data, "tiktok");
      window.open("https://www.tiktok.com/upload", "_blank", "noopener,noreferrer");
      setShareStatus("TikTok non accetta un post precompilato dal browser: ho copiato la caption e aperto l'upload.");
    }

    function syncShareBox(data) {
      const text = buildShareText(data);
      const link = localLinkLabel();
      const shareText = document.getElementById("shareText");
      const shareLink = document.getElementById("shareLink");
      if (shareText) shareText.value = text;
      if (shareLink) shareLink.value = link;
    }

    function drawVisuals(data) {
      drawRadar(data);
      drawBars(data);
      drawMap(data, document.getElementById("mapFilter")?.value || "all");
      setupMapInteractions(data);
    }

    function renderResults(data) {
      state.lastResult = data;
      el("quiz").style.display = "none";
      const warnings = data.contradictions.length
        ? `<div class="warning"><strong>Risultato meno stabile in alcuni blocchi.</strong><br>${data.contradictions.map(x => x.message).join("<br>")}</div>`
        : "";
      const archetype = resultArchetype(data);
      const dominant = dominantAxis(data);
      el("results").classList.add("visible");
      el("results").innerHTML = `
        <div class="tabs">
          <button class="tab active" data-tab="summary" data-icon="◎">Sintesi</button>
          <button class="tab" data-tab="world" data-icon="✦">Mondo</button>
          <button class="tab" data-tab="share" data-icon="□">Condividi</button>
          <button class="tab" data-tab="charts" data-icon="▥">Grafici</button>
          <button class="tab" data-tab="map" data-icon="⌖">Mappa</button>
          <button class="tab" data-tab="history" data-icon="※">Storici</button>
          <button class="tab" data-tab="report" data-icon="§">Spiegazioni</button>
          <button class="tab" data-tab="drivers" data-icon="↯">Peso domande</button>
          <button class="tab" data-tab="method" data-icon="∴">Metodo</button>
          <button class="tab" data-tab="audit" data-icon="◈">Audit</button>
          <button class="tab" data-tab="feedback" data-icon="◇">Feedback</button>
        </div>
        <div id="panel-summary" class="tab-panel active">
          <div class="result-grid">
            <div class="block hero-result">
              <span class="kicker">Il tuo archetipo</span>
              ${renderUserStrip(data)}
              <div class="archetype-card">
                <div class="identity-line">
                  ${renderPortrait(archetype.name, "large")}
                  <div>
                    <h2 class="ideology">${archetype.name}</h2>
                    <p class="small">${archetype.line}</p>
                  </div>
                </div>
                <div class="chips">
                  <span class="chip">${data.interpretation.family}</span>
                  <span class="chip">confidenza ${data.confidence}%</span>
                  <span class="chip">coerenza ${data.self_coherence?.score ?? "n/d"}%</span>
                  <span class="chip">affidabilità ${data.reliability?.label || "n/d"}</span>
                </div>
              </div>
              ${warnings}
              <div class="surface-actions">
                <button class="btn primary" id="surfaceShare">Condividi</button>
                <button class="btn" id="surfaceWorld">Il tuo mondo</button>
                <button class="btn" id="surfaceMap">Apri mappa</button>
                <button class="btn" id="surfaceDeep">Approfondisci</button>
              </div>
            </div>
            <div class="block">
              ${renderCoherence(data)}
              ${renderReliability(data)}
              <h3>Compatibilità partiti</h3>
              <div class="list">${renderMatches(data.parties.slice(0, 3))}</div>
            </div>
          </div>
          <div class="result-grid">
            <div class="block">
              <h3>Segnale dominante</h3>
              <div class="dominant-axis">
                <strong>${dominant.name} ${dominant.value >= 0 ? "+" : ""}${dominant.value.toFixed(2)}</strong>
                <div class="axisbar"><span class="pin" style="left:${Math.max(2, Math.min(98, (dominant.value + 1) * 50))}%"></span></div>
                <p class="small">${dominant.explanation}</p>
              </div>
            </div>
            <div class="block">
              <h3>Intervalli di prudenza</h3>
              ${renderUncertainty(data, 3)}
            </div>
          </div>
          ${renderPoliticalWorld(data, true)}
        </div>
        <div id="panel-world" class="tab-panel">
          ${renderPoliticalWorld(data)}
        </div>
        <div id="panel-history" class="tab-panel">
          <div class="block warning">
            <strong>Nota importante.</strong><br>
            I confronti storici sono opzionali e interpretativi: indicano somiglianza nello spazio a 8 assi, non equivalenza morale, biografica o storica.
          </div>
          <div class="result-grid">
            <div class="block">
            <h3>Confronti storici</h3>
            <div class="list">${renderMatches(data.historical)}</div>
            <h3 style="margin-top:24px;">Nemesi storica metodologica</h3>
            <div class="list">${renderMatches(data.historical_nemesis)}</div>
            <p class="small">La nemesi storica ora include anche figure ad alto rischio interpretativo. Se compaiono, vanno lette come distanza geometrica sugli assi, non come paragone morale o biografico.</p>
            </div>
            <div class="block">
            <h3 style="margin-top:24px;">Figure ad alto rischio interpretativo</h3>
            <div class="list">${renderMatches(data.historical_extreme_context)}</div>
            <p class="small">Sono incluse per completezza storica, ma segnalate separatamente per evitare letture sensazionalistiche o celebrative.</p>
            </div>
          </div>
        </div>
        <div id="panel-charts" class="tab-panel">
          <div class="chart-grid">
            <div class="block">
              <h3>Radar custom degli 8 assi</h3>
              <canvas id="radarCanvas" class="viz-canvas"></canvas>
              <p class="small">Grafico disegnato direttamente dal browser sui valori del modello, non immagine Gradio o Matplotlib.</p>
            </div>
            <div class="block">
              <h3>Barre direzionali</h3>
              <canvas id="barCanvas" class="viz-canvas"></canvas>
              <p class="small">Mostra direzione e intensità: sinistra del centro = polo negativo dell'asse, destra = polo positivo.</p>
            </div>
          </div>
        </div>
        <div id="panel-map" class="tab-panel">
          <div class="block">
            <div class="topbar">
              <div>
                <h3>Mappa PCA interattiva</h3>
                <p class="small">Varianza spiegata: PC1 ${(data.visuals.pca.explained_variance[0] * 100).toFixed(1)}%, PC2 ${(data.visuals.pca.explained_variance[1] * 100).toFixed(1)}%.</p>
              </div>
              <select id="mapFilter">
                <option value="all">Tutti</option>
                <option value="partito">Solo partiti</option>
                <option value="ideologia">Solo ideologie</option>
                <option value="storico">Solo storici</option>
              </select>
            </div>
            <div class="map-wrap">
              <canvas id="mapCanvas" class="viz-canvas"></canvas>
              <div id="mapTooltip" class="tooltip"></div>
            </div>
            <p class="small">Rotella: zoom. Trascina: spostamento. Passa sui punti: dettagli.</p>
          </div>
          <div class="block">
            <h3>Come leggere la mappa</h3>
            <p class="small">Il punto evidenziato sei tu. Punti vicini indicano somiglianza nel modello a 8 assi; punti lontani indicano divergenza. La PCA è una compressione: serve per orientarsi, mentre barre e radar sono più fedeli al profilo completo.</p>
          </div>
        </div>
        <div id="panel-report" class="tab-panel">
          <div class="block">
            <h3>Assi politici completi</h3>
            ${data.axes.map(renderAxis).join("")}
          </div>
          <details class="advanced-panel">
            <summary>Intervalli e prudenza interpretativa</summary>
            <div>${renderUncertainty(data, data.axes.length)}</div>
          </details>
          <div class="block">
            <h3>Referto esteso</h3>
            <div class="explain-grid">${renderCards(data.report)}</div>
          </div>
          <div class="block">
            <h3>Metodo e spiegazioni</h3>
            <div class="explain-grid">${renderCards(data.education)}</div>
          </div>
          <div class="block">
            <h3>Curiosità interpretative</h3>
            <div class="explain-grid">${data.curiosities.map((body, i) => `
              <div class="explain"><h4>Nota ${i + 1}</h4><p class="small">${body}</p></div>
            `).join("")}</div>
          </div>
        </div>
        <div id="panel-drivers" class="tab-panel">
          <div class="block">
            <h3>Le risposte che hanno pesato di più</h3>
            <p class="small">Questa sezione mostra quali risposte hanno spinto maggiormente il profilo. Serve a rendere il risultato spiegabile, non solo spettacolare.</p>
            <div class="list">${data.top_contributions.map((item) => `
              <div class="match">
                <strong>${item.question}<span class="small"> risposta ${item.answer} · ${item.primary_axis} · ${item.direction}</span></strong>
                <span class="score">${item.contribution >= 0 ? "+" : ""}${item.contribution}</span>
              </div>
            `).join("")}</div>
          </div>
        </div>
        <div id="panel-method" class="tab-panel">
          ${renderMethodologyPanel(data)}
        </div>
        <div id="panel-audit" class="tab-panel">
          <div class="result-grid">
            <div class="block">
              <h3>Stato del modello</h3>
              <div class="chips">
                <span class="chip">versione ${data.model_version}</span>
                <span class="chip">ok ${data.model_audit.question_status_counts.ok}</span>
                <span class="chip">review ${data.model_audit.question_status_counts.review}</span>
                <span class="chip">critiche ${data.model_audit.question_status_counts.critical}</span>
              </div>
              <h3 style="margin-top:24px;">Copertura assi</h3>
              <div class="list">${data.model_audit.axis_coverage.map((item) => `
                <div class="match"><strong>${item.axis}</strong><span class="score">${item.questions} domande</span></div>
              `).join("")}</div>
            </div>
            <div class="block">
              <h3>Prototipi</h3>
              <div class="list">${data.model_audit.prototype_status.map((item) => `
                <div class="match">
                  <strong>${item.group}<span class="small">${item.status} · ${item.next_step}</span></strong>
                  <span class="score">${item.count}</span>
                </div>
              `).join("")}</div>
            </div>
          </div>
          <div class="block">
            <h3>Domande da rivedere prima</h3>
            <div class="explain-grid">${data.model_audit.questions_to_review.map((item) => `
              <div class="explain">
                <h4>${item.id}</h4>
                <p class="small"><strong>${item.question}</strong></p>
                <p class="small">Asse primario: ${item.primary_axis}; problemi: ${item.issues.join(", ") || "nessuno"}.</p>
                <p class="small">${item.suggestion}</p>
              </div>
            `).join("")}</div>
          </div>
          <div class="block">
            <h3>Fonti per la calibrazione futura</h3>
            <div class="explain-grid">${data.sources.map((item) => `
              <div class="explain">
                <h4><a href="${item.url}" target="_blank" rel="noreferrer">${item.name}</a></h4>
                <p class="small">${item.use}</p>
              </div>
            `).join("")}</div>
          </div>
        </div>
        <div id="panel-feedback" class="tab-panel">
          <div class="result-grid">
            <div class="block">
              <h3>Aiuta a calibrare il modello</h3>
              <p class="small">Questo feedback serve a capire se il risultato matematico corrisponde alla percezione dell'utente. Viene salvato solo se hai dato consenso alla ricerca all'inizio.</p>
              <div class="field">
                <label for="accuracyRating">Quanto ti rappresenta il risultato?</label>
                <select id="accuracyRating">
                  <option value="5">5 - Molto accurato</option>
                  <option value="4">4 - Abbastanza accurato</option>
                  <option value="3">3 - Parziale</option>
                  <option value="2">2 - Poco accurato</option>
                  <option value="1">1 - Per niente accurato</option>
                </select>
              </div>
              <div class="field">
                <label for="selfLabel">Come ti descriveresti politicamente?</label>
                <input id="selfLabel" maxlength="200" placeholder="Esempio: socialdemocratico, liberale, conservatore sociale...">
              </div>
              <div class="field">
                <label for="closestPartySelf">Partito/movimento che senti più vicino</label>
                <input id="closestPartySelf" maxlength="200" placeholder="Facoltativo">
              </div>
              <div class="field">
                <label for="feedbackNotes">Cosa non torna o cosa manca?</label>
                <textarea id="feedbackNotes" maxlength="1000" placeholder="Facoltativo"></textarea>
              </div>
              <button class="btn primary" id="sendFeedback">Invia feedback</button>
              <p class="small" id="feedbackStatus"></p>
            </div>
            <div class="block">
              <h3>Perché è utile</h3>
              <div class="explain-grid">
                <div class="explain"><h4>Validazione</h4><p class="small">Se molte persone con una certa auto-descrizione finiscono altrove, i prototipi vanno ricalibrati.</p></div>
                <div class="explain"><h4>Domande</h4><p class="small">Se il risultato e spesso poco accurato, alcune domande possono essere ambigue o sovrappesate.</p></div>
                <div class="explain"><h4>Partiti</h4><p class="small">Il confronto tra partito percepito e partiti stimati aiuta a migliorare il mapping.</p></div>
                <div class="explain"><h4>Privacy</h4><p class="small">Il feedback e opzionale e resta locale in questa versione.</p></div>
              </div>
              <h3 style="margin-top:18px;">Test-retest</h3>
              <p class="small">Rifarlo tra circa due settimane aiuta a capire se il profilo e stabile o troppo dipendente dal momento.</p>
              <button class="btn" id="downloadRetest">Promemoria tra 14 giorni</button>
            </div>
          </div>
        </div>
        <div id="panel-share" class="tab-panel">
          <div class="result-grid">
            <div class="block">
              <h3>Card custom</h3>
              <div class="poster-preview" id="posterPreview">${renderPoster(data)}</div>
              <button class="btn primary" id="downloadCard">Scarica card PNG</button>
              <button class="btn" id="downloadPdf">Scarica report PDF</button>
            </div>
            <div class="block">
              <h3>Condividi dal telefono</h3>
              <p class="small">Su iPhone/Android il pulsante di sistema apre WhatsApp, Telegram, AirDrop, note o altre app disponibili. Per TikTok conviene scaricare la card PNG e usare la caption copiata.</p>
              <button class="btn primary" id="nativeShare">Condividi dal telefono</button>
              <div class="share-grid" style="margin-top:10px;">
                <button class="btn" id="shareWhatsapp">WhatsApp</button>
                <button class="btn" id="shareTelegram">Telegram</button>
                <button class="btn" id="shareX">X / Twitter</button>
                <button class="btn" id="shareFacebook">Facebook</button>
                <button class="btn" id="shareLinkedin">LinkedIn</button>
                <button class="btn" id="shareTiktok">TikTok</button>
              </div>
              <p class="small share-status" id="shareStatus"></p>
            </div>
          </div>
          <div class="result-grid">
            <div class="block">
              <h3>Testo e link</h3>
              <div class="field">
                <label for="shareText">Testo pronto</label>
                <textarea id="shareText" class="share-copy" readonly></textarea>
              </div>
              <button class="btn" id="copyShareText">Copia testo</button>
              <div class="field" style="margin-top:12px;">
                <label for="shareLink">Link della pagina</label>
                <div class="share-link-row">
                  <input id="shareLink" readonly>
                  <button class="btn" id="copyShareLink">Copia link</button>
                </div>
              </div>
              <p class="small">Se stai usando il file offline, il test funziona ma quel link non e pubblico. Per condividerlo davvero serve metterlo online o aprirlo da un server raggiungibile.</p>
            </div>
            <div class="block">
              <h3>App installabile</h3>
              <ol class="phone-steps">
                <li>Apri Politometro da un indirizzo http locale o, meglio, da https quando sara pubblicato.</li>
                <li>Usa “Installa app” o “Aggiungi alla schermata Home” dal browser.</li>
                <li>Dopo l'installazione si apre a schermo pieno come una piccola app.</li>
              </ol>
              <button class="btn primary" id="installAppResult" style="margin-top:12px;">Installa app</button>
              <p class="small">Da file offline i browser bloccano l'installazione PWA: è una regola del browser, non un problema del Politometro.</p>
            </div>
          </div>
        </div>
        <button class="btn primary" onclick="location.reload()">↺ Rifai il test</button>
      `;
      document.querySelectorAll(".tab").forEach((tab) => {
        tab.addEventListener("click", () => {
          activateTab(tab.dataset.tab);
          setTimeout(() => drawVisuals(data), 30);
        });
      });
      const mapFilter = document.getElementById("mapFilter");
      if (mapFilter) mapFilter.addEventListener("change", () => drawMap(data, mapFilter.value));
      const feedbackButton = document.getElementById("sendFeedback");
      if (feedbackButton) feedbackButton.addEventListener("click", submitFeedback);
      const retestButton = document.getElementById("downloadRetest");
      if (retestButton) retestButton.addEventListener("click", downloadRetestReminder);
      const cardButton = document.getElementById("downloadCard");
      if (cardButton) cardButton.addEventListener("click", () => downloadCard(data));
      const pdfButton = document.getElementById("downloadPdf");
      if (pdfButton) pdfButton.addEventListener("click", downloadPdf);
      const surfaceShare = document.getElementById("surfaceShare");
      if (surfaceShare) surfaceShare.addEventListener("click", () => jumpToTab("share"));
      const surfaceWorld = document.getElementById("surfaceWorld");
      if (surfaceWorld) surfaceWorld.addEventListener("click", () => jumpToTab("world"));
      const surfaceMap = document.getElementById("surfaceMap");
      if (surfaceMap) surfaceMap.addEventListener("click", () => jumpToTab("map"));
      const surfaceDeep = document.getElementById("surfaceDeep");
      if (surfaceDeep) surfaceDeep.addEventListener("click", () => jumpToTab("report"));
      const nativeShareButton = document.getElementById("nativeShare");
      if (nativeShareButton) nativeShareButton.addEventListener("click", () => nativeShare(data));
      const whatsappButton = document.getElementById("shareWhatsapp");
      if (whatsappButton) whatsappButton.addEventListener("click", () => openShareTarget("whatsapp", data));
      const telegramButton = document.getElementById("shareTelegram");
      if (telegramButton) telegramButton.addEventListener("click", () => openShareTarget("telegram", data));
      const xButton = document.getElementById("shareX");
      if (xButton) xButton.addEventListener("click", () => openShareTarget("x", data));
      const facebookButton = document.getElementById("shareFacebook");
      if (facebookButton) facebookButton.addEventListener("click", () => openShareTarget("facebook", data));
      const linkedinButton = document.getElementById("shareLinkedin");
      if (linkedinButton) linkedinButton.addEventListener("click", () => openShareTarget("linkedin", data));
      const tiktokButton = document.getElementById("shareTiktok");
      if (tiktokButton) tiktokButton.addEventListener("click", () => openTikTokShare(data));
      const copyTextButton = document.getElementById("copyShareText");
      if (copyTextButton) copyTextButton.addEventListener("click", () => copyShareText(data));
      const copyLinkButton = document.getElementById("copyShareLink");
      if (copyLinkButton) copyLinkButton.addEventListener("click", copyShareLink);
      const installResultButton = document.getElementById("installAppResult");
      if (installResultButton) installResultButton.addEventListener("click", requestInstallApp);
      syncShareBox(data);
      setTimeout(() => drawVisuals(data), 60);
      window.scrollTo({ top: 0, behavior: "smooth" });
    }

    async function downloadCard(data) {
      const archetype = resultArchetype(data);
      const canvas = document.createElement("canvas");
      const width = 1080, height = 1920;
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext("2d");
      const bg = ctx.createLinearGradient(0, 0, width, height);
      bg.addColorStop(0, "#10242f");
      bg.addColorStop(.48, "#17384d");
      bg.addColorStop(1, "#4d4059");
      ctx.fillStyle = bg;
      ctx.fillRect(0, 0, width, height);
      ctx.save();
      ctx.globalAlpha = .92;
      ctx.fillStyle = "#38a3a5";
      ctx.beginPath();
      ctx.arc(900, 150, 300, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#f2b880";
      ctx.beginPath();
      ctx.arc(115, 1685, 270, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#6d597a";
      ctx.beginPath();
      ctx.arc(980, 1480, 210, 0, Math.PI * 2);
      ctx.fill();
      ctx.globalAlpha = .20;
      ctx.fillStyle = "#ffffff";
      ctx.translate(-210, 0);
      ctx.rotate(-0.20);
      roundRect(ctx, 0, 395, 1500, 118, 58);
      ctx.fill();
      ctx.restore();

      const cardGradient = ctx.createLinearGradient(70, 238, 1010, 1640);
      cardGradient.addColorStop(0, "rgba(255,255,255,.16)");
      cardGradient.addColorStop(.56, "rgba(255,255,255,.08)");
      cardGradient.addColorStop(1, "rgba(255,255,255,.13)");
      ctx.fillStyle = cardGradient;
      roundRect(ctx, 64, 238, 952, 1420, 34);
      ctx.fill();
      ctx.strokeStyle = "rgba(255,255,255,.20)";
      ctx.lineWidth = 2;
      ctx.stroke();

      drawCanvasAppMark(ctx, 86, 82, 86);
      ctx.fillStyle = "#fff";
      ctx.font = "900 68px system-ui";
      ctx.fillText("POLITOMETRO", 190, 146);
      ctx.fillStyle = "#c5d5dc";
      ctx.font = "700 28px system-ui";
      ctx.fillText("Profilo politico multidimensionale", 192, 187);

      await drawCanvasUserAvatar(ctx, data, 860, 356, 132);
      ctx.font = "700 38px system-ui";
      ctx.fillStyle = "#c5d5dc";
      ctx.fillText(userDisplayName(), 96, 320);
      ctx.font = "900 88px system-ui";
      ctx.fillStyle = "#ffffff";
      wrapCanvasText(ctx, archetype.name.toUpperCase(), 96, 410, 790, 96);
      ctx.font = "500 40px system-ui";
      ctx.fillStyle = "#c5d5dc";
      wrapCanvasText(ctx, `${data.interpretation.family} · confidenza ${data.confidence}%`, 96, 610, 800, 52);

      const chipY = 715;
      drawCanvasChip(ctx, `coerenza ${data.self_coherence?.score ?? "n/d"}%`, 96, chipY, "#38a3a5");
      drawCanvasChip(ctx, `affidabilità ${data.reliability?.label || "n/d"}`, 365, chipY, "#f2b880", "#10242f");
      drawCanvasChip(ctx, data.mode === "deep" ? "60 domande" : data.mode === "social" ? "12 domande" : "20 domande", 660, chipY, "#6d597a");

      const startY = 840;
      data.axes.forEach((axis, i) => {
        const y = startY + i * 96;
        ctx.fillStyle = "#c5d5dc";
        ctx.font = "800 30px system-ui";
        ctx.fillText(`${axis.name} ${axis.value >= 0 ? "+" : ""}${axis.value.toFixed(2)}`, 96, y);
        ctx.fillStyle = "rgba(237,243,244,.92)";
        roundRect(ctx, 96, y + 22, 808, 22, 11);
        ctx.fill();
        const mid = 96 + 404;
        const bar = Math.abs(axis.value) * 404;
        ctx.fillStyle = axis.value >= 0 ? "#f2b880" : "#38a3a5";
        roundRect(ctx, axis.value >= 0 ? mid : mid - bar, y + 22, Math.max(6, bar), 22, 11);
        ctx.fill();
        ctx.fillStyle = "#10242f";
        ctx.beginPath();
        ctx.arc(mid + axis.value * 404, y + 33, 15, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = "rgba(255,255,255,.90)";
        ctx.lineWidth = 4;
        ctx.stroke();
      });

      ctx.save();
      ctx.globalAlpha = .18;
      const shine = ctx.createLinearGradient(180, 0, 900, 1450);
      shine.addColorStop(0, "rgba(255,255,255,0)");
      shine.addColorStop(.48, "rgba(255,255,255,.86)");
      shine.addColorStop(1, "rgba(255,255,255,0)");
      ctx.fillStyle = shine;
      ctx.translate(-70, 0);
      ctx.rotate(-0.18);
      roundRect(ctx, 270, 190, 210, 1660, 80);
      ctx.fill();
      ctx.restore();

      ctx.fillStyle = "#fff";
      ctx.font = "700 34px system-ui";
      ctx.fillText("politometro.local", 86, 1810);
      ctx.fillStyle = "#c5d5dc";
      ctx.font = "500 26px system-ui";
      ctx.fillText("Risultato interpretativo, non diagnostico.", 86, 1854);
      const a = document.createElement("a");
      a.href = canvas.toDataURL("image/png");
      a.download = "politometro-card.png";
      a.click();
    }

    function drawCanvasChip(ctx, text, x, y, color, ink = "#ffffff") {
      ctx.font = "800 28px system-ui";
      const width = Math.min(360, ctx.measureText(text).width + 34);
      ctx.fillStyle = color;
      roundRect(ctx, x, y - 34, width, 48, 24);
      ctx.fill();
      ctx.fillStyle = ink;
      ctx.fillText(text, x + 17, y);
      return width;
    }

    function drawCanvasAppMark(ctx, x, y, size) {
      const r = size * .18;
      const g = ctx.createLinearGradient(x, y, x + size, y + size);
      g.addColorStop(0, "#38a3a5");
      g.addColorStop(.48, "#f2b880");
      g.addColorStop(1, "#6d597a");
      ctx.fillStyle = g;
      roundRect(ctx, x, y, size, size, r);
      ctx.fill();
      const cx = x + size / 2;
      const cy = y + size / 2;
      ctx.fillStyle = "#10242f";
      ctx.beginPath();
      ctx.arc(cx, cy, size * .30, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#ffffff";
      const outer = size * .28;
      const inner = size * .07;
      ctx.beginPath();
      ctx.moveTo(cx, cy - outer);
      ctx.lineTo(cx + inner, cy - inner);
      ctx.lineTo(cx, cy);
      ctx.lineTo(cx - inner, cy - inner);
      ctx.closePath();
      ctx.fill();
      ctx.beginPath();
      ctx.moveTo(cx + outer, cy);
      ctx.lineTo(cx + inner, cy + inner);
      ctx.lineTo(cx, cy);
      ctx.lineTo(cx + inner, cy - inner);
      ctx.closePath();
      ctx.fill();
      ctx.beginPath();
      ctx.moveTo(cx, cy + outer);
      ctx.lineTo(cx - inner, cy + inner);
      ctx.lineTo(cx, cy);
      ctx.lineTo(cx + inner, cy + inner);
      ctx.closePath();
      ctx.fill();
      ctx.beginPath();
      ctx.moveTo(cx - outer, cy);
      ctx.lineTo(cx - inner, cy - inner);
      ctx.lineTo(cx, cy);
      ctx.lineTo(cx - inner, cy + inner);
      ctx.closePath();
      ctx.fill();
      ctx.fillStyle = "#f2b880";
      ctx.beginPath();
      ctx.arc(cx, cy, size * .065, 0, Math.PI * 2);
      ctx.fill();
    }

    function loadImage(src) {
      return new Promise((resolve, reject) => {
        const image = new Image();
        image.onload = () => resolve(image);
        image.onerror = reject;
        image.src = src;
      });
    }

    async function drawCanvasUserAvatar(ctx, data, cx, cy, radius) {
      if (state.identity.avatarMode === "photo" && state.identity.photoDataUrl) {
        try {
          const image = await loadImage(state.identity.photoDataUrl);
          ctx.save();
          ctx.beginPath();
          ctx.arc(cx, cy, radius, 0, Math.PI * 2);
          ctx.clip();
          const side = Math.min(image.width, image.height);
          const sx = (image.width - side) / 2;
          const sy = (image.height - side) / 2;
          ctx.drawImage(image, sx, sy, side, side, cx - radius, cy - radius, radius * 2, radius * 2);
          ctx.restore();
          ctx.lineWidth = 10;
          ctx.strokeStyle = "rgba(255,255,255,.35)";
          ctx.beginPath();
          ctx.arc(cx, cy, radius, 0, Math.PI * 2);
          ctx.stroke();
          return;
        } catch (_) {}
      }
      drawCanvasPortrait(ctx, userAvatarName(data), cx, cy, radius);
    }

    function drawCanvasPortrait(ctx, name, cx, cy, radius) {
      const [a, b] = paletteForName(name);
      const gradient = ctx.createLinearGradient(cx - radius, cy - radius, cx + radius, cy + radius);
      gradient.addColorStop(0, a);
      gradient.addColorStop(1, b);
      ctx.save();
      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.fillStyle = gradient;
      ctx.fill();
      ctx.globalAlpha = .28;
      ctx.beginPath();
      ctx.arc(cx - radius * .28, cy - radius * .34, radius * .42, 0, Math.PI * 2);
      ctx.fillStyle = "#ffffff";
      ctx.fill();
      ctx.globalAlpha = 1;
      ctx.lineWidth = 10;
      ctx.strokeStyle = "rgba(255,255,255,.35)";
      ctx.stroke();
      ctx.fillStyle = "#fff";
      ctx.font = `900 ${Math.floor(radius * .62)}px system-ui`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(initials(name), cx, cy + 3);
      ctx.textAlign = "left";
      ctx.textBaseline = "alphabetic";
      ctx.restore();
    }

    function wrapCanvasText(ctx, text, x, y, maxWidth, lineHeight) {
      const words = text.split(" ");
      let line = "";
      for (const word of words) {
        const test = line ? `${line} ${word}` : word;
        if (ctx.measureText(test).width > maxWidth && line) {
          ctx.fillText(line, x, y);
          y += lineHeight;
          line = word;
        } else {
          line = test;
        }
      }
      ctx.fillText(line, x, y);
    }

    function roundRect(ctx, x, y, w, h, r) {
      ctx.beginPath();
      ctx.moveTo(x + r, y);
      ctx.arcTo(x + w, y, x + w, y + h, r);
      ctx.arcTo(x + w, y + h, x, y + h, r);
      ctx.arcTo(x, y + h, x, y, r);
      ctx.arcTo(x, y, x + w, y, r);
      ctx.closePath();
    }

    async function downloadPdf() {
      const response = await fetch("/api/report-pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answers: state.answers, mode: state.mode }),
      });
      if (!response.ok) {
        showAppNotice("Non riesco a generare il PDF.");
        return;
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "politometro-report.pdf";
      a.click();
      URL.revokeObjectURL(url);
    }

    function downloadRetestReminder() {
      const start = new Date(Date.now() + 14 * 24 * 60 * 60 * 1000);
      const stamp = (date) => date.toISOString().replace(/[-:]/g, "").split(".")[0] + "Z";
      const end = new Date(start.getTime() + 20 * 60 * 1000);
      const ics = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Politometro//Test Retest//IT",
        "BEGIN:VEVENT",
        `UID:politometro-retest-${state.sessionId}`,
        `DTSTAMP:${stamp(new Date())}`,
        `DTSTART:${stamp(start)}`,
        `DTEND:${stamp(end)}`,
        "SUMMARY:Rifai il Politometro per test-retest",
        "DESCRIPTION:Ripeti il test con calma: aiuta a misurare stabilita del profilo e affidabilita delle domande.",
        "END:VEVENT",
        "END:VCALENDAR",
      ].join("\\r\\n");
      const blob = new Blob([ics], { type: "text/calendar" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "politometro-test-retest.ics";
      a.click();
      URL.revokeObjectURL(url);
    }

    async function submitFeedback() {
      const status = document.getElementById("feedbackStatus");
      if (!state.researchConsent) {
        status.textContent = "Feedback non salvato: all'inizio hai scelto di non contribuire ai dati di ricerca.";
        return;
      }
      const payload = {
        research_consent: state.researchConsent,
        session_id: state.sessionId,
        accuracy_rating: Number(document.getElementById("accuracyRating").value),
        self_label: document.getElementById("selfLabel").value,
        closest_party_self: document.getElementById("closestPartySelf").value,
        notes: document.getElementById("feedbackNotes").value,
        predicted_ideology: state.lastResult?.ideology?.name || "",
        predicted_parties: (state.lastResult?.parties || []).map((item) => item.name),
      };
      const response = await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      status.textContent = response.ok ? "Feedback salvato localmente. Grazie: questo migliora davvero il modello." : "Non sono riuscito a salvare il feedback.";
    }

    el("prevBtn").addEventListener("click", () => {
      clearInlineError();
      state.index = Math.max(0, state.index - 1);
      renderQuestionAnimated();
    });

    el("nextBtn").addEventListener("click", () => {
      clearInlineError();
      if (!state.started) {
        collectIdentity();
        state.demographics = collectDemographics();
        state.selectedQuestions = selectQuestionSet();
        if (!state.selectedQuestions.length) {
          useEmbeddedQuestions();
          state.selectedQuestions = selectQuestionSet();
        }
        if (!state.selectedQuestions.length) {
          showInlineError("Non riesco a preparare le domande per questa modalità. Riapri il server locale e riprova.");
          return;
        }
        state.answers = {};
        state.index = 0;
        state.started = true;
        renderQuestionAnimated();
        return;
      }
      const q = state.selectedQuestions[state.index];
      if (!state.answers[q.id]) return;
      if (state.index === state.selectedQuestions.length - 1) completeAndCalculate();
      else {
        state.index += 1;
        renderQuestionAnimated();
      }
    });

    el("resetBtn").addEventListener("click", () => {
      clearInlineError();
      state.index = 0;
      state.answers = {};
      state.researchConsent = false;
      state.demographics = {};
      state.started = false;
      state.selectedQuestions = [];
      state.sessionId = `local-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      state.mode = "quick";
      state.identity = { nickname: "", avatarMode: "generated", photoDataUrl: "" };
      renderConsentIntro();
    });

    const questionPanel = document.querySelector(".question-panel");
    questionPanel?.addEventListener("touchstart", (event) => {
      const touch = event.changedTouches?.[0];
      if (touch) state.touchStart = { x: touch.clientX, y: touch.clientY };
    }, { passive: true });
    questionPanel?.addEventListener("touchend", (event) => {
      if (!state.started || !state.touchStart) return;
      const touch = event.changedTouches?.[0];
      if (!touch) return;
      const dx = touch.clientX - state.touchStart.x;
      const dy = touch.clientY - state.touchStart.y;
      state.touchStart = null;
      if (Math.abs(dx) < 70 || Math.abs(dx) < Math.abs(dy) * 1.3) return;
      if (dx < 0 && !el("nextBtn").disabled) el("nextBtn").click();
      if (dx > 0 && !el("prevBtn").disabled) el("prevBtn").click();
    }, { passive: true });

    useEmbeddedQuestions();
    if (location.protocol !== "file:") {
      fetch("/api/questions", { cache: "no-store" })
        .then((r) => {
          if (!r.ok) throw new Error(`Domande non disponibili: ${r.status}`);
          return r.json();
        })
        .then((data) => {
          const ok = applyQuestionPayload(data, "server");
          if (!ok) throw new Error("Payload domande vuoto");
        })
        .catch(() => {
          useEmbeddedQuestions();
          showAppNotice("Uso le domande incluse nella pagina: il server non ha risposto alla richiesta delle domande.");
        });
    }

    async function requestInstallApp() {
      if (location.protocol === "file:") {
        showAppNotice("Questa copia aperta come file funziona offline e calcola i risultati, ma i browser installano le PWA solo da http://127.0.0.1 o https. Per installarla, avviala con Avvia_Politometro.command e poi usa Installa app dal browser.");
        return;
      }
      if (state.deferredInstallPrompt) {
        state.deferredInstallPrompt.prompt();
        await state.deferredInstallPrompt.userChoice;
        state.deferredInstallPrompt = null;
      } else {
        showAppNotice("Se il browser supporta l'installazione, usa il menu del browser: Aggiungi alla schermata Home / Installa app.");
      }
    }

    function renderConsentIntro() {
      updateProgress();
      el("stepTitle").textContent = "Scegli esperienza";
      el("stepSubtitle").textContent = "Prima identità e ritmo, poi metodo e dettagli quando servono.";
      el("questionText").textContent = "Scopri il tuo profilo politico multidimensionale.";
      el("options").innerHTML = `
        <div class="welcome-card">
          <div class="welcome-sigil">P</div>
          <div>
            <h3 style="margin:0 0 6px;">Benvenuto nel Politometro</h3>
            <p class="small">Un test politico visuale, mobile-first e spiegabile: rispondi, scopri il tuo profilo, esplora affinità, distanza e coerenza interna.</p>
            <div class="hero-badges">
              <span class="hero-badge">3 minuti</span>
              <span class="hero-badge">8 dimensioni</span>
              <span class="hero-badge">Report personale</span>
              <span class="hero-badge">Card social</span>
            </div>
          </div>
        </div>
        <div class="experience-strip">
          <div class="experience-panel">
            <h4>Dal quiz al tuo mondo politico.</h4>
            <p class="small">Il risultato non si ferma a un'etichetta: mostra perché sei vicino a certi partiti, ideologie e figure storiche, e dove invece ti allontani.</p>
          </div>
          <div class="experience-steps">
            <div class="experience-step"><span>1</span> Scegli una modalità</div>
            <div class="experience-step"><span>2</span> Rispondi con calma</div>
            <div class="experience-step"><span>3</span> Guarda mappa, report e card</div>
          </div>
        </div>
        <div class="trust-strip">
          <div class="trust-chip"><strong>8 assi leggibili</strong><span>Economia, autorità, cultura, geopolitica, ambiente, tecnologia, uguaglianza e giustizia.</span></div>
          <div class="trust-chip"><strong>Risultato spiegato</strong><span>Mostra affinità, differenze, coerenza interna e livello di confidenza.</span></div>
          <div class="trust-chip"><strong>Privacy prudente</strong><span>Di base resta nel browser. I dati aggregati richiedono consenso esplicito.</span></div>
          <div class="trust-chip"><strong>Pronto per campagne</strong><span>Modalità editoriali, scolastiche o “Elezioni 2027” con fonti documentate.</span></div>
        </div>
        <div class="explain-grid">
	          <div class="mode-card mode-social" id="modeSocial">
	            <h4>Modalità social</h4>
	            <p class="small">12 domande. Per chi vuole un risultato immediato, leggero e condivisibile.</p>
	          </div>
	          <div class="mode-card mode-quick selected" id="modeQuick">
	            <h4>Modalità rapida</h4>
	            <p class="small">20 domande bilanciate. La scelta migliore per iniziare.</p>
	          </div>
	          <div class="mode-card mode-deep" id="modeDeep">
	            <h4>Modalità profonda</h4>
	            <p class="small">60 domande. Più dettagli, più sfumature, più report.</p>
	          </div>
	          <div class="mode-card mode-election locked" id="modeElection" aria-disabled="true">
	            <h4>Modalità Elezioni 2027 <span class="badge">Lavori in corso</span></h4>
	            <p class="small">Non è ancora utilizzabile perché servono programmi ufficiali, liste definitive, fonti verificabili e doppia revisione delle posizioni dei partiti.</p>
	            <div class="worksite-mini" aria-hidden="true"><span></span><span></span><span></span></div>
	          </div>
        </div>
        <details class="setup-details">
          <summary>Aziende, media e organizzazioni</summary>
          <div class="setup-body">
            <div class="partner-panel">
              <div>
                <h4>Soluzioni professionali</h4>
                <p class="small">Politometro può diventare un'esperienza brandizzata per media, scuole, aziende e organizzazioni: quiz pubblico, report, card social e analytics aggregati.</p>
              </div>
              <div class="partner-grid">
                <div class="partner-card"><strong>Media</strong><span class="small">Quiz editoriale, card social, report aggregati e contenuti data-driven.</span></div>
                <div class="partner-card"><strong>Scuole e fondazioni</strong><span class="small">Strumento educativo per leggere valori, assi politici e partecipazione civica.</span></div>
                <div class="partner-card"><strong>Organizzazioni</strong><span class="small">Dashboard su trend e segmenti, sempre in forma aggregata e con consenso.</span></div>
              </div>
              <div class="surface-actions">
                <a class="btn primary" href="organizzazioni.html">Soluzioni per organizzazioni</a>
                <a class="btn" href="metodo.html">Metodo</a>
              </div>
            </div>
          </div>
        </details>
	        <details class="setup-details">
	          <summary>Ricerca e consenso facoltativi</summary>
          <div class="setup-body">
            <button class="option" id="consentYes">
              <span class="num">Sì</span>
              <span>Salva localmente risposte, risultato e dati facoltativi qui sotto per migliorare pesi, domande e confronti. Non inserisco nome, email o dati identificativi diretti.</span>
            </button>
            <button class="option selected" id="consentNo">
              <span class="num">No</span>
              <span>Faccio il test senza salvare le risposte per ricerca o miglioramento.</span>
            </button>
            <div class="warning">
              <strong>Nota privacy.</strong><br>
              Le opinioni politiche sono dati sensibili. I dati facoltativi non modificano il tuo risultato individuale: servono solo, se dai consenso, per capire se il test funziona in modo diverso per gruppi diversi.
            </div>
          </div>
        </details>
        <details class="setup-details">
          <summary>Nickname e avatar</summary>
          <div class="setup-body">
          <div class="explain-grid">
            <div class="field">
              <label for="nickname">Nickname</label>
              <input id="nickname" maxlength="32" placeholder="Facoltativo">
            </div>
            <div class="field">
              <label for="avatarMode">Avatar</label>
              <select id="avatarMode">
                <option value="generated">Simbolo generato dal nickname</option>
                <option value="historical">Avatar storico più vicino</option>
                <option value="ideology">Simbolo dell'ideologia risultante</option>
                <option value="photo">Foto personale locale</option>
              </select>
            </div>
            <div class="field">
              <label for="avatarPhoto">Foto opzionale</label>
              <input id="avatarPhoto" type="file" accept="image/*">
              <p class="small">La foto resta solo nella pagina e nella card: non viene salvata nei dati di ricerca.</p>
            </div>
            <div class="field">
              <label>Anteprima</label>
              <div id="identityPreview" class="user-strip">${renderPortrait("Tu")}<div><strong>Tu</strong><span class="small">avatar generato</span></div></div>
            </div>
          </div>
          </div>
        </details>
        <details class="setup-details">
          <summary>Dati facoltativi per analisi aggregata</summary>
          <div class="setup-body">
          <div class="explain-grid">
          <div class="field">
            <label for="ageRange">Età</label>
            <select id="ageRange">
              <option value="">Preferisco non rispondere</option>
              <option>meno di 18</option>
              <option>18-24</option>
              <option>25-34</option>
              <option>35-44</option>
              <option>45-54</option>
              <option>55-64</option>
              <option>65+</option>
            </select>
          </div>
          <div class="field">
            <label for="education">Titolo di studio</label>
            <select id="education">
              <option value="">Preferisco non rispondere</option>
              <option>Scuola media o inferiore</option>
              <option>Diploma superiore</option>
              <option>Laurea triennale</option>
              <option>Laurea magistrale o ciclo unico</option>
              <option>Dottorato / master avanzato</option>
              <option>Altro percorso</option>
            </select>
          </div>
          <div class="field">
            <label for="originArea">Area di provenienza</label>
            <select id="originArea">
              <option value="">Preferisco non rispondere</option>
              <option>Nord Italia</option>
              <option>Centro Italia</option>
              <option>Sud Italia / Isole</option>
              <option>Europa occidentale</option>
              <option>Europa orientale</option>
              <option>Nord America</option>
              <option>America Latina</option>
              <option>Africa</option>
              <option>Asia</option>
              <option>Oceania</option>
            </select>
          </div>
          <div class="field">
            <label for="countryRegion">Paese/regione libera</label>
            <input id="countryRegion" maxlength="120" placeholder="Facoltativo, meglio generico">
          </div>
          <div class="field">
            <label for="politicalInterest">Interesse politico</label>
            <select id="politicalInterest">
              <option value="">Preferisco non rispondere</option>
              <option>Molto basso</option>
              <option>Basso</option>
              <option>Medio</option>
              <option>Alto</option>
              <option>Molto alto</option>
            </select>
          </div>
          <div class="field">
            <label for="politicalKnowledge">Competenza politica auto-percepita</label>
            <select id="politicalKnowledge">
              <option value="">Preferisco non rispondere</option>
              <option>Principiante</option>
              <option>Base</option>
              <option>Intermedia</option>
              <option>Avanzata</option>
              <option>Studio/lavoro nel settore</option>
            </select>
          </div>
          <div class="field">
            <label for="newsFrequency">Frequenza informazione politica</label>
            <select id="newsFrequency">
              <option value="">Preferisco non rispondere</option>
              <option>Quasi mai</option>
              <option>Qualche volta al mese</option>
              <option>Settimanalmente</option>
              <option>Quasi ogni giorno</option>
              <option>Ogni giorno da più fonti</option>
            </select>
          </div>
          <div class="field">
            <label for="studentWorker">Situazione prevalente</label>
            <select id="studentWorker">
              <option value="">Preferisco non rispondere</option>
              <option>Studente</option>
              <option>Lavoratore dipendente</option>
              <option>Autonomo / imprenditore</option>
              <option>Disoccupato o in cerca</option>
              <option>Pensionato</option>
              <option>Altro</option>
            </select>
          </div>
        </div>
          </div>
        </details>
        <button class="btn" id="installApp">Installa come app</button>
      `;
      el("prevBtn").disabled = true;
      el("nextBtn").disabled = false;
      el("nextBtn").textContent = "Inizia il test →";
      document.getElementById("consentYes").addEventListener("click", () => {
        state.researchConsent = true;
        document.getElementById("consentYes").classList.add("selected");
        document.getElementById("consentNo").classList.remove("selected");
      });
      document.getElementById("consentNo").addEventListener("click", () => {
        state.researchConsent = false;
        document.getElementById("consentNo").classList.add("selected");
        document.getElementById("consentYes").classList.remove("selected");
      });
      const setMode = (mode) => {
        state.mode = mode;
        ["modeSocial", "modeQuick", "modeDeep"].forEach((id) => document.getElementById(id)?.classList.remove("selected"));
        const selectedId = mode === "social" ? "modeSocial" : mode === "quick" ? "modeQuick" : "modeDeep";
        document.getElementById(selectedId)?.classList.add("selected");
      };
      document.getElementById("modeSocial").addEventListener("click", () => setMode("social"));
      document.getElementById("modeQuick").addEventListener("click", () => setMode("quick"));
      document.getElementById("modeDeep").addEventListener("click", () => setMode("deep"));
	      document.getElementById("modeElection").addEventListener("click", () => showAppNotice("Modalità Elezioni 2027 in lavori in corso: non la attivo finché non ci sono programmi ufficiali, liste definitive, fonti verificabili e revisione delle posizioni."));
      document.getElementById("nickname").addEventListener("input", updateIdentityPreview);
      document.getElementById("avatarMode").addEventListener("change", updateIdentityPreview);
      document.getElementById("avatarPhoto").addEventListener("change", handleAvatarPhoto);
      updateIdentityPreview();
      document.getElementById("installApp").addEventListener("click", requestInstallApp);
    }

    function updateIdentityPreview() {
      const nickname = document.getElementById("nickname")?.value.trim() || "";
      const avatarMode = document.getElementById("avatarMode")?.value || "generated";
      state.identity.nickname = nickname;
      state.identity.avatarMode = avatarMode;
      const label = escapeHtml(nickname || "Tu");
      const avatar = avatarMode === "photo" && state.identity.photoDataUrl
        ? `<span class="avatar user-photo" style="background-image:url('${state.identity.photoDataUrl.replace(/'/g, "%27")}')" aria-hidden="true"></span>`
        : renderPortrait(avatarMode === "historical" ? "Avatar storico" : label);
      const text = avatarMode === "photo" ? "foto locale" : avatarMode === "historical" ? "sarà scelto dal risultato" : avatarMode === "ideology" ? "simbolo dell'ideologia finale" : "avatar generato";
      const preview = document.getElementById("identityPreview");
      if (preview) preview.innerHTML = `${avatar}<div><strong>${label}</strong><span class="small">${text}</span></div>`;
    }

    function handleAvatarPhoto(event) {
      const file = event.target.files?.[0];
      if (!file) {
        state.identity.photoDataUrl = "";
        updateIdentityPreview();
        return;
      }
      if (!file.type.startsWith("image/")) {
        showAppNotice("Scegli un file immagine.");
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        state.identity.photoDataUrl = String(reader.result || "");
        state.identity.avatarMode = "photo";
        const mode = document.getElementById("avatarMode");
        if (mode) mode.value = "photo";
        updateIdentityPreview();
      };
      reader.readAsDataURL(file);
    }

    function collectIdentity() {
      state.identity.nickname = document.getElementById("nickname")?.value.trim().slice(0, 32) || "";
      state.identity.avatarMode = document.getElementById("avatarMode")?.value || "generated";
    }

    function collectDemographics() {
      return {
        age_range: document.getElementById("ageRange")?.value || "",
        education: document.getElementById("education")?.value || "",
        origin_area: document.getElementById("originArea")?.value || "",
        country_region: document.getElementById("countryRegion")?.value || "",
        political_interest: document.getElementById("politicalInterest")?.value || "",
        political_knowledge: document.getElementById("politicalKnowledge")?.value || "",
        news_frequency: document.getElementById("newsFrequency")?.value || "",
        student_worker: document.getElementById("studentWorker")?.value || "",
      };
    }
    if ("serviceWorker" in navigator && location.protocol !== "file:") {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }
  </script>
</body>
</html>
"""

HTML = HTML.replace(
    'const QUESTION_BOOTSTRAP = "__QUESTION_BOOTSTRAP__";',
    "const QUESTION_BOOTSTRAP = " + json.dumps(question_payload(), ensure_ascii=False) + ";",
    1,
)
