#!/bin/sh
# Saves a task's patch from its worktree and removes the worktree.
R=/home/nb/.cache/unsmell-eval/runs/cf-post-unsmell-20261102-005337/repo/.git/unsmell/20261102-005400
t=$1; from=${2:-$(cat $R/base)}
git -C $R/worktrees/$t add -A && git -C $R/worktrees/$t diff --cached $from > $R/fixes/$t.patch &&
git -C /home/nb/.cache/unsmell-eval/runs/cf-post-unsmell-20261102-005337/repo worktree remove --force $R/worktrees/$t && wc -l $R/fixes/$t.patch
