---
name: unsmell
description: Find and fix code smells in the current working changes (unstaged + staged + untracked) — duplication, unnamed tuples and returns, primitive obsession and blind types, boolean and algebraic blindness, long functions/files, if-forests, parameter bloat, data clumps, missing receivers (sibling functions that all take the same context and want to be methods of one type), concept mixing and mixed altitude (functions whose steps are interleaved with setup detail or inline rules), generic data structures and algorithms written inline (memoizing, bounded parallel maps, mailboxes, traversals, retries, caches), narrating doc comments. Refactors what has one right answer, asks about what doesn't, and leaves a reasoned comment on the rare smell worth keeping. Use when the user says "unsmell", "/unsmell", "refactor this", "clean up my changes", "is this smelly", "code smells", "deodorize", or asks for a refactor pass before committing.
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

A second pass in the same session re-reads every touched file from disk. What
you remember writing is the hunk view with extra confidence: it carries the
reasons, which is exactly what hides a smell. "I reviewed that last time" covers
nothing that has been edited since, and nothing you wrote yourself.

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

**Then group the functions by the parameters they share.** A free function
reads fine alone; the smell is only visible across siblings, when the same
context arrives as arguments again and again. For every file, write a table
with one row per function and one column per parameter. Name each column by
what the value is, not by its spelling: `buckets`, `store` and `db` are one
column when they hold the same store. Then look down the columns:

```
answer(request, buckets, console_user)
create_bucket(request, buckets, bucket)       buckets ×3, console_user ×1 but
heartbeat(request, query, buckets, bucket)    only to pick the user for the others
serve(port, buckets, console_user)            → struct Api { buckets, console_user }
```

A column is a finding when two or more functions take it and it is context,
not the input being worked on: a store, a client, a connection, a config, a
registry, a logger, a callback. The input (the request, the line, the event)
stays a parameter. Two more tells make it certain: one sibling passes the
value straight down to another, and the value is captured once by a closure
or a thread and then handed to every call. The fix is the receiver the
functions were missing: the shared values become its fields, the functions its
methods, and the caller builds it once. Use the language's form for state
plus behaviour: a struct with an impl block, a class, a Go type with methods,
a closure over the values, a module-level object. A single shared column
counts when it is real state; the catalog's 3+ threshold for a data clump is
for values that travel together, not for state that every function reaches
into.

**Then look for generic data structures and algorithms written inline in
domain code.** A mechanism hand-built inside a domain function (a cache, a
queue, a traversal, a concurrency pattern) is two concerns in one body. The
reader has to verify the mechanism before reaching the domain logic, and each
copy carries its own subtle bugs. It hides in plain sight because it looks
like ordinary code, in any language. Sweep the changeset for these shapes by
what the code does, not by its names:

| What the body does | The generic thing it is |
|---|---|
| keeps a table of in-progress or finished results per key; later callers wait for or reuse the first | memoize / compute once per key |
| starts work for every item with at most N running, collecting results by index | ordered parallel map with bounded concurrency |
| packs a request with a reply slot, sends it to the owner of some state, and waits with a timeout or cancellation | a call into an actor / mailbox |
| stores a value and wakes one consumer, overwriting what it has not taken yet | latest-value cell / conflating channel |
| races a result against cancellation or a timeout by hand | the codebase's or runtime's await-with-cancel helper |
| copies a collection while skipping, grouping, indexing, partitioning or deduplicating, even when the copy is consumed in the same loop that mutates state | the standard library's filter / group-by / associate / unique operations, applied before the effect |
| walks a graph of dependencies with a visited set, or orders items by them | a traversal / topological sort |
| loops with a sleep that grows, a counter and a give-up condition | retry with backoff |
| evicts by age or size, keeps the N most recent, merges overlapping ranges, keeps a sorted buffer | a cache, a ring buffer, an interval set, a priority queue |

For each hit, look for an existing implementation in this order: the repo's
own utility module, the language's standard library, then the ecosystem's
well-known supplementary libraries. Some places to look:

- Rust: std, `itertools`, `futures` (`buffered`, `join_all`), `tokio::sync`
  (`watch`, `oneshot`, `mpsc`), `once_cell` or `OnceLock`.
- TypeScript/JavaScript: `Map`/`Set`, array and iterator helpers,
  `Promise.all`/`Promise.race`, `AbortSignal`, a small limiter such as
  `p-limit`.
- Kotlin: stdlib collection operations (`groupBy`, `associateBy`,
  `partition`), coroutines (`Channel`, `StateFlow`, `async`/`awaitAll`,
  `Semaphore`, `withTimeout`).
- C++: `<algorithm>` and ranges, `std::future`/`std::promise`,
  `std::call_once`, the containers.
- Python: `functools.cache`, `itertools`, `collections`, `asyncio`
  (`gather`, `Semaphore`, `Queue`, `wait_for`).
- Go: the standard library, `golang.org/x/sync` (`errgroup`,
  `singleflight`).

Check that the semantics match before reusing one. For example, a
single-flight helper shares only an in-flight call and forgets its result, so
it is not memoization. If nothing fits, extract a small generic type or
function into the repo's utility module, in the language's own idiom
(generics, templates, type parameters). Give it its own tests, with the race
checker or sanitizer the language offers and a fake clock for anything
concurrent. Then replace every site in the changeset that has the same shape;
one extraction usually finds two or three callers. The domain code left
behind reads as its domain: a fetch, a decision, a state change.

**Then take every changed function apart by what its lines do.** The
declaration inventory and the doc read both judge one line at a time, and a
flow read judges each hunk on its own ("this edit is small"). None of them
sees a function that grew a second job, one small edit at a time. List every
function the changeset added or changed, with its whole body
(`git diff HEAD -W` prints each touched function in full). Tag each block of
statements with exactly one role:

- **step**: a call to a named thing that the function orders ("create the
  file", "install the layers", "announce the path");
- **detail**: building or configuring a value in place (builder chains,
  format strings, filter parsing, closures handed to a library);
- **decision**: a policy written inline (a heuristic, a string match on a
  message, a threshold, a classification of an error or a value);
- **effect**: I/O, a write, a log line, a send, a state change;
- **assembly**: shaping the result that is returned.

Each of these is a finding:

1. **Steps and details mixed** (mixed altitude): the function orders named
   steps, and between them sit blocks of detail. Extract each block into a
   named `build_…`/`make_…` helper, and move its comment with it, so the
   function reads as its steps.
2. **A decision inside assembly or an effect** (concept mixing): the function
   builds a result or does I/O and also holds the rule that picks the branch.
   The rule gets its own named predicate or classifier. Find the siblings
   before you name it: when other rules of the same kind already live in named
   helpers (`looks_like_range_limit`), a new inline rule
   (`message.contains("batch")`) is a finding however short it is, and its
   helper goes next to theirs.
3. **The diff added a role**: compare with `git show HEAD:<file>`. A function
   that had one role and now has two is a finding even when every added line
   is fine on its own. Growth is how these arrive.
4. **No role of its own** (a pass-through): the whole body is one call,
   passing the parameters on, reshaped at most, plus a trivial result
   (`Ok(())`). One call is not the cleanest shape: it is two names for one
   thing, and the reader hops for nothing. Grep the callee's callers: when
   this function is the only one, merge them. Put the body where the name
   is required (a trait method, a public entry point) and move the callee's
   doc with it. Shrinkage is how these arrive: a refactor removes the
   checks or conversions that surrounded the call and leaves the shell.
   Mark such a function `pass-through` in the role list, never `step`. A
   wrapper that adds something is not one: a default argument, a narrower
   type, a lock, a trait or visibility boundary the callee cannot sit
   behind itself.
5. **A loop that computes and mutates**: one loop body both works out a
   collection or a selection (skipping, splitting into kept and missing,
   grouping, looking a value up to decide) and changes state or does I/O
   with what it found. Tells: a `match`/`if` whose arms mix a `push` onto a
   local with a mutation of `self` or a call with effects; a local `Vec` or
   counter filled beside a write; an `if` wrapping the whole body. The
   selection is a pure computation with a standard name (`partition`,
   `filter`, `filter_map`, `group_by`); take it out first, then run the
   effect over its result. The shape hides from the table row below
   ("copies a collection while partitioning") because the copy is never
   returned: it is consumed in the same body. Mark the loop `decision +
   effect, inline` in the role list.

Write one line per function: `name: roles`, and mark each role as inline or
called (it goes through a named function). A function may combine roles as
long as all but one are called: `match` on a named classifier, then assemble
the result, is fine. Two roles written inline is the finding, and so is a
function whose only role is a call to a callee it alone calls. Fix it, or list
it as Noticed with the split you would make. This is a checklist like
the declaration inventory; do it for the whole changeset, including functions
whose diff is one line.

**Then read each doc comment against its signature, in this order.** A doc
comment is part of the interface: it says what the function produces from what
it is given, and what happens at the edges. "Documented item" means every
`///` and every `//!`: a module doc is the doc of the largest item in the file
and the first one a reader meets. Its first sentence says what the module
decides or provides, in the reader's terms; a list of its mechanisms in the
order they run is narration, and a word only an ADR defines is a finding. One that narrates the body instead
("takes the anchor, walks back, stamps each row, then…") tells a caller nothing
the signature did not, and goes stale the moment the body changes. The author
cannot see this by comparing the comment to the body — a narrating comment
always matches the body; matching is the smell. So for each documented item:

1. Read the signature and the doc only. Write down what you expect to get back
   and when it errors.
2. Only then read the body, and list three things from it, not from the doc:
   - the effects: every write, network call, spawn, delete, or state change
     (grep the body for `INSERT|UPDATE|DELETE|reqwest|spawn|create_|add_|
     record_|store_|remove_`);
   - the exits: every `bail!`, `ensure!`, `?` with a context, or early return
     a caller could cause (grep for `bail!|ensure!|context\(`);
   - the sibling: another method whose difference from this one is one of
     those effects.
   Each effect must be in the doc's main clause, not in a participle ("…,
   registering it when …"). Each caller-caused exit must be named. A sibling
   must be pointed at from the one with the surprising effect. Two further
   findings: your expectation was wrong or blank — the doc does not state the
   contract; or the doc could only have been written after reading the body —
   it names sort keys, tie-breaks, branch order, a SQL or regex mechanism, or
   what the *caller* does with the result ("in the order they are tried").
3. A precondition phrased as "must" ("it must exist and be enabled") is a
   third: name the error instead.
4. Narration has a vocabulary: sequence and branching words, which a body has
   and a contract does not. Grep every doc line in the changeset for them —
   `grep -nE '//[/!].*\b(then|first when|on a miss|in the order|after that|
   before that|once |, or,)\b'` — and treat each hit as a finding until it is
   shown to state what comes out rather than how.
5. A rewrite is the newest text in the changeset and the only text nobody
   re-read. Before the report, run step 1 on every doc you rewrote as if seen
   cold, and run the grep of step 4 over it; a rewrite that needs a second
   reading, or that satisfied a rule by cramming the mechanism into a clause,
   goes back. Presence of the effects and exits is necessary, not sufficient.
   Two shapes pass every rule above and still read as nonsense, so check for
   them by form: a stand-in main verb (gives, makes, handles, deals with) with
   the real contract in an appositive after a colon ("gives block its state
   and its portal transactions: the candidates that…, applied … on state"),
   and an adjective or participle with no referent in the doc or signature
   ("a changed entry": changed from what? "applied on state": what is?). The
   cause is usually that the function's result has no name, because it is
   written into a parameter instead of returned; make it return the result
   and the verb ("returns X and Y") writes itself.

Write the fix in Google developer documentation style for API reference
comments (https://developers.google.com/style/api-reference-comments):
present tense, third person, a verb first — `Returns …` for a value, `Gets …`
for a getter, `Checks whether …` for a boolean, `Sets …` / `Updates …` /
`Deletes …` for an effect, `Creates …` for a constructor — and never "this
method" or the method's own name. A parameter description starts with "The"
or "A"; a boolean reads "True if …; false otherwise." A field is a brief noun
phrase that never opens with the field's own name: `// pending is the committed
snapshot…` above `pending *pendingSet` is the identifier read back, so the
phrase starts at what the field holds (`// The committed snapshot of the
mempool view…`), and a trailing `// Wraps since prevState.` on `wraps` is the
same smell in one line. No declaration's doc opens with its own name —
function, method, type, constant or field: the comment sits on the declaration,
so the name is duplication however much Go's `Name verbs…` convention asks for
it. Only a linter rule the repo enables (revive `exported`, stylecheck
ST1020–ST1022) keeps it, as a §2 rule. And a field comment says why the field
is there — who reads it, or what would go wrong without it — not only what it
holds: `// The outputs paying a tail pkScript; a spend of one is a portal tx`
narrates the set, `…: an input names only the outpoint it spends, so this is
how the scan finds a key rotation` earns it. Survey each field comment for its
why the way step 2 surveys a function doc for its effects; a field is the one
declaration whose reason the signature cannot carry. A type's first sentence
states its purpose without repeating its name.

**Check doc openings mechanically, not by reading**: the eye skips a name it
has just read on the line below, and the `Name verbs…` habit writes the smell
fluently. For every declaration with a doc or trailing comment, compare the
comment's first word to the declared name, case-insensitively for fields, and
rewrite every match. Exact: a `go/ast` walk over `FuncDecl`, `GenDecl` specs and
`StructType.Fields`. Quick, over the changeset's Go files:

```sh
awk '/^[[:space:]]*\/\/ / { if (c=="") { c=$2; sub(/[:,.]$/, "", c) }; next }
     /^(func|type) / { n=$0; sub(/^func (\([^)]*\) )?/, "", n); sub(/^type /, "", n); sub(/[^A-Za-z0-9_].*/, "", n); if (c!="" && c==n) print FILENAME":"FNR": "n }
     { c="" }' $files                                              # doc above a func or type
awk '/^[[:space:]]*\/\/ / { if (c=="") { c=$2; sub(/[:,.]$/, "", c) }; next }
     /^[[:space:]]+[A-Za-z_][A-Za-z0-9_]*([,[:space:]]|$)/ && !/=/ && $1 !~ /^(if|for|return|switch|case|go|defer|var|const|type|func|select|break|continue|else)$/ { if (c!="" && tolower($1)==tolower(c)) print FILENAME":"FNR": "$1 }
     { c="" }' $files                                              # doc comment above the field
grep -nP '(?i)^\s+([A-Za-z_]\w*)\b[^/]*//\s*\1\b' $files          # trailing comment on the field line
```

The field awk also fires on an implicit-iota entry of a `const (` block; that
is a finding too. Everything the three commands print is a finding. Other
languages: the same comparison over functions and `struct`/`class` members
(`/// foo: …` above `foo:` in Rust, a `#:` or attribute docstring in Python).
Fix all of them in one pass; one left over teaches the next reader the habit.

**An entity's doc states its place in the system, never its interface.** A
type, trait or module doc says what the thing is the one way to, who reaches
what through it, and what it keeps the rest from knowing: "The one interface
coverage is read and chunks written through, so rows and coverage agreeing is
the store's concern alone." It never lists its fields ("One run: the chain,
its connections, its block estimator"), its methods ("adds one, finds one by
reference, lists them, slices one") or its subcommands: those are the
declaration read back, they say nothing about why the thing exists, and they
go stale with every change to the interface — an encapsulation leak in prose.
An actor is placed by what it serves and hides; a state or message type by
who produces it and who consumes it for what; an interface by what an
implementor is trusted with. Two lines, rarely three; a worked example
belongs in the ADR or the module doc. Survey it separately: extract every
doc attached to a `struct`, `enum`, `trait`, `type` or module and read each
for a list of verbs or of members — the flow read walks straight past them.

A doc comment is two sentences unless it earns a third: what comes out and
what it does, then the errors a caller can cause. Its first clause says why
the item is called, in the caller's terms, and a reader who finishes it still
not knowing why the call exists has read a useless comment whatever else it
lists ("adds every output of tx paying a tail pkScript to the tracked
outpoints" tells the mechanism; "remembers tx's outputs to tail pkScripts so
the scan can recognise a later spend by its input alone" tells the reason).
One or two lines is the target; a doc that needs more to say why is
describing a function that does too much, so refactor before rewording. Leave out what the types,
defaults, or the type's own doc already say, and infrastructure failures (the
database, the network), which every method has. If the rewrite is longer than
the signature block below it, cut before shipping.

**A doc names a value by what it is at the signature.** A parameter is bare
(`want`); a field is its path (`Query.need`); a method is its path
(`Query::call`). Never the option or flag that fed the value (`--min-sources`
for `Query.need`): that leaks another layer's vocabulary into this one, and
the reader of this layer has no way to find it. And a bare name that is
neither a parameter nor a sibling field reads as a missing or renamed
argument, which is a bug report against the doc. Grep the changeset's doc
lines for flag names — `grep -nE '//[/!].*\B--[a-z]'` — outside the module
that parses them.

**A doc earns its place by a fact the code does not show.** Read each doc
beside its item and ask what the reader learns beyond the signature. A
constructor doc that names its parameters back ("Creates a runner over
`store` and `sources`, paced for `cadence`" on `new(store, sources,
cadence)`), a field doc that names its type back ("The source." on `source:
SourceId`), a getter doc that names the method back ("Gets the label.") is a
tautology: delete it, do not reword it — verb-first restatement is still
restatement. A clause that follows from the one before it is a tautology
too ("it is never mutated; a change replaces it whole": the second is the
first), and what earns the line is the reason for the first. What stays is a unit, an ordering, a None or panic condition,
an inclusive bound, where a value comes from, or who consumes it. Survey it
by listing every doc of a sentence or less and every constructor doc next to
its declaration; tautology lives in the short ones. Restating what sits in
another file counts too: a field doc that lists the fields of its type
("Fetching: chunk size, requests in flight, finality" on `fetch:
FetchTuning`), a method doc that lists what its return type holds — that is
duplication, and it drifts the first time the other file changes. Exceptions that stay
when plain: user-facing help text (clap), columns a doc-capturing table macro
requires, and associated types of a trait. No missing-docs lint means an
undocumented item costs nothing.

**Every noun in a doc names its referent.** A project uses one word for
several things — "request" for a JSON-RPC request, a planner's request and a
fetcher's ask; "call" for a contract call and an RPC method; "logs" for EVM
logs and diagnostics; "lists" for chain lists and token lists; "chunk" for a
log range, a halver's unit and a hypertable's — and a doc that says the bare
word makes the reader guess. Say which: "JSON-RPC requests in flight",
"reports on stderr", "the configured token lists". List the project's
overloaded nouns once, grep the changeset's doc lines for each, and rewrite
every hit that does not disambiguate. The same sweep catches a stale name
(a type renamed, a mechanism removed) and a claim the code no longer makes
(an exemption, a replacement, a fallback); check each against the code, not
against memory. An identifier is a noun too: a method or field whose name is
also a word — `commit`, `retry`, `start`, `next`, `loop` — written bare in
prose ("and commit recomputes it") reads as the word, so it carries its
qualifier (`pendingUpdate.commit`, `blockStream.retry`) wherever it is not
the doc's own subject. Grep the changeset's comment lines for the project's
word-named identifiers and qualify every hit that means the identifier. And a
verb with a settled technical meaning — commit, publish, flush, lock, seal,
sign — applied to an operation that does none of it ("commit the pending set",
for a state that is neither persisted nor bound to anything; "publish", when
nobody gains access) misleads the same way, and the misuse usually starts at a
method name: rename the operation, and the prose follows. Before proposing the
new name, say in one sentence what the operation does and pick the plainest
verb for that ("apply", for an update that takes effect). Include such verbs in
the overloaded-noun list.

**A normal comment is two to three lines**, doc or not. Longer is not a
style slip to trim; it is a smell with one of two causes, and the fix goes to
the cause, not the prose: (a) the thing commented is not structured well — it
does several jobs, its parameters need explaining one by one, its edge cases
outnumber its purpose — so the comment is carrying what the code's shape
should; or (b) the comment describes the wrong thing — the body's steps, the
mechanism, the history, the caller — instead of the contract. Shorten by
fixing (a) or (b); a comment cut in half that still narrates is still the
smell. The report names which cause it was.

```
/// The registered chain `chain_ref` names, registering it from the
/// catalog when it is only listed there.                  ✗ effect in a participle, no errors
/// Returns the registered chain `chain_ref` names, registering it (schema
/// included) when only the catalog knows it. Errors when the reference is
/// unknown or ambiguous; [`Db::registered_chain`] never registers.      ✓ effect, errors, sibling

/// One run: the chain, its connections, its block estimator, and the
/// requested block range.                                   ✗ an actor described by its fields
/// Runs one log-serving command: resolves the chain and the range, serves
/// logs through the cache, stamps block times and answers contract calls.  ✗ its methods read back
/// One command's run on one chain: what the log-serving commands place
/// their ranges and logs in time through; knows no source.  ✓ its place in the system

/// Creates a runner over the log cache `store` and `sources`, the
/// fetchers paced for a chain of `cadence`.                 ✗ the signature read back: delete
/// Requests in flight per fetcher.                          ✗ which requests?
/// JSON-RPC requests in flight per fetcher, at most.        ✓ the referent named
```

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
| **Missing receiver** | Sibling free functions all take the same context (a store, a client, a connection, a config, a callback) besides their real input; one passes it on to the next; a closure or thread captures it once and threads it into every call. Fires at one shared value, not three (§3, the parameter table) | A type holding the shared context as fields, with the functions as its methods, built once by the caller: a struct and impl, a class, a type with methods, a closure over the values |
| **Inline generic machinery** | Domain code that also hand-builds a generic data structure or algorithm: a per-key memo, a bounded parallel map, a request/reply mailbox, a latest-value cell, a hand-rolled await-with-cancel, a filtering or grouping copy loop, a traversal, a retry loop, a cache or queue (the table in §3) | Use the existing helper, the standard library or a well-known library; otherwise extract a generic type or function into the repo's utility module with its own tests (race-checked where concurrent), and replace every site of that shape |
| **Concept mixing** | I/O + business logic + formatting in one unit; a module importing across three layers; a rule (a heuristic, a message match, a classification) written inline in a function that builds a result, while rules of the same kind live in named helpers | Separate; push I/O to the edges, keep the core pure; give the inline rule a named predicate next to its siblings (§3, the role pass) |
| **Mixed altitude** | One function alternating between orchestration and byte-twiddling; a setup function whose named steps are separated by blocks of builder chains, filter parsing or closures | Lift details into named helpers so the caller reads as prose; each helper takes the comment that explained its block |
| **Temporal coupling** | Must call `init()`/`setup()` before the thing works | Constructor, builder, or context manager |
| **Speculative generality** | Unused param, single-implementation interface, config value that never varies, hook nothing calls | Delete it |
| **Computing loop with effects** | One loop both selects or splits (a `match` pushing onto a local, an `if` choosing what to act on) and mutates state or does I/O with the result | Compute the selection first with `partition`/`filter`/`filter_map`, then apply the effect over it |
| **Pass-through** | A function whose whole body calls another with its own parameters, and it is the callee's only caller; often left behind when a refactor removed the work around the call | Merge the two: keep the body where the name is required, move the doc along, delete the other |
| **Misleading name** | Name says less (or other) than the body does; comment explains *what* instead of *why*; a compound whose modifier is a domain term binds to the wrong noun (`pendingUpdate` for an update *to the pending set* reads as an update that is *waiting*) | Rename. First say in one sentence what the objects are, who makes them and how long they live; that sentence usually names a known pattern, and the pattern is the name (`pendingSetBuilder`: a mutable builder of an immutable `pendingSet`, one per event). A name coined from the description alone (`pendingSetEdit`) was judged worse than the original. Take the pattern's name, not its shape: splitting the code to match the pattern's method set (`build` + a separate install step) only added a hand-off and was reverted. Delete the comment the name replaced |
| **Long comment** | Any comment past three lines, doc or `//`. Tells: a bullet list of parameters; a "why" paragraph that is really the design history; a warning to the caller about state the type could enforce | Find the cause. (a) Structure: the item does too much or hides its shape — split it, type the invariant, name the helper — and the comment shrinks by itself. (b) Wrong subject: it narrates steps, mechanism, or the caller — rewrite as the contract per §3. Never just trim; a shorter comment with the same cause is the same smell |
| **Interface read back** | An entity doc that lists its fields ("One run: the chain, its connections…"), its methods ("adds one, finds one, lists them") or its subcommands; changes whenever the interface does | Rewrite as the entity's place in the system: what it is the one way to, who reaches what through it, what it hides (§3) |
| **Tautological comment** | A doc that restates the signature: a constructor naming its parameters, a field naming its type, a doc opening with its declaration's own name (`// pending is the committed…` above `pending`, `// portalTxBase returns…` above `func portalTxBase`), a getter naming itself, "Serves `cmd`." on `run(cmd)`; or restates another file — a field doc listing its type's fields, a method doc listing what its return type holds | Delete it; a doc opening with its declaration's name drops the name and starts at the verb (function) or noun phrase (field, type). Keep only a fact the code does not show: unit, order, None/panic condition, bound, origin, consumer (§3) |
| **Ambiguous noun** | A doc uses a word the project overloads — request, call, logs, lists, chunk, rate — without saying which; or a name the code no longer has | Name the referent ("JSON-RPC request", "the configured token lists", "reports on stderr"); check stale names and claims against the code (§3) |
| **Narrating doc comment** | The function's doc retells the body — "takes X, walks back, stamps each row, then…" — so the reader learns the steps, not the contract. Tells: it lists sort keys, tie-breaks, or branch order; it names a mechanism (`coalesce`, a regex, a flag); it describes what the caller does with the result; it states a precondition as "must" instead of naming the error | Rewrite as the interface in Google developer documentation style (§3): verb first, present tense — what comes out, from what goes in, and the edge cases. Steps stay in the body; a *why* goes in a `//` comment. A mechanism the doc had to explain is often a smell of its own — a policy in the wrong layer — so check the code, not just the prose |

Not exhaustive. If it reads badly and you can say why in one sentence, it counts.

## 5. Triage

Every finding lands in exactly one bucket.

**FIX** — do it now, no asking. Mechanical, behaviour-preserving, one obviously
correct answer, blast radius you can see and verify: extract a function, name a
tuple, replace a bool param with an enum, collapse a duplicate, introduce the type
a data clump was already implying, delete dead flexibility, extract inline
generic machinery into the repo's existing utility module (the new file there
is part of the fix, not a reason to ask).

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

When the pointed-at smell is one a previous run of this skill should have
caught, the report also names, before the fix, which survey step would have
found it and why that step was skipped or passed it. A miss with no named cause
will repeat.

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
- "this file's diff is one line" — a touched file is in the changeset whole (§3);
  a mechanical class is fixed everywhere it lives, and a commit split isolates
  the churn

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
Survey   <n> files read whole · <n> declarations inventoried · <n> parameter tables, <c> shared context columns · <n> functions split by role, <r> mixing roles, <p> pass-throughs · <n> doc items checked, <e> with an effect or exit missing
Rewrote  path:line  the rewritten doc comment, quoted verbatim
Fixed    path:line  smell → what you did
Asked    path:line  smell → the question (answers pending)
Kept     path:line  smell → why, and the trigger
Noticed  path:line  out-of-scope smell, untouched
```

The Survey line is not optional and its numbers come from the pass, not from
memory: a run that skipped a step cannot fill it honestly, and a reader can hold
the doc count against `grep -cE '//[/!]'` over the changeset. The count of items
*looked at* proves nothing by itself; the count with a missing effect or exit
is what a skipped step cannot fake, and the same goes for the count of
functions mixing roles and of shared context columns. Every rewritten doc comment appears
verbatim under `Rewrote`: the user reviews them in one place, and a rewrite
that reads badly in the report reads badly in the code.

Then the verification result (tests/typecheck: pass/fail/absent) in one line. No
essays. If the explanation is longer than the diff, the diff was wrong.
