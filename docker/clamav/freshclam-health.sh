#!/bin/sh
# Health of the signature updater (D-20). Unhealthy when:
# - no freshclam run has succeeded in the last 2 h, or
# - the daily signatures were built more than 24 h ago (the API pauses intake at 48 h).
set -u
now=$(date +%s)
if [ ! -f /tmp/freshclam-last-ok ]; then
  echo "AVENEL: no successful freshclam run yet" >&2; exit 1
fi
ok_age=$(( now - $(stat -c %Y /tmp/freshclam-last-ok) ))
if [ "$ok_age" -gt 7200 ]; then
  echo "AVENEL: last successful freshclam run was ${ok_age}s ago" >&2; exit 1
fi
db=$(ls /var/lib/clamav/daily.cld /var/lib/clamav/daily.cvd 2>/dev/null | head -n 1)
built=$(sigtool --info "$db" 2>/dev/null | sed -n 's/^Build time: //p')
case "$built" in
  *" +0000") ;;
  *) echo "AVENEL: cannot read the signature build time ($built)" >&2; exit 1 ;;
esac
built_s=$(TZ=UTC date -D "%d %b %Y %H:%M" -d "${built% *}" +%s) || exit 1
age_h=$(( (now - built_s) / 3600 ))
if [ "$age_h" -ge 24 ]; then
  echo "AVENEL: WARNING daily signatures are ${age_h} h old (intake pauses at 48 h)" >&2; exit 1
fi
echo "ok: last run ${ok_age}s ago, signatures ${age_h} h old"
