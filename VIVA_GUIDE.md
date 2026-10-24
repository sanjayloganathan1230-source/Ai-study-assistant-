# Viva Guide: AI Study Assistant

Use this to explain the project in simple words and answer examiner questions.

---

## 1. The 30-second explanation

> "My project lets a student upload PDF notes and study from them with AI. The app finds the parts of the notes
> that match a question and gives *only those parts* to an AI model, so the answer comes from the student's own
> notes with page numbers shown. If the notes don't contain the answer, the app says so instead of guessing.
> It can also make summaries, quizzes and flashcards, and it saves study history in a database."

The technique is called **RAG: Retrieval-Augmented Generation**.

---

## 2. The five steps (draw this on the board)

```
PDF → [1 Extract] → [2 Chunk] → [3 Embed] → [4 Search] → [5 Generate]
       PyMuPDF      chunker.py   retrieval.py  retrieval.py   ai_service.py
```

| Step | What happens | Simple analogy |
|---|---|---|
| 1. Extract | PyMuPDF reads the text of each page | Typing out a book page by page |
| 2. Chunk | Text is cut into small pieces, each remembering its page | Cutting notes into index cards |
| 3. Embed | Each chunk becomes a list of numbers (a vector) | Giving each card a "fingerprint" of its words |
| 4. Search | The question gets a fingerprint; closest cards win (cosine similarity) | Finding the cards that look most like your question |
| 5. Generate | The AI reads only those cards and answers | Asking a tutor who may only look at those cards |

---

## 3. What each file does

| File | One-line role |
|---|---|
| `config.py` | All settings in one place; reads the API key from the environment |
| `pdf_processor.py` | Checks the upload, reads text, detects scanned/empty pages |
| `chunker.py` | Splits text into overlapping chunks that keep their page number |
| `retrieval.py` | Turns text into vectors and finds the best matches |
| `validators.py` | Checks the AI's quiz/flashcard output before trusting it |
| `ai_service.py` | Talks to Claude; builds prompts; turns API failures into friendly messages |
| `database.py` | SQLite: document records and study history |
| `document_loader.py` | Runs the whole upload pipeline |
| `ui/pages.py` | The six screens |
| `app.py` | Starts everything |

**Why separate files?** Each file has one job, so it is easy to test, fix, and explain. The UI is thin;
the real logic is in modules that run and are tested without Streamlit.

---

## 4. Key terms in plain English

- **LLM (Large Language Model):** an AI that writes text (here: Claude).
- **Embedding / vector:** a text turned into numbers so a computer can compare meanings or word use.
- **TF-IDF:** gives each word a weight. A word that is frequent in one chunk but rare overall counts more.
- **Cosine similarity:** measures the angle between two vectors. Small angle means similar text. Result is 0 to 1.
- **Chunk overlap:** neighbouring chunks share a sentence or two so ideas at the edges aren't lost.
- **Hallucination:** when an AI confidently states something untrue. We reduce it by restricting the AI to retrieved text.
- **Prompt injection:** hidden instructions inside a document. We tell the AI that notes are data, not commands.
- **Rate limit:** the API allows only so many requests per minute. We retry and then show a friendly message.
- **Session state:** Streamlit re-runs the script on every click; session state is the memory that survives.
- **Dependency injection:** `StudyAI` accepts any client with a `complete()` method, so tests use a fake one.

---

## 5. Likely questions and good answers

**Q: Why not just give the whole PDF to the AI?**
A: Long documents don't fit, cost more, and the AI can lose focus. Retrieval sends only the relevant passages,
which is cheaper, faster, and lets us show the exact pages used as evidence.

**Q: How do you stop the AI from making things up?**
A: Three layers. (1) If search finds nothing relevant, the AI isn't called and the app says "not found".
(2) The prompt says to use only the excerpts and reply `NOT_IN_NOTES` otherwise. (3) We show the source
excerpts so the student can verify. This reduces hallucination, but cannot guarantee it is zero.

**Q: Which embeddings did you use, and why not neural ones?**
A: TF-IDF, running locally. It needs no extra API or large download, works offline, and is easy to explain and test.
The weakness is that it matches words, not meaning ("car" vs "automobile"). The code includes an optional
sentence-transformers embedder as an upgrade path.

**Q: How is the quiz made reliable?**
A: The AI must return JSON. `validators.py` accepts a question only if it has exactly 4 different options,
a correct answer matching one of them, and an explanation. Options are shuffled. If the reply is bad we retry once,
then show an error. We never show an unchecked quiz.

**Q: What happens with a scanned PDF?**
A: A scanned PDF is images with no text layer, so extraction returns almost nothing. The app detects this and says
so. Supporting it would need OCR, which is listed as future work.

**Q: What do you store, and is it safe?**
A: The PDF and its text stay in memory only. SQLite stores metadata (name, pages, counts, hash) and short
history entries. The API key is in `.env`, which is git-ignored and never shown. Note excerpts are sent to the
Anthropic API when AI features are used, and the app says this on screen.

**Q: How do you handle API failures?**
A: `AnthropicClient` converts each failure (bad key, rate limit, timeout, no internet) into a clear message and
never shows raw errors or keys. The SDK retries automatically. With no key, AI buttons are disabled and chat shows
search results only. We never pretend an AI feature worked.

**Q: How did you test it?**
A: About 150 automated tests. For AI code, a fake model returns scripted replies, so tests are free and repeatable.
I also broke the code on purpose to confirm the tests catch the mistake.

**Q: What are the limitations?**
A: No OCR, keyword-based search, one document at a time, long documents are partly sampled, tables/images
aren't read, and the AI can still be wrong. All are listed in the README.

**Q: What would you improve next?**
A: OCR for scanned files, neural embeddings, multiple documents, user accounts, saving quiz questions for review,
and spaced-repetition for flashcards.

---

## 6. Live demo script (5 minutes)

1. Open the app → point out the sidebar and AI status chip.
2. **Documents:** click *Try sample notes* → show pages, chunks, status. Open "How is my data stored?".
3. **Ask Questions:** ask *"What is overfitting?"* → show answer, open **Sources** (page 2).
4. Ask *"What is the best cake recipe?"* → show the "not found in your notes" response.
5. **Summaries:** generate a short, then a detailed summary.
6. **Quiz:** generate 5 questions, answer, submit, show score and explanations.
7. **Flashcards:** generate, reveal, next, shuffle.
8. **History:** show the quiz score and the document record.
9. (Optional) Remove the API key and restart: show the AI buttons disabled with an explanation.

**Prepare:** put your key in `.env` before the viva, run the demo once beforehand, and keep the sample PDF handy.
If the internet fails during the viva, show step 9 and the tests (`python -m pytest -v`) instead.

---

## 7. Be honest about these points

- Most testing used a fake AI. Say you verified the real API behaviour yourself (do this before the viva!).
- TF-IDF is simple keyword matching, which is good enough for a student project but not "deep understanding".
- The AI is helpful but not perfect, which is why sources are always shown.
