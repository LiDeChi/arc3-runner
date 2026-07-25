---
name: archived-skills
description: "Manage the archive of skills that were moved out of active directories to reduce bloat. Skills are preserved (never deleted) in ~/.skills-archive/. This skill lets agents or users discover what was archived, inspect details, search by capability, and restore any skill back to the central ~/.skills/ repository (so it becomes available everywhere via sync)."
user-invocable: true
allowed-tools: Read, Bash, Glob
---

# Archived Skills Manager

You are the guardian of archived skills.

**Core rule**: Skills are **never deleted**. They are only moved to `~/.skills-archive/<skill-name>/` when we want to slim down the active skill set (`~/.grok/skills`, `~/.agents/skills`, etc.).

All original content (SKILL.md + scripts, assets, etc.) remains fully intact and readable.

## Archive Location
- Main archive: `~/.skills-archive/`
- Every archived skill is a full directory: `~/.skills-archive/<skill-name>/SKILL.md`
- There is also `~/.skills-archive/ARCHIVE_README.md` with human-readable notes.

## Available Commands

Run via Bash tool (or directly when acting as this skill):

```bash
# List all archived skills with short descriptions
~/.skills/archived-skills/scripts/list.sh

# Search archived skills by keyword (name or description)
~/.skills/archived-skills/scripts/search.sh "keyword"

# Show full info + path for one skill
~/.skills/archived-skills/scripts/info.sh <skill-name>

# Restore a skill back to central (recommended way)
~/.skills/archived-skills/scripts/restore.sh <skill-name>
```

After restore:
1. The skill will be copied into `~/.skills/<skill-name>/`
2. Run the central sync so it appears everywhere:
   ```bash
   ~/.skills/sync-skills/scripts/sync.sh sync-all
   ```
3. The skill is now treated as a normal central skill (symlinks will be created in Grok, Claude, Gemini, Codex layers).

## How Agents Should Use This

- If a user asks for a capability that used to exist but is no longer available in normal `list` or discovery, call this skill first.
- Example triggers: "where is the sora skill", "I need manim support", "restore notebooklm", "what skills did we archive".
- You can always directly Read `~/.skills-archive/<name>/SKILL.md` if you know the exact name.
- Never assume a skill is gone forever — check here.

## Implementation Notes (for this skill itself)

- Use Bash + Read + Glob to inspect `~/.skills-archive/*/SKILL.md`
- Extract `name:` and `description:` from frontmatter for listings.
- For restore: `cp -a ~/.skills-archive/<name> ~/.skills/<name>`
- Be helpful and precise about paths so the agent (or user) can also manually inspect or copy if needed.

## Maintenance

This skill itself lives in the central repo (`~/.skills/archived-skills/`).

If you archive more skills in the future, just move the full directory into `~/.skills-archive/`. This skill will automatically discover them on next `list` or `search`.

If you want to permanently bring something back into active use long-term, restore it and then keep it in central (do not re-archive it casually).

---

**Archive is the "cold storage" of skills.** This skill is the index + recovery interface. Use it whenever an agent wonders "did we used to have X?".