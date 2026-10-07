#!/usr/bin/env bash

# Unified agent validator
# =======================
#
# Validate YAML frontmatter in GitHub Copilot agent profiles, Gemini CLI
# / Antigravity skills, or Claude Code subagents and skills from one
# deterministic command-line entry point.
#
# USAGE
#   bash validate-agent.sh github <path-to-agent-file>
#   bash validate-agent.sh gemini <path-to-skill-file>
#   bash validate-agent.sh claude <path-to-agent-file>
#   bash validate-agent.sh --help
#
# DESCRIPTION
#   The first line must be an opening `---` delimiter and the next delimiter
#   closes the frontmatter. Only supported top-level fields for the selected
#   platform are accepted. The target file is never modified.
#
# OPTIONS
#   -h, --help    Show usage information and exit.

set -euo pipefail
shopt -s extglob
umask 077

readonly SCRIPT="$(basename -- "${BASH_SOURCE[0]}")"
readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

readonly ALLOWED_KEYS_CLAUDE=(
  agent
  allowed-tools
  argument-hint
  arguments
  context
  description
  disable-model-invocation
  disallowedTools
  effort
  experimental
  hooks
  maxTurns
  model
  name
  paths
  permissionMode
  shell
  tools
  user-invocable
  when_to_use
)
readonly ALLOWED_KEYS_PATTERN_CLAUDE="$(IFS='|'; echo "${ALLOWED_KEYS_CLAUDE[*]}")"

readonly ALLOWED_KEYS_GEMINI=(
  allowed-tools
  argument-hint
  commandExecutionPolicy
  compatibility
  description
  execution-priority
  license
  mainAgent
  metadata
  model
  model-engine
  model-version
  name
  permissionMode
  subagent
  tags
  tools
  usage-limits
  user-experience
  user-invocable
)
readonly ALLOWED_KEYS_PATTERN_GEMINI="$(IFS='|'; echo "${ALLOWED_KEYS_GEMINI[*]}")"

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
usage() { # 19
  cat <<EOF
Usage: $SCRIPT COMMAND [OPTIONS] <path-to-agent-or-skill-file>

Commands:
  github <FILE>    Validate GitHub Copilot agent YAML frontmatter.
  gemini <FILE>    Validate Gemini CLI agent or Antigravity skill frontmatter.
  claude <FILE>    Validate Claude Code subagent or skill frontmatter.

General options:
  -h, --help       Show this help message and exit.
  --               End option processing.

Examples:
  bash $SCRIPT github .github/agents/bash-scripter.agent.md
  bash $SCRIPT gemini .agents/skills/agent-creator/SKILL.md
  bash $SCRIPT claude .claude/agents/reviewer.md
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

# validate_frontmatter_github
# ---------------------------
# Validate GitHub Copilot agent frontmatter fields, types, and constraints.
validate_frontmatter_github() { # 68
  local -r frontmatter="$1"
  local declared_keys key target_val bool_key bool_val tools_val errors=0

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
    target_val=$(get_field_value target "$frontmatter")
    target_val=$(strip_quotes "$target_val")
    case "$target_val" in
      ""|vscode|github-copilot)
        ;;
      *)
        printf '[!] SCHEMA ERROR: unsupported target: %s\n' "$target_val" >&2
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

# validate_frontmatter_gemini
# ---------------------------
# Validate Gemini CLI agent or Antigravity skill frontmatter fields.
validate_frontmatter_gemini() { # 93
  local -r frontmatter="$1"
  local declared_keys key name_val perm_val cmd_val bool_key bool_val tools_val errors=0

  declared_keys=$(awk '/^[[:alnum:]_-]+:/ { key = $0; sub(/:.*/, "", key); print key }' \
    <<< "$frontmatter")
  while IFS= read -r key; do
    [[ -n "$key" ]] || continue
    if [[ "$key" =~ ^($ALLOWED_KEYS_PATTERN_GEMINI)$ ]]; then
      printf '[+] Valid field: %s\n' "$key"
    else
      printf '[!] INVALID FIELD DETECTED: %s\n' "$key" >&2
      ((errors += 1))
    fi
  done <<< "$declared_keys"

  if ! has_key name "$frontmatter"; then
    printf '[!] SCHEMA ERROR: name is required.\n' >&2
    ((errors += 1))
  else
    name_val=$(get_field_value name "$frontmatter")
    name_val=$(strip_quotes "$name_val")
    if [[ -z "$name_val" ]]; then
      printf '[!] SCHEMA ERROR: name must not be empty.\n' >&2
      ((errors += 1))
    fi
  fi

  if ! has_key description "$frontmatter"; then
    printf '[!] SCHEMA ERROR: description is required.\n' >&2
    ((errors += 1))
  elif ! has_non_empty_description "$frontmatter"; then
    printf '[!] SCHEMA ERROR: description must not be empty.\n' >&2
    ((errors += 1))
  fi

  if has_key permissionMode "$frontmatter"; then
    perm_val=$(get_field_value permissionMode "$frontmatter")
    perm_val=$(strip_quotes "$perm_val")
    case "$perm_val" in
      acceptEdits|default|edit|none)
        ;;
      *)
        printf '[!] SCHEMA ERROR: unsupported permissionMode: %s (expected acceptEdits, default, edit, none)\n' "$perm_val" >&2
        ((errors += 1))
        ;;
    esac
  fi

  if has_key commandExecutionPolicy "$frontmatter"; then
    cmd_val=$(get_field_value commandExecutionPolicy "$frontmatter")
    cmd_val=$(strip_quotes "$cmd_val")
    case "$cmd_val" in
      auto|off|on|onSuccess|onError)
        ;;
      *)
        printf '[!] SCHEMA ERROR: unsupported commandExecutionPolicy: %s (expected auto, off, on, onSuccess, onError)\n' "$cmd_val" >&2
        ((errors += 1))
        ;;
    esac
  fi

  for bool_key in mainAgent subagent user-invocable; do
    if has_key "$bool_key" "$frontmatter"; then
      bool_val=$(get_field_value "$bool_key" "$frontmatter")
      bool_val=$(strip_quotes "$bool_val")
      case "$bool_val" in
        true|false|null|"")
          ;;
        *)
          printf '[!] SCHEMA ERROR: %s must be boolean or null (true, false, null), got: %s\n' "$bool_key" "$bool_val" >&2
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
          printf '[!] SCHEMA WARNING: tools should be a list or [], got: %s\n' "$tools_val" >&2
        fi
        ;;
    esac
  fi

  return "$errors"
}

# validate_frontmatter_claude
# ---------------------------
# Validate Claude Code subagent or skill frontmatter fields.
validate_frontmatter_claude() { # 89
  local -r frontmatter="$1"
  local declared_keys key perm_val effort_val turns_val shell_val bool_key bool_val errors=0

  declared_keys=$(awk '/^[[:alnum:]_-]+:/ { key = $0; sub(/:.*/, "", key); print key }' \
    <<< "$frontmatter")
  while IFS= read -r key; do
    [[ -n "$key" ]] || continue
    if [[ "$key" =~ ^($ALLOWED_KEYS_PATTERN_CLAUDE)$ ]]; then
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

  if has_key permissionMode "$frontmatter"; then
    perm_val=$(get_field_value permissionMode "$frontmatter")
    perm_val=$(strip_quotes "$perm_val")
    case "$perm_val" in
      default|acceptEdits|auto|bypassPermissions|plan|dontAsk)
        ;;
      *)
        printf '[!] SCHEMA ERROR: unsupported permissionMode: %s (expected default, acceptEdits, auto, bypassPermissions, plan, dontAsk)\n' "$perm_val" >&2
        ((errors += 1))
        ;;
    esac
  fi

  if has_key effort "$frontmatter"; then
    effort_val=$(get_field_value effort "$frontmatter")
    effort_val=$(strip_quotes "$effort_val")
    case "$effort_val" in
      low|medium|high|xhigh|max)
        ;;
      *)
        printf '[!] SCHEMA ERROR: unsupported effort: %s (expected low, medium, high, xhigh, max)\n' "$effort_val" >&2
        ((errors += 1))
        ;;
    esac
  fi

  if has_key maxTurns "$frontmatter"; then
    turns_val=$(get_field_value maxTurns "$frontmatter")
    turns_val=$(strip_quotes "$turns_val")
    if [[ ! "$turns_val" =~ ^[0-9]+$ ]]; then
      printf '[!] SCHEMA ERROR: maxTurns must be a positive integer, got: %s\n' "$turns_val" >&2
      ((errors += 1))
    fi
  fi

  if has_key shell "$frontmatter"; then
    shell_val=$(get_field_value shell "$frontmatter")
    shell_val=$(strip_quotes "$shell_val")
    case "$shell_val" in
      bash|powershell)
        ;;
      *)
        printf '[!] SCHEMA ERROR: unsupported shell: %s (expected bash or powershell)\n' "$shell_val" >&2
        ((errors += 1))
        ;;
    esac
  fi

  for bool_key in disable-model-invocation user-invocable; do
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

  return "$errors"
}

# run_target
# ----------
# Validate one agent or skill file against the selected runtime schema.
run_target() { # 21
  local -r target_type="$1"
  local -r target_file="$2"
  local frontmatter

  [[ -f "$target_file" ]] || fail 1 "file does not exist: $target_file"
  [[ -r "$target_file" ]] || fail 1 "file is not readable: $target_file"
  frontmatter=$(extract_frontmatter "$target_file") ||
    fail 1 "missing or incomplete YAML frontmatter: $target_file"
  [[ -n "$frontmatter" ]] ||
    fail 1 "YAML frontmatter is empty: $target_file"

  case "$target_type" in
    github) validate_frontmatter_github "$frontmatter" ;;
    gemini) validate_frontmatter_gemini "$frontmatter" ;;
    claude) validate_frontmatter_claude "$frontmatter" ;;
    *) fail 2 "unsupported target type: $target_type" ;;
  esac || fail 1 "frontmatter validation failed: $target_file"

  printf '[OK] %s frontmatter validation passed for: %s\n' "$target_type" "$target_file"
}

# main
# ----
# Parse arguments, validate prerequisites, and dispatch the validator.
main() { # 51
  require_command awk
  require_command date
  require_command printf

  local command=""
  local target_file=""

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
        if [[ -z "$command" ]]; then
          command="$1"
        elif [[ -z "$target_file" ]]; then
          target_file="$1"
        else
          fail 2 "unexpected argument: $1"
        fi
        shift
        ;;
    esac
  done

  [[ -n "$command" ]] || {
    usage >&2
    fail 2 "a command is required (github, gemini, claude)"
  }

  case "$command" in
    github|gemini|claude)
      [[ -n "$target_file" ]] || fail 2 "Usage: $SCRIPT $command <path-to-agent-file>"
      run_target "$command" "$target_file"
      ;;
    *)
      usage >&2
      fail 2 "unknown command: $command (expected github, gemini, or claude)"
      ;;
  esac
}

main "$@"
