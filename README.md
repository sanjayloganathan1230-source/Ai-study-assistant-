# 🎓 AI Study Assistant (PDF Notes)

Upload your PDF study notes, then **ask questions**, get **summaries**, take **quizzes** and practise with
**flashcards**, all based only on your own notes. Built with Python, Streamlit, PyMuPDF, SQLite,
vector search and the Claude API.

> Project for a BCA (Artificial Intelligence & Data Science) course. See `docs/VIVA_GUIDE.md` for presentation notes.

---

## Features

| Feature | What it does |
|---|---|
| 📄 **PDF upload** | Checks the file (type, size, header, password, corruption), extracts text page by page, shows name, pages, chunks and status. Scanned or empty PDFs get a clear message. |
| 💬 **Ask questions** | Finds the most relevant passages first, then asks the AI to answer *only* from them. Shows page numbers and source excerpts. Says "not found in your notes" instead of guessing. |
| 📝 **Summaries** | Short (about 150 words) or detailed section-by-section summaries with page ranges. Downloadable. |
| 🧠 **Quiz** | Multiple-choice questions with 4 options, the correct answer and an explanation. Every question is validated; you get a score and feedback. |
| 🗂️ **Flashcards** | Question/answer cards. Reveal, hide, previous, next, shuffle. |
| 📊 **History** | Questions, summaries, quiz scores and document records stored in SQLite. Records can be removed or cleared. |

---

## Quick start

You need **Python 3.10 or newer**.

```bash
# 1. Create and activate a virtual environment (keeps packages tidy)
python -m venv .venv
.venv\Scripts\activate            # Windows
source .venv/bin/activate         # Mac / Linux

# 2. Install the packages
pip install -r requirements.txt

# 3. Run the tests (no API key needed)
python -m pytest -v

# 4. Add your API key
copy .env.example .env            # Windows   (Mac/Linux: cp .env.example .env)
#    then open .env and set ANTHROPIC_API_KEY=your-real-key

# 5. Start the app
streamlit run app.py
```

**No API key yet?** The app still works for uploading, searching and history. Click **Try sample notes**,
open **Ask Questions**, and you will see the matching passages with page numbers. The AI buttons stay
disabled and the app tells you why. It never fakes an AI result.

---

## How it works (RAG: Retrieval-Augmented Generation)

```
 PDF ──► extract text ──► split into chunks ──► turn chunks into vectors ──► vector store (memory)
        (PyMuPDF)         (keeps page numbers)    (TF-IDF embeddings)

 Question ──► vector ──► find most similar chunks ──► send ONLY those chunks to Claude ──► answer + sources
                          (cosine similarity)          "answer only from this text, or say NOT_IN_NOTES"
```

1. **Extract**: PyMuPDF reads each page. Pages with almost no text are skipped and reported.
2. **Chunk**: text is split on sentence boundaries into pieces of at most 900 characters, with a small overlap.
   Each chunk belongs to exactly one page, so page citations are exact.
3. **Embed**: each chunk becomes a vector of numbers. The default is **TF-IDF** (local, offline, no key).
4. **Search**: the question becomes a vector too. **Cosine similarity** ranks the chunks. Weak matches are dropped.
5. **Answer**: the best chunks go to the AI with strict rules. If nothing matches, the AI isn't even called.

---

## Project structure

```
ai_study_assistant/
├── app.py                    # entry point: page setup, sidebar, page routing
├── requirements.txt          # packages to install
├── .env.example              # template for your settings (copy to .env)
├── .gitignore                # keeps .env and the database out of git
├── pytest.ini
├── .streamlit/config.toml    # colour theme
├── sample_data/              # sample notes (txt + pdf) and a scan-like pdf for testing
├── scripts/make_sample_pdfs.py   # optional: rebuilds the sample PDFs (needs reportlab)
├── docs/VIVA_GUIDE.md        # presentation notes and likely questions
├── src/
│   ├── config.py             # all settings; reads the API key from the environment
│   ├── database.py           # SQLite: document metadata + study history
│   ├── pdf_processor.py      # validation, PyMuPDF extraction, scanned-PDF detection
│   ├── chunker.py            # splits page text into chunks
│   ├── retrieval.py          # embeddings, vector store, similarity search
│   ├── validators.py         # checks quiz/flashcard JSON from the AI
│   ├── ai_service.py         # Claude API client, prompts, error handling
│   ├── document_loader.py    # PDF -> chunks -> index -> database (the pipeline)
│   └── ui/
│       ├── styles.py         # CSS theme
│       ├── state.py          # session memory
│       ├── components.py     # reusable UI pieces
│       ├── formatting.py     # table/text helpers
│       └── pages.py          # the six pages
└── tests/                    # extraction, chunking, retrieval, validation, database, AI, UI
```

---

## Where your data goes

| Data | Where it lives | Saved to disk? |
|---|---|---|
| Your PDF file | Memory, during the session | **No** |
| Extracted text and search index | Memory, during the session | **No** |
| Document record: file name, page count, chunk count, character count, file hash, upload time | SQLite `data/study_assistant.db` | Yes (no text) |
| Study history: question (up to 200 characters), a short preview of the result (up to 1000), quiz scores | SQLite `data/study_assistant.db` | Yes |
| API key | `.env` file or environment variable | Only in your `.env` |
| Note excerpts used for an AI request | Sent to the Anthropic API | See Anthropic's data policy |

You can delete a document record or clear all history on the **History** page, or delete the `data/` folder.
Clearing the history does not delete the PDF, because the PDF was never saved.

## Security notes

- The API key is read from the environment, never hard-coded, never shown in the app, never stored in the database.
  `.env` is listed in `.gitignore`. Check with `git status` that `.env` is not staged before pushing.
- Error messages from the API are replaced with friendly text, so keys and raw responses are never displayed.
- Uploads are validated: `.pdf` extension, `%PDF-` header, size limit (default 25 MB), page limit (default 500),
  password-protected and corrupted files are rejected.
- Text from PDFs is HTML-escaped before display, and the prompts tell the AI to treat notes as data,
  not instructions (this reduces, but cannot completely remove, prompt-injection risk).
- Rate limits, timeouts, and connection errors are handled: the SDK retries automatically,
  then you see a clear message.

---

## Settings (optional, in `.env`)

| Setting | Default | Meaning |
|---|---|---|
| `ANTHROPIC_API_KEY` | none | Your API key |
| `LLM_MODEL` | `claude-sonnet-5-5` | Which Claude model to use |
| `MAX_UPLOAD_MB` | 25 | Largest PDF accepted |
| `MAX_PAGES` | 500 | Most pages accepted |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | 900 / 150 | Chunk size and overlap, in characters |
| `TOP_K` | 4 | Passages retrieved per question |
| `LLM_MAX_TOKENS` | 2000 | Longest AI reply for answers and detailed summaries |
| `STUDY_DB_PATH` | `data/study_assistant.db` | Where the database is stored |

---

## Testing

```bash
python -m pytest -v
```

| Test file | Covers |
|---|---|
| `test_pdf_processor.py` | Upload validation, text cleaning, scanned/partly-empty PDFs, real PDF extraction |
| `test_chunker.py` | Chunk size, overlap, page numbers, edge cases (huge words, empty text) |
| `test_retrieval.py` | Right page found for each topic, unrelated questions return nothing, scores, empty store |
| `test_validators.py` | Quiz validation (4 options, valid answer, explanation), flashcards, scoring |
| `test_ai_service.py` | Prompts, "not in notes" path, retries, API errors, missing key, no key leaks (uses a **fake** AI) |
| `test_database.py` | Metadata, history, stats, no PDF text stored |
| `test_document_loader.py` | Whole upload pipeline and display helpers |
| `test_ui_smoke.py` | Opens the real dashboard with Streamlit's test runner (skipped if Streamlit is missing) |

The tests **never call the real API**. A fake model stands in for it, so tests are free, fast and repeatable.
A test that needs PyMuPDF or Streamlit is skipped (not silently passed) if that package is missing.

---

## Known limitations

- **Real-service testing:** The automated tests use a fake AI and a stand-in for the API library. Do one real
  question, summary, quiz and flashcard run with your own key, and report any difference.
- **No OCR:** scanned PDFs (pictures of pages) are rejected with a clear message. Run OCR first (for example
  with `ocrmypdf`) and upload the result.
- **Keyword-based search:** the default TF-IDF matches on shared words, not meaning, so a question that
  uses completely different words than the notes may find nothing. `SentenceTransformerEmbedder` in
  `src/retrieval.py` gives meaning-based search, but it needs `pip install sentence-transformers` and a model download,
  and it is not part of the tested default.
- **One document at a time**, kept in memory. After a restart, upload the file again (only its record is saved).
- **Long documents:** quizzes, flashcards and short summaries use up to about 12,000 characters spread across
  the document, and a detailed summary covers at most 6 sections. The app shows a warning when only part was used.
- **Tables, images, equations and diagrams** in PDFs are not understood, only the text layer is read.
- **AI can still be wrong.** The prompts forbid guessing and sources are shown so you can check, but always verify
  important facts in your notes.
- **Single-user design:** there are no accounts. If you host it publicly, everyone shares one database.
- **Notes leave your computer** (as excerpts) when you use AI features. Don't upload confidential documents.
- **Layout and styling** were written without seeing the screen. Small visual tweaks may be needed.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| "No API key found" / AI buttons disabled | Copy `.env.example` to `.env`, set `ANTHROPIC_API_KEY`, restart the app |
| "The API key was rejected" | The key is wrong or expired. Create a new one in the Anthropic console |
| "No readable text was found" | The PDF is scanned. Use OCR first |
| "rate limit reached" | Wait a minute and try again |
| `ModuleNotFoundError` | Activate the virtual environment and run `pip install -r requirements.txt` |
| Tests show "skipped" | The related package isn't installed (see the skip message) |

## License / use

Made for learning and college presentation. Add a license before publishing if you want others to reuse it.
