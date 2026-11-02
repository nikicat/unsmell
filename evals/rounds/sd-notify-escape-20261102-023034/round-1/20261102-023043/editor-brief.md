# Editor brief (shared by every editor of run 20261102-023043)

You are an editor agent of an "unsmell" run. Edit ONLY inside your worktree
(given in your prompt). Never touch the main repo at
/home/nb/.cache/unsmell-eval/runs/sd-notify-escape-20261102-023034/repo, never run git add/commit/stage.

Read /home/nb/src/unsmell/skills/unsmell/SKILL.md sections §5 and §6 first.
Your task's findings are in /home/nb/.cache/unsmell-eval/runs/sd-notify-escape-20261102-023034/repo/.git/unsmell/20261102-023043/findings/b1.yaml and its decision entries in
/home/nb/.cache/unsmell-eval/runs/sd-notify-escape-20261102-023034/repo/.git/unsmell/20261102-023043/decisions.yaml (look up the ids given in your prompt).

Style ground truth: gofmt, go vet, staticcheck. House doc style: Google API
reference style, verb first, plain short sentences, error contracts read
"Errors when…", no doc that opens with its declaration's own name, no colon or
semicolon joining two ideas, comments two to three lines at most.

The changeset under review (already in your worktree's HEAD commit, which is
the snapshot "unsmell base") added HTML escaping of client-controlled text to
Handler.formatBody in internal/notification/desktop.go, plus a regression test
TestHandler_FormatBody_EscapesInjectedMarkup in desktop_test.go.

Make the fix in the final shape the finding names. Run the build check only:
  go build -tags dev ./... && go test -tags dev -run '^$' ./internal/notification/ ./...
(the second command only compiles tests; you may additionally run
 go test -tags dev ./internal/notification/ since it is fast and your task may
 pin behaviour). Do not run linters or the full suite.
Before finishing, read your own diff (git -C <worktree> diff) against the
catalog in SKILL.md §4: a fix that adds a smell is not finished.
If the task cannot be done as described, say so and why.
Reply with: what you changed, every doc comment you wrote quoted verbatim, and
any behaviour change.
