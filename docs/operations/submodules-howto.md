# Submodules — workflow

This monorepo (`mml.composer`) tracks five sister repos as **git submodules**.
Each submodule pins a specific commit of its sub-repo. The parent repo is the
authoritative record of which sub-repo commits build together.

## The five submodules

| Path | Sub-repo |
|---|---|
| `mml.3pl.intergration` | [JonaldM/mml.3pl.odoo](https://github.com/JonaldM/mml.3pl.odoo) |
| `mml.fowarder.intergration` | [JonaldM/mml.freight.fowarder](https://github.com/JonaldM/mml.freight.fowarder) |
| `mml.forecasting` | [JonaldM/mml.forecasting](https://github.com/JonaldM/mml.forecasting) |
| `mml.roq.model` | [JonaldM/mml.roq.odoo](https://github.com/JonaldM/mml.roq.odoo) |
| `mml_edi` | [JonaldM/mml.edi.odoo](https://github.com/JonaldM/mml.edi.odoo) |

The mapping lives in `.gitmodules` at the repo root.

## Why this exists

Before this conversion, each sub-repo lived as a nested `.git` directory under
the parent. The parent stored a gitlink (commit pointer) but had no
`.gitmodules` entry, so:

- `git clone <parent>` produced an empty checkout of every sub-repo.
- CI couldn't reproduce a build — it had no way to discover the sub-repo URLs.
- Two developers could see different code and not know it.
- Submodule pointer bumps in the parent were silent and unreviewable.

Proper submodules fix all three by making the URL explicit, the pointer
reviewable, and the clone reproducible.

## Cloning

Always clone with `--recurse-submodules`:

```bash
git clone --recurse-submodules https://github.com/JonaldM/mml.composer.git
cd mml.composer
```

If you already cloned without that flag:

```bash
git submodule update --init --recursive
```

## Pulling latest

To pull the parent and update submodules to whatever commit the parent points
at:

```bash
git pull
git submodule update --init --recursive
```

To pull each submodule's `master` (and update the parent's pointer locally —
do **not** commit that bump unless you mean to ship it):

```bash
git submodule update --remote --merge
```

## Making changes inside a submodule

Per-submodule changes always land in the sub-repo's own PRs first. Only after
the sub-repo PR merges to its `master` do you bump the parent's pointer.

Inside a submodule directory git behaves as if you're in that sub-repo:

```bash
cd mml.forecasting
git checkout -b feat/my-change
# edit, commit, push, open PR in JonaldM/mml.forecasting
```

After the sub-repo PR merges:

```bash
cd mml.forecasting
git fetch origin master
git checkout origin/master         # detached HEAD on the new commit
cd ..
git add mml.forecasting            # stages the new pointer
git commit -m "chore: bump mml.forecasting submodule (PR #NNN)"
git push
```

The parent commit message should reference the sub-repo PR number for traceability.

## Inspecting submodule state

```bash
git submodule status              # SHA, path, branch label for each
cat .gitmodules                   # configured remotes
git diff --submodule              # see pointer bumps as readable summaries
```

A leading `-` in `git submodule status` means the submodule is not initialised
(`git submodule update --init` to fix). A leading `+` means the working copy is
ahead of the parent's recorded pointer (commit it or revert it).

## Rule of thumb

- **Don't** edit submodule code from a parent-repo branch and push from there.
- **Don't** commit a pointer bump that points at an un-merged sub-repo branch.
- **Do** treat the parent's submodule pointer as a release lock: it should
  always point at a sub-repo `master` commit that has merged through review.
