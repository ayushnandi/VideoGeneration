# Full Automation Plan: Auto Video Generation & Multi-Platform Posting

## Overview

Fully automated pipeline that runs in Docker on a cloud VM. Every 6 hours it:
1. Generates a script (dialogue) using an LLM
2. Produces a video using the existing pipeline
3. Posts the video to Instagram Reels, Twitter/X, Facebook Reels, LinkedIn, and YouTube Shorts
4. Logs results and stores the video permanently

Zero manual effort after initial deployment.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                   Cloud VM (EC2 / DigitalOcean)         │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │              Docker Compose Stack                 │  │
│  │                                                   │  │
│  │  ┌─────────────┐   ┌────────────────────────┐    │  │
│  │  │  Scheduler   │──>│  Video Gen Worker      │    │  │
│  │  │  (cron/APSch)│   │  (existing pipeline)   │    │  │
│  │  └─────────────┘   └──────────┬─────────────┘    │  │
│  │                               │                   │  │
│  │                    ┌──────────▼─────────────┐    │  │
│  │                    │  Social Media Poster   │    │  │
│  │                    │  (platform uploaders)  │    │  │
│  │                    └──────────┬─────────────┘    │  │
│  │                               │                   │  │
│  │  ┌─────────────┐   ┌────────▼──────────────┐    │  │
│  │  │  PostgreSQL  │   │  S3 / Cloud Storage   │    │  │
│  │  │  (metadata)  │   │  (video archive)      │    │  │
│  │  └─────────────┘   └───────────────────────┘    │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Implementation Plan

### Phase 1: Script Auto-Generation

**Goal:** Replace the manual `demo_dialogue.json` with LLM-generated scripts.

**New file:** `app/services/script_generator.py`

| Item | Detail |
|------|--------|
| LLM Provider | OpenAI GPT-4o-mini or Claude API (cheapest option that works) |
| Input | A topic pool / trending topics list stored in `config/topics.json` |
| Output | A JSON dialogue array matching the existing format: `[{"speaker": "toji", "text": "...", "cat_image": "..."}, ...]` |
| Topic Selection | Random pick from topic pool, or use a news/trending API (e.g., Google Trends RSS) to pick fresh topics |
| Prompt Template | Stored in `config/prompt_template.txt` — instructs the LLM to write a funny/engaging cat-vs-toji debate script |
| Validation | Validate JSON structure, line count (<200), text length (<2000 chars per line) before proceeding |
| Cost | ~$0.01-0.03 per script with GPT-4o-mini |

**Implementation steps:**
1. Create `config/topics.json` — seed with 50+ topic ideas
2. Create `config/prompt_template.txt` — the system prompt for script generation
3. Create `app/services/script_generator.py` with `generate_script() -> list[dict]`
4. Add `OPENAI_API_KEY` (or `ANTHROPIC_API_KEY`) to `.env`

---

### Phase 2: Scheduler Service

**Goal:** Trigger the pipeline every 6 hours automatically.

**New file:** `app/services/scheduler.py`

| Item | Detail |
|------|--------|
| Library | `APScheduler` (Advanced Python Scheduler) |
| Schedule | Every 6 hours: 00:00, 06:00, 12:00, 18:00 UTC |
| Trigger | Calls the full pipeline: generate script → generate video → post to socials |
| Locking | File-based or DB-based lock to prevent overlapping runs |
| Retry | If a run fails, retry once after 30 minutes |

**New file:** `scheduler_main.py` (entrypoint for the scheduler container)

```python
# Pseudocode
from apscheduler.schedulers.blocking import BlockingScheduler

scheduler = BlockingScheduler()

@scheduler.scheduled_job('interval', hours=6)
def run_pipeline():
    script = generate_script()
    video_path = generate_video(script)
    upload_to_storage(video_path)
    post_to_all_platforms(video_path, script)
    log_result()

scheduler.start()
```

---

### Phase 3: Social Media Posting

**Goal:** Auto-post the generated video to all platforms.

**New file:** `app/services/social_poster.py`

#### Platform-by-Platform Breakdown:

##### 1. Instagram Reels
| Item | Detail |
|------|--------|
| API | Instagram Graph API (via Facebook Business) |
| Auth | Long-lived page access token (60-day, auto-refreshed) |
| Flow | Upload video to container → publish container |
| Requirements | Facebook Business account, Instagram Professional account linked |
| Limits | 25 API-published posts per 24 hours |

##### 2. Twitter / X
| Item | Detail |
|------|--------|
| API | Twitter API v2 + Media Upload API v1.1 |
| Auth | OAuth 1.0a (consumer key + access token) |
| Flow | Chunked media upload → create tweet with media_id |
| Requirements | Twitter Developer account (Basic tier: $100/month for posting) |
| Limits | Video max 140 seconds, 512MB |

##### 3. Facebook Reels
| Item | Detail |
|------|--------|
| API | Facebook Graph API (Pages) |
| Auth | Page access token (same as Instagram setup) |
| Flow | Initialize upload → upload video → publish |
| Requirements | Facebook Page (not personal profile) |
| Limits | Same as Instagram (shared Business account) |

##### 4. LinkedIn
| Item | Detail |
|------|--------|
| API | LinkedIn Marketing API (Community Management) |
| Auth | OAuth 2.0 3-legged flow → refresh token |
| Flow | Register upload → upload binary → create post with video |
| Requirements | LinkedIn Company Page, Marketing Developer Platform app |
| Limits | Video max 15 minutes, 200MB |

##### 5. YouTube Shorts
| Item | Detail |
|------|--------|
| API | YouTube Data API v3 |
| Auth | OAuth 2.0 with refresh token |
| Flow | `videos.insert` with `#Shorts` in title/description |
| Requirements | Google Cloud project, YouTube channel, API quota (10,000 units/day) |
| Limits | Video must be ≤60 seconds and vertical for Shorts |

#### Token Refresh Strategy
All long-lived tokens expire. Create `app/services/token_manager.py`:
- Store tokens in PostgreSQL (encrypted)
- Auto-refresh before expiry (background job every 12 hours)
- Alert via email/webhook if a token refresh fails (requires manual re-auth)

---

### Phase 4: Video Storage

**Goal:** Permanently store all generated videos with metadata.

#### Storage Structure

```
S3 Bucket: your-video-archive
├── videos/
│   ├── 2026/03/06/
│   │   ├── video_abc123.mp4
│   │   └── video_def456.mp4
│   └── 2026/03/07/
│       └── ...
└── thumbnails/
    └── (auto-generated from first frame)
```

#### Database Schema (PostgreSQL)

```sql
CREATE TABLE videos (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id        VARCHAR(64) UNIQUE NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW(),

    -- Script
    topic         TEXT,
    dialogue_json JSONB,

    -- Video
    s3_key        TEXT,
    s3_url        TEXT,
    duration_sec  FLOAT,
    file_size_mb  FLOAT,

    -- Posting status
    posted_instagram  BOOLEAN DEFAULT FALSE,
    posted_twitter    BOOLEAN DEFAULT FALSE,
    posted_facebook   BOOLEAN DEFAULT FALSE,
    posted_linkedin   BOOLEAN DEFAULT FALSE,
    posted_youtube    BOOLEAN DEFAULT FALSE,

    -- Error tracking
    errors        JSONB DEFAULT '[]'
);
```

#### Storage Options (Pick One)

| Option | Cost | Pros | Cons |
|--------|------|------|------|
| AWS S3 | ~$0.023/GB/month | Reliable, CDN-ready | AWS complexity |
| DigitalOcean Spaces | $5/month for 250GB | Simple, S3-compatible | Less ecosystem |
| Cloudflare R2 | Free egress, $0.015/GB stored | Cheapest for serving | Newer service |
| Server disk + backup | $0 extra | Simplest | Risk of data loss |

**Recommendation:** Cloudflare R2 — cheapest, S3-compatible API, free egress.

---

### Phase 5: Docker & Cloud Deployment

#### Updated Docker Compose (`docker-compose.prod.yml`)

```yaml
services:
  # Existing web UI (optional, for manual overrides)
  web:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./assets:/app/assets:ro
      - ./config:/app/config:ro
      - video_output:/app/output
    restart: unless-stopped
    depends_on:
      - db

  # NEW: Automated scheduler
  scheduler:
    build: .
    command: python scheduler_main.py
    env_file: .env
    volumes:
      - ./assets:/app/assets:ro
      - ./config:/app/config:ro
      - video_output:/app/output
    restart: unless-stopped
    depends_on:
      - db
    deploy:
      resources:
        limits:
          memory: 4G

  # NEW: PostgreSQL for metadata + tokens
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: videogen
      POSTGRES_USER: videogen
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  video_output:
  pgdata:
```

#### Cloud VM Recommendation

| Provider | Instance | Specs | Cost/month |
|----------|----------|-------|------------|
| AWS EC2 | t3.medium | 2 vCPU, 4GB RAM | ~$30 |
| DigitalOcean | s-2vcpu-4gb | 2 vCPU, 4GB RAM | $24 |
| Hetzner | CPX21 | 3 vCPU, 4GB RAM | ~$8 (best value) |

**Recommendation:** Hetzner CPX21 — best price-to-performance for FFmpeg workloads.

#### Deployment Steps

```bash
# 1. Provision VM (Ubuntu 24.04)
# 2. Install Docker
curl -fsSL https://get.docker.com | sh

# 3. Clone repo
git clone <your-repo> && cd Video_Genetation

# 4. Configure environment
cp .env.example .env
# Edit .env with all API keys (see Environment Variables section below)

# 5. Place assets
# Upload background video, speaker images, fonts

# 6. Launch
docker compose -f docker-compose.prod.yml up -d --build

# 7. Verify
docker compose logs -f scheduler
```

---

### Phase 6: Monitoring & Alerts

**Goal:** Know when things fail without checking manually.

| Tool | Purpose | Cost |
|------|---------|------|
| UptimeRobot | VM health check | Free (50 monitors) |
| Email alerts | Pipeline failure notifications | Free (via Gmail SMTP) |
| Discord/Slack webhook | Real-time status updates | Free |
| Grafana + Loki (optional) | Log aggregation & dashboards | Free (self-hosted) |

**New file:** `app/services/notifier.py`
- Send notification on: pipeline success, pipeline failure, token expiry warning
- Channels: Discord webhook (simplest) or email via SMTP

---

## Complete File Structure (After Implementation)

```
Video_Genetation/
├── app/
│   ├── services/
│   │   ├── video_service.py        # existing
│   │   ├── tts_service.py          # existing
│   │   ├── job_manager.py          # existing
│   │   ├── script_generator.py     # NEW — LLM script generation
│   │   ├── social_poster.py        # NEW — multi-platform posting
│   │   ├── storage_service.py      # NEW — S3/R2 upload
│   │   ├── token_manager.py        # NEW — OAuth token refresh
│   │   ├── notifier.py             # NEW — alerts & notifications
│   │   └── pipeline.py             # NEW — orchestrates full flow
│   └── ...
├── config/
│   ├── settings.py                 # existing (add new config vars)
│   ├── speakers.json               # existing
│   ├── topics.json                 # NEW — topic pool
│   └── prompt_template.txt         # NEW — LLM prompt
├── scheduler_main.py               # NEW — scheduler entrypoint
├── docker-compose.prod.yml         # NEW — production compose
├── Dockerfile                      # existing (minor updates)
└── .env                            # existing (add new keys)
```

---

## Environment Variables (Complete List)

```env
# Existing
ELEVENLABS_API_KEY=sk-...
FLASK_SECRET_KEY=...

# Script Generation (pick one)
OPENAI_API_KEY=sk-...
# or ANTHROPIC_API_KEY=sk-ant-...

# Social Media - Instagram / Facebook
META_APP_ID=...
META_APP_SECRET=...
META_PAGE_ACCESS_TOKEN=...
INSTAGRAM_BUSINESS_ACCOUNT_ID=...
FACEBOOK_PAGE_ID=...

# Social Media - Twitter / X
TWITTER_CONSUMER_KEY=...
TWITTER_CONSUMER_SECRET=...
TWITTER_ACCESS_TOKEN=...
TWITTER_ACCESS_TOKEN_SECRET=...

# Social Media - LinkedIn
LINKEDIN_CLIENT_ID=...
LINKEDIN_CLIENT_SECRET=...
LINKEDIN_ACCESS_TOKEN=...
LINKEDIN_ORGANIZATION_ID=...

# Social Media - YouTube
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REFRESH_TOKEN=...
YOUTUBE_CHANNEL_ID=...

# Storage
R2_ACCOUNT_ID=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=video-archive

# Database
DB_PASSWORD=...
DATABASE_URL=postgresql://videogen:${DB_PASSWORD}@db:5432/videogen

# Notifications
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Scheduler
PIPELINE_INTERVAL_HOURS=6
```

---

## Monthly Cost Estimate

| Item | Cost |
|------|------|
| Cloud VM (Hetzner CPX21) | $8 |
| ElevenLabs TTS (Starter plan, 30k chars) | $5 |
| LLM API (GPT-4o-mini, ~120 scripts/month) | $1-2 |
| Cloudflare R2 (50GB stored) | $0.75 |
| Twitter API (Basic tier, required for posting) | $100 |
| Domain + SSL (optional) | $1 |
| **Total (with Twitter)** | **~$116/month** |
| **Total (without Twitter)** | **~$16/month** |

> Note: Instagram, Facebook, LinkedIn, and YouTube APIs are free to use. Twitter is the expensive one.

---

## Implementation Order (Recommended)

| Priority | Phase | Effort | Description |
|----------|-------|--------|-------------|
| 1 | Script Generator | 1 session | LLM integration + topic pool |
| 2 | Pipeline Orchestrator | 1 session | Wire script gen → video gen end-to-end |
| 3 | Scheduler | 1 session | APScheduler + Docker scheduler service |
| 4 | Storage (R2/S3) | 1 session | Upload videos + PostgreSQL metadata |
| 5 | YouTube Shorts posting | 1 session | Usually easiest API to set up |
| 6 | Instagram + Facebook | 1 session | Shared Meta Business setup |
| 7 | LinkedIn posting | 1 session | Marketing API integration |
| 8 | Twitter posting | 1 session | Only if budget allows ($100/mo) |
| 9 | Monitoring & Alerts | 1 session | Discord webhook notifications |
| 10 | Production deploy | 1 session | Hetzner VM + domain + final testing |

---

## Key Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Social media token expiry | Posts fail silently | Token manager with auto-refresh + alerts |
| ElevenLabs rate limiting | Video generation stalls | Retry logic (already exists), monitor usage |
| LLM generates bad script | Cringe/inappropriate content | Content filter in script_generator, keep topic pool curated |
| VM runs out of disk | Everything stops | Cron job to delete local videos older than 24h (they're on R2) |
| Platform API changes | Posting breaks | Pin API versions, monitor for deprecation notices |
| FFmpeg OOM on small VM | Process killed | 4GB RAM limit, process one video at a time |

---

## What's Already Done vs What's Needed

| Component | Status |
|-----------|--------|
| Video generation pipeline | DONE |
| TTS integration (ElevenLabs) | DONE |
| FFmpeg compositing | DONE |
| Dockerfile | DONE |
| Docker Compose (basic) | DONE |
| Script auto-generation | TO BUILD |
| Scheduler | TO BUILD |
| Social media posting | TO BUILD |
| Cloud storage | TO BUILD |
| Database | TO BUILD |
| Monitoring/alerts | TO BUILD |
| Production deployment | TO BUILD |
