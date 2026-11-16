---
name: unsmell
description: Find and fix code smells in the current working changes (unstaged + staged + untracked) — duplication, unnamed tuples and returns, primitive obsession, boolean and algebraic blindness, long functions and files, if-forests, parameter bloat, data clumps, missing receivers (sibling functions that all take the same context and want to be methods of one type), misplaced rules (a constant, check or derivation living outside the type it serves), request-scoped values threaded through methods, unparsed input (raw strings, key or position access, too many CLI flags), split protocols (a literal that a writer and a reader must both spell the same way), repeated derivations, concept mixing (I/O, rules and formatting in one function, or a rule written inline) and mixed altitude (orchestration interleaved with setup detail), inline generic machinery (memoizing, bounded parallel maps, mailboxes, traversals, retries, caches), oversized locks, narrating doc comments, garbled sentences, and restated code (docs that restate the code instead of linking its design decision). Refactors what has one right answer, asks about what doesn't, and leaves a reasoned comment on the rare smell worth keeping. Use when the user says "unsmell", "/unsmell", "refactor this", "clean up my changes", "is this smelly", "code smells", "deodorize", or asks for a refactor pass before committing.
---

# Unsmell

Refactor the smells out of what you just wrote, before it becomes what someone
else inherits. Scope is the working changeset — not the repo.

## 1. Arguments

Anything after `/unsmell` narrows or steers this run. Free text, not flags —
read it as intent and apply it before anything else. Common shapes:

| The user says | You do |
| -- | -- |
| `only src/parser.rs`, `just the auth module`, `*.py` | Restrict the changeset (§3) to those paths, and read them whole. Only their changed lines are fixed (§5, "Read whole files, fix the changed lines"). |
| `only changeset-local fixes`, `don't touch other files` | §6 is off. A smell whose fix lies outside the diff becomes an ASK or a PLAN, and it is edited only when the user accepts the ASK. |
| `only duplication`, `just the long functions`, `skip naming` | Run the named rows of §4 only. |
| `report only`, `dry run`, `don't fix anything` | Everything becomes a report line. Zero edits, zero questions. The run still writes its files (§3.0), with the decisions it would have made, and stops before the editors. |
| `patches only`, `don't merge` | Run §3.0 up to the patches (§3.0, step 5) and stop: nothing is merged into the working tree, nothing is re-checked, and no question is asked. The report lists each task with its patch. |
| `fix everything`, `don't ask`, `just do it` | §3.0, step 6 accepts every FIX, ASK and KEEP change without asking. For an ASK, apply the option you'd have recommended, and say what you chose and what the alternative was. |
| `ask first`, `check with me` | The default already asks about every FIX, ASK and KEEP change (§3.0, step 6). |
| `the whole file`, `this module`, `the repo` | Scope becomes what they named instead of the changeset, and every line of it is in scope (§5, "Read whole files, fix the changed lines"). Warn if it's huge, then do it. |
| `aggressive` / `light touch` | Move the bar for what's worth fixing, not the catalog. |
| `threshold 6`, `bar 3` | Set the value threshold of §5.0 for this run. |

Combine freely — `/unsmell only src/db.rs, duplication only, report only` is
three constraints. If an argument contradicts a written style guide (§2), the
user's argument wins for this run; say so once.

Ambiguous argument? Take the reading a careful colleague would and state the
assumption in the report. Only stop to ask if getting it wrong would waste the
whole run. No arguments at all: full default behaviour, everything below.

## 2. Ground truth for style

Load, in this order, and treat as binding:

1. `CLAUDE.md` / `AGENTS.md` (repo and parent dirs)
2. explicit style docs: `CONTRIBUTING.md`, `STYLE.md`, `docs/style*`,
   `.editorconfig`
3. linter/formatter config: `ruff.toml`, `.eslintrc*`, `biome.json`,
   `rustfmt.toml`, `.golangci.yml`, `clippy.toml`, `pyproject.toml`,
   `tsconfig.json` (strictness flags)

**Surrounding code is not a style guide.** If the neighbours are smelly, do not
match them. "The rest of the file does it this way" justifies nothing on its own
— only a written rule does. Conversely, never violate a written rule to fix a
smell (§7).

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

If `git diff HEAD` is empty but the index isn't, fall back to
`git diff --cached`. A target the user named narrows or replaces it (§1). Not a
git repo? Use what the user named. If there is no changeset at all, say so and
stop — don't invent one.

### 3.0 Who runs the survey, and the files each step leaves

The agent that wrote the code is the worst one to survey it. It remembers why
each line is there, and those reasons hide the smells. It also tires on a big
changeset: it narrows the survey to the code it thinks of as new, and it writes
inventories from memory. So every survey, research, editor and re-check agent is
a fresh subagent, and the main agent triages, reviews and merges.

Each step writes its result to a file in the run directory,
`$(git rev-parse --git-dir)/unsmell/<run>/`, where `<run>` is the start time as
`YYYYMMDD-HHMMSS`. The files are the run's record: the user can review what was
found and decided before looking at any edit, and the next step reads the file,
not a summary in an agent's reply. They live outside the working tree, so they
never become part of the next run's changeset.

1. **The main agent splits the changeset into batches** and writes them to
   `batches.yaml`, one entry per batch: its id (`b1`, `b2`, …) and its paths. A
   batch is a few related files that one agent can read whole: about five, or
   about 1,500 lines. A file goes in the same batch as its tests, and a moved
   file goes with the place it moved from. Every file of the changeset is in
   exactly one batch, tests and moved files included. Nothing counts as "only
   moved" or "only edited". The one exception is the plan file, such as
   `TODO.md` (§5, "PLAN").

2. **One survey agent per batch, all in parallel.** Each is a fresh agent, never
   a fork: a fork inherits the main agent's context, and that context is exactly
   what blinds it. Its prompt gives the run directory, the batch's id and paths,
   the style ground truth from §2, any arguments from §1, and an instruction to
   read this skill's §3 to §5 and to run every pass of §3.1 on the batch. It
   edits no code. It writes two files:

   - `inventory/<batch>.md`, its inventory lines, one per item, each starting
     with `path:line`: the declarations, the locks and what each guards, the
     parameter tables, the rules and where each lives, the request-scoped
     values, the roles, the inputs at the edge, the repeated literals and
     expressions, the facts in comments, and the doc items it checked;
   - `findings/<batch>.yaml`, in the form below: the files it read whole, the
     ones it could not read and why, and its findings.

3. **One cross-file agent.** It is also fresh. It gets the inventory files, not
   the code, and the changeset's file list. It looks only for what no single
   batch can see:

   - a literal that two batches spell (a split protocol);
   - a derivation written in two batches;
   - a fact stated in two batches' comments;
   - a value that two batches' functions take as a parameter (a missing
     receiver).

   It writes `findings/cross.yaml`, in the same form. A finding that a batch
   already reported within its own files is still listed, with the batch
   finding's id under `same`.

4. **The main agent triages** every finding by §5 to §7 and writes
   `decisions.yaml`. It triages, rather than a subagent, because only it knows
   what the user has already decided or rejected in this conversation. It reads
   each finding's lines from disk before it decides. A survey agent can be
   wrong, and that is a reason to check the finding, not to drop it. Every
   finding but a discarded one gets a `change`. Findings whose `reach` overlaps,
   or that `same` links, share one change, whose fix makes the shape that all of
   them ask for. When that code has a second defensible shape that goes further,
   and only the first is a FIX, the second is its own change stacked on the
   first (`after`): its patch starts from the first change's result and holds
   only what the second shape adds. `after` marks only such an alternative. It
   never orders two fixes that touch the same file: each patch starts from the
   base, so that each can be accepted or rejected alone (§3.0, step 6). Two
   changes never each make part of one fix, and an alternative never leaves out
   the docs and tests that the first change fixed. Two designs that compete,
   rather than one going further, are the options of one ASK change: its patch
   makes the one you'd pick, and its question names the other.

5. **One editor agent per change, all in parallel, each in its own worktree.**
   Each is fresh. The worktree starts from a snapshot of the working tree, so it
   holds the whole changeset, staged, unstaged and untracked, and the user's
   index is never touched:

   ```sh
   run=$(git rev-parse --git-dir)/unsmell/<run>
   tree=$(GIT_INDEX_FILE=$run/index sh -c 'git read-tree HEAD && git add -A && git write-tree')
   base=$(git -c commit.gpgsign=false commit-tree "$tree" -p HEAD -m "unsmell base")   # once per run
   git worktree add --detach "$run/worktrees/<change>" "$base"   # once per change
   ```

   Every commit the run makes is a temporary one, such as `$base` here or a
   stacked change's start, and is made the same way: `git commit-tree` with
   `-c commit.gpgsign=false`, never `git commit`. Such a commit is never pushed.
   Signing one would wait on the user's signing agent each time, and
   `git commit` would run the project's hooks and move a branch.

   **The build check** is the project's fastest command that fails on code that
   does not compile or type-check: `cargo check`, `go build ./...`,
   `tsc --noEmit`, a Python import or `compileall`. An editor never runs the
   test suite, a linter, or a build in each feature set: a dozen editors that
   each rebuild the project in parallel cost more than the fixes. The one
   exception is a pinning test that the editor wrote (§6, "Pin before you
   move"). It is cheap and targeted, so the editor runs that one test, before
   its edit and after it, as part of the build check. The editors of one run
   share one build directory, such as `CARGO_TARGET_DIR=$run/target`, so that
   dependencies build once. The full check runs once, on the accepted changes
   (§3.0, step 6).

   A stacked change waits for the change it is `after`. Its worktree starts from
   a commit of that change's patch on `$base`, and its patch is the diff from
   that commit.

   The editor's prompt gives the worktree path, the change's findings and
   decision entries, the style ground truth from §2, the user's decisions in
   this conversation that bear on the change, and an instruction to read this
   skill's §5 and §6. It edits only inside its worktree, makes the fix in the
   final shape the findings name (§5, "A fix is finished or not made"), and runs
   the build check above. Before it finishes, it reads its own diff against the
   catalog (§4), because nothing else will until the re-check.

   **A change that writes or rewrites a doc gets its design link first.** Before
   its editor starts, a fresh research agent runs §3, "Design link" for each
   item whose doc the change touches, and writes `design-links.md` in the run
   directory: per item, the current doc, the verdict (§3, "Design link"), the
   (b) facts it keeps, the proposed doc, and the quoted passage of the design
   record with its path and line. The main agent checks each proposal against
   its quote before the editor gets it, and asks the user about every gap whose
   reason would be a guess. When the run may not ask (`patches only`,
   `fix everything`, or a run that no user can answer), such a gap becomes a
   PLAN entry that asks for the record, and the editor writes no reason for that
   item. The editor writes docs only from that file, the docs of the items it
   adds included; a doc that no entry backs is a smell the editor added.

   When it is done, the main agent saves the patch and removes the worktree:

   ```sh
   git -C "$run/worktrees/<change>" add -A
   git -C "$run/worktrees/<change>" diff --cached --no-renames "$base" > "$run/fixes/<change>.patch"
   git worktree remove --force "$run/worktrees/<change>"
   ```

   Changes whose decision is not FIX get a patch too. A KEEP's patch is the Keep
   comment in §7's form. An ASK's patch shows what it proposes, and a PLAN's or
   a SKIP's what it would have cost. An editor that finds the change cannot be
   done as described says so, and the main agent records that in the change's
   decision entries instead of a patch.

6. **The user reviews the changes one at a time.** One change mixed into twenty
   is hard to judge; one at a time, each gets a real verdict. The FIX, ASK and
   KEEP changes are reviewed, highest score first, and an alternative comes
   right after the change it is stacked on. The user reviews in the main
   worktree, where their editor is already open. The review borrows the index:
   it holds the snapshot with every change accepted so far, and the working tree
   adds the change under review, unstaged, so that `git diff` and the editor's
   source control view show exactly that change. The user's own index is saved
   first and given back at the end, so the borrowing never loses what they
   staged:

   ```sh
   # once, before the first change; stop if the working tree moved since $base
   test "$(GIT_INDEX_FILE=$run/index sh -c 'git read-tree HEAD && git add -A && git write-tree')" = "$(git rev-parse "$base^{tree}")"
   git update-ref "refs/unsmell/<run>/index" "$(git -c commit.gpgsign=false commit-tree "$(git write-tree)" -m "unsmell index")"
   git update-ref "refs/unsmell/<run>/base" "$base"
   git read-tree "$base"

   # each change
   git apply "$run/fixes/<change>.patch"
   ```

   While a `refs/unsmell/*/index` ref exists, some run has not given the index
   back. A new run stops at its start and asks the user to finish or restore
   that one (§3.0, step 8); the main agent prints the restore commands when the
   review begins, so that a run that dies can be restored by hand. The working
   tree holds the user's own untracked files, so nothing here runs `git clean`
   or `git reset --hard`. A patch that no longer applies, because an accepted
   one changed its lines, is redone by hand on the current code, to the same
   final shape, before it is shown.

   For each change, the main agent prints the change's findings (row, claim,
   decision and score) and `git apply --stat` of its patch, then asks one
   question (`AskUserQuestion`) with four answers. The question holds everything
   the user needs to find the change, because the question box covers the text
   printed before it. It names the change by what it does, not only by its id,
   and says that it is the unstaged diff (`git diff`, and `git status` for a new
   file). The `accept` answer's preview shows the findings and the `--stat`. The
   user may edit the change in place before answering; the accept takes their
   edit with it.

   - **accept**: stage the paths the patch touches. The index then holds every
     accepted change, and the next change is shown on top of it:
     `git apply --numstat "$run/fixes/<change>.patch" | cut -f3 | xargs git add -A --`.
   - **reject**: the change is not wanted (§5, "Every finding ends in a
     bucket"). The patch stays in the run directory, so that it can be
     reconsidered later.
   - **plan**: the intention is right, but the implementation is not. Write a
     plan entry (§5, "PLAN") whose fix is the direction from the user's note,
     with the patch's path as the alternative already tried. When the note is a
     lasting decision rather than work to do ("settings go through a schema
     library"), it goes where the project keeps its decisions, such as its ADRs
     or design docs, instead.
   - **later**: nothing is applied (§5, "Every finding ends in a bucket").

   Every answer but accept takes the change out of the working tree again with
   `git apply -R` of its patch. When the user edited it and the patch no longer
   reverses, `git restore` its paths from the index and delete the files that
   the patch added.

   Each verdict and the user's note go into the change's entries in
   `decisions.yaml`, as `verdict` and `note`. The SKIP changes are not reviewed;
   their patches stay in the run directory, and the report lists them.

   The PLAN changes come last, and each asks one question before its plan entry
   is written: plan it, or **implement it now**. Implementing it now runs an
   editor (§3.0, step 5) in a worktree that starts from a commit of the borrowed
   index
   (`git -c commit.gpgsign=false commit-tree "$(git write-tree)" -p "$base"`),
   so that a change too large to judge against the base is made on top of
   everything accepted so far. Its patch is then reviewed like the others.

   **A run that no user can answer**, such as a headless one, runs as
   `patches only` does (§1): every patch is written, and nothing is reviewed or
   merged. Every ASK becomes a PLAN entry that records its options.

   After the last verdict, the main agent runs the project's full check once on
   the result: its tests and linters. A failure is fixed in the change whose
   patch caused it.

7. **A fresh re-check agent, until one finds nothing.** It gets the run
   directory, the files that the accepted changes touched, and the accepted
   entries of `decisions.yaml`. It runs §3.1 on those files, because the fixes
   are the newest code and the least read, and it writes
   `findings/recheck-<n>.yaml`. Its findings go back to §3.0, step 4, and the
   fixes that come out of them go through steps 5 and 6 and get a new re-check
   agent. Their editors start from a commit of the borrowed index, as an
   implemented PLAN change does, and their patches are diffs from that commit.
   Stop when a re-check returns no finding that the run would fix, or after
   three re-checks; then every finding still open is planned (§5).

8. **The index goes back to the user, with every accepted line staged.** The
   user has read every line of an accepted change, so it is staged, even where
   it lands on code they had not staged: a line left unstaged would be reviewed
   twice. Everything else stays as they left it. A three-way merge from the
   snapshot computes that index: the user's index is one side, the accepted
   state the other, and `-X theirs` gives an accepted line the place of the
   unstaged one it replaced. This step also runs when the run stops early, and
   the main agent runs it by hand for a run that died:

   ```sh
   i0=refs/unsmell/<run>/index base=refs/unsmell/<run>/base
   out=$(git merge-tree --write-tree --name-only -X theirs --merge-base="$base" "$i0" "$(git write-tree)")
   git read-tree "$(echo "$out" | head -1)"
   echo "$out" | sed -n '2,/^$/p' | sed '/^$/d' | xargs -r git reset -q "$i0" --
   git update-ref -d "$i0" && git update-ref -d "$base"
   ```

   The last but one line handles what the merge cannot: a fix in a file the user
   never added, which was untracked. Staging the fix would stage the whole file,
   so the file keeps the fix and stays untracked, and the report lists it.

A findings file:

```yaml
read: [seb.py, test_seb.py]       # the files read whole
unread: []                        # {path, why} for each file that could not be read
findings:
  - id: b1-3                      # the file's name, then a number
    at: [seb.py:305-311]          # the lines the finding is about
    reach: [seb.py:285-327]       # the lines its fix would edit, as far as can be seen
    row: missing receiver         # the catalog row (§4)
    claim: session() and sync() both take bank, and main calls one after the other
    fix: both become methods of Sync(bank, ledger, start), built once in main
    decision: FIX                 # proposed, by §5: FIX, ASK, KEEP, PLAN, SKIP or DISCARD
    score: 7                      # proposed, by §5.0
    reason: the full tell, since sync passes bank straight down
    same: []                      # ids of findings about the same code (cross-file, re-check)
```

`fix` names the final shape of the code (§5, "A fix is finished or not made"). A
`claim` that rests on what the changeset under review did says so and names
where: "the changeset removed `nameHasOwner(frontConn, …)` at `prompter.go:87`",
never "this change". A reviewer reads each patch alone, with the changeset
beside it, and "this change" names neither. `decision` and `score` are the
survey agent's proposal. The main agent's `decisions.yaml` has one entry per
finding of every findings file:

```yaml
- id: b1-3
  decision: FIX                   # final, by §5
  score: 7
  reason: the full tell; the user named no other shape
  change: c2                      # all but DISCARD: findings with one change get one patch
  after: [c1]                     # a stacked change only: the changes its patch starts from
  verdict: plan                   # step 6: accept, reject, plan or later
  note: use pydantic-settings     # the user's reason or direction, when given
```

Every file is YAML in block style, as above, and must parse. Quote a value that
holds `: `, `#`, `{`, `}`, `[` or `]`. Where the main agent overrules a
proposal, its `reason` says why. A finding with no entry is open work (§5,
"Every finding ends in a bucket").

A changeset of one file, under about 100 changed lines, may skip the
orchestration. The main agent then surveys and edits itself, and still writes
every file and every patch, with `b1` as its one batch. It says so in the
report. Nothing else skips it. Time, cost or a budget is not a reason: a run
that cannot afford the survey says so at the top of its report and is incomplete
(§8).

### 3.1 What each survey agent runs on its batch

**Read whole files, not hunks.** Half this catalog (duplication, long file, data
clumps, concept mixing) is invisible from a diff. For each touched file: read it
end to end, then grep the repo for the distinctive lines of anything the change
added — that's how you find the copy it was pasted from. Every read is from
disk, never from memory of an earlier read.

**Declaration inventory.** Then inventory the declarations, separately and on
purpose. Reading for flow finds smells in *logic* and walks straight past smells
in *types*, because a declaration is one line that looks fine. List every field,
every parameter, every return, every element type of a collection, and against
each write what the value actually is in the language of the problem. Where that
sentence says more than the type does, you have a finding:

```
pub id: u64                    → "the id tying a response to its request"   ✗
pub cwd: String                → "a filesystem path"                        ✗
rw: &'static [&'static str]    → "paths, absolute or ~/-relative to $HOME"  ✗
pub exit: i32                  → "an exit status, 77 meaning refused"       ✗
```

Do this before triage, for the whole changeset, even when you have already found
plenty to fix. It is a checklist rather than a judgement, so it does not get
tired the way reading does.

**Lock inventory.** Then inventory the locks, and what each one guards. For
every mutex, read-write lock, `synchronized` block or similar guard in a touched
file, write the fields or values that only it protects. The declaration
inventory judges each field on its own line, so it walks past a lock whose job
has shrunk. Each of these is a finding:

- it guards one scalar, such as a counter, a flag or a pointer: use the
  language's atomic type (`atomic.Int64`, `AtomicU64`, `AtomicBoolean`);
- it guards nothing that is still shared: delete it;
- it guards a value that is read far more often than written, and is replaced
  whole: use an atomic pointer to an immutable value, or the repo's latest-value
  cell.

**Narrowed fields.** Re-check what serves a field whenever the field narrows.
When a change shrinks what a field holds, re-check everything that exists only
for it: its lock, its constructor argument, its cleanup and its helper methods.
Examples are a map that becomes one counter, or a list that becomes one value.
Compare with `git show HEAD:<file>`, and with what the changeset itself first
wrote. A narrowing usually arrives in an edit made for another reason, such as a
rename or a lint fix, so nobody re-reads what surrounds the field. This is the
pass-through rule (§3, "Role pass") applied to state.

**Inventory files.** Write every inventory down in the batch's inventory file,
as §3.0, step 2 lists.

**Parameter table.** Then group the functions by the parameters they share. A
free function reads fine alone; the smell is only visible across siblings, when
the same context arrives as arguments again and again. For every file, write a
table with one row per function and one column per parameter. Name each column
by what the value is, not by its spelling: `buckets`, `store` and `db` are one
column when they hold the same store. Then look down the columns:

```
answer(request, buckets, console_user)
create_bucket(request, buckets, bucket)       buckets ×4, console_user ×1 but
heartbeat(request, query, buckets, bucket)    only to pick the user for the others
serve(port, buckets, console_user)            → struct Api { buckets, console_user }
                                              request ×3 is the input: it stays
```

A column is a finding when two or more functions take it and it is context, not
the input being worked on: a store, a client, a connection, a config, a
registry, a logger, a callback. The input (the request, the line, the event)
stays a parameter at this level; §3, "Lifetime pass" says when the values
threaded beside it become an object of their own. Two more tells make it
certain: one sibling passes the value straight down to another, and the value is
captured once by a closure or a thread and then handed to every call. The fix is
the receiver the functions were missing: the shared values become its fields,
the functions its methods, and the caller builds it once. Use the language's
form for state plus behaviour: a struct with an impl block, a class, a Go type
with methods, a closure over the values, a module-level object. A single shared
column counts when it is real state; the catalog's threshold for a data clump is
for values that travel together, not for state that every function reaches into.

**Placement pass.** Then place every rule on the type it is about. For each
constant, check, default and derived value in the changeset, write the type
whose invariant it serves, then where it lives. A lifetime, an expiry check or a
storage key that belongs to one type but is written in another is a finding,
however short it is: the next change to that type will miss it. Three tells find
the rest:

- a method that never uses its receiver;
- a free function whose main input is one type, and which only reads it or
  formats it;
- a body that touches another type's fields or constants more than its own.

The fix moves the rule onto its owner, as a method, a constant on the type or
its formatting method. A function that uses neither its receiver nor any one
type belongs with what it builds, or free at the module level. It does not
belong as a method of whatever happened to call it.

**Lifetime pass.** Then sort the values by how long they live. Mark each field,
parameter and local of the changeset as one of three: built once per process
(config, clients, stores), once per request or event, or once per item. Two
findings follow:

- A per-request value other than the input itself (a user resolved from the
  request, a deadline, a transaction) that two or more functions take as a
  parameter: the request is missing an object of its own that holds it. Name it
  for what it is, not for what it does, and the next layer up often needs one
  too. It is the parameter table at request scope, which the per-file table
  misses because the functions often sit on a receiver already.
- A type with fields of two lifetimes, such as an identity plus a session's
  expiry, or a config plus a cache. Split it, so that neither part can outlive
  or outrun the other.

**Input pass.** Then list every input at the program's edge. Write down each way
data enters:

- command-line arguments and environment variables;
- config files;
- request paths, queries and headers;
- database rows;
- external API bodies;
- files read.

Each one becomes a domain type in the first function that touches it. A finding
is any of these:

- raw text or a number passed beyond that first function;
- dynamic access by key or position (`value["key"]`, `row[0]`, `dict.get("k")`),
  which is a schema the code depends on without saying so;
- a value validated later than the edge, or validated again at each use;
- more than about five settings at one edge, which is a config file the program
  has not been given.

Parse into the type at the edge, and keep the raw form only where it is passed
on unchanged. When the edge needs validation, versioning or a schema that a
library provides, the fix is that library (§5, "A library, not a home-grown
one").

**Repeats.** Then look for one name, one expression or one fact in two places.
Three greps over the changeset:

- **Literals:** every string or number literal that appears two or more times,
  and every exported constant whose only use is to be matched or formatted by
  another module. Each is one protocol split across two places that must agree:
  a cookie name written in one place and read in another, a route path in the
  router and again in a link, a query parameter name in its writer and in its
  reader. The fix is one type that both writes and reads it (an enum with parse
  and render, a struct that serializes both ways), and a round-trip test that
  writes with one side and reads with the other.

- **Expressions:** every expression shape that recurs once identifiers are
  normalized: a path joined to a directory, a URL prefix, a lookup and the
  failure check after it, a value built the same way in each test. A derivation
  written twice is a rule with no name, and it drifts the first time one copy
  changes. Give it a named function on the type it derives from.

- **Facts in comments:** every identifier that a doc or comment names (an error
  sentinel, a constant, a type, a method) and every rule that a doc explains.
  Grep the changeset's comment lines, and the docs outside the code (ADRs,
  invariant lists, READMEs), for each one. Two comments that say the same thing
  about it are one fact with two copies, and the second copy goes stale at the
  next change. Typical cases:

  - an error contract repeated up a call chain, where the checker, its caller
    and the caller's caller each list the same sentinels and conditions;
  - why an error happens, explained on the sentinel and again on each function
    that returns it;
  - a rule explained on its type and again on a method, a caller or a test;
  - a reason given in the code and again in a design doc or an invariant list.

  Each fact gets one owner. A design decision is owned as §3, "Design link"
  says. A code fact is owned by the item that decides it. A sentinel owns what
  it means. The function that classifies an error owns which one it returns, and
  in which order. The function that marks an error fatal owns that it is fatal.
  Every other site points to the owner ("Errors as checkPrefix does") and adds
  only its own facts.

None of these shows up in a read for flow, because each copy is short and looks
right where it stands.

**Generic machinery.** Then look for generic data structures and algorithms
written inline in domain code. A mechanism hand-built inside a domain function
(a cache, a queue, a traversal, a concurrency pattern) is two concerns in one
body. The reader has to verify the mechanism before reaching the domain logic,
and each copy carries its own subtle bugs. It hides in plain sight because it
looks like ordinary code, in any language. Sweep the changeset for these shapes
by what the code does, not by its names:

| What the body does | The generic thing it is |
| -- | -- |
| keeps a table of in-progress or finished results per key; later callers wait for or reuse the first | memoize / compute once per key |
| starts work for every item with at most N running, collecting results by index | ordered parallel map with bounded concurrency |
| packs a request with a reply slot, sends it to the owner of some state, and waits with a timeout or cancellation | a call into an actor / mailbox |
| stores a value and wakes one consumer, overwriting what it has not taken yet | latest-value cell / conflating channel |
| races a result against cancellation or a timeout by hand | the codebase's or runtime's await-with-cancel helper |
| copies a collection while skipping, grouping, indexing, partitioning or deduplicating, with no effect in the loop | the standard library's filter / group-by / associate / unique operations |
| walks a graph of dependencies with a visited set, or orders items by them | a traversal / topological sort |
| loops with a sleep that grows, a counter and a give-up condition | retry with backoff |
| evicts by age or size, keeps the N most recent, merges overlapping ranges, keeps a sorted buffer | a cache, a ring buffer, an interval set, a priority queue |

A mutex around one scalar is the lock inventory's case, above. A loop that
selects and, in the same body, mutates state with what it selected is the Role
pass's case (§3, "Role pass").

For each hit, look for an existing implementation in this order: the repo's own
utility module, the language's standard library, then the ecosystem's well-known
supplementary libraries. Some places to look:

- Rust: std, `itertools`, `futures` (`buffered`, `join_all`), `tokio::sync`
  (`watch`, `oneshot`, `mpsc`), `once_cell` or `OnceLock`.
- TypeScript/JavaScript: `Map`/`Set`, array and iterator helpers,
  `Promise.all`/`Promise.race`, `AbortSignal`, a small limiter such as
  `p-limit`.
- Kotlin: stdlib collection operations (`groupBy`, `associateBy`, `partition`),
  coroutines (`Channel`, `StateFlow`, `async`/`awaitAll`, `Semaphore`,
  `withTimeout`).
- C++: `<algorithm>` and ranges, `std::future`/`std::promise`, `std::call_once`,
  the containers.
- Python: `functools.cache`, `itertools`, `collections`, `asyncio` (`gather`,
  `Semaphore`, `Queue`, `wait_for`).
- Go: the standard library, `golang.org/x/sync` (`errgroup`, `singleflight`).

Which of these a fix may adopt without asking is §5, "A library, not a
home-grown one".

Check that the semantics match before reusing one. For example, a single-flight
helper shares only an in-flight call and forgets its result, so it is not
memoization. If nothing fits, extract a small generic type or function into the
repo's utility module, in the language's own idiom (generics, templates, type
parameters). Give it its own tests, with the race checker or sanitizer the
language offers and a fake clock for anything concurrent. Then replace every
site in the changeset that has the same shape; one extraction usually finds two
or three callers. The domain code left behind reads as its domain: a fetch, a
decision, a state change.

**Role pass.** Then take every changed function apart by what its lines do. The
declaration inventory and the doc read both judge one line at a time, and a flow
read judges each hunk on its own ("this edit is small"). None of them sees a
function that grew a second job, one small edit at a time. List every function
the changeset added or changed, with its whole body (`git diff HEAD -W` prints
each touched function in full). Tag each block of statements with exactly one
role:

- **step**: a call to a named thing that the function orders ("create the file",
  "install the layers", "announce the path");
- **detail**: building or configuring a value in place (builder chains, format
  strings, filter parsing, closures handed to a library);
- **decision**: a policy written inline (a heuristic, a string match on a
  message, a threshold, a classification of an error or a value);
- **effect**: I/O, a write, a log line, a send, a state change;
- **assembly**: shaping the result that is returned.

Each of these is a finding:

- **Steps and details mixed** (mixed altitude): the function orders named steps,
  and between them sit blocks of detail. Extract each block into a named
  `build_…`/`make_…` helper, and move its comment with it, so the function reads
  as its steps.
- **A decision inside assembly or an effect** (concept mixing): the function
  builds a result or does I/O and also holds the rule that picks the branch. The
  rule gets its own named predicate or classifier. Find the siblings before you
  name it: when other rules of the same kind already live in named helpers
  (`looks_like_range_limit`), a new inline rule (`message.contains("batch")`) is
  a finding however short it is, and its helper goes next to theirs.
- **The diff added a role**: compare with `git show HEAD:<file>`. A function
  that had one role and now has two is a finding even when every added line is
  fine on its own. Growth is how these arrive.
- **No role of its own** (a pass-through): the whole body is one call, passing
  the parameters on, reshaped at most, plus a trivial result (`Ok(())`). One
  call is not the cleanest shape: it is two names for one thing, and the reader
  hops for nothing. Grep the callee's callers: when this function is the only
  one, merge them. Put the body where the name is required (a trait method, a
  public entry point) and move the callee's doc with it. Shrinkage is how these
  arrive: a refactor removes the checks or conversions that surrounded the call
  and leaves the shell. Mark such a function `pass-through` in the role list,
  never `step`. A wrapper that adds something is not one: a default argument, a
  narrower type, a lock, a trait or visibility boundary the callee cannot sit
  behind itself.
- **A loop that computes and mutates**: one loop body both works out a
  collection or a selection (skipping, splitting into kept and missing,
  grouping, looking a value up to decide) and changes state or does I/O with
  what it found. Tells: a `match`/`if` whose arms mix a `push` onto a local with
  a mutation of `self` or a call with effects; a local `Vec` or counter filled
  beside a write; an `if` wrapping the whole body. The selection is a pure
  computation with a standard name (`partition`, `filter`, `filter_map`,
  `group_by`); take it out first, then run the effect over its result. Mark the
  loop `decision + effect, inline` in the role list.

Write one line per function: `name: roles`, and mark each role as inline or
called (it goes through a named function). The findings are the cases above, and
only those; each names the split you would make. This is a checklist like the
declaration inventory; do it for the whole changeset, including functions whose
diff is one line.

**A doc carries the design, not the code.** A doc carries only what the
signature cannot. That is two kinds of fact:

- **(a) the decision**: the design decision behind the item, linked to where it
  is recorded (an ADR, a design doc, the spec, a task);
- **(b) the contract**: the facts that the signature cannot express. These are
  the effect the caller calls it for, the errors a caller can tell apart, the
  sibling that differs by one effect, a unit, a bound, a None or panic
  condition, an ordering the caller relies on, and a state that is transitional,
  such as a column that is NULL on rows written before a migration. A None or
  panic condition is a (b) fact only when the type cannot express it. When the
  type can, the doc is the tell of algebraic blindness (§4, "Algebraic
  blindness"), and the type is fixed first.

Everything else is restated code: the fields, the members, the steps, the
mechanism, the history, the callers, the producers, the consumers and the uses.
So is what the types, the defaults or the type's own doc already say, and an
infrastructure failure (the database, the network), which every method has.
Restated code adds nothing, and it goes stale at the next change to either
layer. Replacing one restatement by another is no fix: a doc that lists its
users instead of its fields restates the code from the other side. When neither
(a) nor (b) applies, delete the doc, unless it is one of the three kinds below
that stay when plain. Do not reword it: a verb-first restatement is still a
restatement. Unless a missing-docs lint is on, an undocumented item costs
nothing. Under that lint, the doc is the decision or the shortest (b) fact.

A function doc states its (b) facts in plain sentences, and one sentence states
the decision, cited, when one stands behind the item. A doc never gives a
caller's reason for calling. A reason that is a decision goes where §3, "Design
link" puts decisions. A sentence that restates the mechanism is deleted, not
moved into a `//` comment. A `//` comment inside a body is for a non-obvious
local reason at one line, such as a measured workaround.

A doc names a reader only when the reader is outside the repository and the
value is a protocol with it ("read by scripts/pocket_id.py"). What that reader
does with the value still never stays.

Three kinds of doc stay when plain, with no design link. User-facing help text
(a clap doc, a `--help` line, a subcommand's about, a unit's `Description=`) is
the program's interface to its user: `--hostname`, "Overrides every bucket's
hostname"; `run`, "Runs as a console app". It still never names the mechanism or
the callers. The other two are the columns that a doc-capturing table macro
requires, and the associated types of a trait.

**Design link.** A doc is written in two steps, never one. First, find the
decision: read the item, then look for the decision it embodies where the
project records its design (ADRs, design docs, the spec, open task records), and
quote the passage. This is the part that cannot be skipped: a doc written
straight from the code can only retell the code. Then write the doc as a link
from the item to that decision: one plain sentence that states the decision as
it applies to this item, and cites where it is recorded ("…, so both builds get
the same addresses (DESIGN.md §10)"). Each item gets one verdict, and an editor
writes a doc only from it (§3.0, step 5):

- **link**: a recorded decision stands behind the item, and the item has no (b)
  fact. The doc is the link.
- **contract**: no decision stands behind the item, and it has (b) facts. The
  doc keeps only those (§3, "A doc carries the design").
- **link+contract**: both. The doc is the link and the (b) facts.
- **measured**: a dated measurement is the reason (a shape kept for size, gas or
  speed). The comment that records it is the record. Keep it, or point to the
  workarounds file that owns it.
- **delete**: the doc goes, as "A doc carries the design" says.
- **gap**: a decision is visible in the code but recorded nowhere. Record it in
  the design doc first, then link the item to it. A gap whose reason would be a
  guess goes to the user, or to the plan (§3.0, step 5). A doc never invents a
  rationale.

Design docs own the decisions and code docs cite them, never the reverse: moving
a decision out of a design doc into a docstring is a finding. A design doc may
name where the code enforces a rule; it does not restate how.

**Doc read.** Then read each doc comment against its signature. This is the
survey for the (b) facts; "Design link" is the survey for the decision.
"Documented item" means every `///` and every `//!`: a module doc is the doc of
the largest item in the file and the first one a reader meets. It follows the
same rule as any doc: it states the design decision behind the module, cited
(§3, "Design link"). A list of what the module provides, or of its mechanisms in
the order they run, is restated code. A term only an ADR defines is a finding
unless the doc says it in plain words and cites the ADR. A doc that narrates the
body ("takes the anchor, walks back, stamps each row, then…") tells a caller
nothing the signature did not, and goes stale the moment the body changes. The
author cannot see this by comparing the comment to the body: a narrating comment
always matches the body, and matching is the smell. So for each documented item,
in this order:

1. **Expect first.** Read the signature and the doc only. Write down what you
   expect to get back and when it errors.

2. **Contract from the body.** Only then read the body, and list three things
   from it, not from the doc:

   - the effects: every write, network call, spawn, delete, or state change that
     is the function's own outcome, the thing its caller calls it for (grep the
     body for
     `INSERT|UPDATE|DELETE|reqwest|spawn|create_|add_|record_|store_|remove_`).
     An effect that is only the means to that outcome is an implementation
     detail, and so is everything a callee does. `session()` returns a session
     ready to use, loaded or created; that it prompts at the terminal, reads
     stdin or writes a file is how, and its doc does not say so. A caller's doc
     never repeats a callee's effects. Effects count only at the item's
     abstraction level, the one domain its caller works in. No doc says that a
     function spends CPU time, and an effect of a command-line tool is what the
     user meets, not the API calls made to get it. An item with no single level
     is a finding about the code (§4, "Mixed altitude"), and it is fixed before
     the doc (§3, "Long comment");
   - the errors a caller can tell apart: a sentinel, a typed error, or a failure
     the caller handles differently from the others. Any other exit is not a (b)
     fact (§3, "A doc carries the design"), and a doc that lists the branches is
     narration;
   - the sibling: another method whose difference from this one is one of those
     effects.

   Each effect must be in the doc's main clause, not in a participle ("…,
   registering it when …"). Each error a caller can tell apart must be named. A
   sibling must be pointed at from the one with the surprising effect. Two
   further findings: your expectation was wrong or blank, so the doc does not
   state the contract; or the doc could only have been written after reading the
   body, because it names sort keys, tie-breaks or branch order that the caller
   does not rely on, or a SQL or regex mechanism. A contract sentence stays only
   when the caller would act differently knowing it. Write an ordering as what
   the caller sees, not as the steps that produce it. A sentence that states the
   design decision, cited, is tested by "A doc carries the design" instead. A
   check that the function runs on its own result ("every returned record
   matches its source", "the input is not taken on faith") reads like part of
   the promise, but it is mechanism. Grep the doc lines for
   `checked|verified|matches|on faith` and test each hit.

3. **Must.** A precondition phrased as "must" ("it must exist and be enabled")
   is a finding: name the error instead.

4. **Narration grep.** Narration has a vocabulary: sequence and branching words,
   which a body has and a contract does not. Grep every doc line in the
   changeset for them —
   `grep -nE '//[/!].*\b(then|first when|on a miss|in the order|after that|before that|once |, or,)\b'`
   — and treat each hit as a finding until it is shown to state what comes out
   rather than how.

5. **Cold re-read.** Run "Expect first" on every doc the changeset wrote or
   rewrote as if seen cold, and run the narration grep over it; a doc that needs
   a second reading, or that satisfied a rule by cramming the mechanism into a
   clause, is a finding. Presence of the effects and errors is necessary, not
   sufficient. Two shapes pass every rule above and still read as nonsense, so
   check for them by form: a stand-in main verb (gives, makes, handles, deals
   with, matches, verifies) that leaves the real contract to a clause after it,
   whose form step 7 checks ("gives block its state and its portal transactions:
   the candidates that…, applied … on state"), and an adjective or participle
   with no referent in the doc or signature ("a changed entry": changed from
   what? "applied on state": what is?). The cause is usually that the function's
   result has no name, because it is written into a parameter instead of
   returned; make it return the result and the verb ("returns X and Y") writes
   itself.

6. **Parse check.** A doc must also parse. A sentence compressed far enough
   turns ungrammatical while every word in it is right, so it passes every rule
   above. "Whose buckets the export reports them as." on `enum Hostnames` is the
   type of it. Check every doc in the changeset, rewritten or not:

   - **Grep for free relatives:**
     `grep -nE '(//[/!]|#)\s*(Whose|What|Which|Where|When|How|Why)\b'`. "What
     the puller asks for" or "Where a person's aw-server stands" is a sound noun
     phrase: the thing, place or time that the clause describes. A hit is a
     finding when the question word cannot head one. "Whose X …" and "Which X …"
     almost never can, and they read as a question with its question mark
     missing.

   - **Match the question word to the value.** Name the kind of value the item
     holds or returns (a hostname, a duration, a path). "Whose" points to an
     owner, "when" to a time, "how long" to a duration, "where" to a place or
     address. A mismatch, such as "whose" on a name, is a finding.

   - **Read it complete.** Put the item in front of it: "`Hostnames`: whose
     buckets the export reports them as." Each of these is a finding, and its
     fix is a rewrite in the form that "Doc style" gives:

     - it does not read as plain English;
     - a clause trails off with a preposition and a pronoun ("… them as");
     - a pronoun has two referents, or none.

7. **Plain English.** A doc must read as plain English on the first pass. A doc
   can parse and still be compressed: every rule above is met, but the reader
   has to unpack it like code. The user rejects this style outright as "AI
   slop". They prefer a longer doc in simple sentences. This one passes the
   steps above and fails here:

   ```
   // Returns the base of a portal tx spending parent's portal output: the pending
   // portal tx parent is, with the ones under it, or the confirmed tip keeping
   // none when parent is no pending tx.                                       ✗
   // Returns the base of a proposed portal tx that spends the given parent. The
   // base is the parent's pending chain when the parent is a pending portal tx,
   // and the confirmed tip otherwise.                         ✓ outputs, not steps
   ```

   Check every doc and every `//` comment in the changeset for these tells. Each
   hit is a candidate, and the read-aloud test below decides whether it is a
   finding:

   - **A colon or semicolon inside a sentence** that joins a second idea onto
     the first ("Returns X: the Y that…", "…; false when…"). Make it two
     sentences. A colon that introduces a list stays, and so does one that lists
     the items its sentence announces, even two of them, separated by commas:
     "two kinds of listed tx stay out: a tx in a block that the portal applied,
     and a tx that a recent block conflicted". Splitting that into "One is … The
     other is …" sentences reads worse, so never do it.
   - **An appositive or a reduced clause standing in for a sentence**: "…, the
     one it extends", "…, a prefix of the chain", "…, whose X…", "…, keeping
     none". Write it as a sentence with a subject and a verb.
   - **A parameter or field name used as a noun inside a clause**, so that the
     sentence reads as broken English ("the pending portal tx parent is", "the
     room tx leaves", "the weight out adds"). Put "that" or "the given" in front
     of the name, or restructure the sentence.
   - **A noun stack or a missing verb or article**: "a fee for the next block
     within the ceiling", "more settled than", "of more varint bytes than a
     zero's". Write the verb and the articles out.
   - **The error contract not in its house form** (§3, "Doc style").
   - **A sentence in a trailing comment** on a field or constant. Move it to its
     own line above the item.

   Grep the changeset's comment lines as a first pass. The read-aloud test
   decides: a comment that a colleague would have to read twice is a finding.

   ```sh
   git diff HEAD -U0 | grep -nE '^\+.*//.*([a-z]: [a-z]|; |, (the one|a prefix|whose|keeping|leaving)\b|\bReturns an error\b)'
   ```

   No length limit (§3, "Long comment") may be met by compression. A plain
   version that comes out longer is that rule's case, not a reason to compress.

**Restatement survey.** A flow read walks past restated code, so survey for it
by form, against "A doc carries the design":

- **Entity docs.** Extract every doc attached to a `struct`, `enum`, `trait`,
  `type`, NewType or module, and read each for a list of members or of users.
- **Short docs.** List every doc of a sentence or less, and every constructor
  doc next to its declaration; tautology lives in the short ones. A constructor
  doc that names its parameters back, a field doc that names its type back, a
  getter doc that names the method back, a doc on a method whose contract the
  language or a standard interface fixes (a `Compare`, a `String`), and a clause
  that follows from the one before it ("it is never mutated; a change replaces
  it whole") all restate the code. Grep for `on every|agrees|every run`, a claim
  that every deterministic function makes. When the caller relies on getting the
  same result for the same inputs, whatever order or source they came from,
  write "in a canonical order".
- **Interface docs** (help text and public items). Help text is where restating
  leaks most, because it is written beside the code. Test each sentence against
  §3, "A doc carries the design" with two questions. Would it stay true if the
  callers changed? Would it stay true if the implementation changed without
  changing what the item does? A sentence that fails either one restates another
  layer.
- **Field comments.** Read each for its decision or its (b) fact, as "Contract
  from the body" reads a function doc for its effects.

**Doc style.** These forms apply only to the wording of a doc that "A doc
carries the design" keeps. They never make a doc that the rule deletes. Write a
kept doc in Google developer documentation style for API reference comments
(https://developers.google.com/style/api-reference-comments): present tense,
third person, a verb first — `Returns …` for a value, `Checks whether …` for a
boolean, `Sets …` / `Updates …` / `Deletes …` for an effect — and never "this
method" (for the item's own name, see §3, "Doc openings"). The one exception to
Google style is the error contract: it reads "Errors when …" ("Errors with ErrX
when …"), not "Returns an error if …". Never rewrite an existing "Errors when…"
doc into the Google form. A parameter description starts with "The" or "A". A
boolean parameter or field reads "True if …. False otherwise." A function doc
starts with a verb. A type or field doc has no fixed opening.

**Doc openings.** No declaration's doc opens with its own name, whether it is a
function, method, type, constant or field. The comment sits on the declaration,
so the name is duplication, however much Go's `Name verbs…` convention asks for
it. `// pending is the committed snapshot…` above `pending *pendingSet`,
`// portalTxBase returns…` above `func portalTxBase`, and a trailing
`// Wraps since prevState.` on `wraps` all read the identifier back. Only a
linter rule the repo enables (revive `exported`, stylecheck ST1020–ST1022) keeps
the name, as a §2 rule.

Check this mechanically, not by reading: the eye skips a name it has just read
on the line below, and the `Name verbs…` habit writes the smell fluently. For
every declaration with a doc or trailing comment, compare the comment's first
word to the declared name, case-insensitively for fields. Fix every match by "A
doc carries the design": link the decision, keep the (b) fact, or delete the
doc. Dropping the name alone is a rewording. Exact: a `go/ast` walk over
`FuncDecl`, `GenDecl` specs and `StructType.Fields`. Quick, over the changeset's
Go files:

```sh
awk '/^[[:space:]]*\/\/ / { if (c=="") { c=$2; sub(/[:,.]$/, "", c) }; next }
     /^(func|type) / { n=$0; sub(/^func (\([^)]*\) )?/, "", n); sub(/^type /, "", n); sub(/[^A-Za-z0-9_].*/, "", n); if (c!="" && c==n) print FILENAME":"FNR": "n }
     { c="" }' $files                                              # doc above a func or type
awk '/^[[:space:]]*\/\/ / { if (c=="") { c=$2; sub(/[:,.]$/, "", c) }; next }
     /^[[:space:]]+[A-Za-z_][A-Za-z0-9_]*([,[:space:]]|$)/ && !/=/ && $1 !~ /^(if|for|return|switch|case|go|defer|var|const|type|func|select|break|continue|else)$/ { if (c!="" && tolower($1)==tolower(c)) print FILENAME":"FNR": "$1 }
     { c="" }' $files                                              # doc comment above the field
grep -nP '(?i)^\s+([A-Za-z_]\w*)\b[^/]*//\s*\1\b' $files          # trailing comment on the field line
```

The field awk also fires on an implicit-iota entry of a `const (` block; that is
a finding too. Everything the three commands print is a finding. Other
languages: the same comparison over functions and `struct`/`class` members
(`/// foo: …` above `foo:` in Rust, a `#:` or attribute docstring in Python).
Fix all of them in one pass; one left over teaches the next reader the habit.

**Signature names.** A doc names a value by what it is at the signature. A
parameter is bare (`want`); a field is its path (`Query.need`); a method is its
path (`Query::call`). Never the option or flag that fed the value
(`--min-sources` for `Query.need`): that leaks another layer's vocabulary into
this one, and the reader of this layer has no way to find it. And a bare name
that is neither a parameter nor a sibling field reads as a missing or renamed
argument, which is a bug report against the doc. Grep the changeset's doc lines
for flag names — `grep -nE '//[/!].*\B--[a-z]'` — outside the module that parses
them.

**Referents.** Every noun in a doc names its referent. A project uses one word
for several things — "request" for a JSON-RPC request, a planner's request and a
fetcher's ask; "call" for a contract call and an RPC method; "logs" for EVM logs
and diagnostics; "lists" for chain lists and token lists; "chunk" for a log
range, a halver's unit and a hypertable's — and a doc that says the bare word
makes the reader guess. Say which: "JSON-RPC requests in flight", "reports on
stderr", "the configured token lists". List the project's overloaded nouns once,
grep the changeset's doc lines for each, and rewrite every hit that does not
disambiguate. The same sweep catches a stale name (a type renamed, a mechanism
removed) and a claim the code no longer makes (an exemption, a replacement, a
fallback); check each against the code, not against memory. An identifier is a
noun too: a method or field whose name is also a word — `commit`, `retry`,
`start`, `next`, `loop` — written bare in prose ("and commit recomputes it")
reads as the word, so it carries its qualifier (`pendingUpdate.commit`,
`blockStream.retry`) wherever it is not the doc's own subject. Grep the
changeset's comment lines for the project's word-named identifiers and qualify
every hit that means the identifier. And a verb with a settled technical meaning
— commit, publish, flush, lock, seal, sign — applied to an operation that does
none of it ("commit the pending set", for a state that is neither persisted nor
bound to anything; "publish", when nobody gains access) misleads the same way.
The misuse usually starts at a method name, which is a misleading name (§4,
"Misleading name"): rename the operation, and the prose follows. Include such
verbs in the overloaded-noun list.

**Long comment.** A doc is one or two sentences, and three lines is the limit
for any comment, doc or `//`. A longer comment is not a style slip to trim. It
is a smell with one of three causes, and the fix goes to the cause, not the
prose:

- The item does several jobs: its parameters need explaining one by one, or its
  edge cases outnumber its purpose. Split it (§4, "Concept mixing"), so that
  each part needs only a short doc.
- The comment explains an invariant that the code could express: a type, a named
  constant or function, a check at the edge, a database constraint. Express it
  in the code, and drop the sentences that the code now says.
- The comment restates the code. Fix it by §3, "A doc carries the design", which
  keeps any (b) fact it holds.

Fix the code before the doc: a doc rewritten first describes the mix, and it is
wrong again after the split. A comment cut in half that keeps its cause is still
the smell. The report names which cause it was.

```
/// The registered chain `chain_ref` names, registering it from the
/// catalog when it is only listed there.                  ✗ effect in a participle, no errors
/// Returns the registered chain that `chain_ref` names, and registers it
/// first when only the catalog knows it, unlike [`Db::registered_chain`].
/// Errors when the reference is unknown or ambiguous.     ✓ (b): effect, errors, sibling

/// Adds every output of tx paying a tail pkScript to the tracked
/// outpoints.                                             ✗ the mechanism
/// Remembers tx's outputs to tail pkScripts. A key rotation is found by the
/// outpoint it spends, since an input names nothing else (ADR 0012).  ✓ effect and decision, cited

/// One run: the chain, its connections, its block estimator, and the
/// requested block range.                                   ✗ an actor described by its fields
/// Runs one log-serving command: resolves the chain and the range, serves
/// logs through the cache, stamps block times and answers contract calls.  ✗ its methods read back
/// One run of a log-serving command on one chain. The commands use it to
/// place their block ranges and logs in time.               ✗ its users read back: the call graph
/// Block times come from the chain, never from a log source, so one cache
/// serves every source (ADR 0007).                          ✓ the decision it embodies, cited

"""What a call sends, from which account, to which deployment."""
                                                          ✗ the fields read back
"""A call as every build sends it. node_check compares the Outcomes of
two builds in order."""                                   ✗ the "fix": callers instead of fields
"""A call names its target by deployment, not by address, as a call script
does (ADR 0020). A build's addresses exist only after that build deploys."""
                                                          ✓ why it is shaped so, with its record

/// Creates a runner over the log cache `store` and `sources`, the
/// fetchers paced for a chain of `cadence`.                 ✗ the signature read back: delete
/// Requests in flight per fetcher.                          ✗ which requests?
/// JSON-RPC requests in flight per fetcher, at most.        ✓ the referent named, and a bound
```

## 4. The catalog

A row that names a §3 pass gives only a short tell; the pass owns the full tell
and the fix.

| Smell | Tell | Usual fix |
| -- | -- | -- |
| **Duplication** | A rule or derivation written twice, however small; two sites you'd have to edit together | Extract the shared thing. Merge only what changes *for the same reason* — coincidental resemblance stays apart. |
| **Unnamed tuple** | `return (a, b)`, positional bag, dict with implicit keys, `result[0]` at call sites | Named record / dataclass / struct / NamedTuple |
| **Boolean blindness** | `f(true, false)` unreadable at the call site; a bool param that only picks a branch | Enum, or two named functions. Kill the flag param. |
| **Algebraic blindness** | Impossible states are representable: co-dependent nullables, `status` string beside a payload, `(value, error)` both optional, "this field only matters when kind == X"; a doc that explains what a none, empty or zero value means ("none for the list", "0 means unlimited"), above all when several docs repeat it | Sum type / discriminated union / tagged variant. Make the illegal state unspeakable. |
| **Primitive obsession** | `str`/`int`/`&[&str]` carrying domain meaning; a collection whose element type says nothing; two fields that must hold the same kind of value, typed independently; a value with an invariant the type does not carry ("validated", "resolved", "escaped"); re-validated at every use | Wrapper type; validate once at the boundary. A type earns its place by (a) linking the places that must agree and (b) saying what is inside |
| **Unnamed return** | A return type that names nothing — `-> String`, `-> Vec<(A, B)>`, `-> bool`. The function's name is not the value's name: at the call site the name is gone and only the type is left | Name the thing returned, not just the act of returning it |
| **Stringly-typed control flow** | Branching on magic strings | Enum / typed constants |
| **Long function** | Does more than one thing; needs section comments; nesting past 3 | Extract along the section comments; guard clauses to flatten |
| **Long file** | Several unrelated concepts sharing a filename | Split by concept, never by line count |
| **If-forest** | Cascading branches on a type tag; nested conditionals; flag-combination matrix | Dispatch table, polymorphism, or pattern match; early returns |
| **Parameter bloat** | 5+ params, or adjacent same-typed params easy to transpose | Parameter object — or the function does too much, split it |
| **Data clump** | The same 3+ arguments threaded through a series of functions | That cluster *is* a type. Name it, pass one thing. |
| **Missing receiver** | Sibling functions that want to be methods of one type | §3, "Parameter table" |
| **Inline generic machinery** | Domain code that also hand-builds a generic data structure or algorithm | §3, "Generic machinery" |
| **Concept mixing** | I/O, business logic and formatting in one unit; a module importing across three layers; an inline rule | Separate; push I/O to the edges, keep the core pure. The inline rule: §3, "Role pass" |
| **Mixed altitude** | Orchestration interleaved with detail | §3, "Role pass" |
| **Oversized lock** | A lock heavier than what it guards | §3, "Lock inventory" |
| **Temporal coupling** | Must call `init()`/`setup()` before the thing works | Constructor, builder, or context manager |
| **Speculative generality** | Unused param, single-implementation interface, config value that never varies, hook nothing calls | Delete it |
| **Computing loop with effects** | One loop body that both computes and acts | §3, "Role pass" |
| **Misplaced rule** | A rule living outside the type it serves | §3, "Placement pass" |
| **Request-scoped value threaded** | Short-lived values threaded through longer-lived code | §3, "Lifetime pass" |
| **Unparsed input** | Outside input kept raw | §3, "Input pass" |
| **Split protocol** | A literal that a writer and a reader must both spell the same way | §3, "Repeats" |
| **Repeated derivation** | One derivation written twice | §3, "Repeats" |
| **Pass-through** | A function with no role of its own | §3, "Role pass" |
| **Misleading name** | Name says less (or other) than the body does; a compound whose modifier is a domain term binds to the wrong noun (`pendingUpdate` for an update *to the pending set* reads as an update that is *waiting*) | Rename. First say in one sentence what the objects are, who makes them and how long they live; that sentence usually names a known pattern, and the pattern is the name (`pendingSetBuilder`: a mutable builder of an immutable `pendingSet`, one per event). A name coined from the description alone (`pendingSetEdit`) was judged worse than the original. Take the pattern's name, not its shape: splitting the code to match the pattern's method set (`build` + a separate install step) only added a hand-off and was reverted. Delete the comment the name replaced |
| **Long comment** | A comment over the length limit | §3, "Long comment" |
| **Duplicated knowledge** | One fact stated twice | §3, "Repeats" |
| **Restated code** | A doc that restates the code | §3, "A doc carries the design" |
| **Doc opens with its name** | A doc whose first word is its declaration's name | §3, "Doc openings" |
| **Ambiguous noun** | A doc word the project overloads, or a name the code no longer has | §3, "Referents" |
| **Garbled sentence** | A doc that does not parse as plain English | §3, "Parse check" |
| **Compressed doc** | A doc that parses but has to be read twice | §3, "Plain English" |
| **Narrating doc comment** | A doc that retells the body instead of the contract | §3, "Doc read" |

Not exhaustive. If it reads badly and you can say why in one sentence, it
counts.

## 5. Triage

### 5.0 Score each change before it is made

Score every finding that would lead to an edit, docs included, from 0 to 10 by
the value its fix adds, and make the fix only when the score reaches the
threshold. The threshold is 5 unless the arguments set another (§1).

| Score | What the fix does |
| -- | -- |
| 9–10 | fixes a bug, or a doc or name that states something false |
| 7–8 | removes a structural smell with a catalog tell met in full: a duplicated rule, a missing receiver, unparsed input, a misplaced rule, a hidden effect |
| 5–6 | narrows a type, removes dead code; removes or shortens a comment that repeats the code, narrates history or states a fact twice; replaces a doc that restates the code (§3, "A doc carries the design") with what that rule keeps, or deletes it; rewrites a doc that fails a check of §3, such as "Parse check", "Plain English" or the "Errors when" form |
| 3–4 | a doc fact that is true but adds little |
| 0–2 | rewording a correct doc or message that passes every check of §3, renaming a name that is not wrong, reshaping code that has no smell; a rewrite that makes a comment longer without correcting something false in it |

A catalog smell whose tell is met in full scores at least 5, however small the
instance: a conversion written twice, a hand-rolled range merge, a dead constant
kept alive by a lint suppression. Size counts only through the churn rule below.
A comment fix that adds the item's implementation details scores 0, whatever it
corrects; it states the fact the reader lacks and stops.

Subtract 2 when the fix churns more than about 30 lines for a local gain, or
reworks code that a fix earlier in this run wrote, unless that code was wrong. A
finding under the threshold is a SKIP, reported with its score (§8), so that a
user can lower the threshold. It is not planned: an entry in the plan is work
someone should do.

**FIX** — no decision is needed. It is still reviewed one at a time, like an
ASK, and the user accepts or rejects it (§3.0, step 6), unless the arguments say
`fix everything` (§1). Mechanical, behaviour-preserving, one obviously correct
answer, blast radius you can see and verify: extract a function, name a tuple,
replace a bool param with an enum, collapse a duplicate, introduce the type a
data clump was already implying, delete dead flexibility, replace inline generic
machinery as "A library, not a home-grown one" says.

A smell fix may change behaviour a little when that buys a clearly better
design: an internal error message reworded, input rejected at the edge inside
the program because a check moved there, an internal default made explicit. Such
a change is a FIX, and the report names it under `Behaviour`. Behaviour
noticeable outside the repository is an ASK (below), however much it helps. A
bug fix may change behaviour, and the report lists it as a bug fix, with what
changed.

A bug is code that does something wrong today: it loses or corrupts data, fails
silently, or breaks its own contract. Parsing raw input into a domain type at
the edge is a smell fix (above), not a bug fix, even though the type now rejects
what it cannot hold. Replacing a generic error with a more specific one, without
any new type behind it, is a feature: a wrapper that turns `KeyError` into
`BankError`, or a new error class for the same failure. It is not a bug fix and
not a smell fix, and it is planned (§5, "PLAN").

A name or a doc is a finding only when it is wrong. A name is wrong as §4,
"Misleading name" says, or when it gives one thing two names. A doc is wrong
when it says something false, states a fact twice, leaves out a (b) fact,
carries anything else (§3, "A doc carries the design"), or fails a check of §3:
"Parse check", "Plain English", or the "Errors when" form of "Doc style". Those
are defects, not taste. A correct name, or a doc that passes every check, is not
a finding because another wording reads better, or because a neighbour spells it
differently; rewording it only gives the next run something new to reword. A
type is different: narrowing it to what the value can be (`str` to
`Literal["GET", "POST"]`, a list that is never changed to a tuple) is a fix.

**A library, not a home-grown one.** A query, a schema or a wire format written
out in full is not a smell because its column or field names appear in it more
than once. Do not factor it piece by piece: a constant for the column list,
statements built with `format!` or string joins, a values array that must stay
in the column order, generated placeholders. Each step looks like removing
duplication, and a hundred of them make a home-grown ORM or serializer, which is
worse than the strings were. The same holds for any mechanism that an ecosystem
library already provides: schema versioning and migrations, a settings or
environment parser with validation, a schema for an input body, a serializer.
When the repetition is a real problem (several statements that must agree on a
schema), or the fix for a finding would write a small version of such a
mechanism by hand, the fix is a library that does the job: an ORM, a query
builder, a derive. Where the library comes from decides the bucket:

- reusing the repo's own utility module, the standard library or a library the
  repo already depends on is a FIX, and so is extracting a small generic into
  the repo's utility module (§3, "Generic machinery"); the new file there is
  part of the fix, not a reason to ask;
- adopting a new third-party dependency is an ASK or a PLAN, and the finding
  names it (pydantic-settings, Alembic, serde, zod);
- a hand-written version of what a library provides (a schema, migrations,
  settings parsing, a serializer) is never a FIX, whole or built up piece by
  piece.

**A fix is finished or not made.** A finding names the final shape of the code,
not a first step towards it; a finding whose fix only becomes right after
another fix names the shape both reach. The fix leaves no residue: no local that
only renames another (`params = query`), no two names for one value, no half of
the old shape beside the new one, no root cause the findings name left half
done. A fix that adds a smell is not finished either: a library call written out
at every site where a named helper stood is duplication, and so is a value
fetched and parsed inline where a new function would return it typed. The
re-check (§3.0, step 7) treats residue as a finding.

**ASK** — a change whose review (§3.0, step 6) needs a decision, not only a
verdict. Its question says what is wrong, the options and which you'd pick.
§3.0, step 4 says when a second option is a change of its own. Don't ask open
questions you can answer yourself. Ask when:

- it changes behaviour noticeable outside the repository: a
  public/exported/published API, a stored schema or a serialized format, a
  command-line interface, or anything with callers you can't enumerate.
  Behaviour inside the repository follows FIX (above)
- the fix requires inventing a domain concept whose meaning isn't derivable from
  the code
- two or more designs are genuinely defensible with different tradeoffs
- it needs a new file/module, or spans package boundaries
- the fix is large enough that the user might reasonably prefer a follow-up
  commit

A fix that a written style rule forbids is not an ASK (§7). An offer to change
the rule is a PLAN entry against the style guide.

**KEEP** — rare. See §7.

**PLAN** — a real smell that this run does not fix: it is out of scope, too
large for this commit, or waits on a decision. Write it into the project's own
plan, the place where the next person will look for work: the `TODO.md` or plan
document the repo already keeps, or its issue tracker. If the repo has none, ask
once where plans go. A run that may not ask (§1, §3.0, step 6) asks nothing: its
plans go into the report's `Planned` lines, with the note that the repo has no
plan file. Each entry says where the smell is, what is wrong, and the fix or the
options, so that someone without this conversation can act on it. Group the
entries of one run under one heading that names the run. A smell that appears
only in the report is not planned: the report scrolls away, and the smell goes
with it.

An entry already in the plan is a decision that someone has made: the smell is
known and its fix waits. A later run does not act on it unless its arguments
name it (§1); `fix everything` covers this run's findings, not the plan. A
finding that matches a planned entry is discarded (DISCARD, below), and an entry
that a fix in this run makes obsolete is updated or removed. The plan file is
not surveyed, even when the changeset touches it: the run adds its own entries
and edits only the entries its fixes change. Rewording, merging or correcting
other entries is work the plan's owner did not ask for, and each run would redo
it.

**SKIP** — the finding holds, but its fix scores under the threshold (§5.0).

**DISCARD** — the finding needs no work from this run. The code does not do what
the finding says, a fix earlier in the run already removed it, it duplicates
another finding, it matches an entry already in the plan, or the user already
decided that question in this conversation. Each discard gets one line in the
report with its reason, so that the user can overrule it. A discard is never a
smell kept on purpose; that is a Keep (§7), and §7's list of reasons that are
not reasons applies to discards too.

**Survey exhaustively, fix by score.** These are different budgets and
collapsing them is how findings go missing. The survey covers the whole
changeset every time — a three-line change does not license a repo-wide rewrite,
but it does not excuse a partial look either. A long list caps nothing: each
finding goes to its bucket by its score (§5.0). A finding you never wrote down
is a miss you will be told about later.

**Read whole files, fix the changed lines.** The changed lines are what
`git diff HEAD` adds or changes, plus every line of an untracked file. A smell
on them is fixed, together with its root cause wherever that lives (§6). A smell
on other lines of a touched file, which is not the cause of a smell on changed
lines, is planned (§5), not fixed. Otherwise each fix outside the diff becomes
changed lines for the next run, the next run surveys its whole file, and the
scope grows every run instead of settling. A path or module that the user names
(§1) restricts the changeset and leaves this rule as it is. Only "the whole
file", "this module" or "the repo" makes every line of what it names a changed
line.

**Every finding ends in a bucket.** Every finding lands in exactly one of the
buckets above. That covers the survey agents' findings, the cross-file agent's,
the re-check's, and everything a subagent that fixed code reports as skipped,
left over, out of scope or "noticed". There is no "noticed" end state: a
leftover is fixed, asked, kept, planned, skipped or discarded before the run
reports. A change the user answers `later` keeps its decision, and the report
lists it under `Asked` with its patch; it is not open work. A change the user
rejects is dropped, and its findings count as decided. The report lists each
under `Rejected` with the user's reason, and names a finding the user called
wrong as a rule of this skill to fix. A run that no user can answer handles its
ASKs as §3.0, step 6 says. Before the report, check that every finding in the
findings files has its entry in `decisions.yaml` (§3.0). One that fits no bucket
is the run's open work, not its result.

### 5.1 A smell you are pointed at is a class, not an instance

When the user names a smell — in an argument, or after a run that missed it —
they are describing a kind, and the instance they cite is the one that annoyed
them enough to mention. Before fixing it:

1. Sweep the whole changeset for every sibling of that kind. `grep` for the
   shape, not the identifier: other `(A, B)` returns, other `&[&str]` fields,
   other magic-string branches. Hand the sweep to a fresh agent (§3.0) that gets
   the kind, not the instance. It also re-runs, over the files the smell is in,
   the generic-machinery table and the literal and expression greps: a pointed
   smell usually has neighbours of another kind.
2. Fix the class in one pass.
3. Report the sweep — how many you found, where — so the count answers "did you
   get them all?" before it is asked.

Fixing only what was pointed at guarantees another round, and teaches the user
that pointing is how this gets done. For a doc, rewording only the doc that the
user cited counts as fixing only what was pointed at.

When the pointed-at smell is one a previous run of this skill should have
caught, the report also names, before the fix, which survey step would have
found it and why that step was skipped or passed it. A miss with no named cause
will repeat.

## 6. Fixing outside the changeset

Allowed and often required — the smell's *cause* frequently sits in code the
diff didn't touch: the other copy of the duplicated block, the shared helper the
new call site now needs, the type that should have existed before the clump
appeared, the function whose signature the new caller made unwieldy.

Bounded by:

- **Only where the fix belongs.** Follow the root cause outward. Other smells on
  the way follow §5, "Read whole files, fix the changed lines".
- **Update every caller.** Grep before you change a signature; leave nothing
  broken.
- **Behaviour changes follow §5, "FIX".**
- **Verify as §3.0, step 5 says.** Where no test covers non-trivial logic that
  an editor restructured, it leaves one runnable assert-level check behind.
- **Pin before you move.** A fix that touches a URL, a path, an encoding, a
  parser, a default, or who may do what is where a refactor changes behaviour
  without anyone noticing. Examples: a relative redirect that now resolves
  against another host, an identifier no longer escaped, a default taken from
  the wrong source. Before the edit, write a test that pins the current
  behaviour of the function you are changing, and run it (§3.0, step 5).

## 7. Keeping a smell on purpose

Legitimate when the smell is imposed from outside or the cure costs more than
the disease, and the reason must be one of these — the list is exhaustive, not
illustrative: a framework-dictated signature, a serialization shape you don't
own, generated code, a shape kept for a measured size, gas or speed cost and
recorded in a dated comment, an FFI boundary, a deliberate mirror of an external
spec, or a written rule from §2 that mandates the smell or forbids its fix.

**Anything else is a Fix you have not done yet.** These in particular are not
reasons, however reasonable they sound in the moment:

- "only one call site" / "only used here" — call sites multiply, and the second
  one arrives without re-reading your justification
- "it's destructured immediately" / "the name is right there" — that is the
  reader compensating for the type, which is the smell
- "it's obvious in context" — the context is the neighbours, and §2 refuses "the
  rest of the file does it this way"; it is no better here
- "it's small" / "it's private" / "it's just two fields" — the size of an
  instance does not excuse it. The catalog's numbers are tells for finding a
  smell, not exemptions below them
- "renaming would churn the diff" — churn is not a reason to keep a smell whose
  fix scores at or over the threshold (§5.0)
- "this file's diff is one line" — every changed line is in scope however few
  there are, and a mechanical class on them is fixed in all of them; a commit
  split isolates the churn. A smell on the file's unchanged lines follows §5,
  "Read whole files, fix the changed lines"

If you find yourself writing a justification longer than the fix, the fix was
smaller than the argument against it. Just do it.

Never "it's fine" or "no time". Leave a comment in the file's comment syntax —
**a Keep that exists only in the report is not a Keep, it is a silent skip**,
and the comment is what makes it reviewable by the next person:

```
# smell: 7-arg constructor — kept, mirrors the upstream SDK signature 1:1.
# Fix when we wrap the SDK behind our own client.
```

Name the smell, the reason, and the trigger that ends it.

## 8. Report

Code first, then at most:

```
Survey   <n> files read whole · <n> declarations inventoried · <g> locks inventoried, <o> oversized · <n> parameter tables, <c> shared context columns · <m> misplaced rules · <q> request-scoped values threaded · <i> inputs at the edge, <u> unparsed · <l> repeated literals, <x> repeated expressions, <k> facts stated twice · <n> functions split by role, <r> mixing roles, <p> pass-throughs · <n> doc items checked, <e> with an effect or exit missing, <s> leaking mechanism
Rewrote  path:line  the rewritten doc comment, quoted verbatim
Fixed    path:line  smell → what you did
Bug      path:line  bug → the fix, and the behaviour that changed
Behaviour path:line  smell fix → the small behaviour it changed, and why it pays
Asked    path:line  smell → the question, and the patch when the answer was later
Kept     path:line  smell → why, and the trigger
Planned  path:line  smell → where the plan entry is (file and heading, or issue)
Discarded path:line  finding → why it does not hold
Skipped  path:line  finding → its score, under the threshold
Rejected path:line  smell → the user's reason
```

The Survey line is not optional and its numbers come from the pass, not from
memory: a run that skipped a step cannot fill it honestly, and a reader can hold
the doc count against `grep -cE '//[/!]'` over the changeset. The count of items
*looked at* proves nothing by itself; the count with a missing effect or exit is
what a skipped step cannot fake, and the same goes for the count of functions
mixing roles and of shared context columns. Each number is the sum of what the
survey agents returned, counted from the lines that §3.0, step 2 asks of them. A
number with no lines behind it means the step did not run, and so does a batch
whose agent failed or skipped a file. Then the run is incomplete. Say so at the
top of the report, name the steps and the files that were missed, and do not
present the fixes as the result of a full pass. Every rewritten doc comment
appears verbatim under `Rewrote`: the user reviews them in one place, and a
rewrite that reads badly in the report reads badly in the code.

The `Fixed`, `Asked`, `Kept`, `Planned`, `Discarded`, `Skipped` and `Rejected`
lines together account for every finding of the run, and the report names any
finding still open (§5, "Every finding ends in a bucket"). Then one line names
the run directory, so that the user can review the findings and decisions there,
and the last line gives the verification result (tests/typecheck:
pass/fail/absent). No essays. If the explanation is longer than the diff, the
diff was wrong.
