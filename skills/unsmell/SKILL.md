---
name: unsmell
description: Find and fix code smells in the current working changes (unstaged + staged + untracked) — duplication, unnamed tuples and returns, primitive obsession and blind types, boolean and algebraic blindness, long functions/files, if-forests, parameter bloat, data clumps, concept mixing. Refactors what has one right answer, asks about what doesn't, and leaves a reasoned comment on the rare smell worth keeping. Use when the user says "unsmell", "/unsmell", "refactor this", "clean up my changes", "is this smelly", "code smells", "deodorize", or asks for a refactor pass before committing.
---

# Unsmell

Refactor the smells out of what you just wrote, before it becomes what someone
else inherits. Scope is the working changeset — not the repo.

## 1. Arguments

Anything after `/unsmell` narrows or steers this run. Free text, not flags —
read it as intent and apply it before anything else. Common shapes:

| The user says | You do |
|---|---|
| `only src/parser.rs`, `just the auth module`, `*.py` | Restrict the changeset (§3) to those paths. Still read them whole. |
| `only changeset-local fixes`, `don't touch other files` | §6 is off. A smell whose fix lives outside the diff becomes ASK or Noticed, never an edit. |
| `only duplication`, `just the long functions`, `skip naming` | Run the named rows of §4 only. |
| `report only`, `dry run`, `don't fix anything` | Everything becomes a report line. Zero edits, zero questions. |
| `fix everything`, `don't ask`, `just do it` | ASK collapses into FIX: pick the option you'd have recommended, apply it, and say what you chose and what the alternative was. |
| `ask first`, `check with me` | FIX collapses into ASK: propose, don't apply. |
| `the whole file`, `this module`, `the repo` | Scope becomes what they named instead of the changeset. Warn if it's huge, then do it. |
| `aggressive` / `light touch` | Move the bar for what's worth fixing, not the catalog. |

Combine freely — `/unsmell only src/db.rs, duplication only, report only` is three
constraints. If an argument contradicts a written style guide (§2), the user's
argument wins for this run; say so once.

Ambiguous argument? Take the reading a careful colleague would and state the
assumption in the report. Only stop to ask if getting it wrong would waste the
whole run. No arguments at all: full default behaviour, everything below.

## 2. Ground truth for style

Load, in this order, and treat as binding:

1. `CLAUDE.md` / `AGENTS.md` (repo and parent dirs)
2. explicit style docs: `CONTRIBUTING.md`, `STYLE.md`, `docs/style*`, `.editorconfig`
3. linter/formatter config: `ruff.toml`, `.eslintrc*`, `biome.json`, `rustfmt.toml`,
   `.golangci.yml`, `clippy.toml`, `pyproject.toml`, `tsconfig.json` (strictness flags)

**Surrounding code is not a style guide.** If the neighbours are smelly, do not
match them. "The rest of the file does it this way" justifies nothing on its own —
only a written rule does. Conversely, never violate a written rule to fix a smell;
if the guide mandates the smell, that is a Keep (§7).

If the language has an idiomatic construct for the fix, use it rather than
inventing one: TS discriminated unions, Python `dataclass`/`Enum`/`match`, Rust
`enum`, Go named structs + typed constants, Java sealed interfaces + records,
Kotlin sealed classes.

## 3. Collect the changeset

```sh
git status --porcelain=v1              # everything, incl. untracked
git diff HEAD                          # staged + unstaged vs HEAD, tracked files
git ls-files --others --exclude-standard   # untracked files — read them whole
```

If `git diff HEAD` is empty but the index isn't, fall back to `git diff --cached`.
Not a git repo, or the user named a target explicitly? Use what they named. If
there is no changeset at all, say so and stop — don't invent one.

**Read whole files, not hunks.** Half this catalog (duplication, long file, data
clumps, concept mixing) is invisible from a diff. For each touched file: read it
end to end, then grep the repo for the distinctive lines of anything the change
added — that's how you find the copy it was pasted from.

**Then inventory the declarations, separately and on purpose.** Reading for flow
finds smells in *logic* and walks straight past smells in *types*, because a
declaration is one line that looks fine. List every field, every parameter,
every return, every element type of a collection, and against each write what
the value actually is in the language of the problem. Where that sentence says
more than the type does, you have a finding:

```
pub id: u64                    → "the id tying a response to its request"   ✗
pub cwd: String                → "a filesystem path"                        ✗
rw: &'static [&'static str]    → "paths, absolute or ~/-relative to $HOME"  ✗
pub exit: i32                  → "an exit status, 77 meaning refused"       ✗
```

Do this before triage, for the whole changeset, even when you have already found
plenty to fix. It is a checklist rather than a judgement, so it does not get
tired the way reading does.

## 4. The catalog

| Smell | Tell | Usual fix |
|---|---|---|
| **Duplication** | Same shape twice non-trivially, or three times at all; two sites you'd have to edit together | Extract the shared thing. Merge only what changes *for the same reason* — coincidental resemblance stays apart. |
| **Unnamed tuple** | `return (a, b)`, positional bag, dict with implicit keys, `result[0]` at call sites | Named record / dataclass / struct / NamedTuple |
| **Boolean blindness** | `f(true, false)` unreadable at the call site; a bool param that only picks a branch | Enum, or two named functions. Kill the flag param. |
| **Algebraic blindness** | Impossible states are representable: co-dependent nullables, `status` string beside a payload, `(value, error)` both optional, "this field only matters when kind == X" | Sum type / discriminated union / tagged variant. Make the illegal state unspeakable. |
| **Primitive obsession** | `str`/`int`/`&[&str]` carrying domain meaning; a collection whose element type says nothing; two fields that must hold the same kind of value, typed independently; a value with an invariant the type does not carry ("validated", "resolved", "escaped"); re-validated at every use | Wrapper type; validate once at the boundary. A type earns its place by (a) linking the places that must agree and (b) saying what is inside |
| **Unnamed return** | A return type that names nothing — `-> String`, `-> Vec<(A, B)>`, `-> bool`. The function's name is not the value's name: at the call site the name is gone and only the type is left | Name the thing returned, not just the act of returning it |
| **Stringly-typed control flow** | Branching on magic strings | Enum / typed constants |
| **Long function** | Does more than one thing; needs section comments; nesting past 3 | Extract along the section comments; guard clauses to flatten |
| **Long file** | Several unrelated concepts sharing a filename | Split by concept, never by line count |
| **If-forest** | Cascading branches on a type tag; nested conditionals; flag-combination matrix | Dispatch table, polymorphism, or pattern match; early returns |
| **Parameter bloat** | 5+ params, or adjacent same-typed params easy to transpose | Parameter object — or the function does too much, split it |
| **Data clump** | The same 3+ arguments threaded through a series of functions | That cluster *is* a type. Name it, pass one thing. |
| **Concept mixing** | I/O + business logic + formatting in one unit; a module importing across three layers | Separate; push I/O to the edges, keep the core pure |
| **Mixed altitude** | One function alternating between orchestration and byte-twiddling | Lift details into named helpers so the caller reads as prose |
| **Temporal coupling** | Must call `init()`/`setup()` before the thing works | Constructor, builder, or context manager |
| **Speculative generality** | Unused param, single-implementation interface, config value that never varies, hook nothing calls | Delete it |
| **Misleading name** | Name says less (or other) than the body does; comment explains *what* instead of *why* | Rename; delete the comment the name replaced |

Not exhaustive. If it reads badly and you can say why in one sentence, it counts.

## 5. Triage

Every finding lands in exactly one bucket.

**FIX** — do it now, no asking. Mechanical, behaviour-preserving, one obviously
correct answer, blast radius you can see and verify: extract a function, name a
tuple, replace a bool param with an enum, collapse a duplicate, introduce the type
a data clump was already implying, delete dead flexibility.

**ASK** — one batched round of questions (`AskUserQuestion`), never a drip feed.
Ask when:
- it changes a public/exported/published API, or anything with callers you can't enumerate
- the fix requires inventing a domain concept whose meaning isn't derivable from the code
- two or more designs are genuinely defensible with different tradeoffs
- it needs a new file/module, or spans package boundaries
- the correct fix contradicts a written style rule
- the fix is large enough that the user might reasonably prefer a follow-up commit

Present each as: what's wrong → the options → which you'd pick. Don't ask open
questions you can answer yourself.

**KEEP** — rare. See §7.

**Survey exhaustively, fix proportionally.** These are different budgets and
collapsing them is how findings go missing. The survey covers the whole
changeset every time — a three-line change does not license a repo-wide rewrite,
but it does not excuse a partial look either. Only then decide volume: if the
list runs long, fix the top few and put *every* survivor in the report as
Noticed. A finding you chose not to fix is a line in the report; a finding you
never wrote down is a miss you will be told about later.

### 5.1 A smell you are pointed at is a class, not an instance

When the user names a smell — in an argument, or after a run that missed it —
they are describing a kind, and the instance they cite is the one that annoyed
them enough to mention. Before fixing it:

1. Sweep the whole changeset for every sibling of that kind. `grep` for the
   shape, not the identifier: other `(A, B)` returns, other `&[&str]` fields,
   other magic-string branches.
2. Fix the class in one pass.
3. Report the sweep — how many you found, where — so the count answers "did you
   get them all?" before it is asked.

Fixing only what was pointed at guarantees another round, and teaches the user
that pointing is how this gets done.

## 6. Fixing outside the changeset

Allowed and often required — the smell's *cause* frequently sits in code the diff
didn't touch: the other copy of the duplicated block, the shared helper the new
call site now needs, the type that should have existed before the clump appeared,
the function whose signature the new caller made unwieldy.

Bounded by:
- **Only where the fix belongs.** Following the root cause outward: yes. Editing
  unrelated smells you passed on the way: no, they're not in scope — mention them
  in the report if they're bad.
- **Update every caller.** Grep before you change a signature; leave nothing broken.
- **Refactors stay pure.** No behaviour changes riding along in a rename commit.
- **Verify.** Run the project's tests/typecheck/lint if they exist. If they don't,
  leave one runnable assert-level check behind for any non-trivial logic you
  restructured. Report honestly when something fails.

## 7. Keeping a smell on purpose

Legitimate when the smell is imposed from outside or the cure costs more than the
disease, and the reason must be one of these — the list is exhaustive, not
illustrative: a framework-dictated signature, a serialization shape you don't
own, generated code, a measured hot path, an FFI boundary, a deliberate mirror
of an external spec, or a written rule from §2 that mandates it.

**Anything else is a Fix you have not done yet.** These in particular are not
reasons, however reasonable they sound in the moment:

- "only one call site" / "only used here" — call sites multiply, and the second
  one arrives without re-reading your justification
- "it's destructured immediately" / "the name is right there" — that is the
  reader compensating for the type, which is the smell
- "it's obvious in context" — §2 already refuses this argument for style; it is
  no better here
- "it's small" / "it's private" / "it's just two fields" — size is not a reason,
  and the catalog has no size threshold
- "renaming would churn the diff" — churn is the cost of the fix, not a reason
  against it

If you find yourself writing a justification longer than the fix, the fix was
smaller than the argument against it. Just do it.

Never "it's fine" or "no time". Leave a comment in the file's comment syntax —
**a Keep that exists only in the report is not a Keep, it is a silent skip**, and
the comment is what makes it reviewable by the next person:

```
# smell: 7-arg constructor — kept, mirrors the upstream SDK signature 1:1.
# Fix when we wrap the SDK behind our own client.
```

Name the smell, the reason, and the trigger that ends it.

## 8. Report

Code first, then at most:

```
Fixed    path:line  smell → what you did
Asked    path:line  smell → the question (answers pending)
Kept     path:line  smell → why, and the trigger
Noticed  path:line  out-of-scope smell, untouched
```

Then the verification result (tests/typecheck: pass/fail/absent) in one line. No
essays. If the explanation is longer than the diff, the diff was wrong.
