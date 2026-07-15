#!/usr/bin/env bash
set -uo pipefail

LABEL="io.github.asswerus.netblackbox"
BASE_URL="${NETBLACKBOX_BASE_URL:-http://127.0.0.1:8080}"
MAX_WAIT_SECONDS="${NETBLACKBOX_CHECK_WAIT_SECONDS:-30}"

ok=0
warn=0
fail=0

pass() {
  printf '✅ %s\n' "$1"
  ok=$((ok + 1))
}

warning() {
  printf '⚠️  %s\n' "$1"
  warn=$((warn + 1))
}

failure() {
  printf '❌ %s\n' "$1"
  fail=$((fail + 1))
}

section() {
  printf '\n== %s ==\n' "$1"
}

section "launchd"
launchd_output="$(launchctl print "gui/$(id -u)/${LABEL}" 2>&1)"
if printf '%s\n' "$launchd_output" | grep -q 'state = running'; then
  pass "Service is running"
else
  failure "Service is not running"
  printf '%s\n' "$launchd_output" | head -n 20
fi

printf '%s\n' "$launchd_output" | grep -E 'state =|runs =|last exit code =|pid =' | head -n 12 || true

section "API readiness"
deadline=$((SECONDS + MAX_WAIT_SECONDS))
status_json=""
while (( SECONDS < deadline )); do
  if status_json="$(curl -fsS --max-time 3 "${BASE_URL}/status" 2>/dev/null)"; then
    break
  fi
  sleep 1
done

if [[ -n "$status_json" ]]; then
  pass "Status endpoint is reachable"
else
  failure "Status endpoint did not become reachable within ${MAX_WAIT_SECONDS}s"
fi

if [[ -n "$status_json" ]]; then
  STATUS_JSON="$status_json" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["STATUS_JSON"])
probes = payload.get("probes", {})
measurements = probes.get("measurements", {})

print(f"state={payload.get('state')} severity={payload.get('severity')}")
print(
    "sampling="
    f"{payload.get('sampling_mode')} / "
    f"{payload.get('sampling_interval_seconds')}s "
    f"turbo={payload.get('turbo_sampling')}"
)
print(
    "active_event="
    f"{payload.get('active_event_id')} "
    f"started_at={payload.get('active_event_started_at')}"
)

for name in ("dns_resolution", "dns_cloudflare", "dns_google"):
    measurement = measurements.get(name)
    if measurement is None:
        print(f"{name}=MISSING")
        continue
    print(
        f"{name}={'OK' if measurement.get('ok') else 'KO'} "
        f"latency_ms={measurement.get('latency_ms')} "
        f"detail={measurement.get('detail')}"
    )
PY

  state="$(STATUS_JSON="$status_json" python3 -c 'import json,os; print(json.loads(os.environ["STATUS_JSON"]).get("state", ""))')"
  if [[ "$state" == "OK" ]]; then
    pass "Current network state is OK"
  else
    warning "Current network state is ${state:-unknown}"
  fi

  missing_dns="$(STATUS_JSON="$status_json" python3 - <<'PY'
import json
import os

measurements = json.loads(os.environ["STATUS_JSON"]).get("probes", {}).get("measurements", {})
required = ("dns_resolution", "dns_cloudflare", "dns_google")
print(",".join(name for name in required if name not in measurements))
PY
)"
  if [[ -z "$missing_dns" ]]; then
    pass "System, Cloudflare and Google DNS measurements are present"
  else
    failure "Missing DNS measurements: $missing_dns"
  fi
fi

section "Incidents API"
if incidents_json="$(curl -fsS --max-time 5 "${BASE_URL}/api/incidents" 2>/dev/null)"; then
  pass "Incidents endpoint is reachable"
  INCIDENTS_JSON="$incidents_json" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["INCIDENTS_JSON"])
print(
    f"incident_count={payload.get('incident_count')} "
    f"source_event_count={payload.get('source_event_count')} "
    f"longest_duration_seconds={payload.get('longest_duration_seconds')}"
)
PY
else
  failure "Incidents endpoint is not reachable"
fi

section "Process and SQLite descriptors"
pid="$(pgrep -f 'netblackbox' | head -n 1 || true)"
if [[ -n "$pid" ]]; then
  pass "Process found: PID=$pid"
  total_fds="$(lsof -p "$pid" 2>/dev/null | wc -l | tr -d ' ')"
  sqlite_fds="$(lsof -p "$pid" 2>/dev/null | grep -c 'netblackbox.sqlite3' || true)"
  printf 'open_files=%s sqlite_descriptors=%s\n' "$total_fds" "$sqlite_fds"
  if (( sqlite_fds == 0 )); then
    pass "No SQLite descriptors are left open at rest"
  elif (( sqlite_fds <= 4 )); then
    warning "SQLite currently has ${sqlite_fds} open descriptors; rerun to confirm they return to zero"
  else
    failure "Unexpectedly high SQLite descriptor count: ${sqlite_fds}"
  fi
else
  failure "NetBlackBox process not found"
fi

section "Summary"
printf 'passed=%s warnings=%s failed=%s\n' "$ok" "$warn" "$fail"

if (( fail > 0 )); then
  exit 1
fi
