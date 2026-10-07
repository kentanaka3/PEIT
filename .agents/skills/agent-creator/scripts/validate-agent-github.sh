#!/usr/bin/env bash

# GitHub Copilot agent frontmatter validator
# ==========================================
#
# Validate YAML frontmatter in a GitHub Copilot custom agent profile.
# The validator is read-only and reports valid fields on standard output so
# the result can be piped into another review step.
#
# USAGE
#   bash validate-agent-github.sh <path-to-agent-file>
#   bash validate-agent-github.sh --help
#
# DESCRIPTION
#   The first line must be an opening `---` delimiter and the next delimiter
#   closes the frontmatter. Only supported top-level fields are accepted.
#   The file is never modified, and repeated validation has no side effects.
#
# OPTIONS
#   -h, --help    Show usage information and exit.

set -euo pipefail
shopt -s extglob
umask 077

readonly SCRIPT="$(basename -- "${BASH_SOURCE[0]}")"
readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

readonly ALLOWED_KEYS_GITHUB=(
  agents
  argument-hint
  description
  disable-model-invocation
  handoffs
  infer
  mcp-servers
  metadata
  model
  name
  target
  tools
  user-invocable
)
readonly ALLOWED_KEYS_PATTERN_GITHUB="$(IFS='|'; echo "${ALLOWED_KEYS_GITHUB[*]}")"

# log
# ---
# Print a timestamped diagnostic message to standard error.
log() { # 6
  printf '[%s][%s] %s\n' \
    "$SCRIPT" \
    "$(date '+%Y-%m-%d %H:%M:%S%z')" \
    "$*" >&2
}

# fail
# ----
# Report an error and terminate with a non-zero status.
fail() { # 6
  local -r status="$1"
  shift
  log "ERROR: $*"
  exit "$status"
}

# usage
# -----
# Print command-line usage information.
usage() { # 12
  cat <<EOF
Usage: $SCRIPT [OPTIONS] <path-to-agent-file>

Options:
  -h, --help    Show this help message and exit.
  --            End option processing.

Examples:
  bash $SCRIPT .github/agents/bash-scripter.agent.md
EOF
}

# require_command
# ---------------
# Verify that a required executable is available.
require_command() { # 5
  local -r command_name="$1"
  command -v "$command_name" >/dev/null 2>&1 ||
    fail 127 "required command not found: $command_name"
}

# extract_frontmatter
# -------------------
# Extract frontmatter and fail if its delimiters are incomplete.
extract_frontmatter() { # 11
  local -r target_file="$1"
  awk '
    NR == 1 && $0 == "---" { in_frontmatter = 1; next }
    in_frontmatter && $0 == "---" { closed = 1; exit }
    in_frontmatter { print }
    END {
      if (!in_frontmatter || !closed) exit 1
    }
  ' "$target_file"
}

# strip_quotes
# ------------
# Strip matching or outer quotes from a string value.
strip_quotes() { # 8
  local val="$1"
  val="${val#\"}"
  val="${val%\"}"
  val="${val#\'}"
  val="${val%\'}"
  printf '%s\n' "$val"
}

# has_key
# -------
# Return success when the requested top-level key is present.
has_key() { # 14
  local -r expected_key="$1"
  local -r frontmatter="$2"
  awk -v expected_key="$expected_key" '
    /^[[:alnum:]_-]+:/ {
      key = $0
      sub(/:.*/, "", key)
      if (key == expected_key) {
        found = 1
      }
    }
    END { exit !found }
  ' <<< "$frontmatter"
}

# get_field_value
# ---------------
# Extract the scalar value of a top-level key from frontmatter.
get_field_value() { # 13
  local -r key="$1"
  local -r frontmatter="$2"
  awk -v key="$key" '
    $0 ~ "^" key ":" {
      value = $0
      sub("^" key ":[[:space:]]*", "", value)
      sub(/[[:space:]]*$/, "", value)
      print value
      exit
    }
  ' <<< "$frontmatter"
}

# has_non_empty_description
# -------------------------
# Check that the description field is present and non-empty.
has_non_empty_description() { # 33
  local -r frontmatter="$1"
  awk '
    /^description:/ {
      val = $0
      sub(/^description:[[:space:]]*/, "", val)
      sub(/[[:space:]]*$/, "", val)
      if (val ~ /^(\||>)/ || val == "") {
        found_key = 1
        next
      } else {
        gsub(/^["'\'']|["'\'']$/, "", val)
        if (length(val) > 0) has_content = 1
        exit
      }
    }
    found_key && /^[[:space:]]+/ {
      trimmed = $0
      sub(/^[[:space:]]+/, "", trimmed)
      sub(/[[:space:]]+$/, "", trimmed)
      if (length(trimmed) > 0) {
        has_content = 1
        exit
      }
    }
    found_key && !/^[[:space:]]+/ {
      exit
    }
    END {
      exit !has_content
    }
  ' <<< "$frontmatter"
}

# validate_frontmatter
# --------------------
# Validate supported keys, required fields, and field types.
validate_frontmatter() { # 68
  local -r frontmatter="$1"
  local declared_keys key target_value bool_key bool_val tools_val errors=0

  declared_keys=$(awk '/^[[:alnum:]_-]+:/ { key = $0; sub(/:.*/, "", key); print key }' \
    <<< "$frontmatter")
  while IFS= read -r key; do
    [[ -n "$key" ]] || continue
    if [[ "$key" =~ ^($ALLOWED_KEYS_PATTERN_GITHUB)$ ]]; then
      printf '[+] Valid field: %s\n' "$key"
    else
      printf '[!] INVALID FIELD DETECTED: %s\n' "$key" >&2
      ((errors += 1))
    fi
  done <<< "$declared_keys"

  if ! has_key description "$frontmatter"; then
    printf '[!] SCHEMA ERROR: description is required.\n' >&2
    ((errors += 1))
  elif ! has_non_empty_description "$frontmatter"; then
    printf '[!] SCHEMA ERROR: description must not be empty.\n' >&2
    ((errors += 1))
  fi

  if has_key target "$frontmatter"; then
    target_value=$(get_field_value target "$frontmatter")
    target_value=$(strip_quotes "$target_value")
    case "$target_value" in
      ""|vscode|github-copilot)
        ;;
      *)
        printf '[!] SCHEMA ERROR: unsupported target: %s\n' "$target_value" >&2
        ((errors += 1))
        ;;
    esac
  fi

  for bool_key in disable-model-invocation user-invocable infer; do
    if has_key "$bool_key" "$frontmatter"; then
      bool_val=$(get_field_value "$bool_key" "$frontmatter")
      bool_val=$(strip_quotes "$bool_val")
      case "$bool_val" in
        true|false)
          ;;
        *)
          printf '[!] SCHEMA ERROR: %s must be boolean (true or false), got: %s\n' "$bool_key" "$bool_val" >&2
          ((errors += 1))
          ;;
      esac
    fi
  done

  if has_key tools "$frontmatter"; then
    tools_val=$(get_field_value tools "$frontmatter")
    tools_val=$(strip_quotes "$tools_val")
    case "$tools_val" in
      ""|"[]"|"[*]")
        ;;
      *)
        if [[ "$tools_val" != \[* && "$tools_val" != -* ]]; then
          printf '[!] SCHEMA WARNING: tools should be a list, [], or [*], got: %s\n' "$tools_val" >&2
        fi
        ;;
    esac
  fi

  return "$errors"
}

# run
# ---
# Validate one agent file without changing it.
run() { # 14
  local -r target_file="$1"
  local frontmatter

  [[ -f "$target_file" ]] || fail 1 "file does not exist: $target_file"
  [[ -r "$target_file" ]] || fail 1 "file is not readable: $target_file"
  frontmatter=$(extract_frontmatter "$target_file") ||
    fail 1 "missing or incomplete YAML frontmatter: $target_file"
  [[ -n "$frontmatter" ]] ||
    fail 1 "YAML frontmatter is empty: $target_file"
  validate_frontmatter "$frontmatter" ||
    fail 1 "frontmatter validation failed: $target_file"
  printf '[OK] github frontmatter validation passed for: %s\n' "$target_file"
}

# main
# ----
# Parse arguments, validate prerequisites, and dispatch the validator.
main() { # 36
  local target_file=
  require_command awk
  require_command date
  require_command printf

  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help)
        usage
        return 0
        ;;
      --)
        shift
        break
        ;;
      -*)
        usage >&2
        fail 2 "unknown option: $1"
        ;;
      *)
        [[ -z "$target_file" ]] || fail 2 "unexpected argument: $1"
        target_file="$1"
        shift
        ;;
    esac
  done

  [[ -n "$target_file" ]] || {
    usage >&2
    fail 2 "an agent file path is required"
  }
  [[ -f "$target_file" ]] || fail 1 "file does not exist: $target_file"
  [[ -r "$target_file" ]] || fail 1 "file is not readable: $target_file"
  run "$target_file"
}

main "$@"
