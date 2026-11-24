#!/usr/bin/env bash
# Validazione oggettiva di denoising_live (vedi README, "Come validare il programma").
#
#   ./valida.sh              tutti i test (~13 minuti; obiettivo: meno di 15)
#   ./valida.sh --lungo      aggiunge la prova di 3 ore accelerata (B8)
#   ./valida.sh --iniziale   salva il rapporto come rapporto_iniziale (fase 1)
#
# Senza i dati del laboratorio (riferimenti/dati/*.wcp, non pubblicati) esegue
# solo la parte riproducibile: i test sui dati reali risultano NON VERIFICABILI
# e il rapporto va in validazione_uscita/rapporto_riproducibile/, senza toccare
# quello ufficiale in docs/validazione/.
#
# Variabili utili: DLIVE_PYTHON (Python di sviluppo), DLIVE_DOCKER_IMMAGINE
# (immagine con Python 3.4 + numpy 1.15 + scipy 1.2 + Xvfb, predefinita dlive-py34).
# Nessun accesso alla rete: se l'immagine Docker non c'e' i test E1/E3/E5 e la
# parte nella finestra di B9 risultano NON VERIFICABILI.
set -u
QUI="$(cd "$(dirname "$0")" && pwd)"
cd "$QUI"
PY="${DLIVE_PYTHON:-}"
if [ -z "$PY" ]; then
  if [ -x "$HOME/miniforge3/envs/denoising_live/bin/python" ]; then
    PY="$HOME/miniforge3/envs/denoising_live/bin/python"
  else
    PY="$(command -v python3 || command -v python)"
  fi
fi
IMMAGINE="${DLIVE_DOCKER_IMMAGINE:-dlive-py34}"
LUNGO=0
NOME=rapporto_validazione
for a in "$@"; do
  case "$a" in
    --lungo) LUNGO=1 ;;
    --iniziale) NOME=rapporto_iniziale ;;
    -h|--help) sed -n 2,17p "$0"; exit 0 ;;
    *) echo "opzione sconosciuta: $a"; exit 2 ;;
  esac
done
USCITA="$QUI/validazione_uscita"
rm -rf "$USCITA"
mkdir -p "$USCITA"
RAPPORTO_OPZ=()
if ! ls "$QUI"/riferimenti/dati/*.wcp >/dev/null 2>&1; then
  NOME=rapporto_riproducibile
  RAPPORTO_OPZ=(--cartella "$USCITA/rapporto_riproducibile")
  echo "== Dati del laboratorio assenti (riferimenti/dati): eseguo solo la parte riproducibile;"
  echo "   il rapporto ufficiale, ottenuto con i dati reali, e' docs/validazione/rapporto_validazione.md"
fi
T0=$(date +%s)
echo "== Validazione di denoising_live ($(date '+%d/%m/%Y %H:%M')) — risultati in $USCITA"
"$PY" -c "import numpy, scipy, neo, matplotlib, pytest" 2>/dev/null || {
  echo "ATTENZIONE: nel Python $PY manca uno tra numpy, scipy, neo, matplotlib, pytest"; }

PYTEST_OPZ=(-q -p no:cacheprovider --confcutdir=tests/validazione -o "addopts=")

# --- 1. Docker, in parallelo: PC lento (E6), Python 3.4 (E1) e modalita' Digidata (E7)
DOCKER_PID=""
E6_PID=""
HA_DOCKER=0
if command -v docker >/dev/null 2>&1 && docker image inspect "$IMMAGINE" >/dev/null 2>&1; then
  HA_DOCKER=1
  PY_PREFISSO="$(cd "$(dirname "$(readlink -f "$PY")")/.." && pwd)"
  DOCKER_OPZ=(--rm --init --user "$(id -u):$(id -g)" -e HOME=/tmp -e PYTHONDONTWRITEBYTECODE=1
              -e DLIVE_DISPLAY_VIRTUALE=1
              -v "$QUI":/src:ro -v "$USCITA":/out -v "$PY_PREFISSO":"$PY_PREFISSO":ro -w /src)
  XVFB="xvfb-run -a -s '-screen 0 1280x1024x24'"
  echo "-- Docker ($IMMAGINE): E6 PC lento (--cpus=0.2, ~12 min) in parallelo"
  docker run "${DOCKER_OPZ[@]}" --cpus=0.2 "$IMMAGINE" bash -c \
    "$XVFB python tests/validazione/gui_scenario.py e6 /out" > "$USCITA/e6.log" 2>&1 &
  E6_PID=$!
  echo "-- Docker: test A, B, D, E4 con Python 3.4, poi E7 (finestra in modalita' Digidata)"
  (
    docker run "${DOCKER_OPZ[@]}" -e DLIVE_AMBIENTE=docker34 -e DLIVE_VALIDAZIONE_USCITA=/out "$IMMAGINE" \
      python -m pytest "${PYTEST_OPZ[@]}" tests/validazione/test_A_filtro.py tests/validazione/test_B_catena.py \
        tests/validazione/test_D_digidata.py tests/validazione/test_E_compatibilita.py::test_E4_tempo_di_calcolo
    docker run "${DOCKER_OPZ[@]}" "$IMMAGINE" bash -c "
        $XVFB python tests/validazione/gui_scenario.py e7 /out
        $XVFB $PY tests/validazione/gui_scenario.py e7 /out"
  ) > "$USCITA/docker.log" 2>&1 &
  DOCKER_PID=$!
else
  echo "-- Docker o immagine $IMMAGINE non disponibili: E1, E3, E5, E6, E7 e B9 (finestra) NON VERIFICABILI"
  echo "   (per crearla serve la rete: vedi README § 8)"
fi

# --- 2. Prova dei test con i guasti M1-M4 (copie temporanee, in parallelo) ----
echo "-- Mutazioni M1-M4 in copie temporanee del codice"
"$PY" tests/validazione/mutazioni.py "$USCITA" > "$USCITA/mutazioni.log" 2>&1 &
MUT_PID=$!

# --- 3. Test sul PC di sviluppo ------------------------------------------------
echo "-- Test A, B, C, D, E sul PC di sviluppo"
if [ "$LUNGO" = 1 ]; then export DLIVE_LUNGO=1; echo "   (con la prova di 3 ore, B8)"; fi
DLIVE_AMBIENTE=host DLIVE_VALIDAZIONE_USCITA="$USCITA" "$PY" -m pytest "${PYTEST_OPZ[@]}" tests/validazione \
  > "$USCITA/host.log" 2>&1
tail -n 3 "$USCITA/host.log"

wait "$MUT_PID"
tail -n 4 "$USCITA/mutazioni.log"
if [ -n "$DOCKER_PID" ]; then
  echo "-- attendo il contenitore Docker..."
  wait "$DOCKER_PID"
  grep -E "passed|failed" "$USCITA/docker.log" | tail -n 2
fi

# --- 3b. Finestra sotto Xvfb (E3, E4 con il disegno, E5, B9): per ultima, a
#         macchina scarica (E6 usa al massimo 0,2 CPU), perche' misura tempi e CPU
if [ "$HA_DOCKER" = 1 ]; then
  echo "-- Finestra sotto Xvfb 1280x1024: E3/E4/E5 (5 Hz predefinito; 10 Hz informativo), B9"
  docker run "${DOCKER_OPZ[@]}" "$IMMAGINE" bash -c "
      for p in python $PY; do
        $XVFB \$p tests/validazione/gui_scenario.py e3 /out
        $XVFB \$p tests/validazione/gui_scenario.py b9 /out
      done
      DLIVE_GUI_AGGIORNAMENTO_HZ=10 $XVFB $PY tests/validazione/gui_scenario.py e3 /out
    " > "$USCITA/finestra.log" 2>&1
  grep -E '"esito"' "$USCITA/docker.log" "$USCITA/finestra.log"
  echo "-- attendo E6 (PC lento)..."
  wait "$E6_PID"
  grep -E '"esito"' "$USCITA/e6.log"
fi

# --- 4. Rapporto ---------------------------------------------------------------
echo "-- Rapporto"
"$PY" tests/validazione/rapporto.py "$USCITA" --nome "$NOME" "${RAPPORTO_OPZ[@]}"
if [ "$NOME" = rapporto_riproducibile ]; then
  echo "   (solo la parte riproducibile: con 0 FAIL il verdetto e' PARZIALE; il rapporto ufficiale,"
  echo "    ottenuto con i dati reali del laboratorio, e' docs/validazione/rapporto_validazione.md)"
fi
echo "== Fine in $(( $(date +%s) - T0 )) s"
