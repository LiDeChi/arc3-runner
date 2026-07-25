---
name: sync-skills
description: "Manage the centralized personal skill repository (~/.skills). Use to promote skills from Codex or Grok, synchronize Claude/Gemini/Codex links, materialize plugin-linked skills as independent snapshots, or check source drift across agents. Primary command: /sync-skills"
allowed-tools: Read, Bash, Glob
---

# Skill Sync Manager

You are the guardian of the user's **personal skill central repository** at `~/.skills`.

This repository is the single source of truth for high-quality, reusable skills that should be available across Grok, Codex, Gemini, Claude-compatible tools, etc.

## Core Responsibilities

1. **Understand the architecture** (read `~/.skills/README.md` on first use in a session)
2. Help the user **promote** good skills they developed in Codex or elsewhere into the central store so they become available everywhere.
3. **Check status** across all tools.
4. **Refresh symlinks** so that changes in the central repo immediately appear in other agents.
5. Never promote project-specific or low-quality skills.

## Available Commands (via the script)

Run the manager script using the Bash tool:

```bash
~/.skills/sync-skills/scripts/sync.sh status
~/.skills/sync-skills/scripts/sync.sh sync-all
~/.skills/sync-skills/scripts/sync.sh promote my-new-skill
~/.skills/sync-skills/scripts/sync.sh materialize-linked
~/.skills/sync-skills/scripts/sync.sh source-status
~/.skills/sync-skills/scripts/sync.sh list
```

### `status`
Shows:
- How many skills are in the central repo
- How many central entries are real directories versus linked external sources
- Whether Grok's config is correctly pointing at it
- For Claude, Gemini, and Codex: central links, real-entry conflicts, wrong links,
  missing skills, and broken top-level links

### `promote <skill-name>`
The most common operation.

- Looks for `<skill-name>` in `~/.codex/skills`, `~/.grok/skills`, or `~/.agents/skills`
- Moves a real Codex source into `~/.skills/<skill-name>` so only one editable copy remains
- Copies Grok or `.agents` sources into central while retaining their original source
- Immediately runs `sync-all` so it appears in Grok, Claude layer, Gemini, and Codex
- Refuses symlink sources and existing central destinations instead of guessing

Use this after the user says something like:
- "promote this skill"
- "make this available in all my agents"
- "sync the new architecture-decision skill everywhere"

### `sync-all`
Safely refresh central symlinks in all known locations. The command:

- Creates missing links and verifies existing managed links.
- Removes only stale links that already point into `~/.skills`.
- Never overwrites real directories or non-central links.
- Reports conflicts for manual reconciliation instead of nesting links inside directories.

### `materialize-linked`

Convert every valid symlinked skill in `~/.skills` into a verified independent copy.
The command stages and hashes every copy before replacement, saves the original links
under `~/.skills-backups/`, records provenance in
`~/.skills/.materialized-sources.json`, and then runs `sync-all`.
It refuses sources that still contain symlinks or hardcoded references to their source
directory, because those would not be independent snapshots.

Use this when a central skill still depends on a plugin cache or another removable
source. The central copy becomes authoritative after materialization; never refresh it
from the source automatically.

### `source-status`

Compare each tracked central snapshot with both its materialization hash and its
original source. Report local edits, upstream changes, and missing sources without
modifying anything. Reconcile reported changes manually before replacing a central
copy.

### `list`
Pretty list of everything currently in the central repository with their descriptions.

## Promotion Guidelines (Important)

**Promote only when:**
- The skill has a good `description` in frontmatter
- It is genuinely reusable across projects and tools
- It is not tightly coupled to one specific service (e.g. a private Notion workspace, a particular local model, one company's internal MCPs)
- It is not a gstack-specific role skill (those live in `~/gstack/.agents/skills`)

**Do NOT promote:**
- One-off experiment skills
- Skills that only make sense inside one repo
- Skills the user is still heavily iterating on

When in doubt, ask the user: "This looks useful — do you want to promote it to the central cross-tool repository so it's available in Grok, Codex, Gemini etc.?"

## After Any Change

Always run `sync-all` (or call the promote flow) so the user sees the effect immediately in all their agents.

If `status` reports real-entry conflicts or wrong links, inspect and reconcile them
before claiming full synchronization. Preserve divergent content in a backup outside
all auto-discovered skill directories.

## Example Conversation Flow

User: "I just made a really good academic-verify skill in Codex, can you make it available everywhere?"

You:
1. Call the promote command for "academic-verify"
2. Report success
3. Tell the user it is now visible via Grok's paths, in ~/.claude/skills, Gemini, and symlinked into Codex

---

This skill + the script underneath is the long-term solution to the user's "I have to manually copy skills between all my agents" problem.
