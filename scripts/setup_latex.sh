#!/usr/bin/env bash
# One-time machine setup for the LaTeX toolchain that builds the CV and the
# cover letter. Replaces the docker-compose file that recorded the previous
# machine, installing the same TeX Live release locally instead of in a
# container. Idempotent: safe to re-run.
#
# Run with: sudo bash setup_latex.sh
set -euo pipefail

FONT_SRC="/home/shashaank/job application vault - old/Documents/fonts"
FONT_DST="/usr/local/share/fonts/calibri"

if [[ ${EUID} -ne 0 ]]; then
  echo "This installs system packages and system-wide fonts. Run it with sudo." >&2
  exit 1
fi

echo "== TeX Live =="
# Ubuntu 24.04 ships TeX Live 2023.20240207, the same release the compose file
# pinned as TL2023-historic. texlive-fonts-extra is deliberately left out: the
# only thing needed from it is fontawesome, which costs 2.5 GB installed for two
# icons and is fetched into ~/texmf separately if the base set lacks it.
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  texlive-luatex \
  texlive-latex-recommended \
  texlive-latex-extra \
  texlive-fonts-recommended \
  texlive-pictures

echo
echo "== Calibri, system-wide =="
# The class does \setmainfont{Calibri}. On Linux luaotfload resolves family
# names through fontconfig, so a face in /usr/local/share/fonts plus an fc-cache
# is all lualatex needs. No OSFONTDIR, that was a container-only workaround.
if [[ ! -d "${FONT_SRC}" ]]; then
  echo "Font source missing: ${FONT_SRC}" >&2
  exit 1
fi
install -d -m 0755 "${FONT_DST}"
install -m 0644 "${FONT_SRC}"/calibri*.ttf "${FONT_DST}/"
fc-cache -f "${FONT_DST}" >/dev/null

echo
echo "== Verify =="
fail=0

for bin in lualatex kpsewhich; do
  if command -v "${bin}" >/dev/null; then
    echo "ok   ${bin}  $(command -v ${bin})"
  else
    echo "FAIL ${bin} missing"; fail=1
  fi
done

# Every package the class and the two documents load.
for sty in fontspec fontsize geometry xcolor tikz graphicx ifthen parskip \
           hyperref enumitem amsmath fontawesome; do
  if kpsewhich "${sty}.sty" >/dev/null 2>&1; then
    echo "ok   ${sty}.sty"
  else
    echo "MISS ${sty}.sty"; fail=1
  fi
done

# All four faces, resolved by family name the way fontspec will resolve them.
for style in Regular Bold Italic "Bold Italic"; do
  got=$(fc-match "Calibri:style=${style}" family 2>/dev/null)
  if [[ "${got}" == "Calibri" ]]; then
    echo "ok   Calibri ${style}"
  else
    echo "FAIL Calibri ${style} resolved to '${got}'"; fail=1
  fi
done

echo
if [[ ${fail} -eq 0 ]]; then
  echo "Toolchain complete. Next: bash build_artifacts.sh"
else
  echo "Incomplete, see MISS and FAIL lines above." >&2
  exit 1
fi
