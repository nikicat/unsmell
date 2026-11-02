#!/bin/sh
# usage: save.sh <task> [<from-commit>]
set -e
run=$(dirname "$(realpath "$0")"); t=$1; from=${2:-$(cat "$run/base")}
git -C "$run/worktrees/$t" add -A
git -C "$run/worktrees/$t" diff --cached "$from" > "$run/fixes/$t.patch"
git worktree remove --force "$run/worktrees/$t"
git diff --stat --no-index /dev/null "$run/fixes/$t.patch" >/dev/null 2>&1 || true
wc -l "$run/fixes/$t.patch"
