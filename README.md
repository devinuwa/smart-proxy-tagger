# Smart Proxy Tagger

Find a moment in raw footage without uploading the card.

A freelance editor or a small production company copies a shoot onto a laptop, then spends the afternoon hunting for one handshake, one sunset, one line of dialogue. Smart Proxy Tagger indexes that footage on the same machine and returns the file path and the timestamp. Client media stays local. The only outbound media call is a single spoken sentence when the index is finished, and that sentence never includes a frame or a file path.

## How to use it

Open [http://127.0.0.1:5173](http://127.0.0.1:5173) after the stack is running.

1. **Paste a full path.** Put the path of a video or a folder into **Full path on this computer**. **Choose file** and **Choose folder** only share the file name, so an empty path is rejected until the full path is pasted. Example: `C:\Footage\interview.mp4`.
2. **Click Index footage.** The dashboard shows a workflow id, frames seen, and status. You can close the tab. The job keeps running. Reopen the page and it resumes watching the same job. When the index finishes, status is **complete** and **Voice** says **Played**. If an ElevenLabs key is set, the laptop speaks: “Your footage is indexed.”
3. **Search.** Type a few words and click **Search**. Each hit is a timestamp inside a file already on this computer, with the caption and whether keyword search, vector search, or both found it.

That is the whole loop: path, index, search.

## Why this is the product

| What the editor needs | What this does |
| --- | --- |
| Client footage must not leave the laptop | Frames, captions, and embeddings stay on this machine. The database host must be loopback. |
| “Where was that shot?” | Search returns a path and a timestamp, not a vague clip title. |
| A long card should survive a closed laptop lid | Temporal keeps the job and resumes from the last frame cursor. |
| A finished index should be obvious | ElevenLabs speaks one sentence when the moments are ready to search. |
| The bill should not grow with the length of the shoot | There is no per-minute cloud vision API. |

## What you are searching today

The demo samples one moment about every **5 seconds**, up to **24** moments per file. That interval is set next to `FRAME_SAMPLE_INTERVAL_SECONDS` in `frames.py`. If ffmpeg is not installed, the indexer still records three timestamps (0s, 5s, and 10s) and does not pretend those rows came from decoded pictures.

Captions in this build are a local stand-in: the file name and the timestamp (`phase2-stand-in`). Search matches those words. The architecture is ready for a local PaliGemma captioner to replace that text. The design is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). This README does not describe the sample clip as a multi-terabyte run.

## Run it

You need Docker, Python 3.11, and Node.js. On this project’s machine, Python 3.13 has no `venv` module, so the steps use 3.11. TimescaleDB is published on `127.0.0.1:15432` because 5432 and 5433 were already in use.

From the repository root, start the database and Temporal:

```text
docker compose up -d
```

Python worker and API:

```text
py -3.11 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
.venv\Scripts\python -m backend.worker
.venv\Scripts\python -m uvicorn backend.server:app --host 127.0.0.1 --port 8000
```

Leave the worker and the API running. In a third terminal:

```text
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Put `ELEVENLABS_API_KEY` in `.env` when you want the spoken notification. `.env.example` lists the name and nothing else. Never commit `.env`. Without a key, the index still finishes and the dashboard records a clear voice error. The example voice is George, a premade voice a free key can call. Some older public voice ids are treated as library voices and return HTTP 402 on a free plan.

| Surface | Address |
| --- | --- |
| App | http://127.0.0.1:5173 |
| API | http://127.0.0.1:8000 |
| Temporal UI | http://127.0.0.1:8233 |

A useful first path, after you add any short video of your own, is the one you paste into the path box. Index it, wait for **complete**, then search a word from the caption.

## What stays on the laptop

| Piece | Where |
| --- | --- |
| React UI | This machine, port 5173 |
| FastAPI | This machine, port 8000. It starts workflows. It does not caption frames. |
| Temporal worker | This machine, port 7233. One caption activity heartbeats a frame cursor. |
| TimescaleDB and pgvector | Docker on `127.0.0.1:15432` |
| ElevenLabs | One completion sentence. Never a frame. |

Search mixes keyword full-text with vector similarity and shows which signal matched. A vector neighbor with cosine distance of 0.85 or more is dropped, so a query with no overlap does not list every stored moment.

## Read next

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — the design the code follows
- [docs/HACKATHON_BOUNTIES.md](docs/HACKATHON_BOUNTIES.md) — Hacktoberfest Week 2, Side Hustle, and the partner tracks this project is built for
