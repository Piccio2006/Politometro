# ============================================================
# 🧭 POLITOMETRO ASSOLUTO — VERSIONE COMPLETA FUNZIONANTE
# Esegui prima: !pip install gradio numpy scikit-learn matplotlib pillow reportlab pandas
# ============================================================

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
import gradio as gr
import io
import os
import csv
import datetime
import tempfile
import traceback
import pandas as pd
from PIL import Image as PILImage
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RlImage
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

# ============================================================
# ASSI POLITICI
# ============================================================

AXES = [
    "Economia: Stato sociale, redistribuzione ↔ mercato libero, privatizzazioni",
    "Autorità: Libertà individuale, limiti al potere ↔ ordine, controllo, sicurezza",
    "Cultura: Apertura sociale, pluralismo ↔ tradizione, religione, famiglia",
    "Geopolitica: Cooperazione, cosmopolitismo ↔ sovranità nazionale e identità",
    "Ambiente: Transizione verde ↔ crescita economica e industria",
    "Tecnologia: Regolazione AI/dati ↔ innovazione rapida, crypto",
    "Uguaglianza: Pari condizioni ↔ gerarchie, competizione",
    "Giustizia: Pena come recupero ↔ deterrenza, punizione",
]

AXIS_SHORT = ["Economia", "Autorità", "Cultura", "Geopolitica",
              "Ambiente", "Tecnologia", "Uguaglianza", "Giustizia"]

AXIS_EXPLANATIONS = {
    "Economia":    "Welfare e intervento statale ↔ Mercato, privatizzazioni, tasse basse.",
    "Autorità":    "Libertà e limiti al potere ↔ Ordine, controllo, disciplina.",
    "Cultura":     "Diritti civili e pluralismo ↔ Tradizione, religione, famiglia.",
    "Geopolitica": "Cooperazione sovranazionale ↔ Sovranità nazionale, confini.",
    "Ambiente":    "Priorità ecologica ↔ Crescita economica, industria.",
    "Tecnologia":  "Regolazione prudente ↔ Innovazione, automazione.",
    "Uguaglianza": "Riduzione disuguaglianze ↔ Gerarchie, competizione, élite.",
    "Giustizia":   "Recupero sociale ↔ Deterrenza, punizione severa.",
}

# ============================================================
# DATABASE COMPLETO: IDEOLOGIE + PARTITI + STORICI
# ============================================================

PROTOTYPES = {
    # 23 IDEOLOGIE
    "Socialdemocrazia":             np.array([-0.55, -0.15, -0.45, -0.45, -0.50, -0.35, -0.70, -0.45]),
    "Liberalismo classico":         np.array([ 0.45, -0.70, -0.10, -0.30,  0.15,  0.25,  0.05, -0.05]),
    "Conservatorismo liberale":     np.array([ 0.35,  0.35,  0.60,  0.20,  0.10,  0.10,  0.35,  0.45]),
    "Conservatorismo sociale":      np.array([ 0.10,  0.55,  0.85,  0.40,  0.05, -0.10,  0.45,  0.60]),
    "Libertarianismo":              np.array([ 0.85, -0.95,  0.00, -0.20,  0.25,  0.70,  0.10,  0.10]),
    "Comunismo democratico":        np.array([-0.95, -0.20, -0.55, -0.45, -0.65, -0.45, -0.95, -0.35]),
    "Comunismo autoritario":        np.array([-0.95,  0.80, -0.20,  0.10, -0.30, -0.25, -0.85,  0.50]),
    "Anarchismo sociale":           np.array([-0.70, -1.00, -0.65, -0.70, -0.35, -0.15, -1.00, -0.80]),
    "Anarco-capitalismo":           np.array([ 1.00, -0.95,  0.10, -0.20,  0.55,  0.75,  0.45,  0.00]),
    "Fascismo / ultranazionalismo": np.array([ 0.10,  0.95,  0.95,  1.00,  0.30,  0.15,  0.80,  0.95]),
    "Eco-socialismo":               np.array([-0.90, -0.10, -0.65, -0.50, -1.00, -0.70, -0.85, -0.35]),
    "Ecologismo progressista":      np.array([-0.55, -0.35, -0.60, -0.55, -0.95, -0.55, -0.70, -0.35]),
    "Ecologismo conservatore":      np.array([ 0.00,  0.25,  0.65,  0.30, -0.75, -0.25,  0.15,  0.35]),
    "Tecnocrazia liberale":         np.array([ 0.20,  0.20, -0.25, -0.35, -0.15,  0.60,  0.10, -0.10]),
    "Accelerazionismo tecnologico": np.array([ 0.45, -0.15, -0.50, -0.20,  0.70,  1.00,  0.10,  0.00]),
    "Tecno-autoritarismo":          np.array([ 0.30,  0.85,  0.10,  0.20,  0.20,  0.85,  0.55,  0.65]),
    "Neo-reazione / NRx":           np.array([ 0.55,  0.85,  0.85,  0.25,  0.10,  0.45,  0.95,  0.75]),
    "Anarco-primitivismo":          np.array([-0.40, -0.75, -0.20, -0.60, -1.00, -1.00, -0.65, -0.55]),
    "Nazional-populismo":           np.array([ 0.05,  0.60,  0.65,  0.95,  0.20, -0.05,  0.20,  0.70]),
    "Populismo di sinistra":        np.array([-0.80,  0.10, -0.35,  0.15, -0.55, -0.30, -0.85, -0.20]),
    "Populismo digitale":           np.array([-0.20, -0.20, -0.20,  0.00, -0.45,  0.40, -0.50, -0.20]),
    "Centrismo pragmatico":         np.array([ 0.00,  0.00,  0.00,  0.00,  0.00,  0.00,  0.00,  0.00]),
    "Moderato liberal-democratico": np.array([ 0.05, -0.25, -0.20, -0.35, -0.25,  0.10, -0.25, -0.20]),
    # 17 PARTITI
    "PD":                           np.array([-0.35, -0.20, -0.35, -0.45, -0.45, -0.25, -0.55, -0.35]),
    "Alleanza Verdi e Sinistra":    np.array([-0.80, -0.35, -0.70, -0.55, -0.95, -0.65, -0.85, -0.45]),
    "Movimento 5 Stelle":           np.array([-0.35, -0.05, -0.25, -0.10, -0.75, -0.45, -0.65, -0.20]),
    "Azione / Italia Viva":         np.array([ 0.20, -0.20, -0.10, -0.35, -0.20,  0.25, -0.10, -0.10]),
    "Forza Italia":                 np.array([ 0.50,  0.25,  0.35, -0.15,  0.30,  0.25,  0.20,  0.35]),
    "Lega":                         np.array([ 0.20,  0.70,  0.60,  0.85,  0.30,  0.10,  0.35,  0.80]),
    "Fratelli d'Italia":            np.array([ 0.30,  0.65,  0.75,  0.75,  0.20,  0.05,  0.50,  0.75]),
    "Partito Democratico (USA)":    np.array([-0.25,  0.10, -0.45, -0.30, -0.35,  0.10, -0.30,  0.05]),
    "Partito Repubblicano (USA)":   np.array([ 0.65,  0.50,  0.65,  0.40,  0.60,  0.40,  0.55,  0.70]),
    "Labour Party (UK)":            np.array([-0.40,  0.05, -0.35, -0.20, -0.45,  0.00, -0.50, -0.10]),
    "Conservative Party (UK)":      np.array([ 0.40,  0.40,  0.30,  0.60,  0.20,  0.20,  0.35,  0.50]),
    "Rassemblement National (FRA)": np.array([ 0.15,  0.75,  0.70,  0.80,  0.30,  0.10,  0.40,  0.85]),
    "Renaissance - Macron (FRA)":   np.array([ 0.25,  0.20, -0.20, -0.60, -0.15,  0.30,  0.00,  0.10]),
    "SPD (GER)":                    np.array([-0.35, -0.05, -0.30, -0.45, -0.40,  0.05, -0.45, -0.20]),
    "CDU/CSU (GER)":                np.array([ 0.30,  0.25,  0.15, -0.30,  0.10,  0.15,  0.20,  0.30]),
    "AfD (GER)":                    np.array([ 0.50,  0.80,  0.85,  0.90,  0.60,  0.05,  0.60,  0.85]),
    "Partito Comunista Cinese":     np.array([-0.30,  0.95,  0.60,  0.70,  0.20,  0.80,  0.30,  0.90]),
    # 40 STORICI
    "Karl Marx":                    np.array([-1.00, -0.20, -0.60, -0.90,  0.00,  0.20, -1.00, -0.40]),
    "Vladimir Lenin":               np.array([-1.00,  0.75, -0.40, -0.80,  0.00,  0.30, -0.90,  0.60]),
    "Josif Stalin":                 np.array([-0.95,  1.00,  0.60,  0.50,  0.50,  0.40, -0.60,  1.00]),
    "Mao Zedong":                   np.array([-1.00,  0.95,  0.80,  0.60,  0.40,  0.10, -0.80,  0.95]),
    "Che Guevara":                  np.array([-0.90,  0.60, -0.30, -0.85,  0.00,  0.00, -0.90,  0.70]),
    "Fidel Castro":                 np.array([-0.85,  0.85,  0.10, -0.60,  0.00,  0.00, -0.80,  0.80]),
    "Franklin D. Roosevelt":        np.array([-0.50,  0.30, -0.10, -0.30, -0.20,  0.10, -0.40,  0.10]),
    "John F. Kennedy":              np.array([-0.10,  0.10, -0.30, -0.40, -0.10,  0.40, -0.20, -0.10]),
    "Abraham Lincoln":              np.array([ 0.10,  0.40, -0.50,  0.10,  0.00,  0.00, -0.60,  0.20]),
    "George Washington":            np.array([ 0.30,  0.30,  0.20,  0.70,  0.00,  0.00,  0.20,  0.30]),
    "Winston Churchill":            np.array([ 0.40,  0.60,  0.50,  0.20,  0.00,  0.20,  0.50,  0.50]),
    "Margaret Thatcher":            np.array([ 0.85,  0.70,  0.40,  0.40,  0.30,  0.30,  0.60,  0.70]),
    "Ronald Reagan":                np.array([ 0.80,  0.60,  0.55,  0.30,  0.50,  0.40,  0.50,  0.65]),
    "Milton Friedman":              np.array([ 0.95, -0.50, -0.10, -0.20,  0.40,  0.50,  0.40, -0.20]),
    "Murray Rothbard":              np.array([ 1.00, -0.95,  0.10, -0.70,  0.60,  0.60,  0.50, -0.30]),
    "Mahatma Gandhi":               np.array([-0.40, -0.60, -0.20, -0.50, -0.80, -0.80, -0.70, -0.90]),
    "Nelson Mandela":               np.array([-0.50, -0.30, -0.60, -0.70,  0.00,  0.00, -0.80, -0.50]),
    "Martin Luther King Jr.":       np.array([-0.60, -0.40, -0.70, -0.60,  0.00,  0.00, -0.85, -0.60]),
    "Benito Mussolini":             np.array([ 0.20,  0.95,  0.85,  0.90,  0.30,  0.40,  0.70,  0.90]),
    "Adolf Hitler":                 np.array([ 0.10,  1.00,  1.00,  1.00,  0.20,  0.50,  0.90,  1.00]),
    "Augusto Pinochet":             np.array([ 0.85,  1.00,  0.80,  0.60,  0.40,  0.20,  0.80,  0.95]),
    "Francisco Franco":             np.array([ 0.30,  0.95,  0.95,  0.70,  0.10,  0.00,  0.75,  0.90]),
    "Maximilien Robespierre":       np.array([-0.30,  0.90, -0.80, -0.10,  0.00,  0.00, -0.70,  0.95]),
    "Napoleone Bonaparte":          np.array([ 0.10,  0.85, -0.20,  0.80,  0.00,  0.20,  0.10,  0.60]),
    "Otto von Bismarck":            np.array([-0.20,  0.80,  0.60,  0.70,  0.00,  0.20,  0.50,  0.70]),
    "Giulio Cesare":                np.array([ 0.00,  0.85,  0.20,  0.80,  0.00,  0.00,  0.60,  0.80]),
    "Thomas Jefferson":             np.array([ 0.40, -0.40, -0.30,  0.30,  0.00,  0.00,  0.10,  0.00]),
    "Simon Bolivar":                np.array([ 0.00,  0.60, -0.20,  0.50,  0.00,  0.00, -0.10,  0.40]),
    "John Locke":                   np.array([ 0.60, -0.60, -0.30,  0.00,  0.00,  0.00,  0.20, -0.10]),
    "Thomas Hobbes":                np.array([ 0.20,  0.95,  0.40,  0.50,  0.00,  0.00,  0.60,  0.70]),
    "Niccolò Machiavelli":          np.array([ 0.00,  0.70,  0.10,  0.60,  0.00,  0.00,  0.40,  0.50]),
    "Platone":                      np.array([-0.10,  0.90,  0.70,  0.20,  0.00,  0.00,  0.90,  0.60]),
    "Aristotele":                   np.array([ 0.10,  0.50,  0.60,  0.30,  0.00,  0.00,  0.70,  0.30]),
    "Augusto (Imperatore)":         np.array([ 0.10,  0.90,  0.50,  0.80,  0.00,  0.00,  0.70,  0.70]),
    "Elisabetta I d'Inghilterra":   np.array([ 0.20,  0.80,  0.30,  0.70,  0.00,  0.00,  0.60,  0.60]),
    "Luigi XIV (Re Sole)":          np.array([-0.10,  1.00,  0.70,  0.80,  0.00,  0.00,  0.90,  0.80]),
    "Pietro il Grande":             np.array([ 0.20,  0.95, -0.10,  0.70,  0.00,  0.30,  0.80,  0.80]),
    "Giuseppe Garibaldi":           np.array([-0.30, -0.20, -0.50,  0.40,  0.00,  0.00, -0.40, -0.10]),
    "Camillo Benso di Cavour":      np.array([ 0.40,  0.30, -0.10,  0.50,  0.00,  0.20,  0.30,  0.20]),
    "Giuseppe Mazzini":             np.array([-0.20, -0.10, -0.40, -0.20,  0.00,  0.00, -0.30, -0.10]),
}

CAT_IDEOLOGIE = [
    "Socialdemocrazia", "Liberalismo classico", "Conservatorismo liberale", "Conservatorismo sociale",
    "Libertarianismo", "Comunismo democratico", "Comunismo autoritario", "Anarchismo sociale",
    "Anarco-capitalismo", "Fascismo / ultranazionalismo", "Eco-socialismo", "Ecologismo progressista",
    "Ecologismo conservatore", "Tecnocrazia liberale", "Accelerazionismo tecnologico", "Tecno-autoritarismo",
    "Neo-reazione / NRx", "Anarco-primitivismo", "Nazional-populismo", "Populismo di sinistra",
    "Populismo digitale", "Centrismo pragmatico", "Moderato liberal-democratico",
]
CAT_PARTITI = [
    "PD", "Alleanza Verdi e Sinistra", "Movimento 5 Stelle", "Azione / Italia Viva",
    "Forza Italia", "Lega", "Fratelli d'Italia", "Partito Democratico (USA)",
    "Partito Repubblicano (USA)", "Labour Party (UK)", "Conservative Party (UK)",
    "Rassemblement National (FRA)", "Renaissance - Macron (FRA)", "SPD (GER)",
    "CDU/CSU (GER)", "AfD (GER)", "Partito Comunista Cinese",
]
CAT_STORICI = [
    "Karl Marx", "Vladimir Lenin", "Josif Stalin", "Mao Zedong", "Che Guevara", "Fidel Castro",
    "Franklin D. Roosevelt", "John F. Kennedy", "Abraham Lincoln", "George Washington",
    "Winston Churchill", "Margaret Thatcher", "Ronald Reagan", "Milton Friedman", "Murray Rothbard",
    "Mahatma Gandhi", "Nelson Mandela", "Martin Luther King Jr.", "Benito Mussolini", "Adolf Hitler",
    "Augusto Pinochet", "Francisco Franco", "Maximilien Robespierre", "Napoleone Bonaparte",
    "Otto von Bismarck", "Giulio Cesare", "Thomas Jefferson", "Simon Bolivar", "John Locke",
    "Thomas Hobbes", "Niccolò Machiavelli", "Platone", "Aristotele", "Augusto (Imperatore)",
    "Elisabetta I d'Inghilterra", "Luigi XIV (Re Sole)", "Pietro il Grande", "Giuseppe Garibaldi",
    "Camillo Benso di Cavour", "Giuseppe Mazzini",
]

PROTO_COLORS = {
    "Socialdemocrazia": "#e74c3c", "Liberalismo classico": "#3498db",
    "Conservatorismo liberale": "#e67e22", "Conservatorismo sociale": "#8e44ad",
    "Libertarianismo": "#1abc9c", "Comunismo democratico": "#c0392b",
    "Comunismo autoritario": "#922b21", "Anarchismo sociale": "#f39c12",
    "Anarco-capitalismo": "#2ecc71", "Fascismo / ultranazionalismo": "#2c3e50",
    "Eco-socialismo": "#27ae60", "Ecologismo progressista": "#16a085",
    "Ecologismo conservatore": "#d35400", "Tecnocrazia liberale": "#2980b9",
    "Accelerazionismo tecnologico": "#9b59b6", "Tecno-autoritarismo": "#6c3483",
    "Neo-reazione / NRx": "#1a252f", "Anarco-primitivismo": "#784212",
    "Nazional-populismo": "#b7950b", "Populismo di sinistra": "#cb4335",
    "Populismo digitale": "#117a65", "Centrismo pragmatico": "#85929e",
    "Moderato liberal-democratico": "#5d6d7e",
    "PD": "#c0392b", "Alleanza Verdi e Sinistra": "#27ae60",
    "Movimento 5 Stelle": "#f39c12", "Azione / Italia Viva": "#2e86c1",
    "Forza Italia": "#1f618d", "Lega": "#196f3d", "Fratelli d'Italia": "#1c2833",
    "Partito Democratico (USA)": "#0015BC", "Partito Repubblicano (USA)": "#FF0000",
    "Labour Party (UK)": "#E4003B", "Conservative Party (UK)": "#0087DC",
    "Rassemblement National (FRA)": "#0D378A", "Renaissance - Macron (FRA)": "#FFD600",
    "SPD (GER)": "#E3000F", "CDU/CSU (GER)": "#444444",
    "AfD (GER)": "#009EE0", "Partito Comunista Cinese": "#DE2910",
}
for nome in CAT_STORICI:
    PROTO_COLORS[nome] = "#95a5a6"

# ============================================================
# DOMANDE (60) — AGGIUNTE SPIEGAZIONE INIZIALE + 60° DOMANDA
# ============================================================

QUESTIONS = [
    {"id": "immigration_policy", "question": "Quale politica migratoria preferisci?",
     "options": ["1 – Frontiere molto aperte, cittadinanza rapida e canali umanitari ampi","2 – Accoglienza ampia ma organizzata con controlli amministrativi","3 – Ingressi regolati per lavoro, studio, famiglia e asilo","4 – Sistema bilanciato: accoglienza e controllo in pari misura","5 – Ingressi limitati e selettivi in base alle esigenze nazionali","6 – Blocco quasi totale dei nuovi ingressi irregolari","7 – Espulsioni sistematiche/deportazioni degli irregolari e frontiere militarizzate"],
     "weights": [0, 0.25, 0.15, 1, 0, 0, 0, 0.15]},
    {"id": "taxation", "question": "Come dovrebbe funzionare la tassazione?",
     "options": ["1 – Tasse molto alte sui grandi patrimoni e redditi elevati","2 – Forte progressività fiscale","3 – Progressività moderata","4 – Sistema bilanciato","5 – Tasse più basse per stimolare investimenti","6 – Flat tax o quasi-flat tax","7 – Tassazione minima e Stato molto leggero"],
     "weights": [1, 0, 0, 0, 0, 0, 0.8, 0]},
    {"id": "welfare", "question": "Quale ruolo dovrebbe avere il welfare pubblico?",
     "options": ["1 – Welfare universale molto esteso","2 – Sanità, scuola e casa fortemente pubbliche","3 – Welfare pubblico robusto ma sostenibile","4 – Mix pubblico-privato equilibrato","5 – Welfare mirato solo ai più fragili","6 – Più assicurazioni e servizi privati","7 – Welfare minimo: responsabilità individuale"],
     "weights": [1, 0, 0, 0, 0, 0, 0.7, 0]},
    {"id": "privatization", "question": "Privatizzazioni dei servizi pubblici essenziali:",
     "options": ["1 – Contrario: servizi essenziali sempre pubblici","2 – Privato solo come supporto marginale","3 – Pubblico prevalente con controllo qualità","4 – Dipende dal settore","5 – Privato spesso più efficiente","6 – Ampie privatizzazioni","7 – Privatizzare quasi tutto ciò che può stare sul mercato"],
     "weights": [1, 0, 0, 0, 0, 0, 0.2, 0]},
    {"id": "labor_market", "question": "Mercato del lavoro:",
     "options": ["1 – Forte tutela del lavoro, sindacati centrali e licenziamenti difficili","2 – Tutele alte ma con qualche flessibilità","3 – Equilibrio tra tutele e competitività","4 – Sistema bilanciato","5 – Più flessibilità per assumere e licenziare","6 – Contratti molto flessibili","7 – Mercato del lavoro quasi totalmente deregolato"],
     "weights": [1, 0.1, 0, 0, 0, 0, 0.5, 0]},
    {"id": "minimum_wage", "question": "Salario minimo:",
     "options": ["1 – Salario minimo alto fissato per legge","2 – Salario minimo nazionale robusto","3 – Soglia legale moderata","4 – Dipende dai contratti collettivi","5 – Meglio contrattazione privata","6 – Lo Stato non dovrebbe fissare salari","7 – Qualsiasi salario concordato liberamente va accettato"],
     "weights": [1, 0, 0, 0, 0, 0, 0.55, 0]},
    {"id": "property", "question": "Proprietà privata dei grandi mezzi produttivi:",
     "options": ["1 – Settori strategici collettivi o pubblici","2 – Forte controllo pubblico sulle grandi imprese","3 – Mercato con regolazione intensa","4 – Economia mista","5 – Proprietà privata come regola","6 – Poche restrizioni alla proprietà privata","7 – Proprietà privata quasi sacra e inviolabile"],
     "weights": [1, 0, 0, 0, 0, 0, 0.45, 0]},
    {"id": "basic_income", "question": "Reddito di base / sostegno economico pubblico:",
     "options": ["1 – Reddito universale garantito a tutti","2 – Reddito minimo forte per chi è in difficoltà","3 – Sostegno temporaneo con politiche attive","4 – Misura limitata e controllata","5 – Solo aiuti emergenziali","6 – Meglio ridurre le tasse che dare sussidi","7 – Nessun reddito pubblico: responsabilità individuale"],
     "weights": [1, 0, 0, 0, 0, 0, 0.75, 0]},
    {"id": "public_debt", "question": "Debito pubblico:",
     "options": ["1 – Può aumentare molto se serve a finanziare diritti sociali","2 – Accettabile per investimenti pubblici importanti","3 – Va gestito ma non demonizzato","4 – Equilibrio tra spesa e sostenibilità","5 – Va ridotto con disciplina fiscale","6 – Priorità assoluta al pareggio","7 – Tagli drastici allo Stato per abbattere il debito"],
     "weights": [0.75, 0.1, 0, 0, 0, 0, 0.35, 0]},
    {"id": "business_regulation", "question": "Regolazione delle imprese:",
     "options": ["1 – Regolazione forte su lavoro, ambiente e profitti","2 – Regole stringenti ma prevedibili","3 – Regole moderate","4 – Equilibrio","5 – Meno burocrazia per competere","6 – Deregulation ampia","7 – Libertà d'impresa quasi totale"],
     "weights": [0.75, 0, 0, 0, 0.15, 0.25, 0.25, 0]},
    {"id": "police_power", "question": "Poteri di polizia:",
     "options": ["1 – Devono essere molto limitati e controllati","2 – Servono forti garanzie contro abusi","3 – Poteri ordinari con controllo giudiziario","4 – Equilibrio sicurezza-libertà","5 – Più poteri per contrastare criminalità","6 – Controlli più duri e meno vincoli operativi","7 – Ordine pubblico sopra quasi ogni altra cosa"],
     "weights": [0, 1, 0.2, 0.1, 0, 0, 0.25, 0.85]},
    {"id": "surveillance", "question": "Sorveglianza pubblica e telecamere intelligenti:",
     "options": ["1 – No: rischio autoritario troppo alto","2 – Solo in casi eccezionali","3 – Ammessa con forti garanzie","4 – Dipende dai contesti","5 – Utile nelle città e nei luoghi sensibili","6 – Da usare ampiamente per sicurezza","7 – Sorveglianza estesa se riduce crimine e disordine"],
     "weights": [0, 1, 0.1, 0, 0, 0.35, 0.1, 0.6]},
    {"id": "protest", "question": "Proteste e disobbedienza civile:",
     "options": ["1 – Sono strumenti fondamentali anche se disturbano l'ordine","2 – Vanno protette quasi sempre","3 – Legittime se non violente","4 – Dipende dalla causa e dai metodi","5 – Devono avere limiti rigidi","6 – Chi blocca servizi pubblici va punito severamente","7 – L'ordine viene prima del diritto di protesta"],
     "weights": [0, 1, 0.25, 0, 0, 0, 0.15, 0.65]},
    {"id": "military_service", "question": "Servizio militare/civile obbligatorio:",
     "options": ["1 – Contrario: scelta individuale","2 – Solo volontario","3 – Servizio civile incentivato","4 – Opzione mista","5 – Servizio civile obbligatorio","6 – Servizio militare o civile obbligatorio","7 – Leva obbligatoria come dovere nazionale"],
     "weights": [0, 0.75, 0.45, 0.55, 0, 0, 0.25, 0.15]},
    {"id": "drug_policy", "question": "Droghe leggere:",
     "options": ["1 – Legalizzazione ampia e regolata","2 – Legalizzazione con vincoli","3 – Depenalizzazione","4 – Sistema attuale ma meno repressivo","5 – Divieto con sanzioni moderate","6 – Repressione dura dello spaccio","7 – Tolleranza zero anche per consumo"],
     "weights": [0, 0.75, 0.55, 0, 0, 0, 0, 0.75]},
    {"id": "free_speech", "question": "Libertà di espressione e discorsi offensivi:",
     "options": ["1 – Proteggere anche opinioni molto offensive","2 – Limitare solo istigazione concreta alla violenza","3 – Bilanciare libertà e tutela delle minoranze","4 – Dipende dal contesto","5 – Sanzionare hate speech in modo più ampio","6 – Piattaforme e Stato devono intervenire spesso","7 – Limitare fortemente discorsi divisivi o pericolosi"],
     "weights": [0, 0.65, -0.1, 0, 0, -0.1, -0.1, 0.2]},
    {"id": "religion_state", "question": "Religione e Stato:",
     "options": ["1 – Laicità rigorosa e religione fuori dalle istituzioni","2 – Stato laico con piena libertà religiosa","3 – Neutralità pubblica","4 – Riconoscimento culturale della religione storica","5 – Valori religiosi importanti nella vita pubblica","6 – Leggi ispirate alla tradizione religiosa","7 – Stato apertamente fondato su principi religiosi"],
     "weights": [0, 0.25, 1, 0.25, 0, 0, 0.25, 0.15]},
    {"id": "family_policy", "question": "Famiglia:",
     "options": ["1 – Riconoscere tutte le forme familiari allo stesso modo","2 – Massima inclusione nei diritti familiari","3 – Parità giuridica ma con tutela dei minori","4 – Equilibrio tra tradizione e pluralismo","5 – Famiglia tradizionale da valorizzare maggiormente","6 – Politiche pubbliche centrate sulla famiglia tradizionale","7 – Solo la famiglia tradizionale è fondamento legittimo della società"],
     "weights": [0, 0.2, 1, 0.1, 0, 0, 0.25, 0.1]},
    {"id": "gender_policy", "question": "Politiche di genere:",
     "options": ["1 – Massima autodeterminazione e riconoscimento identitario","2 – Diritti molto estesi contro discriminazioni","3 – Tutela giuridica ampia ma con equilibrio","4 – Tema da gestire caso per caso","5 – Riconoscere differenze biologiche tradizionali","6 – Limitare politiche gender nelle scuole e istituzioni","7 – Rifiuto delle politiche di genere contemporanee"],
     "weights": [0, 0.15, 1, 0.05, 0, 0, 0.25, 0.05]},
    {"id": "school_values", "question": "Scuola pubblica:",
     "options": ["1 – Educazione critica, inclusiva e pluralista","2 – Centralità di pensiero critico e diritti","3 – Formazione civica equilibrata","4 – Conoscenze e competenze senza ideologia","5 – Disciplina, merito e identità culturale","6 – Autorità docente e valori tradizionali","7 – Scuola come trasmissione di ordine, patria e tradizione"],
     "weights": [0, 0.35, 0.85, 0.25, 0, 0, 0.45, 0.2]},
    {"id": "european_union", "question": "Unione Europea:",
     "options": ["1 – Più integrazione politica fino a federazione","2 – UE più forte su difesa, clima e diritti","3 – Integrazione pragmatica","4 – Cooperazione ma senza eccessi","5 – Restituire competenze agli Stati","6 – UE molto ridimensionata","7 – Uscita o sovranità nazionale quasi totale"],
     "weights": [0, 0, -0.15, 1, 0, 0, 0, 0]},
    {"id": "nato_defense", "question": "NATO e difesa occidentale:",
     "options": ["1 – Critica radicale delle alleanze militari","2 – Ridurre ruolo militare e investire in diplomazia","3 – Difesa comune ma con cautela","4 – Equilibrio tra diplomazia e deterrenza","5 – NATO utile per sicurezza","6 – Rafforzare spesa militare e deterrenza","7 – Massima priorità alla potenza militare nazionale/occidentale"],
     "weights": [0.1, 0.45, 0.15, 0.4, 0, 0.1, 0.15, 0.35]},
    {"id": "trade_globalization", "question": "Globalizzazione economica:",
     "options": ["1 – Regole globali solidali e tutela dei lavoratori","2 – Commercio aperto ma con diritti sociali","3 – Apertura regolata","4 – Dipende dai settori","5 – Protezione strategica dell'economia nazionale","6 – Protezionismo ampio","7 – Priorità assoluta all'autarchia/sovranità economica"],
     "weights": [0.25, 0, 0, 0.85, 0, 0, 0.1, 0]},
    {"id": "climate_policy", "question": "Politiche climatiche:",
     "options": ["1 – Transizione radicale anche con sacrifici economici","2 – Tagli rapidi alle emissioni","3 – Transizione verde graduale","4 – Bilanciamento clima-industria","5 – Nessun danno alla competitività","6 – Ambiente subordinato alla crescita","7 – Rifiuto delle politiche climatiche costose"],
     "weights": [0.2, 0, 0, 0, 1, -0.1, 0.15, 0]},
    {"id": "nuclear_energy", "question": "Energia nucleare:",
     "options": ["1 – Contrario per rischio e modello centralizzato","2 – Preferisco rinnovabili diffuse","3 – Possibile solo come ultima opzione","4 – Valutare caso per caso","5 – Favorevole come parte del mix","6 – Molto favorevole per autonomia energetica","7 – Nucleare prioritario e accelerato"],
     "weights": [0, 0, 0.1, 0.2, 0.75, 0.45, 0.05, 0]},
    {"id": "animal_rights", "question": "Diritti degli animali e allevamenti intensivi:",
     "options": ["1 – Abolizione progressiva degli allevamenti intensivi","2 – Forti limiti e riduzione consumo carne","3 – Standard severi di benessere animale","4 – Riforme moderate","5 – Tutela ma senza colpire troppo il settore","6 – Priorità ad agricoltura e produzione","7 – Nessun vincolo ulteriore agli allevamenti"],
     "weights": [0.15, 0, -0.25, 0, 0.85, -0.1, 0.25, 0]},
    {"id": "ai_governance", "question": "Governance dell'intelligenza artificiale:",
     "options": ["1 – Bloccare modelli molto potenti finché non sono sicuri","2 – Regolazione molto severa","3 – Regolazione forte ma favorevole all'innovazione","4 – Equilibrio","5 – Innovazione libera con controlli ex post","6 – Pochi limiti per non perdere competitività","7 – Accelerare senza freni: più tecnologia è meglio"],
     "weights": [0, 0.15, -0.1, 0, 0, 1, 0.05, 0]},
    {"id": "data_privacy", "question": "Dati personali e piattaforme digitali:",
     "options": ["1 – Privacy radicale e controllo degli utenti","2 – Regole severe contro big tech","3 – Trasparenza e diritto alla portabilità","4 – Equilibrio privacy-innovazione","5 – Meno vincoli per servizi migliori","6 – Uso ampio dei dati per efficienza","7 – I dati sono risorsa strategica da sfruttare pienamente"],
     "weights": [0, 0.45, -0.1, 0, 0, 0.8, -0.05, 0.1]},
    {"id": "crypto", "question": "Criptovalute:",
     "options": ["1 – Fortemente regolate o vietate se rischiose","2 – Regole severe antiriciclaggio","3 – Consentite con controllo pubblico","4 – Neutrale","5 – Innovazione finanziaria utile","6 – Massima libertà per finanza decentralizzata","7 – Crypto come alternativa allo Stato e alle banche centrali"],
     "weights": [0.15, -0.2, 0, -0.1, 0, 0.85, 0.25, 0]},
    {"id": "platform_censorship", "question": "Moderazione dei social network:",
     "options": ["1 – Moderazione forte contro odio e disinformazione","2 – Regole chiare e interventi frequenti","3 – Moderazione trasparente","4 – Equilibrio","5 – Lasciare più libertà agli utenti","6 – Pochissima moderazione","7 – Libertà totale salvo reati gravissimi"],
     "weights": [0, -0.55, -0.15, 0, 0, 0.35, 0, -0.1]},
    {"id": "education_merit", "question": "Scuola e università: merito o inclusione?",
     "options": ["1 – Ridurre fortemente disuguaglianze di partenza","2 – Sostegno pubblico intenso agli svantaggiati","3 – Inclusione con valutazione seria","4 – Equilibrio","5 – Più selezione meritocratica","6 – Competizione forte tra studenti e scuole","7 – Solo i migliori devono avanzare"],
     "weights": [0.35, 0.1, 0.2, 0, 0, 0, 1, 0]},
    {"id": "healthcare", "question": "Sanità:",
     "options": ["1 – Sanità totalmente pubblica e universale","2 – Pubblico dominante","3 – Pubblico forte con privato integrativo","4 – Sistema misto","5 – Privato più rilevante","6 – Assicurazioni private centrali","7 – Sanità prevalentemente privata"],
     "weights": [1, 0, 0, 0, 0, 0, 0.5, 0]},
    {"id": "housing", "question": "Casa e affitti:",
     "options": ["1 – Grande piano pubblico per casa e affitti calmierati","2 – Forti limiti agli affitti e case popolari","3 – Incentivi pubblici e regole anti-speculazione","4 – Equilibrio","5 – Meno vincoli ai proprietari","6 – Mercato immobiliare più libero","7 – Nessun controllo pubblico sui canoni"],
     "weights": [1, 0, 0, 0, 0, 0, 0.6, 0]},
    {"id": "public_transport", "question": "Mobilità urbana:",
     "options": ["1 – Ridurre drasticamente auto private, più trasporto pubblico","2 – Priorità a metro, bus, bici","3 – Limitazioni moderate alle auto","4 – Equilibrio","5 – Auto private da tutelare","6 – No a ZTL e limiti eccessivi","7 – Libertà totale di circolazione privata"],
     "weights": [0.2, -0.1, -0.2, 0, 0.75, -0.1, 0.15, 0]},
    {"id": "crime_sentencing", "question": "Pene per reati gravi:",
     "options": ["1 – Percorsi di recupero anche per reati gravi","2 – Pena e riabilitazione insieme","3 – Detenzione ma con reinserimento","4 – Equilibrio","5 – Pene più lunghe","6 – Ergastolo più frequente","7 – Massima severità, certezza e durezza della pena"],
     "weights": [0, 0.4, 0.1, 0, 0, 0, 0.15, 1]},
    {"id": "prison_model", "question": "Carcere:",
     "options": ["1 – Va trasformato in luogo di recupero sociale","2 – Più misure alternative","3 – Carcere solo quando necessario","4 – Sistema misto","5 – Più carcere per sicurezza","6 – Carceri più dure","7 – Il carcere deve principalmente neutralizzare il colpevole"],
     "weights": [0, 0.35, 0, 0, 0, 0, 0.2, 1]},
    {"id": "death_penalty", "question": "Pena di morte:",
     "options": ["1 – Sempre contraria","2 – Contraria anche nei casi estremi","3 – Contraria ma capisco il dibattito","4 – Neutrale/indeciso","5 – Possibile solo in casi eccezionali","6 – Favorevole per crimini gravissimi","7 – Favorevole come strumento di giustizia e deterrenza"],
     "weights": [0, 0.45, 0.25, 0, 0, 0, 0.3, 1]},
    {"id": "elite_governance", "question": "Governo delle élite:",
     "options": ["1 – La democrazia popolare viene prima delle competenze tecniche","2 – Più partecipazione diretta dei cittadini","3 – Tecnici utili ma subordinati alla politica","4 – Equilibrio tra competenza e consenso","5 – Più tecnici nelle decisioni complesse","6 – Le masse capiscono poco: decidano i competenti","7 – Governo di élite competenti meglio della democrazia di massa"],
     "weights": [0, 0.45, 0.1, 0, 0, 0.25, 1, 0.25]},
    {"id": "democracy", "question": "Democrazia parlamentare:",
     "options": ["1 – Va ampliata con partecipazione diretta","2 – Va difesa e resa più inclusiva","3 – Funziona con buone riforme","4 – Ha pregi e limiti","5 – È lenta e inefficiente","6 – Meglio leader forti con meno vincoli","7 – La democrazia è un sistema debole da superare"],
     "weights": [0, 1, 0.1, 0.1, 0, 0.25, 0.65, 0.25]},
    {"id": "referendum", "question": "Referendum e democrazia diretta:",
     "options": ["1 – Usarli spesso per dare potere al popolo","2 – Più consultazioni popolari","3 – Utili su temi chiari","4 – Uso moderato","5 – Rischiano populismo","6 – Meglio affidarsi a Parlamento e tecnici","7 – Il popolo non dovrebbe decidere questioni complesse"],
     "weights": [0, 0.35, 0, 0, 0, 0.1, 0.75, 0]},
    {"id": "national_identity", "question": "Identità nazionale:",
     "options": ["1 – Identità fluida e multiculturale","2 – Patriottismo inclusivo","3 – Identità nazionale aperta","4 – Equilibrio","5 – Tradizione nazionale da difendere","6 – Prima gli interessi nazionali","7 – Nazione, cultura e confini sopra tutto"],
     "weights": [0, 0.35, 0.75, 1, 0, 0, 0.35, 0.2]},
    {"id": "minorities", "question": "Minoranze culturali e religiose:",
     "options": ["1 – Riconoscimento ampio di differenze e diritti specifici","2 – Tutela attiva contro discriminazioni","3 – Integrazione con pari diritti","4 – Equilibrio","5 – Assimilazione alle regole nazionali","6 – Niente eccezioni culturali","7 – Le minoranze devono adattarsi completamente o andarsene"],
     "weights": [0, 0.35, 0.75, 0.8, 0, 0, 0.35, 0.25]},
    {"id": "abortion", "question": "Aborto:",
     "options": ["1 – Libertà di scelta piena entro termini ragionevoli","2 – Tutela ampia dell'autodeterminazione","3 – Diritto garantito con consulenza","4 – Equilibrio","5 – Più limiti e prevenzione","6 – Ammesso solo in casi gravi","7 – Contrarietà quasi totale"],
     "weights": [0, 0.25, 1, 0, 0, 0, 0.15, 0.2]},
    {"id": "euthanasia", "question": "Eutanasia e fine vita:",
     "options": ["1 – Diritto pieno all'autodeterminazione","2 – Legalizzazione con garanzie","3 – Apertura controllata","4 – Caso per caso","5 – Solo cure palliative e pochi casi limite","6 – Contrario salvo eccezioni drammatiche","7 – Sempre contrario per principio morale/religioso"],
     "weights": [0, 0.25, 0.9, 0, 0, 0, 0.1, 0.15]},
    {"id": "vaccines_public_health", "question": "Vaccini e sanità pubblica obbligatoria:",
     "options": ["1 – Scelta individuale quasi sempre","2 – Obblighi solo in emergenza estrema","3 – Raccomandazioni forti, pochi obblighi","4 – Equilibrio libertà-salute pubblica","5 – Obblighi se tutelano collettività","6 – Poteri sanitari forti in emergenza","7 – La salute pubblica prevale nettamente sulla scelta individuale"],
     "weights": [0, 0.65, -0.05, 0, 0, -0.15, -0.1, 0.2]},
    {"id": "pandemic_restrictions", "question": "Restrizioni in caso di pandemia:",
     "options": ["1 – Mai lockdown o restrizioni forti","2 – Solo misure volontarie","3 – Restrizioni leggere e temporanee","4 – Dipende dai dati","5 – Restrizioni forti se servono","6 – Lockdown e obblighi se necessari","7 – Lo Stato deve poter imporre misure dure per salvare vite"],
     "weights": [0, 0.75, -0.05, 0, 0, -0.2, -0.15, 0.25]},
    {"id": "localism", "question": "Comunità locali e autonomie:",
     "options": ["1 – Autogoverno locale forte e federalismo dal basso","2 – Più potere a comuni e comunità","3 – Decentramento amministrativo","4 – Equilibrio centro-territori","5 – Stato centrale più forte","6 – Uniformità nazionale delle decisioni","7 – Centralizzazione forte per ordine ed efficienza"],
     "weights": [0, 0.55, 0.15, 0.35, 0, 0, 0.1, 0]},
    {"id": "urban_rural", "question": "Modello di vita ideale:",
     "options": ["1 – Comunità aperte, urbane e cosmopolite","2 – Città inclusive e multiculturali","3 – Equilibrio urbano-rurale","4 – Indifferente","5 – Comunità locali radicate","6 – Vita tradizionale e territoriale","7 – Piccole comunità omogenee e chiuse"],
     "weights": [0, 0.15, 0.55, 0.65, 0.1, -0.1, 0.25, 0]},
    {"id": "art_culture", "question": "Arte e cultura pubblica:",
     "options": ["1 – Sperimentazione, provocazione e rottura delle forme","2 – Avanguardia e pluralismo culturale","3 – Innovazione con accessibilità","4 – Equilibrio","5 – Valorizzare patrimonio e bellezza tradizionale","6 – Più arte classica e identitaria","7 – Rifiuto dell'arte contemporanea caotica o provocatoria"],
     "weights": [0, 0.05, 0.75, 0.25, 0, 0, 0.15, 0]},
    {"id": "food_identity", "question": "Cibo e identità culturale:",
     "options": ["1 – Massima apertura a cucine e contaminazioni globali","2 – Curiosità multiculturale","3 – Apertura con attenzione alla qualità","4 – Equilibrio","5 – Preferenza per cucina nazionale/tradizionale","6 – Difesa delle tradizioni alimentari locali","7 – Diffidenza verso contaminazioni culturali e globalizzazione alimentare"],
     "weights": [0, 0, 0.45, 0.55, 0.25, 0, 0.15, 0]},
    {"id": "science_tradition", "question": "Scienza, tradizione e decisioni pubbliche:",
     "options": ["1 – Decisioni basate su evidenza scientifica anche contro tradizioni","2 – Scienza centrale ma con dialogo sociale","3 – Tecnica e valori devono bilanciarsi","4 – Equilibrio","5 – Tradizione e senso comune contano quanto gli esperti","6 – Diffidenza verso élite scientifiche","7 – La tradizione comunitaria vale più degli esperti"],
     "weights": [0, 0.2, 0.65, 0.15, 0, -0.2, 0.25, 0]},
    {"id": "meritocracy", "question": "Meritocrazia:",
     "options": ["1 – Il merito è spesso maschera delle disuguaglianze","2 – Prima correggere le condizioni di partenza","3 – Merito sì, ma con sostegni sociali","4 – Equilibrio","5 – Premiare fortemente chi si impegna","6 – Le differenze di risultato sono giuste","7 – I migliori devono emergere senza freni redistributivi"],
     "weights": [0.35, 0, 0.05, 0, 0, 0, 1, 0]},
    {"id": "inheritance", "question": "Eredità e grandi patrimoni familiari:",
     "options": ["1 – Tassare molto le grandi eredità","2 – Forte imposta sui grandi patrimoni ereditari","3 – Tassa moderata sulle grandi eredità","4 – Sistema attuale o simile","5 – Tassazione bassa","6 – Quasi nessuna tassa di successione","7 – L'eredità familiare non va toccata dallo Stato"],
     "weights": [1, 0, 0.15, 0, 0, 0, 0.85, 0]},
    {"id": "international_aid", "question": "Aiuti internazionali ai Paesi poveri:",
     "options": ["1 – Aumentarli molto come dovere globale","2 – Aumentarli con controllo efficacia","3 – Mantenerli su progetti mirati","4 – Equilibrio","5 – Ridurre e pensare prima al nostro Paese","6 – Aiuti solo se convengono strategicamente","7 – Prima esclusivamente i cittadini nazionali"],
     "weights": [0.3, 0, -0.25, 1, 0.1, 0, 0.25, 0]},
    {"id": "war_peace", "question": "Uso della forza militare all'estero:",
     "options": ["1 – Quasi mai giustificato","2 – Solo per difesa strettissima o mandato ONU","3 – Possibile in casi umanitari estremi","4 – Dipende","5 – Necessario per difendere interessi strategici","6 – Usare forza per deterrenza e influenza","7 – La potenza militare è strumento normale della politica"],
     "weights": [0.1, 0.65, 0.15, 0.35, 0, 0.1, 0.25, 0.55]},
    {"id": "law_and_order", "question": "Ordine pubblico in città:",
     "options": ["1 – Politiche sociali prima della repressione","2 – Prevenzione e inclusione","3 – Polizia e servizi sociali insieme","4 – Equilibrio","5 – Più pattuglie e controlli","6 – Tolleranza zero per degrado e microcriminalità","7 – Ordine urbano anche con misure molto dure"],
     "weights": [0.35, 0.8, 0.25, 0.25, 0, 0, 0.35, 0.9]},
    {"id": "central_bank", "question": "Banche centrali e politica monetaria:",
     "options": ["1 – Devono sostenere occupazione e investimenti sociali","2 – Mandato più sociale","3 – Stabilità prezzi ma attenzione al lavoro","4 – Mandato equilibrato","5 – Indipendenza e lotta all'inflazione","6 – Disciplina monetaria rigorosa","7 – Politica monetaria durissima contro inflazione e debito"],
     "weights": [0.8, 0.15, 0, 0.2, 0, 0, 0.25, 0]},
    {"id": "corporate_power", "question": "Potere delle grandi corporation:",
     "options": ["1 – Spezzare monopoli e ridurre drasticamente il loro potere","2 – Regolazione forte e antitrust duro","3 – Più controlli su abusi","4 – Equilibrio","5 – Le grandi imprese sono motore d'innovazione","6 – Lasciarle competere globalmente","7 – Le corporation efficienti possono gestire servizi meglio dello Stato"],
     "weights": [0.9, 0.05, -0.1, -0.15, 0, 0.4, 0.45, 0]},
    {"id": "public_order_vs_rights", "question": "Quando sicurezza e diritti entrano in conflitto:",
     "options": ["1 – I diritti individuali vengono prima","2 – Limitare potere pubblico il più possibile","3 – Bilanciare ma con garanzie forti","4 – Dipende dalla gravità","5 – Sicurezza collettiva spesso prevalente","6 – Meglio sacrificare libertà per ordine","7 – La sicurezza dello Stato viene prima dei diritti individuali"],
     "weights": [0, 1, 0.15, 0.25, 0, 0, 0.25, 0.65]},
    {"id": "cultural_preservation", "question": "Preservazione culturale vs apertura globale:",
     "options": ["1 – Massima apertura, le culture si contaminano naturalmente e migliora","2 – Accogliere influenze globali ma proteggere il patrimonio","3 – Bilanciare tradizione e innovazione culturale","4 – Equilibrio neutrale","5 – Priorità alla preservazione delle radici culturali","6 – Difendere attivamente la cultura tradizionale dalla corruzione esterna","7 – Chiudere i confini culturali, la contaminazione è una minaccia"],
     "weights": [0, 0.2, 0.6, 0.7, 0.3, 0, 0.4, 0.15]},
]

# ============================================================
# MOTORE DI CALCOLO
# ============================================================

def normalize(value):
    return (value - 4) / 3.0

def compute_profile(answers: dict) -> np.ndarray:
    scores = np.zeros(len(AXES))
    totals = np.zeros(len(AXES))
    for q in QUESTIONS:
        qid = q["id"]
        if qid not in answers:
            continue
        norm = normalize(answers[qid])
        for i in range(len(AXES)):
            w = q["weights"][i]
            if w != 0:
                scores[i] += norm * w
                totals[i] += abs(w)
    for i in range(len(AXES)):
        if totals[i] > 0:
            scores[i] /= totals[i]
    return np.clip(scores, -1.0, 1.0)

def closest_prototypes(profile, subset=None, top_n=3, reverse=False):
    dists = []
    for name, proto in PROTOTYPES.items():
        if subset and name not in subset:
            continue
        dist = np.linalg.norm(profile - proto)
        dists.append((name, dist))
    return sorted(dists, key=lambda x: x[1], reverse=reverse)[:top_n]

# ============================================================
# WIKIPEDIA LINKS
# ============================================================

def get_wiki_link(name):
    custom = {
        "Azione / Italia Viva": "Azione_(partito_politico)",
        "Forza Italia": "Forza_Italia_(2013)",
        "Fratelli d'Italia": "Fratelli_d'Italia_(partito_politico)",
        "Partito Democratico (USA)": "Partito_Democratico_(Stati_Uniti_d'America)",
        "Partito Repubblicano (USA)": "Partito_Repubblicano_(Stati_Uniti_d'America)",
        "Labour Party (UK)": "Partito_Laburista_(Regno_Unito)",
        "Conservative Party (UK)": "Partito_Conservatore_(Regno_Unito)",
        "Rassemblement National (FRA)": "Rassemblement_National",
        "Renaissance - Macron (FRA)": "Renaissance_(partito_politico_francese)",
        "SPD (GER)": "Partito_Socialdemocratico_di_Germania",
        "CDU/CSU (GER)": "Unione_Cristiano-Democratica_di_Germania",
        "AfD (GER)": "Alternative_für_Deutschland",
        "Augusto (Imperatore)": "Augusto",
        "Luigi XIV (Re Sole)": "Luigi_XIV_di_Francia",
        "Pietro il Grande": "Pietro_I_di_Russia",
    }
    slug = custom.get(name, name.replace(" ", "_"))
    return f"https://it.wikipedia.org/wiki/{slug}"

# ============================================================
# GRAFICI
# ============================================================

def make_radar_chart(profile):
    labels = ["Eco", "Aut", "Cult", "Geo", "Amb", "Tec", "Ugu", "Giu"]
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    values = profile.tolist() + profile.tolist()[:1]
    angles += angles[:1]
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#1a1a2e")
    plt.xticks(angles[:-1], labels, color='#94a3b8', size=11, fontweight="bold")
    ax.set_rlabel_position(0)
    plt.yticks([-1, -0.5, 0, 0.5, 1], ["-1", "-0.5", "0", "0.5", "1"], color="#94a3b8", size=8)
    plt.ylim(-1.1, 1.1)
    ax.plot(angles, values, color='#818cf8', linewidth=2.5)
    ax.fill(angles, values, color='#818cf8', alpha=0.25)
    ax.set_title("🕸️ Impronta Ideologica", size=14, color="#f1f5f9", y=1.1, fontweight="bold")
    ax.grid(color='#334155')
    ax.spines['polar'].set_color('#475569')
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    img = PILImage.open(buf)
    buf2 = io.BytesIO()
    img.save(buf2, format="PNG")
    buf2.seek(0)
    return img, buf2

def make_bar_chart(profile):
    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#1a1a2e")
    bar_colors = ["#ef4444" if v < 0 else "#3b82f6" for v in profile]
    bars = ax.barh(AXIS_SHORT, profile, color=bar_colors, edgecolor="#334155", height=0.6)
    ax.axvline(0, color="#64748b", linewidth=1.5, linestyle="--")
    ax.set_xlim(-1.15, 1.15)
    ax.set_title("📊 Punteggi Assoluti", fontsize=14, fontweight="bold", pad=15, color="#f1f5f9")
    ax.tick_params(colors="#94a3b8")
    for spine in ax.spines.values():
        spine.set_visible(False)
    for bar, val in zip(bars, profile):
        ax.text(val + (0.05 if val >= 0 else -0.05), bar.get_y() + bar.get_height() / 2,
                f"{val:+.2f}", va="center", ha="left" if val >= 0 else "right",
                fontsize=10, fontweight="bold", color="#f1f5f9")
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    img = PILImage.open(buf)
    buf2 = io.BytesIO()
    img.save(buf2, format="PNG")
    buf2.seek(0)
    return img, buf2

def make_pca_map(profile, filter_type="Tutti"):
    names = list(PROTOTYPES.keys())
    matrix = np.array([PROTOTYPES[n] for n in names])
    scaler = StandardScaler()
    mat_s = scaler.fit_transform(matrix)
    usr_s = scaler.transform(profile.reshape(1, -1))
    pca = PCA(n_components=2)
    pca.fit(mat_s)
    coords = pca.transform(mat_s)
    user_xy = pca.transform(usr_s)
    if filter_type == "Solo Partiti":
        to_plot = CAT_PARTITI
    elif filter_type == "Solo Ideologie":
        to_plot = CAT_IDEOLOGIE
    elif filter_type == "Solo Storici":
        to_plot = CAT_STORICI
    else:
        to_plot = names
    fig, ax = plt.subplots(figsize=(12, 8))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#1a1a2e")
    ax.axhline(0, color="#334155", linewidth=1, linestyle="--")
    ax.axvline(0, color="#334155", linewidth=1, linestyle="--")
    for i, name in enumerate(names):
        if name not in to_plot:
            continue
        c = PROTO_COLORS.get(name, "#94a3b8")
        ax.scatter(coords[i, 0], coords[i, 1], color=c, s=50, zorder=3, alpha=0.8, edgecolors="white")
        ax.annotate(name, (coords[i, 0], coords[i, 1]), textcoords="offset points", xytext=(5, 4),
                    fontsize=8, color="#cbd5e1")
    ax.scatter(user_xy[0, 0], user_xy[0, 1], color="#fbbf24", s=500, zorder=6, marker="*",
               edgecolors="#b45309", linewidths=1.5)
    ax.annotate("⭐ TU", (user_xy[0, 0], user_xy[0, 1]), textcoords="offset points", xytext=(12, 10),
                fontsize=14, color="#fbbf24", fontweight="bold")
    ax.set_xlabel(f"Spazio Politico ({pca.explained_variance_ratio_[0]*100:.0f}%)", fontsize=10, color="#94a3b8")
    ax.set_ylabel(f"Spazio Valoriale ({pca.explained_variance_ratio_[1]*100:.0f}%)", fontsize=10, color="#94a3b8")
    ax.set_title("🗺️ Mappa Multidimensionale", color="#f1f5f9", fontsize=16, fontweight="bold", pad=15)
    for spine in ax.spines.values():
        spine.set_edgecolor("#334155")
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    img = PILImage.open(buf)
    buf2 = io.BytesIO()
    img.save(buf2, format="PNG")
    buf2.seek(0)
    return img, buf2

def make_social_card(profile, top_id, top_pt, worst_st):
    fig = plt.figure(figsize=(4.5, 8))
    fig.patch.set_facecolor('#0f172a')
    fig.text(0.5, 0.94, "IL MIO PROFILO POLITICO", color='#94a3b8', ha='center', fontsize=12, fontweight='bold')
    fig.text(0.5, 0.88, top_id[0].upper(), color='#fbbf24', ha='center', fontsize=18, fontweight='heavy')
    ax = fig.add_axes([0.15, 0.45, 0.7, 0.35], polar=True)
    ax.set_facecolor('#0f172a')
    labels = ["Eco", "Aut", "Cult", "Geo", "Amb", "Tec", "Ugu", "Giu"]
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    values = profile.tolist() + profile.tolist()[:1]
    angles += angles[:1]
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, color='#cbd5e1', size=9, fontweight="bold")
    ax.set_yticks([-1, -0.5, 0, 0.5, 1])
    ax.set_yticklabels([])
    ax.set_ylim(-1.1, 1.1)
    ax.plot(angles, values, color='#818cf8', linewidth=2.5)
    ax.fill(angles, values, color='#818cf8', alpha=0.4)
    ax.grid(color='#334155', linewidth=0.5)
    ax.spines['polar'].set_color('#334155')
    fig.text(0.5, 0.38, "I MIEI ALLEATI", color='#cbd5e1', ha='center', fontsize=11, fontweight='bold')
    y_pos = 0.33
    medals = ["🥇", "🥈", "🥉"]
    for rank, (name, dist) in enumerate(top_pt):
        sim = max(0, 100 - dist * 40)
        fig.text(0.5, y_pos, f"{medals[rank]} {name} ({sim:.0f}%)", color='white', ha='center', fontsize=11)
        y_pos -= 0.04
    fig.text(0.5, 0.16, "LA MIA NEMESI STORICA", color='#ef4444', ha='center', fontsize=11, fontweight='bold')
    fig.text(0.5, 0.11, worst_st[0], color='white', ha='center', fontsize=15, fontweight='bold')
    fig.text(0.5, 0.04, "Generato dal Politometro", color='#475569', ha='center', fontsize=9)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=200, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    img = PILImage.open(buf)
    buf2 = io.BytesIO()
    img.save(buf2, format="PNG")
    buf2.seek(0)
    return img, buf2

# ============================================================
# EXPORT: PDF e CSV
# ============================================================

def export_report_pdf(report_md, bar_buf, radar_buf, pca_buf, social_buf):
    path = os.path.join(tempfile.gettempdir(), "politometro_report.pdf")
    doc = SimpleDocTemplate(path, pagesize=letter)
    styles = getSampleStyleSheet()
    story = [Paragraph("Politometro Assoluto — Il Tuo Referto", styles['h1']), Spacer(1, 0.2*inch)]
    for line in report_md.split('\n'):
        if not line.strip():
            story.append(Spacer(1, 0.1*inch))
            continue
        clean = line.lstrip('#> ').replace('**', '').replace('*', '')
        import re
        clean = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', clean)
        if line.startswith('###'):
            story.append(Paragraph(clean, styles['h3']))
        elif line.startswith('##'):
            story.append(Paragraph(clean, styles['h2']))
        else:
            story.append(Paragraph(clean, styles['Normal']))
    for label, buf in [("Grafico a Barre", bar_buf), ("Radar Chart", radar_buf),
                       ("Mappa PCA", pca_buf), ("Social Card", social_buf)]:
        if buf:
            buf.seek(0)
            try:
                story.append(Spacer(1, 0.2*inch))
                story.append(Paragraph(label, styles['h3']))
                story.append(RlImage(buf, width=4*inch, height=3*inch))
            except Exception:
                pass
    doc.build(story)
    return path

def export_report_csv(profile, top_id_name, top_pt, worst_pt, top_st_name, worst_st_name):
    path = os.path.join(tempfile.gettempdir(), "politometro_report.csv")
    rows = [["Tipo", "Nome", "Punteggio / Affinità"]]
    rows.append(["Ideologia dominante", top_id_name, ""])
    rows.append(["Alter-ego storico", top_st_name, ""])
    rows.append(["Nemesi storica", worst_st_name, ""])
    for rank, (name, dist) in enumerate(top_pt):
        rows.append([f"Partito vicino #{rank+1}", name, f"{max(0, 100-dist*40):.0f}%"])
    for name, dist in worst_pt:
        rows.append(["Partito antagonista", name, ""])
    rows.append([])
    rows.append(["Asse", "Punteggio"])
    for short, val in zip(AXIS_SHORT, profile):
        rows.append([short, round(float(val), 3)])
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    return path

# ============================================================
# FUNZIONE PRINCIPALE
# ============================================================

def calculate_all(*args):
    try:
        missing_questions = []
        for i, raw in enumerate(args):
            if raw is None:
                missing_questions.append(i + 1)

        if missing_questions:
            msg = ", ".join(map(str, missing_questions[:5]))
            if len(missing_questions) > 5:
                msg += f", +{len(missing_questions)-5} altre"
            raise gr.Error(f"⚠️ Domande non risposte: {msg}. Torna su e rispondi a tutte!")

        answers = {}
        for i, q in enumerate(QUESTIONS):
            val = int(str(args[i]).strip()[0])
            answers[q["id"]] = val

        profile = compute_profile(answers)
        top_id   = closest_prototypes(profile, subset=CAT_IDEOLOGIE, top_n=1)[0]
        top_pt   = closest_prototypes(profile, subset=CAT_PARTITI,   top_n=3)
        top_st   = closest_prototypes(profile, subset=CAT_STORICI,   top_n=1)[0]
        worst_pt = closest_prototypes(profile, subset=CAT_PARTITI,   top_n=2, reverse=True)
        worst_st = closest_prototypes(profile, subset=CAT_STORICI,   top_n=1, reverse=True)[0]

        log_path = "sondaggi_politometro.csv"
        file_exists = os.path.isfile(log_path)
        with open(log_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Data", "Ideologia", "AlterEgo", "Nemesi"] + AXIS_SHORT)
            writer.writerow([
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                top_id[0], top_st[0], worst_st[0],
                *[round(float(x), 3) for x in profile]
            ])

        medals = ["🥇", "🥈", "🥉"]
        strongest_axis_idx = np.argmax(np.abs(profile))
        strongest_axis = AXIS_SHORT[strongest_axis_idx]
        strongest_val = profile[strongest_axis_idx]

        econ_val = profile[0]
        auth_val = profile[1]
        if econ_val < -0.3 and auth_val < -0.3:
            general_desc = "🔴 **Progressista-Libertario**: Sei favorevole al cambiamento sociale e alla libertà individuale."
        elif econ_val < -0.3 and auth_val > 0.3:
            general_desc = "🟠 **Progressista-Autoritario**: Credi nel cambiamento sociale ma sotto un ordine forte."
        elif econ_val > 0.3 and auth_val < -0.3:
            general_desc = "🟡 **Conservatore-Libertario**: Preferisci mercato libero e pochi vincoli."
        elif econ_val > 0.3 and auth_val > 0.3:
            general_desc = "🔵 **Conservatore-Autoritario**: Credi in tradizione e ordine sociale forte."
        else:
            general_desc = "🟢 **Centrista**: Il tuo profilo è equilibrato tra gli estremi."

        lines = [
            "# 🎯 IL TUO REFERTO POLITICO COMPLETO",
            f"\n## Profilo Generale",
            general_desc,
            f"\n## 🧠 Ideologia Dominante: **{top_id[0]}**",
            f"> *La cornice filosofica che meglio rappresenta il tuo profilo.*",
            f"\n**Distanza ideologica:** {top_id[1]:.3f}",
            f"**Affinità percentuale:** {max(0, 100 - top_id[1] * 40):.0f}%",
            f"\n## 📊 I Tuoi 8 Assi Politici (Analisi Dettagliata)",
            "> **Scala:** -1.0 (estrema sinistra) a +1.0 (estrema destra)",
            ""
        ]

        for i, short in enumerate(AXIS_SHORT):
            val = profile[i]
            bar_length = int(abs(val) * 20)
            if val < 0:
                bar = "█" * bar_length + "░" * (20 - bar_length)
                direction = "← SINISTRA/LIBERTARIO"
            else:
                bar = "░" * (20 - bar_length) + "█" * bar_length
                direction = "DESTRA/AUTORITARIO →"

            intensity = ""
            if abs(val) > 0.7:
                intensity = " (MOLTO ACCENTUATO)"
            elif abs(val) > 0.4:
                intensity = " (MARCATO)"

            lines.append(f"### {short} ({val:+.2f}){intensity}")
            lines.append(f"```")
            lines.append(f"{bar} {direction}")
            lines.append(f"```")
            lines.append(f"**Significato:** {AXIS_EXPLANATIONS[short]}\n")

        lines.append("\n## 🏛️ I Tuoi Alleati Politici (Top 3 Partiti Più Vicini)")
        for rank, (name, dist) in enumerate(top_pt):
            sim = max(0, 100 - dist * 40)
            alignment_pct = int(sim)
            bar_fill = "█" * (alignment_pct // 10) + "░" * (10 - alignment_pct // 10)
            lines.append(f"\n{medals[rank]} **[{name}]({get_wiki_link(name)})**")
            lines.append(f"```")
            lines.append(f"Affinità: [{bar_fill}] {sim:.0f}%")
            lines.append(f"Distanza euclidea: {dist:.3f}")
            lines.append(f"```")

        lines.append("\n## 🚫 I Tuoi Antagonisti Politici (Top 2 Partiti Opposti)")
        for rank, (name, dist) in enumerate(worst_pt):
            lines.append(f"\n❌ **[{name}]({get_wiki_link(name)})**")
            lines.append(f"> *Divergenza massima dal tuo profilo ideologico.*")

        lines.append(f"\n## 📜 Alter-Ego Storico: **[{top_st[0]}]({get_wiki_link(top_st[0])})**")
        lines.append(f"> *Un personaggio storico con il tuo stesso profilo ideologico approssimativo.*")
        lines.append(f"\n**Distanza:** {top_st[1]:.3f}")

        lines.append(f"\n## ⚔️ Nemesi Storica: **[{worst_st[0]}]({get_wiki_link(worst_st[0])})**")
        lines.append(f"> *Il tuo opposto ideologico nella storia.*")
        lines.append(f"\n**Divergenza:** {worst_st[1]:.3f}")

        lines.append("\n---")
        lines.append(f"\n## 📈 Asse Più Forte")
        lines.append(f"**{strongest_axis}**: {strongest_val:+.2f}")
        lines.append(f"> Il tuo valore più accentuato.")

        lines.append("\n## ⚖️ Equilibrio Complessivo")
        progressiveness = -profile[0]
        libertarianism = -profile[1]
        lines.append(f"- **Progressismo Economico:** {progressiveness:+.2f}")
        lines.append(f"- **Libertarianismo Generale:** {libertarianism:+.2f}")

        report = "\n".join(lines)

        bar_img,    bar_buf    = make_bar_chart(profile)
        radar_img,  radar_buf  = make_radar_chart(profile)
        pca_img,    pca_buf    = make_pca_map(profile, "Tutti")
        social_img, social_buf = make_social_card(profile, top_id, top_pt, worst_st)

        pdf_path = export_report_pdf(report, bar_buf, radar_buf, pca_buf, social_buf)
        csv_path = export_report_csv(profile, top_id[0], top_pt, worst_pt, top_st[0], worst_st[0])

        return report, bar_img, radar_img, pca_img, social_img, profile, pdf_path, csv_path

    except gr.Error:
        raise
    except Exception:
        return f"🚨 **ERRORE:**\n\n```\n{traceback.format_exc()}\n```", None, None, None, None, None, None, None

def update_map_only(filter_val, profile):
    if profile is None:
        return None
    img, _ = make_pca_map(profile, filter_type=filter_val)
    return img

def reset_all():
    return [None] * len(QUESTIONS) + ["", None, None, None, None, None, "Tutti", None, None]

# ============================================================
# INTERFACCIA GRADIO
# ============================================================

def build_app():
    with gr.Blocks(
        title="🗳️ Politometro Assoluto",
        theme=gr.themes.Soft(primary_hue="indigo", secondary_hue="blue"),
        css="""
        @media (max-width: 768px) {
            .gradio-container { padding: 10px !important; }
            h1 { font-size: 24px !important; }
            .gradio-accordion { margin: 10px 0 !important; }
            .gradio-button { width: 100% !important; font-size: 14px !important; }
        }
        @media (max-width: 480px) {
            h1 { font-size: 20px !important; }
            .gradio-button { padding: 12px 16px !important; }
        }
        .gradio-container { max-width: 1200px; margin: 0 auto; }
        """
    ) as app:

        gr.Markdown("""
        <div style="text-align:center; margin-bottom:1.5rem;">
            <h1 style="color: #1e293b; font-size: 2.5em; margin: 0;">🧭 Il Politometro Assoluto</h1>
            <p style="font-size:1.1em; color:#4b5563; margin-top: 1rem;">
                Rispondi a 60 domande per scoprire la tua posizione nello scacchiere politico
            </p>
        </div>
        """)

        # SPIEGAZIONE INIZIALE COMPLETA
        gr.Markdown("""
# 📚 Come Funziona il Politometro?

## Il Sistema dei 8 Assi Politici

Il tuo profilo politico viene calcolato attraverso **8 dimensioni indipendenti**:

1. **Economia** (-1.0 a +1.0): Da welfare statale e redistribuzione → mercato libero e privatizzazioni
2. **Autorità** (-1.0 a +1.0): Da libertà individuale e limiti al potere → ordine, controllo, sicurezza
3. **Cultura** (-1.0 a +1.0): Da pluralismo e diritti civili → tradizione, religione, famiglia
4. **Geopolitica** (-1.0 a +1.0): Da cooperazione sovranazionale → sovranità nazionale e identità
5. **Ambiente** (-1.0 a +1.0): Da transizione verde rigida → priorità crescita economica
6. **Tecnologia** (-1.0 a +1.0): Da regolazione cauta → innovazione rapida e decentralizzazione
7. **Uguaglianza** (-1.0 a +1.0): Da pari condizioni → gerarchie e competizione
8. **Giustizia** (-1.0 a +1.0): Da recupero sociale → deterrenza e punizione severa

---

## Il Calcolo del Tuo Profilo

### Step 1: Normalizzazione delle Risposte
Ogni tua risposta (da 1 a 7) viene trasformata in un valore numerico. L'opzione **4 (equilibrio)** equivale a 0, mentre gli estremi (1 e 7) raggiungono -1.0 e +1.0 rispettivamente.

**Formula:** (tua_risposta - 4) / 3.0

### Step 2: Ponderazione per Asse
Ogni domanda non ha lo stesso peso su ogni asse. Ad esempio, la domanda sulla tassazione pesa MOLTO sull'asse Economia, ma poco o nulla su altri assi. I pesi sono stati assegnati da esperti di scienze politiche.

### Step 3: Aggregazione
Il tuo punteggio su **Economia** è la media ponderata di TUTTE le domande che toccano l'asse economico. Stesso per gli altri 7 assi.

**Formula:** Media ponderata = Σ(risposta_normalizzata × peso) / Σ(pesi)

### Step 4: Clipping
I punteggi finali vengono "bloccati" tra -1.0 e +1.0, così che nessun valore sia estremo oltre il limite.

---

## Matchmaking: Come Ti Confrontiamo ai Partiti?

### Distanza Euclidea
Una volta calcolati i tuoi 8 valori, li confrontiamo con i profili di:
- **23 Ideologie** (Socialdemocraz ia, Libertarianismo, Fascismo, ecc.)
- **17 Partiti** (PD, Fratelli d'Italia, Lega, Democratic Party USA, ecc.)
- **40 Storici** (Marx, Lenin, Hitler, Gandhi, ecc.)

**Metrica:** Calcoliamo la **distanza euclidea** in spazio 8-dimensionale:

d = √[(x₁-y₁)² + (x₂-y₂)² + ... + (x₈-y₈)²]

Chi è più vicino = più affinità

---

## La Mappa PCA: Compressione 8D → 2D

La **Mappa Multidimensionale** usa **Principal Component Analysis** per ridurre le 8 dimensioni a 2 visualizzabili:

- **PC1 (Orizzontale ~50% varianza)**: Combina soprattutto Economia + Autorità (Progressismo vs Conservatorismo)
- **PC2 (Verticale ~30% varianza)**: Combina Autorità + Libertà (Autoritarismo vs Libertarianismo)

⚠️ **Attenzione:** La mappa non è "perfetta" perché perde il 20% dell'informazione, ma è il miglior modo di visualizzare uno spazio complesso in 2D.

---

## Interpretazione dei Risultati

- **Valori negativi** su un asse = tendenza sinistra/libertaria su quel tema
- **Valori positivi** su un asse = tendenza destra/autoritaria su quel tema
- **Valori vicini a 0** = equilibrio su quel tema
- **Ideologia Dominante** = il "contenitore" filosofico più vicino a te
- **Partiti Vicini** = dove il tuo voto potrebbe valere di più (salvo altre considerazioni)
- **Storici** = figure dalla storia che hanno un profilo simile al tuo

---

## Note Tecniche

- **60 domande** coverage completa dei 8 assi
- **Pesi differenziati** per accuratezza
- **No compressione dei dati** = ogni risposta conta
- **Aggiornamenti regolari** basati su feedback della comunità
- **Privacy:** i dati vengono salvati localmente, non tracciati globalmente

**Inizia il test! ⬇️**
""")

        radio_widgets = []
        for i in range(0, len(QUESTIONS), 10):
            fine = min(i + 10, len(QUESTIONS))
            with gr.Accordion(f"📋 Domande {i+1}–{fine}", open=(i == 0)):
                for j in range(i, fine):
                    q = QUESTIONS[j]
                    r = gr.Radio(choices=q["options"], label=f"{j+1}. {q['question']}")
                    radio_widgets.append(r)

        with gr.Row():
            submit_btn = gr.Button("⚡ Calcola il mio Profilo", variant="primary", size="lg")
            clear_btn  = gr.Button("🔄 Ricomincia da Capo",     variant="secondary", size="lg")

        gr.Markdown("---")
        user_profile_state = gr.State(None)

        with gr.Row():
            with gr.Column(scale=1):
                report_out = gr.Markdown("### ⏳ In attesa dei risultati...")
            with gr.Column(scale=2):
                with gr.Tabs():
                    with gr.TabItem("🗺️ Mappa Globale"):
                        map_filter = gr.Radio(
                            choices=["Tutti", "Solo Partiti", "Solo Ideologie", "Solo Storici"],
                            value="Tutti", label="🔍 Filtra:", interactive=True
                        )
                        pca_out = gr.Image(label="Posizionamento", type="pil")
                        with gr.Accordion("📖 Come leggere la Mappa?", open=False):
                            gr.Markdown("""
### 🗺️ Guida alla Mappa PCA

**Asse Orizzontale (PC1)**: Progressismo ← → Conservatorismo
**Asse Verticale (PC2)**: Libertà ← → Autoritarismo

La **stella gialla (⭐)** sei TU.
- Vicino = Affinità alta
- Lontano = Disaccordo profondo
""")
                    with gr.TabItem("📊 Analisi Valoriale"):
                        with gr.Row():
                            radar_out = gr.Image(label="Impronta Ideologica", type="pil")
                            bar_out   = gr.Image(label="Punteggi Assoluti",   type="pil")
                    with gr.TabItem("📲 Card Social"):
                        gr.Markdown("### 🔥 Scarica e condividi nelle Storie")
                        social_out = gr.Image(label="Il Tuo Patentino", type="pil", show_download_button=True)
                    with gr.TabItem("⬇️ Esporta"):
                        gr.Markdown("### Scarica il tuo referto completo")
                        pdf_download = gr.File(label="📄 PDF Report")
                        csv_download = gr.File(label="📊 CSV Dettagli")

        submit_btn.click(
            fn=calculate_all,
            inputs=radio_widgets,
            outputs=[report_out, bar_out, radar_out, pca_out, social_out,
                     user_profile_state, pdf_download, csv_download],
        )
        map_filter.change(
            fn=update_map_only,
            inputs=[map_filter, user_profile_state],
            outputs=[pca_out],
        )
        clear_btn.click(
            fn=reset_all,
            outputs=radio_widgets + [report_out, bar_out, radar_out, pca_out, social_out,
                                     user_profile_state, map_filter, pdf_download, csv_download],
        )
    return app

# ============================================================
# AVVIO
# ============================================================
if __name__ == "__main__":
    app = build_app()
    app.launch(share=True, debug=False)