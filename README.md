# LinkedIn Commodity Markets Automation Tool

Automated LinkedIn content generation and posting tool focused on **Commodity Markets & Supply Chain**. Uses multi-AI fusion (Claude, GPT, Gemini, Perplexity, Grok) to create top 1% professional content with a self-learning loop that improves with every post.

## Features

- **Multi-AI Content Generation**: Fuses insights from 5 AI engines for best-in-class content
- **LinkedIn Optimization**: Posts formatted for maximum reach (hooks, paragraph style, CTAs)
- **Visual Content**: Auto-generated carousel PDFs and branded images
- **Current Affairs**: Crawls commodity news via RSS feeds and real-time AI research
- **Self-Learning**: Tracks post metrics and adjusts content strategy automatically
- **Knowledge Briefing**: Generates topic briefs so you learn alongside your audience
- **CLI Approval**: Review and approve every post before it goes live
- **Scheduled Posting**: 3x/week via GitHub Actions (Mon/Wed/Fri 8AM IST)

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/AryanShah45/AryanShah45.git
cd AryanShah45
pip install -r requirements.txt
```

### 2. Configure API Keys

```bash
cp .env.example .env
# Edit .env with your API keys (see LinkedIn Setup below)
```

### 3. Generate Content

```bash
# Generate a new post (dry run — saves to posts/drafts/)
python -m src.main generate --dry-run

# Review pending posts
python -m src.main review

# Publish approved posts
python -m src.main publish

# View learning insights
python -m src.main learn --report
```

## LinkedIn API Setup

### Step 1: Create a LinkedIn Developer App

1. Go to [LinkedIn Developers](https://www.linkedin.com/developers/apps)
2. Click **Create App**
3. Fill in:
   - App name: `Commodity Content Automation`
   - LinkedIn Page: Link your company/personal page
   - App logo: Upload any logo
4. Under **Auth** tab, add redirect URL: `http://localhost:8080/callback`

### Step 2: Request API Access

1. In your app's **Products** tab, request access to:
   - **Share on LinkedIn** (for posting)
   - **Sign In with LinkedIn using OpenID Connect** (for auth)
2. Wait for approval (usually instant for Share on LinkedIn)

### Step 3: Get OAuth Tokens

1. Note your **Client ID** and **Client Secret** from the Auth tab
2. Run the auth setup:
   ```bash
   python -m src.linkedin.auth setup
   ```
3. This opens a browser for LinkedIn login and saves tokens to `.env`

### Step 4: Configure Other AI API Keys

Get API keys from:
- **Anthropic (Claude)**: https://console.anthropic.com/
- **OpenAI (GPT)**: https://platform.openai.com/api-keys
- **Google (Gemini)**: https://aistudio.google.com/app/apikey
- **Perplexity**: https://www.perplexity.ai/settings/api
- **xAI (Grok)**: https://console.x.ai/

Add all keys to your `.env` file.

## CLI Commands

| Command | Description |
|---------|-------------|
| `python -m src.main generate` | Generate a new post based on content calendar |
| `python -m src.main generate --dry-run` | Generate without posting |
| `python -m src.main generate --topic crude_oil` | Generate for specific topic |
| `python -m src.main review` | Review and approve pending drafts |
| `python -m src.main publish` | Publish all approved posts |
| `python -m src.main analytics` | View post performance metrics |
| `python -m src.main learn --report` | View learning insights |
| `python -m src.main learn --optimize` | Run strategy optimization |

## Project Structure

```
src/
  ai_engines/     — Multi-AI fusion (Claude, GPT, Gemini, Perplexity, Grok)
  content/        — Research, generation, formatting pipeline
  visuals/        — Carousel PDF and branded image generation
  linkedin/       — OAuth 2.0 auth, posting, analytics
  learning/       — Self-learning loop (track, analyze, optimize)
  knowledge/      — Topic briefings for the user
  cli/            — CLI review and approval interface
config/           — Settings, content calendar, brand assets
data/             — Performance logs, learning insights
posts/            — Drafts, approved, published archive
```

## How the Self-Learning Loop Works

1. **Post** content to LinkedIn
2. **Track** metrics at 24h, 48h, and 7 days
3. **Analyze** what topics, hooks, lengths, and formats perform best
4. **Optimize** future content based on patterns (adjusts AI prompts automatically)
5. **Repeat** — the tool gets smarter with every single post

## License

MIT
