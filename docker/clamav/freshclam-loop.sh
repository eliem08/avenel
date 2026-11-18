#!/bin/sh
# D-20: the freshclam daemon stalled twice on the dev stack (it stopped checking, signatures reached 53 h and
# 67.8 h, intake paused). Instead of one long-lived daemon, run freshclam once an hour as a new process with
# a time limit, so a stuck run is killed and the next hour starts clean. The mirror asks for at most one
# check per hour. clamd reloads changed signatures by itself (SelfCheck, default 600 s) and is also notified.
set -u
while :; do
  if timeout 900 freshclam --daemon-notify=/etc/clamav/notify-clamd.conf; then
    touch /tmp/freshclam-last-ok
  else
    echo "AVENEL: freshclam run failed or was stopped after 15 min (exit $?); next try in 1 h" >&2
  fi
  /bin/sh /opt/avenel/freshclam-health.sh || true  # logs a warning when signatures are too old
  sleep 3600
done
