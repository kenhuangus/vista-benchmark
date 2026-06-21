# experiments/ — real-LLM runs (Pillar A)

These scripts drive **real frontier models** through the same VISTA adapter +
deterministic scorer the reference agents use, so a model's scorecard is directly
comparable to `naive` and `ranger`. The benchmark core stays pure-stdlib and
deterministic; the model is the only stochastic part (which is what `pass^k`
absorbs). Models are invoked via **subscription-login CLIs**, not metered API keys.

## Claude models (work now)

Driven through the Claude Code CLI (`claude -p --output-format json`) on a
subscription login in WSL (the `ANTHROPIC_API_KEY` is unset for the call):

```bash
python experiments/real_agent_run.py --model sonnet            # all 3 hand-authored journeys
python experiments/real_agent_run.py --model opus  --runs 3    # pass^k variance
python experiments/real_agent_run.py --model haiku --out results/pillar-a/haiku.json
```

Each run prints a per-journey comparison (naive / ranger / model), the model's raw
plan and applied path, and a token + cost summary parsed from the CLI envelope.

## Gemini models (via Vertex AI)

Google **discontinued** the Gemini CLI's free "Sign in with Google" (Code Assist
for individuals) tier — it now errors and points to the Antigravity GUI, which has
no headless CLI. So Gemini is driven through **Vertex AI** on a GCP project, billed
to that project's credits. The CLI is installed under WSL's nvm node.

One-time setup (see `gemini_vertex_setup.sh` for the gcloud commands): create a
service-account key for the project, grant it `roles/aiplatform.user`, store the
key **outside the repo**, then pin the CLI's auth type:

```bash
bash experiments/gemini_vertex_setup.sh        # sets ~/.gemini auth to vertex-ai
```

Then the runner auto-selects the Gemini backend from the model name and runs
headlessly (Vertex config via env or the runner's defaults):

```bash
GOOGLE_CLOUD_PROJECT=<proj> VERTEX_SA_KEY_WSL=/mnt/c/Users/<you>/.vista/vertex-sa.json \
  python experiments/real_agent_run.py --model gemini-2.5-pro
```

Vertex usage is billed to the GCP project (not surfaced as USD by the CLI, so cost
shows `$0.0000`); token counts are reported from the CLI's `stats` block. The agent
also supports `--gemini-mode apikey` (uses `GEMINI_API_KEY`) as a fallback.

## Cost note

When using the Claude Code CLI, most of each call's cost is Claude Code's own
cached system prompt, not the small VISTA planning prompt. A leaner path (direct
API or a minimal CLI) would cut per-call cost substantially before scaling to a
large corpus × k runs.
