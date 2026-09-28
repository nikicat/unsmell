# unsmell

A [Claude Code](https://claude.com/claude-code) skill that refactors the smells
out of your working changes before you commit them.

It reads what you've actually changed — unstaged, staged, and untracked — then
checks it against a catalog of smells: duplication, unnamed tuples and unnamed
returns, boolean and algebraic blindness, long functions and files, if-forests,
parameter bloat, data clumps, concept mixing, primitive obsession, speculative
generality, generic machinery (caches, retries, bounded parallel maps) written
inline in domain code, and comments that narrate the code instead of stating its contract.

Functions that grew a second job get their own pass, because reading hunk by
hunk never sees them: every changed function is taken apart line by line and
each block tagged with one role — step, detail, decision, effect, assembly.
Two roles written inline is a finding (named steps with builder chains wedged
between them, a policy written inside the code that acts on it, a loop that
both selects and mutates), and so is the opposite: a function whose whole body
is one call to a callee only it calls.

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

Comments get a pass of their own, because both of the other reads walk straight
past them. A doc that narrates the body, restates the signature, or reads the
interface back is not a style slip to trim — it is a second copy of the code
with a shorter life, and it usually points at something structural: a doc that
can't say why the call exists in a line is describing a function that does too
much. So the fix goes to whichever is actually wrong, the comment or the thing
it sits above.

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

## Update

```
/plugin marketplace update unsmell
/plugin update unsmell@unsmell
```

Then restart Claude Code. The first command refreshes the marketplace (this
repo) so the second one sees the new version.

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
