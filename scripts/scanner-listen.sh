#!/usr/bin/env bash
# Foreground HLS → Pulse listener for ScanHead path `player`.
# Another script should detach this (nohup/systemd). Use `stop` to SIGTERM it.
#
#   SCANNER_HLS_URL=http://192.168.10.70:8888/player/index.m3u8 ./scanner-listen.sh
#   ./scanner-listen.sh stop

set -u

HLS_URL="${SCANNER_HLS_URL:-http://192.168.10.70:8888/player/index.m3u8}"
AUDIO_FORMAT="${SCANNER_AUDIO_FORMAT:-pulse}"
AUDIO_DEVICE="${SCANNER_AUDIO_DEVICE:-default}"
PIDFILE="${SCANNER_LISTEN_PIDFILE:-$HOME/scanner-listen.pid}"
LOG="${SCANNER_LISTEN_LOG:-$HOME/scanner-listen.log}"
MIN_DELAY="${SCANNER_LISTEN_MIN_DELAY:-2}"
MAX_DELAY="${SCANNER_LISTEN_MAX_DELAY:-60}"
FFPID=""
DELAY="$MIN_DELAY"

usage() {
  echo "usage: $0 [run|stop|status]" >&2
  exit 2
}

alive() {
  local pid="$1"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

read_pid() {
  [[ -f "$PIDFILE" ]] || return 1
  tr -d '[:space:]' <"$PIDFILE"
}

cmd_status() {
  local pid
  pid="$(read_pid 2>/dev/null || true)"
  if alive "$pid"; then
    echo "running pid $pid"
    exit 0
  fi
  echo "not running"
  exit 1
}

cmd_stop() {
  local pid
  pid="$(read_pid 2>/dev/null || true)"
  if ! alive "$pid"; then
    rm -f "$PIDFILE"
    echo "not running"
    exit 0
  fi
  kill -TERM "$pid" 2>/dev/null || true
  local i
  for i in 1 2 3 4 5 6 7 8 9 10; do
    alive "$pid" || break
    sleep 0.3
  done
  if alive "$pid"; then
    kill -KILL "$pid" 2>/dev/null || true
    sleep 0.2
  fi
  rm -f "$PIDFILE"
  echo "stopped"
}

cleanup() {
  trap - INT TERM
  if alive "${FFPID:-}"; then
    kill -TERM "$FFPID" 2>/dev/null || true
    wait "$FFPID" 2>/dev/null || true
  fi
  if [[ -f "$PIDFILE" ]] && [[ "$(read_pid 2>/dev/null || true)" == "$$" ]]; then
    rm -f "$PIDFILE"
  fi
  exit 0
}

playlist_ready() {
  local code
  if ! command -v curl >/dev/null 2>&1; then
    return 0
  fi
  code="$(curl -sS -o /dev/null -w '%{http_code}' --connect-timeout 3 --max-time 5 "$HLS_URL" || true)"
  [[ "$code" == "200" ]]
}

bump_delay() {
  DELAY=$((DELAY * 2))
  if [[ "$DELAY" -gt "$MAX_DELAY" ]]; then
    DELAY="$MAX_DELAY"
  fi
}

cmd_run() {
  local existing
  existing="$(read_pid 2>/dev/null || true)"
  if alive "$existing"; then
    echo "already running pid $existing" >&2
    exit 1
  fi
  rm -f "$PIDFILE"
  echo $$ >"$PIDFILE"
  trap cleanup INT TERM
  DELAY="$MIN_DELAY"

  while true; do
    if ! playlist_ready; then
      echo "$(date -Is) playlist unavailable, retry in ${DELAY}s" >>"$LOG"
      sleep "$DELAY"
      bump_delay
      continue
    fi
    echo "$(date -Is) starting ffmpeg" >>"$LOG"
    local start now ran rc
    start="$(date +%s)"
    ffmpeg -hide_banner -nostdin -loglevel warning \
      -i "$HLS_URL" \
      -f "$AUDIO_FORMAT" "$AUDIO_DEVICE" \
      >>"$LOG" 2>&1 &
    FFPID=$!
    wait "$FFPID"
    rc=$?
    FFPID=""
    now="$(date +%s)"
    ran=$((now - start))
    echo "$(date -Is) ffmpeg exit $rc after ${ran}s" >>"$LOG"
    if [[ "$ran" -ge 15 ]]; then
      DELAY="$MIN_DELAY"
    fi
    sleep "$DELAY"
    if [[ "$rc" -ne 0 ]]; then
      bump_delay
    fi
  done
}

case "${1:-run}" in
  run|start) cmd_run ;;
  stop) cmd_stop ;;
  status) cmd_status ;;
  -h|--help) usage ;;
  *) usage ;;
esac
