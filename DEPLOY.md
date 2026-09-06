# Deploying to Vercel

The repo is already configured: `api/index.py` (WSGI entrypoint), `vercel.json`
(routing + function limits) and `.vercelignore`.

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
per-instance and wiped between cold starts. `api/index.py` sets `DATA_DIR=/tmp`
for this reason. Audio is returned inline as a data URI so playback does not
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
```
