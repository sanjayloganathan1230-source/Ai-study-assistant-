"""Look and feel: one CSS block shared by every page.

Colour theme (indigo + slate):
    primary  #4F46E5   buttons, accents
    ink      #0F172A   main text
    muted    #64748B   secondary text
    surface  #FFFFFF   cards
    tint     #EEF2FF   sidebar / highlights
The base colours also live in .streamlit/config.toml.
"""

import streamlit as st

CSS = """
<style>
:root {
  --primary: #4F46E5; --primary-dark: #4338CA; --ink: #0F172A; --muted: #64748B;
  --surface: #FFFFFF; --tint: #EEF2FF; --line: #E2E8F0;
  --ok: #047857; --ok-bg: #D1FAE5; --warn: #B45309; --warn-bg: #FEF3C7;
  --off: #B91C1C; --off-bg: #FEE2E2;
}
html, body, [class*="css"] { font-family: Inter, "Segoe UI", system-ui, -apple-system, sans-serif; }
#MainMenu, footer { visibility: hidden; }
.block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1100px; }
h1, h2, h3 { letter-spacing: -0.01em; color: var(--ink); }

/* ---- sidebar ---- */
section[data-testid="stSidebar"] { border-right: 1px solid var(--line); }
.brand { display: flex; align-items: center; gap: .6rem; margin: .2rem 0 1rem 0; }
.brand-logo { font-size: 1.6rem; background: var(--primary); color: #fff; width: 2.4rem; height: 2.4rem;
  border-radius: .7rem; display: flex; align-items: center; justify-content: center; }
.brand-name { font-weight: 700; font-size: 1.05rem; color: var(--ink); line-height: 1.1; }
.brand-sub { font-size: .75rem; color: var(--muted); }

/* ---- page header ---- */
.page-header { margin-bottom: 1.2rem; }
.page-header h1 { font-size: 1.9rem; margin: 0; }
.page-header p { color: var(--muted); margin: .25rem 0 0 0; font-size: 1rem; }

/* ---- hero ---- */
.hero { background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%); color: #fff; padding: 1.6rem 1.8rem;
  border-radius: 1rem; margin-bottom: 1.4rem; }
.hero h1 { color: #fff; font-size: 1.9rem; margin: 0 0 .3rem 0; }
.hero p { color: #E0E7FF; margin: 0; font-size: 1.02rem; }

/* ---- cards ---- */
.card { background: var(--surface); border: 1px solid var(--line); border-radius: .9rem; padding: 1rem 1.2rem;
  margin-bottom: .8rem; box-shadow: 0 1px 2px rgba(15,23,42,.04); }
.card-title { font-weight: 650; font-size: 1.05rem; color: var(--ink); margin-bottom: .35rem; word-break: break-word; }
.card-muted { color: var(--muted); font-size: .9rem; }
.empty { text-align: center; padding: 2.2rem 1rem; }
.empty .emoji { font-size: 2.4rem; }
.empty .card-title { font-size: 1.15rem; }

/* ---- chips ---- */
.chip { display: inline-block; padding: .12rem .6rem; border-radius: 999px; font-size: .78rem; font-weight: 600;
  background: var(--tint); color: var(--primary-dark); margin-right: .35rem; }
.chip.ok { background: var(--ok-bg); color: var(--ok); }
.chip.warn { background: var(--warn-bg); color: var(--warn); }
.chip.off { background: var(--off-bg); color: var(--off); }

/* ---- source excerpts ---- */
.source { border-left: 3px solid var(--primary); background: #F8FAFF; padding: .6rem .9rem; border-radius: 0 .6rem .6rem 0;
  margin-bottom: .6rem; }
.source-head { font-size: .8rem; font-weight: 650; color: var(--primary-dark); margin-bottom: .2rem; }
.source-text { font-size: .9rem; color: #334155; white-space: pre-wrap; }

/* ---- flashcards ---- */
.flashcard { min-height: 14rem; display: flex; flex-direction: column; justify-content: center; align-items: center;
  text-align: center; padding: 2rem 1.6rem; border-radius: 1.1rem; margin: .4rem 0 1rem 0;
  border: 1px solid var(--line); box-shadow: 0 6px 18px rgba(79,70,229,.10); }
.flashcard.front { background: #fff; }
.flashcard.back { background: linear-gradient(135deg, #EEF2FF, #F5F3FF); border-color: #C7D2FE; }
.fc-label { font-size: .75rem; letter-spacing: .08em; text-transform: uppercase; font-weight: 700; color: var(--primary); }
.fc-text { font-size: 1.45rem; font-weight: 600; color: var(--ink); margin: .7rem 0; line-height: 1.4; }
.fc-page { font-size: .8rem; color: var(--muted); }

/* ---- quiz result rows ---- */
.result { border-radius: .8rem; padding: .8rem 1rem; margin-bottom: .7rem; border: 1px solid var(--line); background: #fff; }
.result.good { border-left: 5px solid #10B981; }
.result.bad { border-left: 5px solid #EF4444; }
.result.skip { border-left: 5px solid #94A3B8; }

/* ---- buttons ---- */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button { border-radius: .6rem; font-weight: 600; }
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
