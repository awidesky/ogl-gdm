#!/usr/bin/env bash
# Bulk smoke test for an ogl-gdm artifact (macOS and Linux).
#
#   ./smoke-test.sh               # each window waits until you close it (Esc)
#   ./smoke-test.sh --timed 5     # instead: 5 seconds each, then kill it
#   ./smoke-test.sh --list        # only show what would run
#
# Runs the tutorial executables from inside their own directory (the assets are
# loaded relative to it), and reports whether they ran.
#
# Interactive (the default): no timeout and no kill - the script waits until you
# close each window (Esc), then moves on to the next one, with the executable's
# output inline. This is the mode for actually using the tutorials, and for
# reading what the gdm probe at the payload root prints about this machine.
#
# Timed (--timed [seconds]): same console output, but each executable is killed
# after a few seconds - a quick pass over the whole set, for when nobody is
# watching. Surviving there means an executable started, found its assets and
# loaded its libraries.
#
# Every executable runs, all of them: four source directories hold two or three
# (tutorial09_vbo_indexing, misc05_picking, t16, t18) and they are separate
# demos, not duplicates of each other - misc05_picking alone covers glReadPixels
# picking, custom ray-box intersection and Bullet physics.
#
# Whatever ships in the payload is picked up automatically - an executable at
# the root (gdm's gdm_example_1_HelloWindow prints the GL/GLSL and GPU info of
# the machine it runs on) needs no entry anywhere.
#
# See README.txt for the libraries the machine needs: on Linux, X11 + Mesa;
# on macOS nothing at all.

set -u

here="$(cd -- "$(dirname -- "$0")" && pwd)"
cd "$here" || exit 2

timed=0
list_only=0
wait_seconds=5
usage="usage: $0 [--list] [--timed [seconds]]"
for argument in "$@"; do
    case "$argument" in
        --list)   list_only=1 ;;
        --timed)  timed=1 ;;
        --*)      echo "$usage" >&2; exit 2 ;;
        *)        wait_seconds="$argument"
                  timed=1 ;;      # a seconds value only means one thing
    esac
done
case "$wait_seconds" in
    ''|*[!0-9]*) echo "$usage" >&2; exit 2 ;;
esac

# one cleanup for the whole script, registered once. The second trap used to
# overwrite the first (leaking the listing file on every run), and zsh cannot
# resolve a bare command name inside an EXIT trap in every context - so resolve
# rm once, up front, and call cleanup explicitly where the script exits.
RM="$(command -v rm)"
listing="$(mktemp)"
cleanup() {
    [ -n "${listing:-}" ] && "$RM" -rf -- "$listing" 2>/dev/null
    return 0
}
trap cleanup EXIT

# 1. let a downloaded copy run.
case "$(uname -s)" in
    Darwin)
        # macOS quarantines everything it downloads; one command clears all of
        # it, which is faster than approving each binary in System Settings.
        xattr -dr com.apple.quarantine . 2>/dev/null || true
        ;;
    Linux)
        # X11 and Mesa come from the distribution - see README.txt.
        # A headless machine needs them too, plus a display: xvfb-run -a "$0"
        ;;
esac

# 2. the executables: every executable file inside a tutorial directory, plus
# one shipped beside them at the payload root (gdm_example_1_HelloWindow, once
# the gdm examples are built and packaged, prints the machine's GL/GLSL info).
# The payload layout needs no list of names to keep in sync with the build; only
# the bundled libraries and the smoke-test scripts themselves are excluded.
# A listing file keeps this identical under bash and zsh: zsh does not split
# unquoted expansions into words, so a for-loop or a process substitution would
# behave differently in each shell.
# The loop variable is deliberately not called `path`: in zsh that name is the
# array behind $PATH, so reading file names into it wipes the command search
# path and every later external command fails with "command not found".
find . -mindepth 1 -maxdepth 2 -type f -perm -u+x \
    ! -path './lib/*' ! -name 'smoke-test.sh' ! -name 'smoke-test.ps1' \
    | sort > "$listing"

executables=()
while IFS= read -r entry; do
    [ -n "$entry" ] || continue
    executables+=("$entry")
done < "$listing"

if [ "${#executables[@]}" -eq 0 ]; then
    echo "error: no executables found under $here (wrong directory?)" >&2
    exit 2
fi

if [ "$timed" -eq 0 ]; then
    printf '%s\n' \
        "smoke test: ${#executables[@]} executables, close each window to move on" \
        "root: $here"
else
    printf '%s\n' \
        "smoke test: ${#executables[@]} executables, ${wait_seconds}s each" \
        "root: $here"
fi
if [ "$list_only" -eq 1 ]; then
    printf '  %s\n' "${executables[@]}"
    cleanup
    exit 0
fi

# 3. run each one. Output is never redirected, in either mode: it lands in this
#    console as the executable produces it.
passed=0
failed=0

for exe in "${executables[@]}"; do
    label="${exe#./}"
    name="${exe##*/}"
    # a separator per executable, so the console can be read - or split at - the
    # boundary between runs
    printf '\n========== %s ==========\n' "$name"
    if [ "$timed" -eq 0 ]; then
        # no timeout and no kill: the script blocks until the window is closed
        # (Esc), and the executable writes straight to this terminal
        ( cd -- "$(dirname -- "$exe")" && exec "./$(basename -- "$exe")" )
        exit_status=$?      # not `status`: that is read-only in zsh
        if [ "$exit_status" -eq 0 ]; then
            passed=$((passed + 1))
            printf 'PASS  %s (closed)\n' "$label"
        else
            failed=$((failed + 1))
            printf 'FAIL  %s (exit %d)\n' "$label" "$exit_status"
        fi
        continue
    fi
    # timed: same console output, but the process is killed after a few seconds.
    # exec replaces the subshell, so $! is the executable itself and can be
    # killed.
    ( cd -- "$(dirname -- "$exe")" && exec "./$(basename -- "$exe")" ) &
    pid=$!
    sleep "$wait_seconds"

    if kill -0 "$pid" 2>/dev/null; then
        # still alive -> kill it. disown first: bash otherwise reports every
        # terminated background job, which buries the actual result.
        disown "$pid" 2>/dev/null || true
        kill -TERM "$pid" 2>/dev/null
        sleep 1
        kill -KILL "$pid" 2>/dev/null
        wait "$pid" 2>/dev/null
        passed=$((passed + 1))
        printf 'PASS  %s\n' "$label"
    else
        # already gone: it exited on its own, and bash has reaped it by now.
        # A clean exit is a pass - the tutorials normally loop until you close
        # them, so exiting at all is unusual, but exiting *successfully* is not
        # a failure of the artifact.
        wait "$pid"
        exit_status=$?      # not `status`: that is read-only in zsh
        if [ "$exit_status" -eq 0 ]; then
            passed=$((passed + 1))
            printf 'PASS  %s (exited cleanly)\n' "$label"
        else
            failed=$((failed + 1))
            printf 'FAIL  %s (exit %d)\n' "$label" "$exit_status"
        fi
    fi
done

printf '\n%d passed, %d failed\n' "$passed" "$failed"
cleanup
[ "$failed" -eq 0 ] || exit 1
