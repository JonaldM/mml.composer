# Nested-Repos Restructure — Tradeoff Analysis

**Date:** 2026-04-27
**Author:** Claude (audit follow-up, agent P1)
**Status:** Decision required — recommendation included, owner picks
**Related audit finding:** Nested git repos with no `.gitmodules` — HIGH severity reproducibility risk

---

## 1. Current state

`mml.odoo.apps` (the parent repo, pushed to `JonaldM/mml.composer`) physically contains the working trees of five other independent git repositories. None of them are registered as submodules. There is no `.gitmodules` file. The parent's working tree shows each nested repo as a single "untracked" or "modified" entry, depending on whether anything inside happens to be staged at that moment.

| Folder in parent | Inner repo's `origin` | Inner repo's HEAD at audit |
|---|---|---|
| `mml.3pl.intergration/` | `https://github.com/JonaldM/mml.3pl.odoo.git` | `70826ef` |
| `mml.fowarder.intergration/` | `https://github.com/JonaldM/mml.freight.fowarder.git` | `6f12080` |
| `mml.forecasting/` | `https://github.com/JonaldM/mml.forecasting.git` | `6feb3f2` |
| `mml.roq.model/` | `https://github.com/JonaldM/mml.roq.odoo.git` | `aacf294` |
| `mml_edi/` | `https://github.com/JonaldM/mml.edi.odoo.git` | `2f7cd17` |

The parent repo itself only tracks `mml_base/`, `mml_roq_freight/`, `mml_freight_3pl/`, `mml.barcodes/`, `mml_test_sprint/`, `docs/`, `conftest.py`, `pytest.ini`, `requirements.txt`, `ssh_utils.py`, `README.md`, `CLAUDE.md`. The nested repos are excluded *only* by virtue of git's "don't recurse into a directory containing its own `.git`" behaviour — not by `.gitignore`, not by `.gitmodules`, not by any explicit declaration.

### Why this is a HIGH-severity finding

1. **No commit pinning.** The parent never records "this build of `mml.composer` requires `mml.forecasting@6feb3f2`". A developer who pulls master and `cd`s into `mml.forecasting/` will see whatever HEAD that nested clone is sitting on — which depends entirely on when *they* last ran `git pull` inside it. Two engineers can run identical-looking workflows on the same parent SHA and get materially different installed Odoo modules.

2. **CI cannot reproduce.** A clean CI checkout of `mml.composer` produces empty directories where the nested repos used to be. There is no manifest CI can read to know which commits to fetch. Any test run that touches `mml_freight`, `stock_3pl_core`, `mml_edi`, `mml_forecast_*`, or `mml_roq_forecast` is currently impossible from a fresh clone without out-of-band knowledge.

3. **Parallel-divergence risk.** Five repos × N developers means each nested repo can drift independently. There is no enforcement that `mml_freight_3pl` (a bridge in the parent) is being tested against the same `mml_freight` and `stock_3pl_core` revisions that production uses. This is exactly the class of failure that the bridge modules' `auto_install` semantics are most sensitive to — the bridge silently activates against a peer schema that may not match what was tested.

4. **Contributor confusion.** New contributors (and agents) reasonably assume `mml.odoo.apps` is the source of truth for everything inside it. They run `git status`, see clean, edit a file inside `mml.forecasting/`, commit, push — and push to `JonaldM/mml.forecasting` without realising the parent repo's history doesn't reflect any of that. The audit transcript flagged this exact pattern.

5. **The `mml.composer` pitch breaks.** The whole point of `mml.composer` (per parent `CLAUDE.md`) is that it is the SaaS license server / billing engine that knows which `mml_*` apps a customer has installed. If the modules' source-of-truth versions are unpinned, "customer X has `mml_freight@<sha>` installed" is unprovable. That is a billing-integrity issue, not just a developer-ergonomics one.

---

## 2. Option A — Convert to true git submodules

Make the relationship explicit. Each of the five nested folders becomes a registered submodule with a pinned SHA recorded in `.gitmodules` and the parent's tree.

### Pros

- **Commit pinning solved.** The parent records the exact SHA of each child. CI can `git submodule update --init --recursive` and reproduce any historical build. The audit's primary HIGH-severity issue is closed.
- **GitHub renders submodules natively** — folder icons turn into "submodule pointer" icons with click-through. Anyone browsing `mml.composer` on GitHub immediately sees this is a composition of five repos and can navigate to each.
- **Familiar tool.** Submodules have been part of git since 2007. Most developers have used them at least once, and CI runners (GitHub Actions, GitLab, Jenkins) all support them as a first-class concept.
- **Independent module sale path is preserved.** Each `mml_*` repo continues to exist as its own GitHub project — exactly the architecture the parent `CLAUDE.md` calls out as a hard requirement ("Each `mml_*` module is a standalone, independently installable Odoo app — a sellable SaaS product"). A buyer who only wants `mml_freight` clones `JonaldM/mml.freight.fowarder` directly, never touches `mml.composer`.
- **PRs against children stay simple.** A PR against `mml.forecasting` is the same as today — push to a branch on `JonaldM/mml.forecasting`, open a PR there. Only the *integration bump* (parent commit moving the submodule pointer) lives in the parent's PR queue.

### Cons

- **Developer ergonomics tax.** Every fresh clone needs `git submodule update --init --recursive` (or `git clone --recurse-submodules`). Forgetting this gives you the empty-folder failure mode again. A single broken `make setup` script is enough to onboard nobody for a week.
- **Submodule pointer drift.** When a contributor lands a fix inside `mml.forecasting`, the parent doesn't move automatically. Someone must `git add mml.forecasting && git commit` in the parent to bump the pointer. If they forget, the parent stays pinned to the old SHA forever — which is correct submodule behaviour, but surprising to anyone expecting subtree-style atomicity.
- **Two-PR cross-cutting change.** A change that touches both `mml_base` (in parent) and `mml.forecasting/mml_forecast_core` (in child) requires: PR #1 against the child, merge, PR #2 against the parent moving the submodule pointer. CI on the parent must wait for the child merge. This is fine for mature multi-repo teams; it is a real friction tax for a one-engineer-plus-agents team.
- **Detached HEAD by default.** Submodules check out at the recorded SHA, which means working inside one for the first time looks like detached HEAD — confusing. A `git submodule foreach git checkout master` or `submodule.<name>.branch = master` config can mitigate but not fully fix this.
- **Sub-repo PRs target the child remote.** If you forget which remote you're pushing to (very easy when terminal cwd is the only signal), you can land work on the wrong project. Worth making a `direnv` / shell-prompt cue mandatory.

### Migration steps (5–7 numbered)

1. **Snapshot today's state.** From parent root: `git submodule status` is empty, but record each nested HEAD SHA and write them into `docs/operations/2026-04-27-submodule-snapshot.md` so we can roll back if anything breaks. (Already captured in §1 above.)
2. **For each of the five nested folders, run inside the parent:**
   ```bash
   inner_remote=$(git -C mml.forecasting remote get-url origin)
   inner_sha=$(git -C mml.forecasting rev-parse HEAD)
   rm -rf mml.forecasting           # NB: removes the inner clone — push first
   git submodule add "$inner_remote" mml.forecasting
   git -C mml.forecasting checkout "$inner_sha"
   git add .gitmodules mml.forecasting
   ```
   (Repeat for `mml.3pl.intergration`, `mml.fowarder.intergration`, `mml.roq.model`, `mml_edi`.) Make sure each child's local commits are pushed to its `origin` *before* `rm -rf` — they will otherwise be lost.
3. **Update `conftest.py` paths if needed.** The root `conftest.py` imports from each workspace; verify nothing breaks with the freshly checked-out submodule layout. Run `pytest -m "not odoo_integration" -q` to confirm.
4. **Add a `make setup` (or `scripts/setup.sh`) that runs `git submodule update --init --recursive` and `pip install -r requirements.txt`.** Wire this into a `CONTRIBUTING.md` and the README's quickstart. Document the "did you forget `--recurse-submodules`" failure mode.
5. **Update CI.** Wherever the pipeline does `git clone`, change it to `git clone --recurse-submodules` (or add an explicit `git submodule update --init --recursive` step). For GitHub Actions: `actions/checkout@v4` with `submodules: recursive`.
6. **Add a parent-side sanity check.** A small script in `scripts/check-submodules.py` that fails CI if any submodule is on a SHA not pushed to its remote, or on a detached HEAD that doesn't match the parent's recorded pointer. Cheap to write, prevents the "I forgot to push the child" footgun.
7. **Document the cross-cutting workflow** in `CONTRIBUTING.md`: child-PR-first, then parent-pointer-bump-PR. Include a worked example using the next bridge change.

### Estimated effort

**1.5 to 2 days.** The mechanical conversion is half a day; the CI and `CONTRIBUTING.md` work is the rest. Risk is low because all five children already exist as standalone GitHub repos with active history.

---

## 3. Option B — Split into independent repos with a manifest

Stop pretending `mml.composer` is a monorepo. Each `mml_*` repo lives entirely on its own. A new tool — a manifest file plus a small CLI — describes which versions of which repos make up an "MML platform release", and a `mml-platform setup` command clones them at the right SHAs into a workspace folder.

### Pros

- **Cleanest boundaries.** Each `mml_*` ships independently as designed. The architecture goal stated in parent `CLAUDE.md` ("each module is a sellable SaaS app") becomes reality at the *repo* level, not just the Odoo-module level. Selling a customer just `mml_edi` is a one-line `pip install -e git+...@v1.4.2` and they never see the rest.
- **No `mml.composer`-as-monorepo confusion.** `mml.composer` becomes what its name says — the SaaS *composer* that orchestrates running instances. The version manifest moves to a small dedicated repo (e.g. `JonaldM/mml-platform-manifest`).
- **Per-repo CI is simpler.** Each project's CI only cares about its own tests. Cross-repo integration testing happens in a single dedicated "platform-integration" job that uses the manifest.
- **Each repo can have its own release cadence.** `mml_freight` can ship a hotfix without dragging the rest of the platform into a release window.

### Cons

- **No single-clone dev workflow.** The most painful change. Today, `git clone JonaldM/mml.composer` (with submodules or even without, sloppily) gives you most of the platform. Under this option, you clone five repos and run a tool to assemble them. This is fine for production deploys; it is harder for the day-to-day of developing a bridge module that needs all parents present.
- **Cross-cutting changes become coordinated multi-repo PRs.** A schema change that ripples through `mml_freight`, `mml_freight_3pl`, `stock_3pl_core` is now three PRs against three repos with manual ordering. Submodules at least give you the parent SHA to anchor "these three landed together". A flat manifest does not.
- **You have to build the manifest tool.** Even a 100-line Python script needs maintenance, docs, tests, error messages. There is no off-the-shelf option that fits Odoo cleanly:
  - **Yarn/pnpm workspaces:** JavaScript-only, irrelevant.
  - **Cargo workspaces:** Rust-only, irrelevant.
  - **Python `pyproject.toml` workspaces (PEP 735, uv, hatch):** would work for the Python side, but Odoo modules are not pip-installable in the standard sense — they live in addons paths and are loaded by `odoo-bin`. You can't lean on a registry.
  - **`google/repo`** (the Android multi-repo tool) is the closest existing fit: an XML manifest of git repos and SHAs, plus a CLI that clones/syncs them. Mature, used at scale, but heavyweight and Python-2-flavoured. Most teams that look at it pick a homegrown shell wrapper instead.
  - **OCA's `repos.yaml` / `oca-fork-merger` / `oca-decentralized-build`** is another viable model — Odoo-aware. Worth studying before rolling your own.
- **CI integration test becomes the expensive job.** Whichever repo owns the cross-repo test must check out all five at the manifest-pinned SHAs every run.

### Example manifest format

A reasonable starting point — borrowed from `repo`'s spirit, kept in YAML so it's editable:

```yaml
# mml-platform-manifest/release-2026-05.yaml
name: mml-platform
version: 2026.05.0
release_notes: docs/releases/2026-05.md

repos:
  - name: mml_base
    remote: https://github.com/JonaldM/mml.base.odoo
    sha: <pinned>
    addons_path: .

  - name: mml_freight
    remote: https://github.com/JonaldM/mml.freight.fowarder
    sha: 6f12080
    addons_path: addons

  - name: mml_3pl
    remote: https://github.com/JonaldM/mml.3pl.odoo
    sha: 70826ef
    addons_path: addons

  - name: mml_edi
    remote: https://github.com/JonaldM/mml.edi.odoo
    sha: 2f7cd17
    addons_path: .

  - name: mml_forecasting
    remote: https://github.com/JonaldM/mml.forecasting
    sha: 6feb3f2
    addons_path: .

  - name: mml_roq
    remote: https://github.com/JonaldM/mml.roq.odoo
    sha: aacf294
    addons_path: .
    note: legacy — superseded by mml_forecast_demand

bridges:
  # bridge modules currently live inside mml.composer alongside mml_base
  - mml_roq_freight
  - mml_freight_3pl
```

A 100-line `mml-platform setup --manifest release-2026-05.yaml --dest ./workspace` script clones each repo to `./workspace/<name>` at the pinned SHA, builds an addons path string, and writes a `.env` the dev can `source`.

### Migration steps

1. Carve `mml_base`, the bridges, and `mml.barcodes` out of the current `mml.composer` repo into their own dedicated repos. This is the largest mechanical change — `mml.composer` shrinks to *just* the SaaS-platform bits (license server stub, billing engine, dashboard) where it belongs.
2. Build `mml-platform-manifest` repo with a starter `release-current.yaml` pinning each child to its current HEAD.
3. Write `mml-platform setup` script (Python, ~100 LOC). Test on a fresh Windows + WSL + Linux laptop.
4. Update `CLAUDE.md` and `README.md` in each repo to point new contributors at the manifest workflow.
5. Stand up a single platform-integration CI job that uses the manifest and runs the existing pytest + odoo-bin tests across the assembled workspace.
6. Deprecate the old `mml.composer` monorepo path. Keep the repo as the SaaS-platform-only home.

### Estimated effort

**1.5 to 2 weeks.** The carve-out and tooling are real work. This is the most disruptive option short term — and arguably the cleanest long term.

---

## 4. Option C — Flatten into a single repo (subtree merge)

Use `git subtree` (or `git read-tree -u` + `git merge -s subtree`) to absorb the full history of each nested repo into `mml.composer` as ordinary directories. Drop the standalone child repos (or keep them read-only as archives). One repo, one history, one truth.

### Pros

- **Single source of truth, end of story.** No submodule init, no manifest tool, no cross-repo PR ordering. `git clone` and you have everything.
- **Atomic cross-cutting commits.** A schema change that touches `mml_base`, `mml_freight`, `stock_3pl_core` is one commit, one PR. Bisect across the whole platform Just Works.
- **Simpler CI.** One pipeline. One coverage number. One release tag.
- **Subtree preserves history.** Unlike a naive copy-and-commit, `git subtree add --prefix=mml.forecasting <remote> master` preserves every commit from the child as ancestor commits of the parent. `git log -- mml.forecasting/` still works.

### Cons

- **Loses per-module sellable-SaaS narrative at the *repo* level.** This is the showstopper given parent `CLAUDE.md`'s explicit architecture goal. A customer who buys only `mml_edi` no longer gets a clean repo to clone — they get a directory inside a much larger one. You can mitigate with `git sparse-checkout` or by exporting subtree subsets at release time, but the "each module is its own thing" story takes a real hit.
- **Repo size grows.** Five repos' histories merged into one — manageable today (still small), but if any one of them later accumulates large binary assets (the .NET `BriscoesEditOrder` binaries inside `mml_edi/` are already a hint of this) it bloats the whole repo's clone size for everyone.
- **Per-module CI granularity is harder.** You can still run `pytest mml.forecasting/` only, but every push triggers the whole pipeline unless you build path-filter logic.
- **The split-back-out path is painful.** If you later decide a module should be its own repo again (e.g. a customer wants to fork `mml_freight` independently), `git subtree split --prefix=...` works but produces a divergent history that's awkward to merge with any external fork.
- **Loses the existing GitHub presence of each child.** `JonaldM/mml.forecasting`, `JonaldM/mml.edi.odoo` etc. become archived. Anyone who linked to them externally hits stale repos.

### Migration steps

1. Push every nested repo's local commits to its `origin` first. (Same first move as Option A.)
2. From the parent: `git subtree add --prefix=mml.forecasting https://github.com/JonaldM/mml.forecasting master --squash` — *or* without `--squash` to retain full history. Repeat for the other four.
3. Delete the existing nested `.git` directories before each subtree add (subtree add expects the prefix to not exist). Stage and commit.
4. Update `CLAUDE.md` and `README.md` to remove all "this is a separate repo" language.
5. Archive each child repo on GitHub with a top-level `MOVED.md` pointing at `JonaldM/mml.composer`.
6. Update CI to drop any cross-repo coordination logic.

### Estimated effort

**3–4 days.** The mechanical merge is one day. The post-merge cleanup of paths, READMEs, archive notices, and CI is the rest.

---

## 5. Option D — Stay as-is, document the assumption

Accept the current shape. Add a small set of guardrails so the audit's risk is *known* rather than *latent*. No structural change.

### Pros

- **Zero migration cost today.**
- **Doesn't lock in a structural decision before MML actually has the team size or external-customer base that justifies one.** The current state is sandbox-stage by the user's own description; the cost of a wrong choice now (six months of manifest-tool maintenance for a one-engineer shop) is real.

### Cons

- **The audit's HIGH-severity finding is not closed, only annotated.** Anyone reading the audit a year from now will see "fixed by docs" and rightly raise it again.
- **The reproducibility hole is real.** A single laptop dying or a CI runner being recreated still loses the implicit "which SHA of the children was tested" knowledge.
- **Does not scale to the SaaS path.** The moment `mml.composer` (the actual platform) starts shipping a paid customer's bundle, "I think we tested against `aacf294` but I'm not sure" is not a billing-defensible position.

### Guardrails that would mitigate the risk

If we go with D, the absolute minimum is:

1. **`CONTRIBUTING.md` at the parent root** explaining the layout: "the five folders below contain independent git clones of these five repos. They are not submodules. Treat each as its own project. Push to its own remote. Do not commit to the parent and expect changes inside these folders to be tracked."
2. **`docs/operations/known-good-shas.md`** — a manually maintained file listing today's HEAD SHA of each nested repo, updated whenever the user does a "release". This gives CI and rollback a target without forcing a tooling decision.
3. **A pre-commit hook in the parent** that warns (or fails) if the working tree contains a nested `.git` directory whose HEAD is not in the latest `known-good-shas.md`. ~30 lines of Python. Cheap insurance.
4. **A `scripts/snapshot-shas.py`** that prints each nested repo's HEAD and remote, suitable for embedding in CI logs and release notes. Already half-built in §1's audit table — promote it to a real script.
5. **A note in `CLAUDE.md`** that any agent or contributor working in a nested folder is operating on a different repo and must verify `git remote -v` before pushing. Belt and braces against the contributor-confusion risk.

### Estimated effort

**Half a day** for all five guardrails.

---

## 6. Recommendation

**Option A — convert to true git submodules — with the Option D guardrails layered on top.**

### Why

The architecture goal in parent `CLAUDE.md` is unambiguous: each `mml_*` repo is a sellable SaaS app, independently installable. That rules out Option C (flatten) — it directly contradicts the stated goal and erases the per-repo GitHub presence that makes "buy just `mml_edi`" credible.

Option B (split with manifest) is the architecturally cleanest answer for the world where MML has 3+ engineers and external customers cloning `mml_freight` directly. It is *too much tooling* for today's reality (effectively one engineer plus agents, sandbox-stage, no paying customers yet). Spending two weeks building and documenting a manifest tool now is premature optimisation; the same two weeks spent on `mml.composer` (the actual SaaS billing engine that doesn't yet exist) returns more.

Option D alone leaves the HIGH-severity audit finding open. That is the wrong message to send the next person who reads the audit.

Option A is the smallest change that closes the audit finding while preserving every architectural property MML actually wants:

- **Each `mml_*` keeps its own GitHub repo** — the sellable-SaaS story is intact.
- **Commit pinning is real** — CI can reproduce, billing can attest "customer is on `mml_freight@<sha>`", rollback has a target.
- **Cross-cutting changes are explicit** — the parent SHA is a single artifact that says "these five children's revisions are the version of the platform that was tested together".
- **It's a 1.5-day change**, not a two-week one. The team-size argument that kills Option B doesn't kill Option A.
- **The Option D guardrails (`CONTRIBUTING.md`, `known-good-shas.md`, `scripts/snapshot-shas.py`) all still make sense on top of Option A** — they protect against the "I forgot to push the child before bumping the parent pointer" failure mode that submodules don't fix on their own.

When to revisit: when MML hires its second engineer, OR when the first paying `mml.composer` customer goes live, OR when the next audit hits the manifest's lack of a release-versioning story. At any of those triggers, re-evaluate whether to graduate from Option A to Option B. Until then, A + D's guardrails is the minimum viable correctness floor.

---

## 7. Decision matrix

Score key: ●●● strong, ●●○ adequate, ●○○ weak.

| Criterion | A: Submodules | B: Split + manifest | C: Flatten | D: Stay-as-is |
|---|:---:|:---:|:---:|:---:|
| Closes audit HIGH-severity reproducibility finding | ●●● | ●●● | ●●● | ●○○ |
| CI can reproduce a historical build from a single SHA | ●●● | ●●● | ●●● | ●○○ |
| Contributor onboarding time (clone → tests pass) | ●●○ | ●○○ | ●●● | ●●○ |
| Atomicity of cross-cutting changes (mml_base + child) | ●●○ | ●○○ | ●●● | ●●○ |
| Ease of selling individual `mml_*` modules as SaaS apps | ●●● | ●●● | ●○○ | ●●● |
| Per-module independent release cadence | ●●● | ●●● | ●○○ | ●●● |
| Migration cost / engineering effort | ●●○ (1.5–2d) | ●○○ (1.5–2w) | ●●○ (3–4d) | ●●● (0.5d) |
| Tooling surface area added | ●●○ (existing) | ●○○ (new tool) | ●●● (none) | ●●● (none) |
| Compatibility with parent `CLAUDE.md` architecture goal | ●●● | ●●● | ●○○ | ●●● |
| GitHub UX — visible structure for outsiders | ●●● | ●●○ | ●●○ | ●○○ |
| Blast radius if reverted | ●●● (low) | ●○○ (high) | ●○○ (high) | ●●● (n/a) |

**Sum (recommendation):** Option A scores highest on the criteria that matter for MML's stated goals — reproducibility, sellable-modules, low migration cost — without taking on the tooling burden of Option B or sacrificing the architecture goal of Option C.
