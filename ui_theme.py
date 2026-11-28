"""Visual theme: dark ink + gold, serif headings. Injects CSS and small HTML blocks."""
import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');
:root{--ink:#0B0F19;--panel:#121826;--panel2:#171F31;--line:rgba(212,175,55,.30);--gold:#D4AF37;--gold2:#F1D77A;--ivory:#F5F1E8;--muted:#9AA3B5;}
html, body, .stApp, .stMarkdown, .stMarkdown p, .stMarkdown li, label, input, textarea, button, [data-baseweb="select"]{font-family:'Inter',system-ui,-apple-system,'Segoe UI',sans-serif;}
.stApp{background:radial-gradient(1100px 560px at 88% -8%, rgba(212,175,55,.11), transparent 60%),radial-gradient(900px 520px at -8% 8%, rgba(80,110,200,.13), transparent 55%),var(--ink);color:var(--ivory);}
.block-container{max-width:1120px;padding-top:2rem;padding-bottom:3rem;}
h1,h2,h3,h4{font-family:'Playfair Display',Georgia,serif !important;color:var(--ivory);letter-spacing:.2px;}
h2,h3{color:var(--gold2);}
a{color:var(--gold2) !important;}
hr{border-color:var(--line);}
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"]{visibility:hidden;display:none;}
[data-testid="stHeader"]{background:transparent;}

/* ---------- hero ---------- */
.hero{text-align:center;padding:2.6rem 1rem 1.6rem;}
.eyebrow{font-size:.74rem;letter-spacing:.28em;color:var(--gold);font-weight:600;margin:.4rem 0 .6rem;}
.eyebrow.center{text-align:center;margin-top:1.6rem;}
.hero-title{font-family:'Playfair Display',Georgia,serif;font-size:3.6rem;line-height:1.1;font-weight:600;color:var(--ivory);margin:.2rem 0 .9rem;}
.hero-title .gold{background:linear-gradient(135deg,#F1D77A,#D4AF37 55%,#B8901F);-webkit-background-clip:text;background-clip:text;color:transparent;}
.hero-sub{max-width:680px;margin:0 auto 1.2rem;color:var(--muted);font-size:1.05rem;line-height:1.6;}
.chips{display:flex;gap:.6rem;justify-content:center;flex-wrap:wrap;margin-top:.8rem;}
.chips span{border:1px solid var(--line);background:rgba(212,175,55,.06);color:var(--gold2);padding:.38rem .9rem;border-radius:999px;font-size:.82rem;}
.gold-rule{height:1px;background:linear-gradient(90deg,transparent,var(--gold),transparent);margin:1.4rem 0;border:0;}

/* ---------- top bar & sidebar brand ---------- */
.topbar{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line);padding:.2rem 0 .9rem;margin-bottom:1.1rem;}
.topbar .name{font-family:'Playfair Display',Georgia,serif;font-size:1.45rem;color:var(--ivory);}
.topbar .name b{color:var(--gold);font-weight:600;}
.topbar .mode{border:1px solid var(--line);color:var(--gold2);padding:.3rem .85rem;border-radius:999px;font-size:.8rem;background:rgba(212,175,55,.06);}
.brand{font-family:'Playfair Display',Georgia,serif;font-size:1.35rem;color:var(--ivory);}
.brand-sub{letter-spacing:.3em;font-size:.68rem;color:var(--gold);margin-bottom:1rem;}
.side-note{font-size:.8rem;color:var(--muted);line-height:1.5;border-top:1px solid var(--line);margin-top:1rem;padding-top:.8rem;}
.legal-foot{text-align:center;color:var(--muted);font-size:.78rem;margin-top:2.5rem;padding-top:1rem;border-top:1px solid var(--line);}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#0E1424,#0B0F19);border-right:1px solid var(--line);}

/* ---------- cards (containers whose key starts with "card") ---------- */
[class*="st-key-card"]{background:linear-gradient(180deg,var(--panel),var(--panel2));border:1px solid var(--line) !important;border-radius:18px !important;padding:1.2rem 1.4rem;box-shadow:0 10px 30px rgba(0,0,0,.35);}
[class*="st-key-card_aud"]{transition:box-shadow .25s ease,transform .25s ease;}
[class*="st-key-card_aud"]:hover{box-shadow:0 0 0 1px var(--gold),0 18px 44px rgba(0,0,0,.55);transform:translateY(-2px);}
[class*="st-key-card_aud"] button{width:100%;}

/* ---------- forms, inputs ---------- */
[data-testid="stForm"]{background:linear-gradient(180deg,var(--panel),var(--panel2));border:1px solid var(--line);border-radius:18px;padding:1.4rem 1.5rem;box-shadow:0 10px 30px rgba(0,0,0,.3);}
[data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] > div{background:#0F1524 !important;border:1px solid rgba(255,255,255,.09) !important;border-radius:10px !important;}
[data-baseweb="input"]:focus-within, [data-baseweb="textarea"]:focus-within, [data-baseweb="select"] > div:focus-within{border-color:var(--gold) !important;box-shadow:0 0 0 1px var(--gold);}
label, [data-testid="stWidgetLabel"] p{color:#D9D4C7 !important;font-weight:500;}

/* ---------- buttons ---------- */
button[data-testid="stBaseButton-primary"], button[data-testid="stBaseButton-primaryFormSubmit"], .stButton button[kind="primary"], .stFormSubmitButton button[kind="primaryFormSubmit"]{background:linear-gradient(135deg,#F1D77A,#D4AF37 55%,#B8901F) !important;color:#1B1405 !important;border:0 !important;font-weight:600;border-radius:12px;padding:.55rem 1.3rem;box-shadow:0 6px 18px rgba(212,175,55,.25);}
button[data-testid="stBaseButton-primary"]:hover, button[data-testid="stBaseButton-primaryFormSubmit"]:hover{filter:brightness(1.07);box-shadow:0 8px 24px rgba(212,175,55,.38);}
button[data-testid="stBaseButton-secondary"], button[data-testid="stBaseButton-secondaryFormSubmit"], .stDownloadButton button{background:rgba(255,255,255,.03) !important;color:var(--ivory) !important;border:1px solid var(--line) !important;border-radius:12px;}
button[data-testid="stBaseButton-secondary"]:hover, .stDownloadButton button:hover{border-color:var(--gold) !important;color:var(--gold2) !important;}

/* ---------- service menu (radio shown as pills) ---------- */
[data-testid="stRadio"] [role="radiogroup"]{gap:.55rem;flex-wrap:wrap;}
[data-testid="stRadio"] label[data-baseweb="radio"]{background:rgba(255,255,255,.03);border:1px solid var(--line);border-radius:999px;padding:.45rem 1.05rem;margin:0;cursor:pointer;transition:all .2s ease;}
[data-testid="stRadio"] label[data-baseweb="radio"] > div:first-child{display:none;}
[data-testid="stRadio"] label[data-baseweb="radio"]:hover{border-color:var(--gold);}
[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked){background:linear-gradient(135deg,#F1D77A,#D4AF37 55%,#B8901F);border-color:transparent;}
[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) *{color:#1B1405 !important;font-weight:600;}

/* ---------- tabs, expanders, metrics, alerts, quotes ---------- */
.stTabs [data-baseweb="tab-list"]{gap:.4rem;border-bottom:1px solid var(--line);}
.stTabs [data-baseweb="tab"]{color:var(--muted);}
.stTabs [aria-selected="true"]{color:var(--gold2) !important;}
.stTabs [data-baseweb="tab-highlight"]{background:var(--gold);}
[data-testid="stExpander"]{border:1px solid rgba(255,255,255,.09);border-radius:14px;background:rgba(255,255,255,.02);}
[data-testid="stMetric"]{background:var(--panel2);border:1px solid var(--line);border-radius:14px;padding:.8rem 1rem;}
[data-testid="stMetricValue"]{color:var(--gold2);font-family:'Playfair Display',Georgia,serif;}
[data-testid="stAlert"]{border-radius:12px;border:1px solid rgba(255,255,255,.08);}
blockquote{border-left:3px solid var(--gold) !important;background:rgba(212,175,55,.06);padding:.6rem 1rem !important;border-radius:0 10px 10px 0;color:#E8E2D2;}
[data-testid="stFileUploader"] section{background:#0F1524;border:1px dashed var(--line);border-radius:12px;}
[data-testid="stStatusWidget"], [data-testid="stStatus"]{border:1px solid var(--line);border-radius:14px;}

@media (max-width:640px){.hero-title{font-size:2.5rem;}.topbar{flex-direction:column;align-items:flex-start;gap:.5rem;}}
</style>
"""


def apply_theme() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def hero() -> None:
    st.markdown(
        '<div class="hero"><div class="eyebrow">YOUR AI LEGAL COMPANION &nbsp;·&nbsp; INDIA</div>'
        '<div class="hero-title">Legal<span class="gold">Saathi</span></div>'
        '<div class="hero-sub"><b>Legal research you can verify.</b> Memos, document review, case search and drafting for Indian law, '
        'with every cited case checked against a real legal source.</div>'
        '<div class="chips"><span>✓ Source-linked answers</span><span>✓ Citations checked by code</span>'
        '<span>✓ Ready for lawyer review</span></div></div>',
        unsafe_allow_html=True,
    )


def topbar(mode_label: str) -> None:
    st.markdown(
        f'<div class="topbar"><div class="name">⚖️ Legal<b>Saathi</b></div>'
        f'<div class="mode">{mode_label}</div></div>',
        unsafe_allow_html=True,
    )


def footer_note() -> None:
    st.markdown(
        '<div class="legal-foot">AI-assisted output from public sources. Not legal advice. '
        'Review by a qualified Indian lawyer is required before any decision, signing or filing.</div>',
        unsafe_allow_html=True,
    )
