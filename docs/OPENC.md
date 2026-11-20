# OpenC

OpenC is a fork of [Open WebUI](https://github.com/open-webui/open-webui) that adds the
ChatGPT / Claude / Kimi features Open WebUI was missing, tuned for
**Alibaba Cloud Model Studio (DashScope / Qwen)** and **OpenCode Zen**.

Everything Open WebUI already does still works: multi-user accounts and RBAC, chat history,
folders/projects with instructions and files, branching, sharing, temporary chats, RAG and
knowledge bases, memory, code interpreter, artifacts, voice, MCP/tools, notes and channels.

## What OpenC adds

| Feature | Inspired by | Where |
|---|---|---|
| **DashScope and OpenCode Zen connections from env vars** | — | `backend/open_webui/openc/providers.py` |
| **Think toggle** for Qwen hybrid-thinking models, with budgets of 4k / 16k / 38k | Claude extended thinking, Kimi K2 Thinking | composer → `openc/dashscope.py` |
| **Qwen built-in web search**: with Web Search on and a Qwen model selected, Qwen searches the web itself and its sources show as citations | Kimi | `openc/features.py`, `openc/dashscope.py` |
| **Deep Research**: multi-round plan → search → read → analyse loop, then a structured report with `[n]` citations | ChatGPT Deep Research, Kimi Researcher, Claude Research | composer "Research" → `openc/deep_research.py` |
| **Response styles**: Normal, Concise, Explanatory, Formal, or your own styles (synced to your account) | Claude Styles | composer pen icon → `openc/styles.py` |
| **Canvas editing for artifacts**: edit the code live, revert, or select a part and "Ask AI" to change it; the reply becomes the next version | ChatGPT Canvas | artifact panel "Edit" → `components/openc/CanvasEditor.svelte` |
| **Slides**: the model calls `create_slides` and you get a themed .pptx with speaker notes, previewed inline | Kimi PPT | `openc/slides.py` |
| **Wanx / Qwen-Image image generation** engine | ChatGPT image generation | Admin → Settings → Images → "Alibaba Wanx / Qwen-Image" → `openc/wanx.py` |
| **OpenC branding** | — | see the license note below |

## Quick start

```bash
docker build -t openc .
docker run -d -p 3000:8080 \
  -e DASHSCOPE_API_KEY=sk-... \
  -e OPENCODE_API_KEY=... \
  -v openc:/app/backend/data --name openc openc
```

Then open http://localhost:3000. The first account you create becomes the admin.

For local development, see the upstream instructions. In short, run `npm ci && npm run dev`
for the frontend and `cd backend && ./dev.sh` for the backend.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `DASHSCOPE_API_KEY` | — | Adds an "Alibaba Qwen" OpenAI-compatible connection at startup |
| `DASHSCOPE_BASE_URL` | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` | Use `https://dashscope.aliyuncs.com/compatible-mode/v1` for mainland China accounts |
| `DASHSCOPE_MODEL_IDS` | all models | Comma-separated list to show only some models, e.g. `qwen-max,qwen-plus,qwen-vl-max` |
| `OPENCODE_API_KEY` | — | Adds an "OpenCode Zen" connection at startup |
| `OPENCODE_BASE_URL` | `https://opencode.ai/zen/v1` | |
| `OPENCODE_MODEL_IDS` | all models | Comma-separated model filter |
| `OPENC_QWEN_NATIVE_SEARCH` | `true` | Use Qwen's built-in search for Qwen models instead of Open WebUI's search engine |
| `OPENC_DEEP_RESEARCH_MAX_ROUNDS` | `3` | Research rounds before writing the report |
| `OPENC_DEEP_RESEARCH_QUERIES_PER_ROUND` | `4` | |
| `OPENC_DEEP_RESEARCH_PAGES_PER_ROUND` | `6` | |
| `OPENC_DEEP_RESEARCH_MAX_SOURCES` | `20` | |
| `OPENC_DEEP_RESEARCH_CHARS_PER_SOURCE` | `6000` | Characters of each page passed to the model |

Connections from env vars are added once and then managed in **Admin → Settings → Connections**.
OpenC never overwrites or removes a connection an admin has edited.

### Feature requirements

- **Deep Research** uses the web search engine configured in **Admin → Settings → Web Search**
  (for example Tavily, Brave, SearXNG or Bocha), which must be enabled. Users need the
  web-search permission.
- **Slides** and other built-in tools need native function calling, which is the default
  (`function_calling` is not `legacy`) and works with a model that supports tool calls, such as Qwen
  or Kimi K2.
- **Wanx images**: add an image connection of type *Alibaba Wanx / Qwen-Image* with your
  DashScope key and the base URL `https://dashscope-intl.aliyuncs.com/api/v1`.

## Staying up to date with Open WebUI

This repository keeps upstream history, so updates are an ordinary merge:

```bash
git remote add upstream https://github.com/open-webui/open-webui.git
git fetch upstream main
git merge upstream/main
```

OpenC code lives mostly in `backend/open_webui/openc/`, `src/lib/openc/` and
`src/lib/components/openc/`. Each hook into upstream files is a few lines marked with an
`OpenC:` comment.

## Tests

```bash
cd backend && python -m pytest open_webui/openc/tests
```

## License and branding

OpenC is distributed under the [Open WebUI License](../LICENSE), and every upstream copyright
notice is retained. Replacing the Open WebUI name and logo with OpenC is allowed by **clause 4(i)**
only while a deployment has **50 or fewer end users in any rolling 30-day period**. Above that,
restore the Open WebUI branding (`git checkout upstream/main -- static/ src/app.html` and unset
the name changes), or obtain written permission or an enterprise license from Open WebUI Inc.
