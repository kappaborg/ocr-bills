# ExTaSy — Free-tier deploy (Koyeb + Supabase + Vercel)

No credit card required for any of the three services. Total time ≈ 45 min if accounts don't exist yet, ≈ 15 min if they do.

| Step | Service | Time |
|---|---|---|
| 1 | Supabase (Postgres) | 5 min |
| 2 | Koyeb (Backend) | 10 min |
| 3 | Vercel (Frontend) | 10 min |
| 4 | Gemini key (optional, OCR upgrade) | 5 min |
| 5 | Smoke test | 5 min |

---

## 1 — Supabase Postgres

1. Open https://supabase.com → **Sign up with GitHub**
2. **New project**
   - Name: `extasy-prod`
   - Database password: **generate one + save it somewhere safe** (you'll never see it again)
   - Region: pick `Central EU (Frankfurt)` to match Koyeb
   - Pricing plan: Free
3. Wait ~2 min for the project to provision
4. Project settings → **Database** → **Connection string** → **URI** mode → copy it. Looks like:
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.xxxxxxxxxxxx.supabase.co:5432/postgres
   ```
   Replace `[YOUR-PASSWORD]` with the password from step 2.

Paste it somewhere — you'll need it in step 2.

---

## 2 — Koyeb backend

1. Open https://koyeb.com → **Sign up with GitHub** (free tier is automatic, no card)
2. **Create Service** → **GitHub** → select `kappaborg/ocr-bills`
3. Configure:
   - **Branch**: `main`
   - **Builder**: `Dockerfile`
   - **Work directory**: `backend`
   - **Dockerfile location**: `backend/Dockerfile`
   - **Service name**: `extasy-backend`
   - **Region**: `Frankfurt (fra)`
   - **Instance type**: `Nano (Free)`
   - **Exposed port**: `8000`
   - **Health check**: `HTTP` on path `/health`

4. **Environment variables** — paste each line in the Koyeb UI:

   ```
   ENVIRONMENT=production
   DATABASE_URL=<paste-the-supabase-URI-here>
   JWT_SECRET=<we-generated-this-for-you-already-see-below>
   OCR_ENGINE=tesseract
   UPLOAD_DIR=/tmp/uploads
   PORT=8000

   # Optional — leave empty until you have keys
   GEMINI_API_KEY=
   STRIPE_SECRET_KEY=
   STRIPE_WEBHOOK_SECRET=
   STRIPE_PRICE_PRO=
   STRIPE_PRICE_BUSINESS=

   # Will fill in after step 3 (Vercel)
   FRONTEND_URL=
   FRONTEND_ORIGINS=
   ```

   **Generate your own JWT_SECRET** — run this in any terminal once, paste the output above:
   ```bash
   openssl rand -hex 32
   ```
   (Never commit this value to a repo. Treat it like a password.)

5. **Deploy** — Koyeb builds the Docker image (~5 min first time because tesseract language packs are ~200 MB).

6. When build completes, Koyeb shows your service URL — looks like `https://extasy-backend-<yourname>.koyeb.app`. **Copy this URL** — you'll need it in step 3.

7. Verify:
   ```bash
   curl https://extasy-backend-<yourname>.koyeb.app/health
   # → {"status":"ok"}
   ```

---

## 3 — Vercel frontend

1. Open https://vercel.com → **Sign up with GitHub** (no CC for the Hobby tier)
2. **Add new project** → **Import** `kappaborg/ocr-bills`
3. Configure:
   - **Framework Preset**: Next.js (auto-detected)
   - **Root Directory**: `backend/frontend`  ← important
   - **Build Command**: `next build` (default)
   - **Output Directory**: `.next` (default)
4. **Environment variables**:
   ```
   NEXT_PUBLIC_API_BASE_URL=https://extasy-backend-<yourname>.koyeb.app
   ```
   (the URL you copied in step 2.6)
5. **Deploy** — first build is ~3 min.

6. When done, Vercel gives you a URL like `https://ocr-bills-<random>.vercel.app`. **Copy it.**

### Back to Koyeb — fill in the frontend URL

In the Koyeb service → Settings → Environment Variables, set:
```
FRONTEND_URL=https://ocr-bills-<random>.vercel.app
FRONTEND_ORIGINS=https://ocr-bills-<random>.vercel.app
```

Click **Save & redeploy**. Takes ~30s for the new vars to apply.

---

## 4 — Gemini key (optional but big accuracy upgrade)

Without this, OCR uses Tesseract (≈70-85% accuracy on receipts). With Gemini, accuracy jumps to ≈92-97% and is multilingual native.

1. https://aistudio.google.com/app/apikey → **Create API key**
2. Copy the key
3. Koyeb → Settings → Environment Variables:
   ```
   GEMINI_API_KEY=<paste-here>
   OCR_ENGINE=gemini
   ```
4. Save & redeploy

Free tier is 1500 receipts/day — plenty for your first batch of users.

---

## 5 — Smoke test on the live site

Open your Vercel URL in a private tab (so you're logged out):

1. ✅ Landing page renders
2. ✅ Click **Try it free** → register a fresh account
3. ✅ Land on `/onboarding` → pick currency → finish
4. ✅ Dashboard shows `FREE 0 / 20 receipts` chip
5. ✅ `/upload` → upload a receipt photo
6. ✅ Status moves `queued → processing → parsed` within ~30s (longer first time if Gemini)
7. ✅ Open receipt detail → items extracted
8. ✅ Confirm → category breakdown appears
9. ✅ `/pricing` shows three plans (Pro/Business buttons say "Setup pending" until Stripe configured)

If all green: **the product is live**.

---

## Common pitfalls

**Build fails on Koyeb with "out of memory"**
- Free Nano is 256 MB. The Docker image is ~350 MB but most of that is on-disk; runtime memory is more like 150-200 MB. If you genuinely OOM, drop the unused Tesseract language packs in `backend/Dockerfile` (we ship 20+, you probably need 4-5 for your audience).

**`DATABASE_URL` rejection on startup**
- Supabase URIs start with `postgresql://`. Our `session.py` rewrites that to `postgresql+psycopg://` automatically, so this should just work. If you see psycopg2 errors in Koyeb logs, double-check the env var is exactly the Supabase URI you copied.

**Receipt images "404" after a Koyeb redeploy**
- Expected — `/tmp/uploads` is ephemeral on Koyeb's free tier. The OCR-extracted data is in Postgres so the dashboard still works; only the original photo blob is lost. Add Supabase Storage integration later if this matters.

**CORS error in the browser console after deploying**
- `FRONTEND_ORIGINS` must include the **exact** URL your browser is on. If Vercel deployed to `https://ocr-bills-xyz.vercel.app` and you set `FRONTEND_ORIGINS=https://ocr-bills.vercel.app`, the trailing-xyz mismatch breaks CORS. Copy the URL precisely.

**Koyeb says "PORT mismatch"**
- The `EXPOSE 8000` in our Dockerfile + `PORT=8000` env var must match the **Exposed port** field in Koyeb's UI. All three should be `8000`.

---

## What you'll pay

| Service | Tier | Cost |
|---|---|---|
| Koyeb Nano | Free | $0 |
| Supabase | Free | $0 (500 MB DB, 1 GB storage) |
| Vercel Hobby | Free | $0 |
| Gemini API | Free tier | $0 (1500/day) |
| Stripe | Per-transaction | 2.9% + $0.30 |
| **Total fixed** | | **$0/mo** |

When you hit ~50 daily users, you'll probably want:
- Koyeb Starter at $7.20/mo (always-on Small, more RAM)
- Supabase Pro at $25/mo (8 GB DB, daily backups)

But for the first 100+ test users, the free tier holds.
