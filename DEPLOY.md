# Deploying to Vercel

The repo is already configured: `vercel.json` (function limits) and
`.vercelignore`. Vercel serves `app.py` at the repo root directly as the
function - there is no wrapper and no rewrite. Do not add a
`"/(.*)" -> "/api/index"` rewrite: Flask then receives `/api/index` as the path
for every request and returns its own 404 for every page.

## 1. Get a fresh API key

Do **not** reuse the key in your local `.env` if it has ever been shared.
Generate one at <https://build.nvidia.com> → avatar → **API Keys** → *Generate
API Key*. Copy the `nvapi-...` value; it is shown only once.

## 2. Deploy

```bash
npm i -g vercel        # if you don't have it
vercel login
vercel link            # create/link the project (run in the repo root)
```

Add the key to all three environments:

```bash
vercel env add NVIDIA_API_KEY production
vercel env add NVIDIA_API_KEY preview
vercel env add NVIDIA_API_KEY development
```

Add a Flask session secret too (any long random string):

```bash
vercel env add SECRET_KEY production
```

Then ship it:

```bash
vercel            # preview deployment, gives you a URL to check
vercel --prod     # promote to production
```

## 3. Verify

```bash
curl https://<your-app>.vercel.app/api/model-info
```

Expect `{"provider": "NVIDIA NIM", ...}`. Then open the site and try each of the
four features once — the first request after a deploy pays a cold start.

## Things that will bite you

**Generated files are temporary.** On Vercel only `/tmp` is writable, and it is
per-instance and wiped between cold starts. `app.py` detects this (via the
`VERCEL` environment variable) and writes under `/tmp`; creating directories in
the read-only working directory otherwise crashes the function at import with
`OSError: [Errno 30] Read-only file system`. Audio is returned inline as a data URI so playback does not
depend on a later request landing on the same instance, but the
`/api/download-code/<file>` and `/api/download-audio/<file>` links only work
while that instance is warm. If you want durable downloads, put the files in
object storage (Vercel Blob or S3) instead.

**Requests are slow.** Text and code take 15-40s, images 20-60s, audio 30-60s.
`vercel.json` sets `maxDuration: 300`, which every plan now allows. Do not lower
it.

**Response size.** The audio endpoint returns the MP3 inline. The TTS script is
trimmed to 3500 characters (at a sentence boundary) to keep that response a few
MB. If you raise `MAX_TTS_CHARS` in `utils/audio_utils.py`, you risk exceeding
the function response limit.

**Rate limits.** The NVIDIA free tier allows roughly 40 requests/minute across
all models. A handful of simultaneous users is fine; a classroom is not. The
image path already retries on 429 and 5xx.

**Static files** are served by Flask through the function rather than the CDN.
Fine at this size; move `static/` to a separate route if it ever matters.

**The Run button costs the server nothing.** Generated code executes in the
learner's browser via Pyodide (CPython compiled to WebAssembly) inside
`static/js/pyworker.js`, never on the function. It downloads about 15 MB from
`cdn.jsdelivr.net` on first use and caches it; if the CDN is unreachable, every
page still loads and generates normally and only Run reports an error.

Two things about that worker are deliberate and easy to break:

- It is a **module worker** loading `pyodide.mjs` with a dynamic `import()`,
  not the classic build with `importScripts`. Cross-origin `importScripts` is
  blocked in some environments (it failed outright in the browser used for
  testing while `fetch` and `import()` both worked), and the ESM build then
  loads its own sub-assets the same way. Keep
  `new Worker(url, { type: 'module' })` in `static/js/code_generation.js`.
- **No SRI hash on Pyodide.** Every other CDN asset in `base.html` carries
  `integrity` + `crossorigin`, but Subresource Integrity does not apply to a
  worker's own imports, and Pyodide fetches `pyodide.asm.wasm`, the stdlib zip
  and each package at runtime - those cannot be hashed ahead of time either.
  The version is pinned in `PYODIDE_BASE` instead; bump it deliberately.

## Running locally

```bash
pip install -r requirements.txt
cp .env.example .env      # then put your nvapi-... key in it
python app.py             # http://127.0.0.1:5000
```

Run the checks:

```bash
python -m utils.test_code_extraction
python -m utils.test_code_smells
python -m utils.test_prompt_enhance
python -m utils.test_code_sections
python -m utils.test_quiz
```
