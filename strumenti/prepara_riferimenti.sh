#!/usr/bin/env bash
# Ricopia in riferimenti/ i file pesanti esclusi da git (dati di prova,
# sorgenti completi di WinWCP, guida PDF) dalla cartella sorgente originale.
set -euo pipefail
QUI="$(cd "$(dirname "$0")/.." && pwd)"
# La cartella dei materiali del laboratorio non e' pubblica: va indicata.
SRC="${1:?Uso: strumenti/prepara_riferimenti.sh CARTELLA_DEI_MATERIALI_DEL_LABORATORIO}"
MP="$SRC/software micropunture"
mkdir -p "$QUI/riferimenti/dati" "$QUI/riferimenti/doc" "$QUI/riferimenti/winwcp_sorgenti"
cp -p "$MP/dati di prova/"*.wcp "$QUI/riferimenti/dati/"
cp -p "$SRC/LPF-8 manual.pdf" "$MP/WinWCP_User_Guide.pdf" "$QUI/riferimenti/doc/"
cd "$QUI/riferimenti/winwcp_sorgenti"
[ -d master ] || { unzip -q "$MP/WinWCP-master.zip" -d tmp_m && mv tmp_m/WinWCP-master master && rmdir tmp_m; }
[ -d XE-5.8.1 ] || { unzip -q "$MP/WinWCPXE-5.8.1.zip" -d tmp_x && mv tmp_x/WinWCPXE-5.8.1 XE-5.8.1 && rmdir tmp_x; }
# WinWCP 5.2.7 (la versione piu' vicina alla 5.1.6 del laboratorio): estratto in
# winwcp_sorgenti/installatore_5.2.7 (fuori da git; riepilogo in riferimenti/winwcp5_2_7/LEGGIMI.txt)
V="$SRC/versioni winwcp NON CANCELLARE, INTROVABILI ONLINE/WinWCP_V5.2.7_Setup.exe"
if [ -f "$V" ] && [ ! -d installatore_5.2.7 ] && command -v 7z >/dev/null; then
  7z x -y -oinstallatore_5.2.7 "$V" >/dev/null
fi
echo "Riferimenti pronti in $QUI/riferimenti"
