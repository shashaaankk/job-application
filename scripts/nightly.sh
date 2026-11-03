#!/usr/bin/env bash
# The nightly pipeline. Sweeps the portals, screens what comes back, and writes a
# card for every posting that survives into the board's `matched` column.
#
# Nothing here needs an agent. It is the two Python entry points in order, so a run
# produces the same cards whether or not anyone is watching.
#
#   1. sweep.py      collects listings from LinkedIn, Stepstone and Naukri
#   1b. recover_naukri hands Naukri recovery to Antigravity when the sweep's own
#                    remedy did not clear the block
#   2. make_cards.py checks the screen against his rulings, refuses to continue if
#                    any ruling is broken, then screens and writes the cards
#   3. score.py      scores every new card with Antigravity, five at a time, and
#                    moves the ones that fire the document trigger into `to apply`
#   4. prune_matched  clears `matched` of cards below the threshold and cards that
#                    have aged out of the freshness window
#
# Scoring runs on Antigravity rather than Claude because a hundred cards costs about
# 1.5 million Claude tokens and his plan is Pro. His three caps bind the move, so at
# most 35 cards reach `to apply` from one run.
#
# The browser is headed, per the vault, so the run needs a graphical display. A
# laptop asleep at midnight has none, so this waits for one rather than failing, and
# the systemd timer carries Persistent=true so a missed midnight runs on resume.
set -u -o pipefail

VAULT="$HOME/job-application"
PY="$VAULT/.venv/bin/python"
LOGDIR="$VAULT/scripts/data/nightly"
LOG="$LOGDIR/$(date +%Y-%m-%d_%H%M).log"
LOCK="$LOGDIR/.lock"
PROFILE="$HOME/.playwright-profiles/jobs"

mkdir -p "$LOGDIR"
exec >>"$LOG" 2>&1

say() { echo "[$(date +%H:%M:%S)] $*"; }

# one run at a time. A second run would fight the first for the browser profile.
exec 9>"$LOCK"
if ! flock -n 9; then
  say "another nightly run holds the lock, exiting"
  exit 0
fi

say "nightly run starting, vault $VAULT"

# --- wait for a display, up to five hours in five minute steps ---------------
have_display() {
  [ -n "${WAYLAND_DISPLAY:-}" ] && [ -S "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/${WAYLAND_DISPLAY}" ] && return 0
  [ -n "${DISPLAY:-}" ] && [ -S "/tmp/.X11-unix/X${DISPLAY#:}" ] && return 0
  return 1
}
for i in $(seq 1 60); do
  if have_display; then say "display available on attempt $i"; break; fi
  if [ "$i" -eq 60 ]; then say "FAIL no display after five hours, nothing ran"; exit 1; fi
  sleep 300
done

# --- wait for the browser profile to be free --------------------------------
# A Chrome already holding the profile is his own session. The profile allows one
# instance, so the sweep would fail. Waiting is correct; killing his browser is not.
for i in $(seq 1 24); do
  if ! pgrep -af "user-data-dir=$PROFILE" >/dev/null; then
    say "browser profile free on attempt $i"; break
  fi
  if [ "$i" -eq 24 ]; then say "FAIL the browser profile was in use for two hours, nothing ran"; exit 1; fi
  say "profile in use, waiting five minutes"
  sleep 300
done
# a stale lock from a killed browser looks like a live session to Chrome itself
rm -f "$PROFILE/SingletonLock" "$PROFILE/SingletonCookie" "$PROFILE/SingletonSocket" 2>/dev/null

cd "$VAULT" || { say "FAIL vault not found"; exit 1; }

# --- 1. the sweep -----------------------------------------------------------
say "=== sweep starting ==="
"$PY" scripts/sweep.py
rc_sweep=$?
say "=== sweep finished, exit $rc_sweep ==="
# A portal that refuses is recorded by the sweep itself and is not a reason to skip
# the cards, because the other portals' rows are still worth screening.
if [ "$rc_sweep" -ne 0 ]; then say "WARNING the sweep exited non-zero, continuing to the cards"; fi

# --- 1b. Naukri recovery, if its breaker tripped ----------------------------
# The sweep already applies the documented remedy by itself, so reaching here means
# that was not enough. Antigravity takes over, inside the vault's rules, and costs
# no Claude tokens. A portal that stays blocked is recorded and left alone.
say "=== naukri recovery check ==="
"$PY" scripts/recover_naukri.py
rc_naukri=$?
say "=== naukri recovery check finished, exit $rc_naukri ==="
if [ "$rc_naukri" -eq 0 ]; then
  say "naukri is collecting, or never needed help"
else
  say "WARNING naukri is still down, exit $rc_naukri. The cards stage continues on "\
      "what the other portals collected"
fi

# --- 2. the cards -----------------------------------------------------------
say "=== make_cards starting ==="
"$PY" scripts/make_cards.py
rc_cards=$?
say "=== make_cards finished, exit $rc_cards ==="

# --- 3. the score -----------------------------------------------------------
# No cards is not a failure. A night inside a 24 hour window can legitimately find
# nothing new, and the stage says so rather than exiting non-zero.
say "=== score starting ==="
"$PY" scripts/score.py
rc_score=$?
say "=== score finished, exit $rc_score ==="

# --- 4. clear what matched is done with -------------------------------------
# Runs after scoring, so every card has had its band. Pruned cards go to
# .trash/<date>/ and their ids to retired.tsv, so nothing is deleted and nothing
# returns on the next sweep.
say "=== prune starting ==="
"$PY" scripts/prune_matched.py
rc_prune=$?
say "=== prune finished, exit $rc_prune ==="

# --- the summary he reads in the morning ------------------------------------
board="$VAULT/01. job application tracker.md"
matched=$(awk '/^## matched/,/^## to apply/' "$board" | grep -c '^- \[ \]')
toapply=$(awk '/^## to apply/,/^## applied/' "$board" | grep -c '^- \[ \]')
say "RESULT sweep $rc_sweep, naukri $rc_naukri, make_cards $rc_cards, score $rc_score, prune $rc_prune, matched $matched, to apply $toapply"
ln -sf "$LOG" "$LOGDIR/latest.log"
[ "$rc_cards" -eq 0 ] && [ "$rc_score" -eq 0 ] || exit 1
exit 0
