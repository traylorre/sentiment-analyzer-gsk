# Feature Backlog

Bare numbers (117, 118) are features of this repo. A `REPO-NN` prefix means the work
lands somewhere else and this board is just tracking it.

## Queued Features

### 117 - Fix Keyboard Shortcuts Order
**Priority**: Low
**Spec**: specs/117-keyboard-shortcuts-fix/spec.md

CTRL+7,8,9 keyboard shortcuts navigate to wrong sections compared to hamburger menu order.
- Current: circuit, chaos, caching
- Expected: chaos, caching, circuit

### 118 - Fix Dashboard Connection Status
**Priority**: Medium
**Spec**: specs/118-dashboard-connection-status/spec.md

ONE URL dashboard shows "Disconnected" because SSE stream endpoint routes to wrong Lambda.
- Dashboard Lambda has BUFFERED mode
- SSE requires RESPONSE_STREAM mode
- ~~Need CloudFront routing fix or graceful fallback~~ *(Superseded: CloudFront removed in Feature 1203)*

### DOTFILES-01 - Treehouse: git worktree pool manager
**Repo**: ~/dotfiles *(not this repo)*
**Priority**: High
**Spec**: dotfiles/specs/031-treehouse/spec.md *(not written yet)*

Run parallel Claude sessions against the same repo without clobbering each other. Right
now two sessions in one checkout share a working tree, an index, and a branch, so edits,
stashes, and hook state collide.

Treehouse hands each session its own worktree from a managed pool: lease one on session
start, return it on rotate, GC the abandoned ones. Same shape as the handoff tree in 021,
but for checkouts instead of carryovers.

- Follow-on to 015, which listed multi-worktree carryover routing as out of scope and
  called worktree orphans "mitigated, not eliminated" (specs/015-session-scoped-carryover/spec.md:142,
  Race 3 at :20). Treehouse is the piece that closes it.
- Needs to interact with carryover-rotate.sh and carryover-loader.sh, which resolve the
  handoff dir per repo. Pooled worktrees mean the repo root is no longer stable per session.
- Interacts with the battleplan worktree rule in 016 and the "never rebase live hooks in
  the live worktree" hazard, so dotfiles itself is a first-class test case.
- Open questions: pool size, lease identity (session id vs tmux pane), what happens to a
  leased worktree with uncommitted work when the session dies.

---

## Completed Features

(Features moved here after completion)
