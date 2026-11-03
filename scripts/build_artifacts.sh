#!/usr/bin/env bash
# Builds the CV and the cover letter from the LaTeX sources in the vault.
# This is the local form of the compose file's entrypoint: lualatex twice per
# document, then a page count as the completion check.
#
# Needs no root. Run setup_latex.sh once first.
# Run with: bash build_artifacts.sh [name ...]
set -euo pipefail

VAULT="${VAULT:-$HOME/job-application}"
OUT="${OUT:-$VAULT/build}"

# Kills LuaTeX's build timestamp and document ID, so identical input produces a
# byte-identical PDF. Carried over from the compose file unchanged. Any fixed
# epoch works, the only thing that matters is that it never changes.
export SOURCE_DATE_EPOCH=1735689600

# name -> source directory, for the three base templates. lualatex runs with its
# cwd set to the source directory, so the class file and any \includegraphics
# beside the .tex resolve without TEXINPUTS games.
declare -A DEST=()
declare -A SRC=(
  [sbm_de_26]="$VAULT/resume"
  [sbm_in_26]="$VAULT/resume"
  [sbm_coverletter_26]="$VAULT/coverletter"
)

# A per-role variant is not in that map, so a path may be given instead of a
# name. The directory it sits in becomes the compile cwd, which is why the class
# file has to sit beside it. Added 2026-10-02, because the map-only form made
# every generated variant an "unknown target".
targets=()
for arg in "$@"; do
  if [[ "$arg" == *.tex && -f "$arg" ]]; then
    abs="$(cd "$(dirname "$arg")" && pwd)/$(basename "$arg")"
    name="$(basename "$arg" .tex)"
    SRC["$name"]="$(dirname "$abs")"
    # A variant's PDF belongs beside its own source, so a card's two links sit
    # next to each other. Only the three base templates go to $OUT.
    #
    # A base named by its path is still a base. Passing resume/sbm_de_26.tex put
    # its PDF in resume/ and left the stale copy in build/, which is where the
    # script says base templates go and where other things read them from.
    case "$name" in
      sbm_de_26|sbm_in_26|sbm_coverletter_26) DEST["$name"]="$OUT" ;;
      *) DEST["$name"]="$(dirname "$abs")" ;;
    esac
    targets+=("$name")
  else
    targets+=("$arg")
  fi
done

if [[ ${#targets[@]} -eq 0 ]]; then
  targets=(sbm_de_26 sbm_in_26 sbm_coverletter_26)
fi

mkdir -p "$OUT"
fail=0

for name in "${targets[@]}"; do
  dir="${SRC[$name]:-}"
  if [[ -z "$dir" ]]; then
    echo "FAIL $name  unknown target" >&2; fail=1; continue
  fi
  if [[ ! -f "$dir/$name.tex" ]]; then
    echo "FAIL $name  missing $dir/$name.tex" >&2; fail=1; continue
  fi

  out="${DEST[$name]:-$OUT}"
  mkdir -p "$out"
  echo "== $name =="
  # Twice, because the class uses hyperref and the letterhead measures itself,
  # so references and box widths only settle on the second pass.
  for pass in 1 2; do
    if ! ( cd "$dir" && lualatex \
             -interaction=nonstopmode \
             -halt-on-error \
             -file-line-error \
             -output-directory="$out" \
             "$name.tex" ) > "$out/$name.pass$pass.out" 2>&1; then
      echo "FAIL $name  pass $pass, lualatex returned non-zero" >&2
      # The first line-numbered error is the one worth reading.
      grep -m3 -E "^[^ ]+\.(tex|cls|sty):[0-9]+:" "$out/$name.pass$pass.out" >&2 || \
        tail -20 "$out/$name.pass$pass.out" >&2
      fail=1
      continue 2
    fi
  done

  if [[ ! -f "$out/$name.pdf" ]]; then
    echo "FAIL $name  no PDF produced" >&2; fail=1; continue
  fi

  pages=$(pdfinfo "$out/$name.pdf" | awk '/^Pages:/{print $2}')
  bytes=$(stat -c %s "$out/$name.pdf")

  # A missing font is not an error in lualatex, it silently substitutes. The log
  # is the only place that says so, so the build checks it rather than trusting
  # the exit code.
  if grep -qiE "font.*(not found|not loadable)|Unable to find font" "$out/$name.pass2.out"; then
    echo "FAIL $name  a font was not found, see $OUT/$name.pass2.out" >&2; fail=1; continue
  fi

  overfull=$(grep -c "Overfull \\\\hbox" "$out/$name.pass2.out" || true)
  echo "ok   $name  pages=$pages  bytes=$bytes  overfull=$overfull"
done

echo
if [[ $fail -eq 0 ]]; then
  echo "Built. Base templates go to $OUT, and a variant's PDF sits beside its own source."
else
  echo "Build incomplete, see FAIL lines above." >&2
  exit 1
fi
