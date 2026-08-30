#!/usr/bin/env bash
set -Eeuo pipefail

project_dir="${1:?project directory is required}"
deploy_sha="${2:?deploy SHA is required}"
archive_name="${3:?archive name is required}"

release_dir="$project_dir/release"
incoming_dir="$project_dir/incoming"
archive_path="$incoming_dir/$archive_name"
backup_dir="$project_dir/backups/$(date -u +%Y%m%dT%H%M%SZ)-$deploy_sha"
staging_dir="$project_dir/.release-$deploy_sha"
api_service="content-ops-api.service"
worker_service="content-ops-worker.service"
pip_bin="$project_dir/venv/bin/pip"
python_bin="$project_dir/venv/bin/python"

rollback_needed=0

cleanup() {
  if [[ "$rollback_needed" == "1" ]]; then
    systemctl stop "$worker_service" "$api_service" || true
    rm -rf "$release_dir"
    if [[ -d "$backup_dir" ]]; then
      mv "$backup_dir" "$release_dir"
    fi
    systemctl start "$api_service" "$worker_service" || true
  fi
  rm -rf "$staging_dir"
}
trap cleanup EXIT

report_health_failure() {
  echo "new release health diagnostics:" >&2
  systemctl --no-pager --full status "$api_service" "$worker_service" || true
  journalctl --no-pager -n 80 -u "$api_service" -u "$worker_service" || true
}

[[ -f "$archive_path" ]] || { echo "release archive not found: $archive_path" >&2; exit 1; }
[[ -x "$pip_bin" ]] || { echo "production virtualenv not found: $pip_bin" >&2; exit 1; }
[[ -x "$python_bin" ]] || { echo "production virtualenv is missing Python: $python_bin" >&2; exit 1; }
[[ -d "$release_dir/backend" ]] || { echo "current release is missing: $release_dir/backend" >&2; exit 1; }

rm -rf "$staging_dir"
mkdir -p "$staging_dir" "$project_dir/backups"
tar -xzf "$archive_path" -C "$staging_dir"
[[ -f "$staging_dir/backend/pyproject.toml" ]] || { echo "invalid release archive" >&2; exit 1; }
[[ -d "$staging_dir/frontend-dist" ]] || { echo "frontend release assets are missing" >&2; exit 1; }

# Keep production-only configuration and SQLite/storage data outside Git.
cp -a "$release_dir/backend/.env" "$staging_dir/backend/.env"
if [[ -d "$release_dir/backend/data" ]]; then
  cp -a "$release_dir/backend/data" "$staging_dir/backend/data"
fi
if [[ -d "$release_dir/storage" ]]; then
  cp -a "$release_dir/storage" "$staging_dir/storage"
fi

# Install dependencies before stopping the current services. A failed install
# therefore leaves the currently running release untouched. Use a regular
# wheel install because an editable install would retain the temporary path
# after the release directory is swapped.
PIP_DISABLE_PIP_VERSION_CHECK=1 "$pip_bin" install --no-input "$staging_dir/backend"

# The production SQLite database predates Alembic's version table, so a full
# `alembic upgrade head` would replay historical DDL. Apply this release's
# additive session-revocation field idempotently before switching services.
(
  cd "$staging_dir/backend"
  PYTHONPATH="$staging_dir/backend/src" "$python_bin" -m content_ops.schema_maintenance
)

systemctl stop "$worker_service" "$api_service"
mv "$release_dir" "$backup_dir"
mv "$staging_dir" "$release_dir"
rollback_needed=1
systemctl daemon-reload
systemctl start "$api_service" "$worker_service"

for _ in $(seq 1 30); do
  if systemctl is-active --quiet "$api_service" && \
     systemctl is-active --quiet "$worker_service" && \
     curl --fail --silent --show-error http://127.0.0.1:8000/health >/dev/null; then
    rollback_needed=0
    rm -f "$archive_path"
    echo "deployed $deploy_sha"
    echo "backup retained at $backup_dir"
    exit 0
  fi
  sleep 2
done

echo "new release failed health check; rolling back" >&2
report_health_failure
exit 1
