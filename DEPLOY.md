# ExTaSy Deployment Runbook

End-to-end production deploy. Follow top-to-bottom — each section assumes the previous ones are done. Total time: **~90 minutes** if accounts already exist, otherwise add account-creation time.

| Step | Service | Time | Outcome |
|---|---|---|---|
| 1 | Fly.io + Fly Postgres | 25 min | Backend live at `*.fly.dev`, talking to Postgres |
| 2 | Vercel | 10 min | Frontend live at `*.vercel.app` |
| 3 | Stripe | 20 min | Real billing, sandbox or live mode |
| 4 | Cloudflare | 15 min | Your domain on HTTPS pointing at both deploys |
| 5 | Gemini | 5 min | High-accuracy OCR turned on |
| 6 | Smoke test | 10 min | End-to-end checkout works |

Anything in `<angle-brackets>` is a value you paste in.

---

## 1 — Postgres + backend on Fly.io

### Prerequisites
- Install the CLI: `brew install flyctl` (or [docs](https://fly.io/docs/hands-on/install-flyctl/))
- `fly auth signup` — adds a credit card; the free tier covers a small backend + Postgres ~~indefinitely~~ for ≈$0/mo if you stay under 256 MB RAM. Bigger machines bill per second.

### Launch
```bash
cd "/Users/kappasutra/OCR BILLS/backend"

# Create the app from fly.toml. --no-deploy lets us set secrets before the first boot.
fly launch --no-deploy --copy-config --name extasy-backend

# Persistent volume for uploaded receipt images.
fly volumes create extasy_uploads --size 1 --region fra

# Provisioned Postgres. fly-pg is a free shared instance; for paying customers,
# go to https://fly.io/docs/postgres/getting-started/ for managed Postgres.
fly postgres create --name extasy-db --region fra --vm-size shared-cpu-1x --volume-size 1
fly postgres attach extasy-db
# ↑ this sets DATABASE_URL automatically as a fly secret.
```

### Secrets
```bash
# Required
fly secrets set JWT_SECRET="$(openssl rand -hex 32)"

# Stripe (see section 3 below for getting these)
fly secrets set STRIPE_SECRET_KEY="sk_live_xxx"
fly secrets set STRIPE_WEBHOOK_SECRET="whsec_xxx"
fly secrets set STRIPE_PRICE_PRO="price_xxx"
fly secrets set STRIPE_PRICE_BUSINESS="price_xxx"

# OCR (see section 5)
fly secrets set GEMINI_API_KEY="xxx"

# Frontend URL (set after section 4)
fly secrets set FRONTEND_URL="https://your-domain.com"
fly secrets set FRONTEND_ORIGINS="https://your-domain.com"
```

You can deploy with placeholder values now and update later — billing endpoints will return 503 until the Stripe vars land, but everything else works.

### Deploy
```bash
fly deploy
```

This builds the Dockerfile, pushes it, and rolls out a new machine. First deploy ≈ 5 min (mostly the Tesseract language packs). Subsequent deploys: ≈ 90 s.

### Verify
```bash
fly status                       # should show 1 machine, started
fly logs                         # tail recent logs
curl https://extasy-backend.fly.dev/health
# → {"status":"ok"}
```

---

## 2 — Frontend on Vercel

### Prerequisites
- Connect your GitHub repo to vercel.com (free tier covers personal projects)

### Setup
1. **Vercel → New Project → Import** your repo
2. **Root Directory**: `backend/frontend` (this is where `package.json` lives)
3. **Framework Preset**: Next.js (auto-detected from `vercel.json`)
4. **Environment Variables**:
   - `NEXT_PUBLIC_API_BASE_URL` = `https://extasy-backend.fly.dev` (or your domain after section 4)
5. Click **Deploy**

First build: ≈ 3 min. Vercel auto-deploys every push to `main` from then on.

### Verify
- Visit `https://your-vercel-deployment.vercel.app`
- Landing page renders. Sign up → onboarding wizard → dashboard.
- If the dashboard shows "Failed to load", check the Network tab — the API base URL is probably wrong.

---

## 3 — Stripe products + webhook

### Sign in
Stripe Dashboard: https://dashboard.stripe.com. Start in **Test mode** (toggle top-right). Move to Live mode only after you've verified end-to-end checkout works.

### Create the products
For each plan, **Products → Add product**:

**Pro plan**
- Name: `ExTaSy Pro`
- Description: `500 receipts/month + PDF/Xero/QuickBooks export + budgets + recurring`
- Pricing → `Recurring`, $4.99/month, USD
- Save → copy the **Price ID** (`price_xxxx...`)

**Business plan**
- Name: `ExTaSy Business`
- Description: `Unlimited receipts + household sharing + bank reconciliation`
- Pricing → `Recurring`, $19.99/month, USD
- Save → copy the **Price ID**

Set as Fly secrets:
```bash
fly secrets set STRIPE_PRICE_PRO="price_xxx_pro"
fly secrets set STRIPE_PRICE_BUSINESS="price_xxx_business"
```

### API key
Stripe Dashboard → **Developers → API keys** → copy the **Secret key** (`sk_test_...` or `sk_live_...`).

```bash
fly secrets set STRIPE_SECRET_KEY="sk_test_xxx"
```

### Webhook
Stripe Dashboard → **Developers → Webhooks → Add endpoint**:
- Endpoint URL: `https://extasy-backend.fly.dev/billing/webhook` (or `https://api.your-domain.com/billing/webhook` after section 4)
- Events to send:
  - `customer.subscription.created`
  - `customer.subscription.updated`
  - `customer.subscription.deleted`
  - `checkout.session.completed`
- Add endpoint → reveal the **Signing secret** (`whsec_...`)

```bash
fly secrets set STRIPE_WEBHOOK_SECRET="whsec_xxx"
fly deploy   # secrets need a restart to apply
```

### Customer Portal config
Stripe Dashboard → **Settings → Billing → Customer portal**:
- Enable "Customers can update their payment method"
- Enable "Customers can cancel subscriptions"
- Enable "Customers can switch plans" → add Pro + Business
- Add your domain to the allowed return URLs

### Test
- Open `https://your-app/pricing` (logged in)
- Click "Subscribe to Pro"
- Use the Stripe test card `4242 4242 4242 4242`, any future date, any CVV
- After checkout you should be redirected to `/billing/success`
- Refresh `/dashboard` → the plan chip should switch to `PRO`
- If the chip doesn't update, check **Stripe → Webhooks → your endpoint** for failed deliveries

---

## 4 — Domain + HTTPS via Cloudflare

### Buy / point your domain
- Buy via Cloudflare Registrar (cheapest, no markup) or transfer in
- Free Cloudflare plan is fine

### DNS records
| Type | Name | Target | Proxy |
|---|---|---|---|
| CNAME | `@` (apex) | `cname.vercel-dns.com` | DNS only |
| CNAME | `www` | `cname.vercel-dns.com` | DNS only |
| CNAME | `api` | `extasy-backend.fly.dev` | DNS only |

(Vercel and Fly both terminate HTTPS themselves; Cloudflare's proxy isn't required.)

### Vercel custom domain
Vercel → Project → Settings → Domains → add `your-domain.com` + `www.your-domain.com`. Vercel will validate the CNAME and issue an SSL cert in ~60 seconds.

### Fly custom domain
```bash
fly certs create api.your-domain.com
fly certs show  api.your-domain.com    # wait until "Issued" (~60s)
```

### Update env vars
After domains resolve:
```bash
# Backend
fly secrets set FRONTEND_URL="https://your-domain.com"
fly secrets set FRONTEND_ORIGINS="https://your-domain.com,https://www.your-domain.com"
fly deploy

# Frontend (Vercel UI)
# Settings → Environment Variables → edit:
#   NEXT_PUBLIC_API_BASE_URL=https://api.your-domain.com
# Redeploy
```

Then update the **Stripe webhook URL** to `https://api.your-domain.com/billing/webhook`.

---

## 5 — Gemini API key (OCR accuracy)

1. https://aistudio.google.com/app/apikey → **Create API key** (free tier: 1500 req/day)
2. Copy the key
3. `fly secrets set GEMINI_API_KEY="xxx"`
4. `fly secrets set OCR_ENGINE="gemini"` (already set in `fly.toml`)
5. `fly deploy`

Verify with `curl https://api.your-domain.com/fx/rates` (any authenticated endpoint will do — first OCR call will trigger a Gemini hit and show in their console).

---

## 6 — Smoke test (production)

From a logged-out browser tab pointing at your real domain:

1. ✅ Landing page renders, "Try it free" CTA visible
2. ✅ Register a fresh account → lands on `/onboarding`
3. ✅ Complete onboarding → `/dashboard` shows `FREE / 0 of 20 receipts` chip
4. ✅ Upload a receipt photo → status moves `queued → processing → parsed`
5. ✅ Open receipt detail → items + total visible
6. ✅ Click **Confirm** → category breakdown appears on dashboard
7. ✅ Visit `/pricing` → click **Subscribe to Pro** → Stripe checkout opens
8. ✅ Pay with `4242 4242 4242 4242` → redirected to `/billing/success`
9. ✅ Return to `/dashboard` → plan chip says `PRO`
10. ✅ **Export ▾ → QuickBooks CSV** downloads a file with the right header
11. ✅ Settings → Subscription → **Manage billing** opens the Stripe portal

If all eleven pass, you're live.

---

## What you'll be paying

| Service | Tier | Cost |
|---|---|---|
| Fly.io backend (1×256 MB) | Hobby | ~$0–3/mo (scales to zero when idle) |
| Fly Postgres (256 MB shared) | Hobby | $0 |
| Fly volume (1 GB) | Hobby | $0.15/mo |
| Vercel | Hobby | $0 (commercial use technically requires Pro at $20/mo) |
| Cloudflare DNS + domain | Free + $9/yr | $0.75/mo |
| Stripe | Per-transaction | 2.9% + $0.30 per charge |
| Gemini | Free tier | $0 (up to 1500 req/day) |
| **Total fixed** | | **≈$1–4/mo** before any subscribers |

When you have ~50 paying users you'll likely upgrade Fly to a dedicated 1 GB machine (~$5/mo) and Vercel to Pro ($20/mo). Both pay for themselves at that volume.

---

## Common pitfalls

**Stripe webhook signature failures**
- The webhook secret is the per-endpoint `whsec_...`, not your API key. Different value each environment.

**CORS errors on the dashboard after deploy**
- `FRONTEND_ORIGINS` must include the **exact** scheme + host the browser uses. `https://www.x.com` and `https://x.com` are different origins. Add both.

**"Receipt image not found" on detail page**
- Fly volumes are per-machine. If you autoscale to zero and back, files on the volume *do* persist (it's not a tmpfs), but only the machine that wrote them sees them. If you scale beyond 1 machine you need shared storage (S3-compatible). For v1 keep `min_machines_running = 0` and a single machine.

**psycopg can't connect**
- The Fly Postgres URL uses `postgres://` — SQLAlchemy 2.x defaults that to psycopg2. The session.py normalizer rewrites it to `postgresql+psycopg://`. If you're connecting from outside Fly (local debugging), prepend the dialect yourself.

**Gemini quota exhausted**
- Free tier is 1500 req/day across all callers using your key. For paid users + free trial users combined this is enough until ~50 active users/day. After that, enable billing on the Google Cloud project — Gemini Flash is $0.075 per million input tokens (so still very cheap).
