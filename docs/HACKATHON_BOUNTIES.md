# Hackathon bounties — Hacktoberfest Week 2

Smart Proxy Tagger is a new project for the **Hacktoberfest Open-Source AI Challenge: Week 2** (Side Hustle).

- Challenge page: https://dev.to/challenges/hacktoberfest-week2-2026-10-12
- Status when these notes were written: live
- Submissions close: **October 18, 2026 at 11:59 PM PDT** (October 19, 2026 at 7:59 AM in UTC+1)
- Winners announced: the week of October 19, 2026
- Required post tags: `#devchallenge` and `#hf26challenge`
- The project and its repository must be started inside this challenge window

Judging, from that page, weighs **writing quality** most heavily, then relevance to the prompt and theme, creativity, technical execution, and use of partner technology when a partner category is claimed. One submission can enter the overall prize and every partner category it actually uses. A submission can win once.

The prompt: build something with open-source AI at its core that someone would actually pay for, and explain why the open approach beats a closed one. Open-source AI here means an open-weight model, an open-source agent harness, local inference, or a mix. The open piece has to be what makes the product work.

Per the DevRelay Hacktoberfest guide (verified 2026-09-30 against hacktoberfest.com), 2026 rewards challenge entries and stickers. Pull requests do not count.

## Overall prize — Side Hustle ($250)

**Who pays.** A freelance videographer or a small production company that needs to find a moment inside raw footage.

**What they pay for.** Search that runs on the machine where the cards are copied. They type "handshake at the door" and get a file path and a timestamp.

**Why open weights are the product.** Client footage stays on the laptop. There is no per-minute vision bill that grows with the shoot, and the caption model can be swapped later without waiting on a vendor's API. A closed vision API would upload the frames and price the job by duration. That is the wrong shape for terabytes of unreleased footage.

Bonus the judges asked for, still ahead of us: put the demo in front of one editor and write down whether they would pay and what they asked for next.

## Best Use of Gemma ($200, featured)

**How we qualify.** Frame captions come from **PaliGemma**, Google's open vision-language model in the Gemma family, loaded on this machine through Hugging Face. The model sees pixels and writes the text that search indexes. The product does not function without that local caption step.

**What we will show.** A short clip, the captions PaliGemma produced, and the hardware it ran on. The write-up will name PaliGemma as a Gemma-family open-weight model and say that inference stayed local.

**What we will not claim.** We will not describe a cloud Gemma endpoint as the captioner. A llama.cpp path is documented as a fallback for a vision-capable GGUF, and it is used only if that checkpoint loads.

## Best Use of Temporal ($100)

**How we qualify.** Indexing is a Temporal workflow. Discover, extract, caption-and-store, and notify are activities. The caption activity heartbeats a frame cursor. If the app or the worker stops, the workflow resumes from that cursor instead of starting the card over.

**What we will show.** A workflow id that keeps moving after the UI is closed, and a history that stays small because frames are not one activity each.

## Best Use of Tiger Data ($100)

**How we qualify.** Captions and embeddings live in **TimescaleDB with pgvector** on localhost. TimescaleDB is Tiger Data's Postgres engine. Search runs keyword full-text and vector similarity together, and the gallery shows which signal matched.

**What we will show.** The Docker service bound to `127.0.0.1`, the `vector(384)` column, a `tsvector` column, and a query that uses both.

**What we will not claim.** No Tiger Cloud, no hosted Postgres, no connection string that leaves the machine. The local rule in `.cursorrules` is the constraint. Hybrid fusion is implemented with the measured caveat in `docs/ARCHITECTURE.md`: on some corpora, rank fusion hurts paraphrase queries, so both signals stay visible.

## Best Use of ElevenLabs ($100)

**How we qualify.** When the workflow finishes, one short sentence is synthesized with the ElevenLabs text-to-speech API and played on the laptop. The voice is the notification that a long local job is done. Frames are not sent to ElevenLabs.

**What we will show.** The activity that calls the API, the audio file it writes locally, and the key living only in `.env`.

## Best Use of Entire ($100)

**How we qualify.** DevRelay is installed (`devrelay 0.1.19`) and the MCP gateway is connected in Cursor. The MLH account for this machine is signed in, which is what lets a later step save this agent session to DEV.

**What we will show.** A saved agent session, embedded in the DEV write-up, once you approve the upload. Sessions are unlisted until they are made public. The transcript will be scrubbed of API keys and private machine paths before it is sent.

DevRelay does not record the chat continuously. Saving the session is an explicit step.

## Categories this project is not entering

Render, DigitalOcean, MongoDB Atlas, and any other hosted runtime or hosted database. Those conflict with the localhost footage rule. Other Week 2 partners (TabPFN, Tinker, Arduino, Backboard, GitHub Copilot, Mastra, Sentry, SerpApi, a `.tech` domain) are unused, so they will not be listed in the prize-categories section of the post.

## Submission checklist (for the later DEV post)

- Publish with the challenge template and the tags `#devchallenge` and `#hf26challenge`.
- Say what was built, who would pay, and why the open model matters.
- Include a demo: a clip, a search, and the spoken notification.
- List the partner categories actually used: Gemma, Temporal, Tiger Data, ElevenLabs, Entire.
- Keep the repository new to this window. Commits after the deadline must be noted in the README.
- Disclose AI assistance on the post. An agent-drafted entry uses `some_ai`.
- Credit any borrowed snippet. The design notes in `docs/ARCHITECTURE.md` already cite the DEV posts that shaped the Temporal and pgvector choices.
- English, so the entry stays prize-eligible. Teams of up to four list every DEV handle in the post. This build is currently one person.
