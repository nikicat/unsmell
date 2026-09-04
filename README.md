# unsmell

A [Claude Code](https://claude.com/claude-code) skill that refactors the smells
out of your working changes before you commit them.

It reads what you've actually changed — unstaged, staged, and untracked — then
checks it against a catalog of smells: duplication, unnamed tuples and unnamed
returns, boolean and algebraic blindness, long functions and files, if-forests,
parameter bloat, data clumps, concept mixing, primitive obsession, speculative
generality.

Reading for flow finds smells in logic and walks past smells in types, so there
is a second pass that ignores the prose entirely: every field, parameter, return
and element type gets written down next to what the value actually *is*. Where
that sentence says more than the type does — `id: u64` for "the id tying a
response to its request", `&[&str]` for "paths relative to `$HOME`" — that's a
finding. Findings get triaged three ways:

- **Fixed** when there's one obviously correct, behaviour-preserving answer —
  including when the real fix lives outside the changeset (the other copy of the
  duplicated block, the type the data clump was implying).
- **Asked** when the design is genuinely a judgement call — public API changes,
  new modules, competing defensible options. One batched round of questions, with
  a recommendation, not a drip feed.
- **Kept** in the rare case where the smell is imposed from outside (framework
  signature, external spec, hot path) — with a comment *in the file* naming the
  reason and the trigger that ends it. That list of reasons is exhaustive:
  "only one call site", "it's obvious here" and "it's small" are not on it, and
  a Keep that appears only in the report is a silent skip rather than a Keep.

The survey covers the whole changeset every time; only the *fixing* is
proportional to the diff. Anything surveyed and not fixed shows up as **Noticed**
rather than going quiet. And when you point at a smell it missed, that names a
kind, not a line — it sweeps the changeset for every sibling before fixing, and
tells you the count.

Style comes from written rules only: `CLAUDE.md`, `CONTRIBUTING.md`, linter and
formatter configs. It deliberately does **not** imitate the surrounding code —
"the rest of the file does it this way" is not a justification if the rest of the
file is smelly.

## Install

In Claude Code (the repo is its own single-plugin marketplace):

```
/plugin marketplace add nikicat/unsmell
/plugin install unsmell@unsmell
```

For local development: `claude --plugin-dir /path/to/unsmell` (single session),
or `/plugin marketplace add /path/to/unsmell` (tracks your working tree).

`/unsmell` appears in the skill list after a restart.

## Use

```
/unsmell
/unsmell only src/parser.rs
/unsmell only changeset-local fixes
/unsmell duplication only, report only
/unsmell the whole auth module, aggressive
/unsmell just do it
```

Arguments are free text, not flags — they narrow the scope, filter the catalog,
or shift the fix/ask balance. See §1 of [SKILL.md](skills/unsmell/SKILL.md) for the full set.

## Not this

Not a bug hunter and not a linter — it's about shape, not correctness or
formatting. Run your test suite; it will too, and it reports honestly when
something fails.
