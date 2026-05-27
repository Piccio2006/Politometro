from __future__ import annotations

import json
import math
import os
import shutil
import time
from pathlib import Path

import build_standalone_app


ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
SITE_URL = os.environ.get("POLITOMETRO_SITE_URL", "https://politometro.example/")
SITE_NAME = "Politometro"
SITE_DESCRIPTION = "Scopri il tuo profilo politico in 8 dimensioni: economia, autorità, cultura, geopolitica, ambiente, tecnologia, uguaglianza e giustizia."
CONTACT_EMAIL = os.environ.get("POLITOMETRO_CONTACT_EMAIL", "piccioligiovanni@outlook.it")


PRIVACY_HTML = """<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Privacy - Politometro</title>
  <style>
    body{margin:0;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f6f8f8;color:#172026;line-height:1.6}
    main{max-width:860px;margin:0 auto;padding:34px 18px}
    a{color:#22577a} h1{font-family:Georgia,serif;font-size:42px;line-height:1.05;margin:0 0 12px}
    section{background:white;border:1px solid #d9e1e7;border-radius:8px;padding:20px;margin:14px 0}
    .muted{color:#60707c}
  </style>
</head>
<body>
  <main>
    <p><a href="./">← Torna al Politometro</a></p>
    <h1>Privacy</h1>
    <p class="muted">Versione statica pubblica del Politometro.</p>
    <section>
      <h2>Cosa viene salvato</h2>
      <p>Questa prima versione online non invia le risposte a un server del progetto. Il calcolo avviene nel browser e gli eventuali salvataggi restano nel dispositivo dell'utente, tramite memoria locale del browser.</p>
    </section>
    <section>
      <h2>Dati politici</h2>
      <p>Le opinioni politiche sono dati sensibili. Per questo la versione pubblica iniziale evita la raccolta centralizzata. Quando verrà attivata una dashboard online con dati aggregati, serviranno consenso esplicito, informativa completa, cancellazione dati e accesso admin protetto.</p>
    </section>
    <section>
      <h2>Hosting</h2>
      <p>Il servizio di hosting potrebbe raccogliere log tecnici minimi, come indirizzo IP e user agent, per sicurezza e funzionamento del sito. Questi log non sono gestiti dal Politometro nella versione statica.</p>
    </section>
    <section>
      <h2>Contatti</h2>
      <p>Per richieste sulla privacy o sulla rimozione di dati eventualmente raccolti in future versioni: <a href="mailto:{contact_email}">{contact_email}</a>.</p>
    </section>
  </main>
</body>
</html>
"""


METODO_HTML = """<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Metodo - Politometro</title>
  <style>
    body{margin:0;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f6f8f8;color:#172026;line-height:1.6}
    main{max-width:940px;margin:0 auto;padding:34px 18px}
    a{color:#22577a} h1{font-family:Georgia,serif;font-size:42px;line-height:1.05;margin:0 0 12px}
    section{background:white;border:1px solid #d9e1e7;border-radius:8px;padding:20px;margin:14px 0}
    li{margin:8px 0}.muted{color:#60707c}
  </style>
</head>
<body>
  <main>
    <p><a href="./">← Torna al Politometro</a></p>
    <h1>Metodo</h1>
    <p class="muted">Politometro è un modello multidimensionale trasparente, in fase di validazione empirica: non sostituisce una ricerca scientifica validata, ma mostra in modo chiaro come calcola il profilo.</p>
    <section>
      <h2>Come funziona</h2>
      <ul>
        <li>Le risposte vengono trasformate su una scala da -1 a +1.</li>
        <li>Ogni domanda pesa su uno o più assi politici.</li>
        <li>Il risultato finale vive in uno spazio a 8 dimensioni.</li>
        <li>Coerenza interna, confidenza e affidabilità interpretativa sono indicatori separati.</li>
        <li>Partiti, ideologie e figure storiche sono confronti geometrici, non giudizi morali.</li>
      </ul>
    </section>
    <section>
      <h2>Limite importante</h2>
      <p>La versione V5 ha una buona validità di contenuto, un audit interno delle domande e una struttura trasparente. Non è ancora uno strumento psicometrico validato: per quello serviranno campioni, test-retest, analisi fattoriale e confronto con fonti esterne.</p>
    </section>
    <section>
      <h2>Cosa cambia nella V5</h2>
      <ul>
        <li>Massimo quattro assi attivi per domanda.</li>
        <li>Asse principale più dominante rispetto ai pesi secondari.</li>
        <li>Formulazioni estreme rese meno emotive.</li>
        <li>Affidabilità interpretativa separata dalla posizione politica.</li>
      </ul>
    </section>
    <section>
      <h2>Prossimo passo</h2>
      <p>Durante la campagna elettorale potrà essere aggiunta una modalità temporanea Elezioni 2027 con domande tratte da programmi, dichiarazioni e posizioni ufficiali dei partiti, sempre con fonti documentate.</p>
    </section>
  </main>
</body>
</html>
"""


SUPPORTO_HTML = """<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Supporto e contatti - Politometro</title>
  <meta name="description" content="Contatti Politometro per privacy, supporto, assistenza, partnership e offerte commerciali.">
  <style>
    :root{--ink:#172026;--muted:#60707c;--line:#d9e1e7;--accent:#22577a;--accent2:#38a3a5;--warm:#f2b880;--rose:#b84a62}
    *{box-sizing:border-box}
    body{margin:0;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:linear-gradient(120deg,rgba(56,163,165,.14),transparent 28%),linear-gradient(240deg,rgba(242,184,128,.20),transparent 34%),#f6f8f8;color:var(--ink);line-height:1.6}
    main{max-width:980px;margin:0 auto;padding:34px 18px 56px}
    a{color:var(--accent)}
    h1{font-family:Georgia,serif;font-size:46px;line-height:1.04;margin:0 0 12px}
    section,.hero{background:#fff;border:1px solid var(--line);border-radius:8px;padding:22px;margin:14px 0;box-shadow:0 14px 38px rgba(16,36,47,.08)}
    .hero{background:linear-gradient(135deg,rgba(56,163,165,.14),rgba(242,184,128,.18)),#fff}
    .grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}
    .card{border:1px solid var(--line);border-radius:8px;padding:16px;background:linear-gradient(135deg,rgba(56,163,165,.08),rgba(242,184,128,.10)),#fff}
    .btn{display:inline-flex;align-items:center;justify-content:center;min-height:44px;border-radius:8px;padding:11px 14px;text-decoration:none;font-weight:900;background:linear-gradient(135deg,var(--accent),#17384d);color:white}
    .muted{color:var(--muted)}
    @media(max-width:820px){h1{font-size:36px}.grid{grid-template-columns:1fr}}
  </style>
</head>
<body>
  <main>
    <p><a href="./">← Torna al Politometro</a></p>
    <div class="hero">
      <h1>Supporto, assistenza e offerte</h1>
      <p class="muted">Per assistenza, privacy, segnalazioni metodologiche e collaborazioni professionali.</p>
      <p><a class="btn" href="mailto:{contact_email}?subject=Politometro%20-%20contatto">Scrivi a {contact_email}</a></p>
    </div>
    <div class="grid">
      <div class="card"><h2>Supporto utenti</h2><p>Problemi tecnici, installazione PWA, risultati che sembrano incoerenti, segnalazioni su testi o grafici.</p></div>
      <div class="card"><h2>Privacy</h2><p>Richieste sui dati, cancellazione, consenso, sicurezza e informazioni prima della futura dashboard online.</p></div>
      <div class="card"><h2>Partnership</h2><p>Media, scuole, fondazioni, organizzazioni civiche e collaborazioni tecniche o editoriali.</p></div>
    </div>
  </main>
</body>
</html>
"""


ORGANIZZAZIONI_HTML = """<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Per organizzazioni - Politometro</title>
  <meta name="description" content="Politometro per media, scuole, fondazioni e organizzazioni: quiz politico multi-asse, dashboard aggregata, report e modalità elettorale con fonti.">
  <style>
    :root{--ink:#172026;--muted:#60707c;--line:#d9e1e7;--bg:#f6f8f8;--panel:#fff;--accent:#22577a;--accent2:#38a3a5;--warm:#f2b880}
    *{box-sizing:border-box}
    body{margin:0;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:radial-gradient(circle at 10% 0,rgba(56,163,165,.16),transparent 30%),radial-gradient(circle at 88% 8%,rgba(242,184,128,.24),transparent 28%),linear-gradient(180deg,#fbfcf7 0%,var(--bg) 48%,#eaf4f1 100%);color:var(--ink);line-height:1.6}
    main{max-width:1100px;margin:0 auto;padding:34px 18px 56px}
    a{color:var(--accent)}
    h1{font-family:Georgia,serif;font-size:46px;line-height:1.04;margin:0 0 12px;letter-spacing:0}
    h2{font-size:24px;margin:0 0 10px}
    h3{font-size:18px;margin:0 0 8px}
    p{margin:0 0 12px}
    .muted{color:var(--muted)}
    .hero{border:1px solid #b9ccd3;border-radius:8px;padding:30px;background:linear-gradient(135deg,rgba(56,163,165,.16),transparent 38%),linear-gradient(315deg,rgba(242,184,128,.24),transparent 42%),#fff;box-shadow:0 24px 70px rgba(16,36,47,.12);position:relative;overflow:hidden}
    .hero::after{content:"";position:absolute;right:-46px;bottom:-52px;width:220px;height:220px;border-radius:50%;border:26px solid rgba(34,87,122,.08)}
    .nav{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:18px;flex-wrap:wrap}
    .grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:18px 0}
    .two{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:18px 0}
    section,.card{background:rgba(255,255,255,.92);border:1px solid var(--line);border-radius:8px;padding:20px;box-shadow:0 14px 36px rgba(16,36,47,.06)}
    .card{transition:transform .18s ease,box-shadow .18s ease,border-color .18s ease}
    .card:hover{transform:translateY(-2px);box-shadow:0 20px 52px rgba(16,36,47,.10);border-color:#b9ccd3}
    .card strong{color:var(--accent)}
    .kpi{font-size:30px;font-weight:900;color:var(--accent);display:block;line-height:1}
    .pillrow{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}
    .pill{border:1px solid var(--line);border-radius:999px;padding:7px 10px;background:#fff;font-size:13px;font-weight:800;color:#24404c}
    .proof{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:18px 0}
    .proof-card{border:1px solid var(--line);border-radius:8px;background:#fff;padding:16px}
    .proof-card strong{display:block;font-size:28px;color:var(--accent);line-height:1}
    .proof-card span{display:block;margin-top:6px;color:var(--muted);font-size:13px;font-weight:750}
    .cta{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}
    .btn{display:inline-flex;align-items:center;justify-content:center;min-height:44px;border-radius:8px;padding:11px 14px;text-decoration:none;font-weight:900;background:#e5ecef;color:var(--ink)}
    .btn.primary{background:linear-gradient(135deg,var(--accent),#17384d);color:white}
    .warning{border-left:4px solid var(--warm);background:rgba(242,184,128,.16);border-radius:8px;padding:14px;color:#4f3b22}
    ul{padding-left:20px;margin:0}
    li{margin:8px 0}
    table{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden}
    th,td{border:1px solid var(--line);padding:10px;text-align:left;vertical-align:top}
    th{background:#10242f;color:#fff}
    .journey{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:18px 0}
    .journey-step{border:1px solid rgba(34,87,122,.16);border-radius:8px;background:linear-gradient(135deg,rgba(56,163,165,.08),rgba(242,184,128,.10)),#fff;padding:16px}
    .journey-step b{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;background:#10242f;color:#fff;margin-bottom:10px}
    .journey-step strong{display:block;color:var(--accent);margin-bottom:6px}
    @media(max-width:800px){h1{font-size:36px}.grid,.two,.proof,.journey{grid-template-columns:1fr}.hero{padding:20px}}
  </style>
</head>
<body>
  <main>
    <div class="nav">
      <a href="./">← Torna al Politometro</a>
      <span class="muted">Soluzioni per media, aziende, scuole e organizzazioni</span>
    </div>

    <div class="hero">
      <h1>Una piattaforma di civic intelligence pronta per il pubblico.</h1>
      <p class="muted">Politometro unisce un test politico mobile-first a report, card social e analytics aggregati. Per media, aziende e organizzazioni offre esperienze brandizzabili, dati consensuali e letture metodologicamente trasparenti.</p>
      <div class="pillrow">
        <span class="pill">Quiz multi-asse</span>
        <span class="pill">PWA installabile</span>
        <span class="pill">Report e card social</span>
        <span class="pill">Dashboard aggregata</span>
        <span class="pill">Modalità Elezioni 2027</span>
      </div>
      <div class="cta">
        <a class="btn primary" href="mailto:{contact_email}?subject=Politometro%20-%20partnership">Parla di una partnership</a>
        <a class="btn" href="metodo.html">Metodo e limiti</a>
        <a class="btn" href="privacy.html">Privacy</a>
      </div>
    </div>

    <div class="proof">
      <div class="proof-card"><strong>8</strong><span>assi politici leggibili</span></div>
      <div class="proof-card"><strong>3</strong><span>modalità di test</span></div>
      <div class="proof-card"><strong>PDF</strong><span>report e card social</span></div>
      <div class="proof-card"><strong>CSV</strong><span>dashboard ed export aggregati</span></div>
    </div>

    <div class="grid">
      <div class="card"><span class="kpi">B2C</span><strong>Per utenti</strong><p class="muted">Esperienza rapida, identitaria, mobile-first: risultato, mondo politico, card social e spiegazioni.</p></div>
      <div class="card"><span class="kpi">B2B</span><strong>Per media e organizzazioni</strong><p class="muted">Versioni brandizzate, dashboard aggregate, report editoriali e campagne tematiche.</p></div>
      <div class="card"><span class="kpi">2027</span><strong>Per elezioni</strong><p class="muted">Modulo temporaneo con domande tratte da programmi ufficiali e posizioni documentate.</p></div>
    </div>

    <section>
      <h2>Come si presenta al pubblico</h2>
      <div class="journey">
        <div class="journey-step"><b>1</b><strong>Test rapido</strong><p class="muted">L'utente entra, sceglie la modalità e completa il quiz da telefono.</p></div>
        <div class="journey-step"><b>2</b><strong>Risultato visuale</strong><p class="muted">Archetipo, assi, coerenza interna, mappa e mondo politico.</p></div>
        <div class="journey-step"><b>3</b><strong>Condivisione</strong><p class="muted">Card social, report PDF e link condivisibili.</p></div>
        <div class="journey-step"><b>4</b><strong>Insight</strong><p class="muted">Dashboard aggregata per capire trend e segmenti, con consenso.</p></div>
      </div>
    </section>

    <section>
      <h2>Soluzioni disponibili</h2>
      <table>
        <tr><th>Prodotto</th><th>Cliente possibile</th><th>Valore</th></tr>
        <tr><td>Quiz editoriale brandizzato</td><td>Giornali, creator, media locali</td><td>Traffico, tempo di permanenza, card condivisibili, contenuti data-driven.</td></tr>
        <tr><td>Dashboard aggregata</td><td>Fondazioni, associazioni, scuole, think tank</td><td>Distribuzioni per asse, segmenti demografici consensuali, trend nel tempo.</td></tr>
        <tr><td>Modalità elettorale</td><td>Media e progetti civici</td><td>Confronto tra risposte utente e programmi, con fonti e criteri trasparenti.</td></tr>
        <tr><td>Versione white-label</td><td>Organizzazioni e campagne informative</td><td>Interfaccia personalizzata, report PDF, export aggregato, pagine metodo/privacy dedicate.</td></tr>
      </table>
    </section>

    <div class="two">
      <section>
      <h2>Per media e redazioni</h2>
        <ul>
          <li>Trasforma un tema politico astratto in esperienza interattiva.</li>
          <li>Genera contenuti condivisibili senza sembrare un sondaggio vecchio stile.</li>
          <li>Permette articoli su cluster, valori e fratture culturali, non solo intenzioni di voto.</li>
          <li>La pagina metodo rende il progetto più difendibile pubblicamente.</li>
        </ul>
      </section>
      <section>
      <h2>Per aziende e organizzazioni</h2>
        <ul>
          <li>Aiuta a capire quali valori avvicinano o allontanano gruppi diversi.</li>
          <li>Mostra correlazioni esplorative tra temi, istruzione, età e informazione politica.</li>
          <li>Può diventare uno strumento educativo o di ascolto pubblico.</li>
          <li>Funziona come PWA, quindi è semplice da distribuire da link o QR code.</li>
        </ul>
      </section>
    </div>

    <section class="warning">
      <h2>Linea etica e privacy</h2>
      <p>Politometro lavora su consenso, trasparenza e risultati aggregati. Le opinioni politiche sono dati sensibili: la piattaforma è pensata per insight collettivi, contenuti editoriali e strumenti educativi, non per vendere profili individuali o fare microtargeting opaco.</p>
    </section>

    <section>
      <h2>Pacchetti</h2>
      <table>
        <tr><th>Pacchetto</th><th>A chi venderlo</th><th>Cosa include</th></tr>
        <tr><td>Demo pubblica</td><td>Creator, scuole, community</td><td>PWA, quiz rapido/profondo, card social, report PDF, pagina metodo e privacy.</td></tr>
        <tr><td>Editoriale</td><td>Giornali, media locali, newsletter</td><td>Pagina brandizzata, dashboard aggregata, export CSV, insight automatici e articolo di sintesi.</td></tr>
        <tr><td>Research beta</td><td>Fondazioni, think tank, università, associazioni</td><td>Dataset consensuale, controlli qualità, correlazioni esplorative, soglie minime e report metodologico.</td></tr>
        <tr><td>Elezioni 2027</td><td>Media e progetti civici</td><td>Domande basate su programmi ufficiali, fonti, revisione delle posizioni e confronto partiti/utente.</td></tr>
      </table>
    </section>

    <div class="two">
      <section>
        <h2>Dashboard che puoi mostrare</h2>
        <ul>
          <li>Stato dataset: fase iniziale, beta, validazione o scala.</li>
          <li>Trend giorno per giorno: test, feedback, confidenza e ideologie principali.</li>
          <li>Correlazioni automatiche tra assi, domande e dati facoltativi.</li>
          <li>Export CSV/JSON per analisi esterne e report professionali.</li>
        </ul>
      </section>
      <section>
        <h2>Soglie di lettura</h2>
        <ul>
          <li>30 risposte: primi segnali esplorativi.</li>
          <li>100 risposte: primi report aggregati prudenti.</li>
          <li>300 risposte: analisi più seria sugli assi e sugli item.</li>
          <li>1.000 risposte: percentili, segmenti e calibrazione più credibili.</li>
        </ul>
      </section>
    </div>
  </main>
</body>
</html>
"""


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def build_version() -> str:
    return str(int(time.time()))


def public_url(path: str = "") -> str:
    return SITE_URL.rstrip("/") + "/" + path.lstrip("/")


def social_meta_tags() -> str:
    return f"""
  <meta name="description" content="{SITE_DESCRIPTION}">
  <link rel="canonical" href="{public_url()}">
  <meta property="og:title" content="{SITE_NAME}">
  <meta property="og:description" content="{SITE_DESCRIPTION}">
  <meta property="og:image" content="{public_url('og-image.png')}">
  <meta property="og:url" content="{public_url()}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="{SITE_NAME}">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{SITE_NAME}">
  <meta name="twitter:description" content="{SITE_DESCRIPTION}">
  <meta name="twitter:image" content="{public_url('og-image.png')}">
  <link rel="apple-touch-icon" href="icon-192.png">
"""


def patch_html_links(html: str) -> str:
    links = """
        <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:10px;">
          <a href="metodo.html" style="color:#b9c8d0;">Metodo</a>
          <a href="privacy.html" style="color:#b9c8d0;">Privacy</a>
          <a href="supporto.html" style="color:#b9c8d0;">Supporto</a>
          <a href="organizzazioni.html" style="color:#b9c8d0;">Aziende e organizzazioni</a>
        </div>
    """
    return html.replace(
        "Il risultato non misura una verità definitiva: stima un profilo coerente con le risposte, segnala incertezza e mostra dove il dato è più o meno stabile.",
        "Il risultato non misura una verità definitiva: stima un profilo coerente con le risposte, segnala incertezza e mostra dove il dato è più o meno stabile." + links,
    )


def patch_index_html(html: str) -> str:
    html = patch_html_links(html)
    if 'property="og:title"' not in html:
        html = html.replace("  <title>Politometro</title>\n", "  <title>Politometro</title>\n" + social_meta_tags(), 1)
    return html


def patch_admin_html(html: str) -> str:
    note = """
    <section class="card warn">
      <strong>Dashboard locale.</strong>
      Questa pagina mostra solo i dati salvati nel browser di chi la apre. Non mostra dati di altri utenti e non è una dashboard online centralizzata.
    </section>
"""
    if "Questa pagina mostra solo i dati salvati nel browser" not in html:
        html = html.replace("  <main>\n", "  <main>\n" + note, 1)
    return html


def generate_launch_images() -> None:
    from PIL import Image, ImageDraw, ImageFont

    def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        candidates = [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Georgia Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Georgia.ttf",
            "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return ImageFont.truetype(candidate, size)
        return ImageFont.load_default()

    def icon(size: int) -> Image.Image:
        img = Image.new("RGB", (size, size), "#10242f")
        draw = ImageDraw.Draw(img)
        margin = int(size * 0.11)
        draw.rounded_rectangle([margin, margin, size - margin, size - margin], radius=int(size * 0.2), fill="#f6f8f8")
        cx = cy = size // 2
        outer = int(size * 0.30)
        inner = int(size * 0.13)
        points = []
        for i in range(10):
            angle = math.radians(-90 + i * 36)
            radius = outer if i % 2 == 0 else inner
            points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
        draw.polygon(points, fill="#38a3a5")
        dot = int(size * 0.09)
        draw.ellipse([cx - dot, cy - dot, cx + dot, cy + dot], fill="#f2b880")
        return img

    icon(192).save(DIST / "icon-192.png", "PNG", optimize=True)
    icon(512).save(DIST / "icon-512.png", "PNG", optimize=True)

    og = Image.new("RGB", (1200, 630), "#10242f")
    draw = ImageDraw.Draw(og)
    for i, color in enumerate(["#38a3a5", "#f2b880", "#dce8ea"]):
        radius = 176 - i * 36
        draw.ellipse([1010 - radius, 72 - radius, 1010 + radius, 72 + radius], outline=color, width=6)
    draw.rounded_rectangle([70, 70, 1130, 560], radius=36, outline="#31505d", width=2)
    draw.text((110, 118), SITE_NAME, fill="#f6f8f8", font=font(82, True))
    draw.text((112, 220), "Test politico multi-asse", fill="#f2b880", font=font(38, True))
    draw.text((112, 292), "8 dimensioni, report, mappa interattiva, coerenza interna e card social.", fill="#dce8ea", font=font(31))
    chips = ["Economia", "Autorità", "Cultura", "Geopolitica", "Ambiente", "Tecnologia", "Uguaglianza", "Giustizia"]
    x, y = 112, 388
    for chip in chips:
        text_box = draw.textbbox((0, 0), chip, font=font(24, True))
        width = text_box[2] - text_box[0] + 34
        if x + width > 1088:
            x = 112
            y += 58
        draw.rounded_rectangle([x, y, x + width, y + 40], radius=20, fill="#f6f8f8")
        draw.text((x + 17, y + 7), chip, fill="#10242f", font=font(22, True))
        x += width + 14
    og.save(DIST / "og-image.png", "PNG", optimize=True)


def build() -> None:
    version = build_version()
    build_standalone_app.build()
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()

    app_html = (ROOT / "politometro_standalone.html").read_text(encoding="utf-8")
    write_text(DIST / "index.html", patch_index_html(app_html))

    manifest = json.loads((ROOT / "manifest.webmanifest").read_text(encoding="utf-8"))
    manifest["start_url"] = "./"
    manifest["id"] = "./"
    manifest["description"] = SITE_DESCRIPTION
    manifest["icons"] = [
        {"src": "icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
        {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        {"src": "icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any"},
    ]
    manifest["shortcuts"] = [
        {"name": "Inizia test", "url": "./", "description": "Apri Politometro"},
        {"name": "Supporto", "url": "supporto.html", "description": "Contatti e assistenza"},
        {"name": "Organizzazioni", "url": "organizzazioni.html", "description": "Soluzioni per aziende e media"},
    ]
    write_text(DIST / "manifest.webmanifest", json.dumps(manifest, ensure_ascii=False, indent=2))

    shutil.copy2(ROOT / "icon.svg", DIST / "icon.svg")
    generate_launch_images()
    write_text(
        DIST / "sw.js",
        f"""const CACHE = "politometro-public-{version}";
	const CORE = ["./", "./index.html", "./manifest.webmanifest", "./icon.svg", "./icon-192.png", "./icon-512.png", "./privacy.html", "./metodo.html", "./supporto.html", "./organizzazioni.html", "./og-image.png"];
self.addEventListener("install", event => {{
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(CORE)));
  self.skipWaiting();
}});
self.addEventListener("activate", event => {{
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))));
  self.clients.claim();
}});
self.addEventListener("fetch", event => {{
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.pathname.startsWith("/api/") || url.pathname === "/admin" || url.pathname.startsWith("/admin/") || url.pathname === "/login" || url.pathname.startsWith("/login/")) return;
  event.respondWith(fetch(request).then(response => {{
    if (!response || !response.ok || response.type === "opaque") return response;
    const copy = response.clone();
    caches.open(CACHE).then(cache => cache.put(request, copy));
    return response;
  }}).catch(() => caches.match(request).then(cached => cached || caches.match("./index.html"))));
}});
""",
    )
    write_text(DIST / "privacy.html", PRIVACY_HTML.replace("{contact_email}", CONTACT_EMAIL))
    write_text(DIST / "metodo.html", METODO_HTML)
    write_text(DIST / "supporto.html", SUPPORTO_HTML.replace("{contact_email}", CONTACT_EMAIL))
    write_text(DIST / "organizzazioni.html", ORGANIZZAZIONI_HTML.replace("{contact_email}", CONTACT_EMAIL))
    write_text(DIST / "robots.txt", f"User-agent: *\nAllow: /\nSitemap: {public_url('sitemap.xml')}\n")
    write_text(
        DIST / "sitemap.xml",
        f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{public_url()}</loc><priority>1.0</priority></url>
  <url><loc>{public_url('metodo.html')}</loc><priority>0.7</priority></url>
  <url><loc>{public_url('supporto.html')}</loc><priority>0.7</priority></url>
  <url><loc>{public_url('organizzazioni.html')}</loc><priority>0.7</priority></url>
  <url><loc>{public_url('privacy.html')}</loc><priority>0.6</priority></url>
</urlset>
""",
    )
    write_text(
        DIST / "_headers",
        """/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  X-Frame-Options: DENY
  Permissions-Policy: camera=(), microphone=(), geolocation=()
  Cross-Origin-Opener-Policy: same-origin
  Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https://commons.wikimedia.org https://upload.wikimedia.org; connect-src 'self'; worker-src 'self'; manifest-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'
""",
    )
    write_text(DIST / "_redirects", "/privacy.html /privacy.html 200\n/metodo.html /metodo.html 200\n/supporto.html /supporto.html 200\n/organizzazioni.html /organizzazioni.html 200\n/* /index.html 200\n")
    print(DIST.resolve())


if __name__ == "__main__":
    build()
