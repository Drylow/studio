#!/usr/bin/env bash
# Run a native Qt editor with an authenticated display; never use Qt offscreen.
set -euo pipefail
umask 077
if (( $# == 0 )); then
  printf 'Usage: %s command [arguments…]\n' "$0" >&2
  exit 2
fi

editor_runtime=$(mktemp -d "${TMPDIR:-/tmp}/conversation-chess-display.XXXXXXXX")
editor_xvfb_pid=''
editor_package=''
cleanup_editor_display() {
  if [[ -n "$editor_xvfb_pid" ]]; then
    kill "$editor_xvfb_pid" 2>/dev/null || true
    wait "$editor_xvfb_pid" 2>/dev/null || true
  fi
  [[ -z "$editor_package" ]] || rm -f -- "$editor_package"
  rm -rf -- "$editor_runtime"
}
trap cleanup_editor_display EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
  editor_xvfb=$(command -v Xvfb || true)
  if [[ -z "$editor_xvfb" && -x /workspace/.cache/desktop/root/usr/bin/Xvfb ]]; then
    editor_xvfb=/workspace/.cache/desktop/root/usr/bin/Xvfb
  fi
  if [[ -z "$editor_xvfb" ]]; then
    editor_cache=${CONVERSATION_CHESS_EDITOR_CACHE:-/workspace/.cache/conversation-chess-editor}
    editor_xvfb="$editor_cache/root/usr/bin/Xvfb"
    if [[ ! -x "$editor_xvfb" ]]; then
      command -v curl >/dev/null || { printf 'curl is required to fetch the verified Xvfb package.\n' >&2; exit 1; }
      command -v dpkg-deb >/dev/null || { printf 'dpkg-deb is required to unpack Xvfb without root.\n' >&2; exit 1; }
      mkdir -p "$editor_cache"
      editor_package=$(mktemp "$editor_cache/xvfb.deb.XXXXXXXX")
      curl --fail --silent --show-error --location --max-time 60 \
        https://deb.debian.org/debian/pool/main/x/xorg-server/xvfb_21.1.16-1.3+deb13u3_amd64.deb \
        --output "$editor_package"
      if ! printf '365da2b6c93339f34337c434a9489bb6411a240fa47b9f49693d3091745f28c2  %s\n' "$editor_package" | sha256sum --check --status; then
        rm -f -- "$editor_package"
        printf 'Xvfb package checksum mismatch; refusing to execute it.\n' >&2
        exit 1
      fi
      dpkg-deb --extract "$editor_package" "$editor_cache/root"
      rm -f -- "$editor_package"
      editor_package=''
    fi
  fi
  command -v xauth >/dev/null || { printf 'xauth is required for the private display.\n' >&2; exit 1; }
  command -v xdpyinfo >/dev/null || { printf 'xdpyinfo is required to verify display readiness.\n' >&2; exit 1; }
  export XAUTHORITY="$editor_runtime/authority"
  touch "$XAUTHORITY"
  editor_cookie=$(python3 -c 'import secrets; print(secrets.token_hex(16))')
  xauth -f "$XAUTHORITY" add :0 . "$editor_cookie" >/dev/null 2>&1
  "$editor_xvfb" -displayfd 3 -screen 0 1920x1080x24 -auth "$XAUTHORITY" -nolisten tcp \
    3>"$editor_runtime/display-number" >"$editor_runtime/xvfb.log" 2>&1 &
  editor_xvfb_pid=$!
  for ((editor_attempt=0; editor_attempt<100; editor_attempt++)); do
    [[ -s "$editor_runtime/display-number" ]] && break
    if ! kill -0 "$editor_xvfb_pid" 2>/dev/null; then
      cat "$editor_runtime/xvfb.log" >&2
      printf 'Xvfb did not start; check its installed library dependencies.\n' >&2
      exit 1
    fi
    sleep 0.05
  done
  editor_number=$(cat "$editor_runtime/display-number")
  [[ "$editor_number" =~ ^[0-9]+$ ]] || { printf 'Xvfb did not announce a display.\n' >&2; exit 1; }
  export DISPLAY=":$editor_number"
  xauth -f "$XAUTHORITY" add "$DISPLAY" . "$editor_cookie" >/dev/null 2>&1
  unset editor_cookie
  for ((editor_attempt=0; editor_attempt<100; editor_attempt++)); do
    xdpyinfo -display "$DISPLAY" >/dev/null 2>&1 && break
    sleep 0.05
  done
  xdpyinfo -display "$DISPLAY" >/dev/null 2>&1 || { printf 'The private display is not ready.\n' >&2; exit 1; }
fi

if [[ -n "${DISPLAY:-}" ]]; then
  export QT_QPA_PLATFORM=xcb
else
  export QT_QPA_PLATFORM=wayland
fi
# Keep an existing Wayland runtime/socket; all new task directories are private.
if [[ -z "${WAYLAND_DISPLAY:-}" ]]; then
  export XDG_RUNTIME_DIR="$editor_runtime/runtime"
fi
export XDG_CONFIG_HOME="$editor_runtime/config"
export XDG_CACHE_HOME="$editor_runtime/cache"
export XDG_DATA_HOME="$editor_runtime/data"
mkdir -p "${XDG_RUNTIME_DIR:-$editor_runtime/runtime}" "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$XDG_DATA_HOME"

if [[ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ]] && command -v dbus-run-session >/dev/null; then
  dbus-run-session -- "$@"
else
  "$@"
fi
