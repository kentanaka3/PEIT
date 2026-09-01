#!/usr/bin/env bash

# LLM Markdown handler
# =======================
#
# Coordinate the LLM workspace lifecycle from one command-line interface.
# The handler combines workspace initialization, Markdown navigation reporting,
# and workspace validation without changing the behavior of the original
# standalone scripts.
#
# USAGE
#   bash handler.sh adr init|new <title>|update
#   bash handler.sh init [--dry-run]
#   bash handler.sh navigate [--root DIRECTORY|--file FILE] [--format table|tsv] [--scripts]
#   bash handler.sh validate [--root DIRECTORY|--file FILE]
#   bash handler.sh --help
#
# COMMANDS
#   adr        Initialize, create, or index Architecture Decision Records (ADRs).
#   init       Create missing LLM directories and starter documents.
#   navigate   Print a Markdown navigation report to standard output.
#   validate   Validate documentation, links, paths, and script syntax.
#
# Function          | description
# ------------------|--------------------------------------------------------
# log               | Print a timestamped informational message.
# fail              | Report an error and terminate.
# require_command   | Verify that a required executable is available.
# usage             | Print command-line usage information.
# initialize        | Create missing workspace directories and starters.
# navigate          | Generate the Markdown navigation report.
# validate          | Check required files, links, paths, and script syntax.
# navigate_scripts  | Inventory Makefile targets, Bash functions, and Python
#                     definitions with line-number references.
# validate_functions| Validate Bash function documentation and line counts.
# main              | Parse the command and dispatch the requested operation.
#
# SAFETY
#   `adr` writes only doc/adr and preserves existing ADRs and index prose.
#   `init` is idempotent and never overwrites existing starter files. Use
#   `--dry-run` to report changes without modifying the workspace.
#   `navigate` writes only to standard output.
#   `validate` does not modify files or contact external services.

set -euo pipefail
umask 077

readonly SCRIPT="$(basename -- "${BASH_SOURCE[0]}")"
readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly WORKSPACE="$(cd -- "$SCRIPT_DIR/.." && pwd)"
readonly ROOT="$(cd -- "$WORKSPACE/.." && pwd)"

# log
# ---
# Print a timestamped informational message to standard error.
log() { # 6
    printf '[%s][%s] %s\n' \
        "$SCRIPT" \
        "$(date '+%Y-%m-%d %H:%M:%S%z')" \
        "$*" >&2
}

# fail
# ----
# Report an error message and terminate the script with a non-zero exit code.
fail() { # 7
    local -r status="$1"
    shift

    log "ERROR: $*"
    exit "$status"
}

# require_command
# ---------------
# Verify that a required executable is available.
require_command() { # 6
    local -r command_name="$1"

    command -v "$command_name" >/dev/null 2>&1 ||
        fail 127 "required command not found: $command_name"
}

# usage
# -----
# Print command-line usage information.
usage() { # 29
    cat <<EOF
Usage: $SCRIPT COMMAND [OPTIONS]

Commands:
  adr init               Initialize doc/adr and its index.
  adr new <title>        Create a numbered ADR from config/adr_schema.md.
  adr update             Rebuild the ADR index.
  init [--dry-run]       Create missing workspace directories and starters.
  navigate [OPTIONS]     Generate a Markdown navigation report.
  validate [--root DIR]  Validate documentation and project scripts.

Options:
  -h, --help            Show this help message and exit.
  --                    End option processing.

Navigate options:
  --root DIRECTORY      Scan DIRECTORY instead of the PhD project root.
  --file FILE           Navigate or validate one supported script file.
  --format FORMAT       Use table (default) or machine-readable tsv output.
  --scripts             Include Makefile, Bash, and Python symbol inventory.

Examples:
  bash $SCRIPT init
  bash $SCRIPT navigate
  bash $SCRIPT navigate --root /path/to/PhD > markdown_navigation_report.md
  bash $SCRIPT validate
EOF
}

# adr_initialize
# --------------
# Create the ADR directory and index without overwriting existing files.
adr_initialize() { # 16
    local -r adr_dir="$ROOT/doc/adr"
    local -r index_file="$adr_dir/README.md"
    if [[ ! -d "$adr_dir" ]]; then
        mkdir -p -- "$adr_dir"
        log "Created directory: $adr_dir"
    fi
    if [[ ! -f "$index_file" ]]; then
        printf '%s\n' '# Architecture Decision Records (ADR)' '' \
            'This directory contains records of architectural and engineering decisions for this project.' '' \
            '## Index' '' '<!-- ADR_TABLE_START -->' \
            '| ADR | Title | Status | Date |' '| :--- | :--- | :--- | :--- |' \
            '<!-- ADR_TABLE_END -->' > "$index_file"
        log "Created initial index at: $index_file"
    fi
}

# adr_next_number
# ---------------
# Return the next zero-padded four-digit ADR identifier.
adr_next_number() { # 13
    local -r adr_dir="$ROOT/doc/adr"
    local highest=0 file filename num
    shopt -s nullglob
    for file in "$adr_dir"/[0-9][0-9][0-9][0-9]-*.md; do
        filename=$(basename -- "$file")
        num="${filename%%-*}"
        num=$((10#$num))
        (( num > highest )) && highest=$num
    done
    shopt -u nullglob
    printf '%04d\n' "$((highest + 1))"
}

# adr_slugify
# -----------
# Convert a title to a lowercase kebab-case filename slug.
adr_slugify() { # 3
    printf '%s\n' "$1" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-//;s/-$//'
}

# adr_build_table
# ---------------
# Build the Markdown table for all numbered ADR files.
adr_build_table() { # 15
    local -r adr_dir="$ROOT/doc/adr"
    local file base title status adr_date
    printf '%s\n' '| ADR | Title | Status | Date |' '| :--- | :--- | :--- | :--- |'
    shopt -s nullglob
    local -a files=("$adr_dir"/[0-9][0-9][0-9][0-9]-*.md)
    shopt -u nullglob
    for file in "${files[@]}"; do
        base=$(basename -- "$file")
        title=$(grep -m1 '^# ADR-[0-9][0-9][0-9][0-9]:' "$file" | sed -E 's/^# ADR-[0-9]+:[[:space:]]*//' || true)
        status=$(grep -m1 '^\*[[:space:]]*\*\*Status:\*\*' "$file" | sed -E 's/^\*[[:space:]]*\*\*Status:\*\*[[:space:]]*//' || true)
        adr_date=$(grep -m1 '^\*[[:space:]]*\*\*Date:\*\*' "$file" | sed -E 's/^\*[[:space:]]*\*\*Date:\*\*[[:space:]]*//' || true)
        printf '| [ADR-%s](%s) | %s | %s | %s |\n' "${base%%-*}" "$base" "${title:-Untitled}" "${status:-Proposed}" "${adr_date:-N/A}"
    done
}

# adr_update_index
# ----------------
# Replace the generated ADR table between its markers.
adr_update_index() { # 20
    local -r index_file="$ROOT/doc/adr/README.md"
    local table_file temporary
    adr_initialize
    table_file=$(mktemp)
    temporary=$(mktemp)
    adr_build_table > "$table_file"
    awk -v table_file="$table_file" '
        $0 == "<!-- ADR_TABLE_START -->" {
            print
            while ((getline line < table_file) > 0) print line
            close(table_file); skip = 1; next
        }
        $0 == "<!-- ADR_TABLE_END -->" { skip = 0 }
        !skip { print }
    ' "$index_file" > "$temporary"
    mv -- "$temporary" "$index_file"
    rm -f -- "$table_file"
    log "Updated index: ${index_file#$ROOT/}"
}

# adr_create
# ----------
# Create a numbered ADR from config/adr_schema.md and update the index.
adr_create() { # 21
    local -r title="$1"
    local next_num slug target today author
    [[ -n "$title" ]] || fail 2 "Usage: $SCRIPT adr new <title>"
    adr_initialize
    next_num=$(adr_next_number)
    slug=$(adr_slugify "$title")
    [[ -n "$slug" ]] || fail 2 "title must contain an alphanumeric character"
    target="$ROOT/doc/adr/${next_num}-${slug}.md"
    today=$(date '+%Y-%m-%d')
    author=$(git config user.name 2>/dev/null || true)
    [[ -n "$author" ]] || author='Architecture Team'
    {
        printf '# ADR-%s: %s\n\n' "$next_num" "$title"
        printf '* **Status:** Proposed\n* **Deciders:** %s\n* **Consulted:**\n* **Informed:**\n* **Date:** %s\n* **Technical Story / Ticket:**\n\n' "$author" "$today"
        sed -n '/^---$/,$p' "$ROOT/config/adr_schema.md" |
            sed "s/ADR-\\[NUMBER\\]/ADR-${next_num}/; s/\\[Short, Imperative Title Summarizing the Decision\\]/${title}/"
    } > "$target"
    log "Created ADR: ${target#$ROOT/}"
    adr_update_index
}

# adr_lint
# --------
# Validate status and ISO calendar date metadata in numbered ADR files.
adr_lint() { # 31
    local -r adr_dir="$ROOT/doc/adr"
    local errors=0 file status_val adr_date
    local -r status_regex='^(Proposed|Accepted|Deprecated|Superseded( by ADR-[0-9]{4})?|Rejected)$'
    local -r date_regex='^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$'

    shopt -s nullglob
    local -a files=("$adr_dir"/[0-9][0-9][0-9][0-9]-*.md)
    shopt -u nullglob
    if [[ ${#files[@]} -eq 0 ]]; then
        log "No ADR files to lint."
        return 0
    fi
    for file in "${files[@]}"; do
        status_val=$(grep -m1 '^\*[[:space:]]*\*\*Status:\*\*' "$file" |
            sed -E 's/^\*[[:space:]]*\*\*Status:\*\*[[:space:]]*//' || true)
        if [[ ! "$status_val" =~ $status_regex ]]; then
            printf '[LINT FAIL] %s: Invalid Status %q\n' "$(basename -- "$file")" "$status_val" >&2
            errors=1
        fi
        adr_date=$(grep -m1 '^\*[[:space:]]*\*\*Date:\*\*' "$file" |
            sed -E 's/^\*[[:space:]]*\*\*Date:\*\*[[:space:]]*//' || true)
        if [[ ! "$adr_date" =~ $date_regex ]]; then
            printf '[LINT FAIL] %s: Invalid Date %q (expected YYYY-MM-DD)\n' \
                "$(basename -- "$file")" "$adr_date" >&2
            errors=1
        fi
    done
    (( errors == 0 )) || fail 1 "ADR linting failed"
    log "All ADR files are valid."
}

# initialize
# ----------
# Create missing workspace directories and starter documents.
initialize() { # 37
    local -r dry_run="$1"
    local -a directories=(
        00_governance 01_context 02_prompts 03_workflows 04_experiments
        05_evaluations 06_outputs 07_archive config scripts templates
    )
    local -A starter_files=(
        ["04_experiments/README.md"]=$'# Experiment records\n\nUse ../templates/experiment.md for each meaningful run.\n'
        ["06_outputs/README.md"]=$'# Reviewed outputs\n\nRecord reviewer, date, sources, and allowed use.\n'
        ["07_archive/README.md"]=$'# Archive\n\nMove superseded material here; preserve research history.\n'
    )
    local directory relative_path target

    require_command mkdir
    for directory in "${directories[@]}"; do
        if [[ "$dry_run" == false ]]; then
            mkdir -p -- "$WORKSPACE/$directory"
        else
            log "Would create directory: $WORKSPACE/$directory"
        fi
    done

    for relative_path in "${!starter_files[@]}"; do
        target="$WORKSPACE/$relative_path"
        if [[ ! -e "$target" && "$dry_run" == false ]]; then
            printf '%s' "${starter_files[$relative_path]}" > "$target"
            log "Created ${target#$WORKSPACE/}"
        elif [[ ! -e "$target" ]]; then
            log "Would create file: ${target#$WORKSPACE/}"
        else
            log "Preserved ${target#$WORKSPACE/}"
        fi
    done

    printf '\nLLM workspace ready: %s\nNext: review 00_governance/open_questions.md and run the validator.\n' \
        "$WORKSPACE"
}

# navigation_rows
# ---------------
# Generate the Markdown navigation report.
navigation_rows() { # 34
    local -r scan_root="$1"
    local markdown_count file relative lines headings

    require_command awk
    require_command find
    require_command sort
    require_command wc
    [[ -d "$scan_root" ]] ||
        fail 1 "scan root does not exist or is not a directory: $scan_root"

    markdown_count=$(find "$scan_root" -path "$scan_root/.git" -prune -o \
        -type f -name '*.md' -print | wc -l)
    printf '# Markdown navigation report\n\nRepository: `%s`\n\n' "$scan_root"
    printf 'Markdown files discovered (excluding `.git`): `%s`\n\n' "$markdown_count"
    printf '| File | Lines | Headings |\n|---|---:|---|\n'
    while IFS= read -r -d '' file; do
        relative=${file#"$scan_root/"}
        lines=$(wc -l < "$file")
        headings=$(awk -v file="$relative" '
            /^```|^~~~/ { fenced = !fenced; next }
            !fenced && /^#{1,6}[[:space:]]/ {
                gsub(/\|/, "\\|", $0)
                printf "%s:%d %s; ", file, FNR, $0
            }
        ' "$file")
        [[ -n "$headings" ]] || headings='(no Markdown heading found)'
        headings=${headings//|/\\|}
        printf '| `%s` | %s | %s |\n' "$relative" "$lines" "$headings"
    done < <(
        find "$scan_root" -path "$scan_root/.git" -prune -o \
            -type f -name '*.md' -print0 | sort -z
    )
}

# navigation_tsv
# --------------
# Generate the tab-separated navigation report.
navigation_tsv() { # 20
    local -r scan_root="$1"
    local file relative lines headings

    printf 'file\tlines\theadings\n'
    while IFS= read -r -d '' file; do
        relative=${file#"$scan_root/"}
        lines=$(wc -l < "$file")
        headings=$(awk '
            /^```|^~~~/ { fenced = !fenced; next }
            !fenced && /^#{1,6}[[:space:]]/ { printf "%s; ", $0 }
        ' "$file")
        headings=${headings//$'\t'/ }
        headings=${headings//$'\n'/ }
        printf '%s\t%s\t%s\n' "$relative" "$lines" "${headings:-"(no heading)"}"
    done < <(
        find "$scan_root" -path "$scan_root/.git" -prune -o \
            -type f -name '*.md' -print0 | sort -z
    )
}

# validate_markdown
# -----------------
# Validate local Markdown paths and fenced code blocks.
validate_markdown() { # 25
    local -r scan_root="$1"
    local failures=0 file target link line_number content

    while IFS= read -r -d '' file; do
        if (( $(awk '/^```|^~~~/ { fenced = !fenced } END { print fenced + 0 }' "$file") != 0 )); then
            printf 'ERR %s (unclosed fenced code block)\n' "${file#$scan_root/}" >&2
            ((failures += 1))
        fi
        while IFS=: read -r line_number content; do
            link=$(printf '%s\n' "$content" | sed -E 's/.*\]\(([^)#]+).*/\1/')
            [[ -n "$link" && "$link" != http* && "$link" != mailto:* ]] || continue
            target="$scan_root/$(dirname -- "${file#$scan_root/}")/$link"
            [[ -e "$target" ]] || {
                printf 'ERR %s:%s (broken Markdown path: %s)\n' \
                    "${file#$scan_root/}" "$line_number" "$link" >&2
                ((failures += 1))
            }
        done < <(grep --line-number --extended-regexp '\]\([^)#]+(\#[^)]*)?\)' "$file" || true)
    done < <(
        find "$scan_root" -path "$scan_root/.git" -prune -o \
            -type f -name '*.md' -print0 | sort -z
    )
    return "$failures"
}

# validate_script_references
# --------------------------
# Detect stale references to project shell scripts.
validate_script_references() { # 20
    local -r scan_root="$1"
    local failures=0 file reference

    while IFS= read -r -d '' file; do
        while IFS= read -r reference; do
            [[ -e "$scan_root/$reference" ]] || {
                printf 'ERR %s (stale or missing script reference: %s)\n' \
                    "${file#$scan_root/}" "$reference" >&2
                ((failures += 1))
            }
        done < <(grep --only-matching --no-filename \
            --extended-regexp '(LLM/scripts|OGS/utils/Leonardo|OGS/utils/\.local)/[A-Za-z0-9_.-]+\.sh' \
            "$file" | sort -u || true)
    done < <(
        find "$scan_root" -path "$scan_root/.git" -prune -o \
            -type f -name '*.md' -print0 | sort -z
    )
    return "$failures"
}

# validate_bash
# ------------
# Validate the syntax of every project Bash script.
validate_bash() { # 16
    local -r scan_root="$1"
    local failures=0 file

    require_command bash
    while IFS= read -r -d '' file; do
        if ! bash -n "$file"; then
            printf 'ERR %s (Bash syntax check failed)\n' "${file#$scan_root/}" >&2
            ((failures += 1))
        fi
    done < <(
        find "$scan_root" -path "$scan_root/.git" -prune -o \
            -type f -name '*.sh' -print0 | sort -z
    )
    return "$failures"
}

# Validate the required workspace, Markdown, and Bash surfaces.
# navigate_scripts
# ----------------
# Inventory Makefile targets, Bash functions, and Python definitions.
navigate_scripts() { # 44
    local -r scan_root="$1"
    local -r selected_file="${2:-}"
    local file line symbol

    printf '# Script navigation report\n\nRoot: `%s`\n\n' "$scan_root"
    printf '| File | Type | Line | Symbol |\n|---|---|---:|---|\n'
    while IFS= read -r -d '' file; do
        case "$(basename -- "$file")" in
            Makefile)
                while IFS=: read -r line symbol; do
                    printf '| `%s` | Make target | %s | `%s` |\n' \
                        "${file#$scan_root/}" "$line" "$symbol"
                done < <(grep --line-number --extended-regexp \
                    '^[[:alnum:]_.%+-]+[[:space:]]*:' "$file" |
                    sed -E 's/^([0-9]+):([^:]+):.*/\1:\2/' || true)
                ;;
            *.sh)
                while IFS=: read -r line symbol; do
                    printf '| `%s` | Bash function | %s | `%s` |\n' \
                        "${file#$scan_root/}" "$line" "$symbol"
                done < <(grep --line-number --extended-regexp \
                    '^[[:alnum:]_]+\(\)[[:space:]]*\{' "$file" |
                    sed -E 's/^([0-9]+):([A-Za-z_][A-Za-z0-9_]*)\\(\\).*/\1:\2/' || true)
                ;;
            *.py)
                while IFS=: read -r line symbol; do
                    printf '| `%s` | Python definition | %s | `%s` |\n' \
                        "${file#$scan_root/}" "$line" "$symbol"
                done < <(grep --line-number --extended-regexp \
                    '^[[:space:]]*(async[[:space:]]+)?def[[:space:]]+[A-Za-z_][A-Za-z0-9_]*' "$file" |
                    sed -E 's/^([0-9]+):[[:space:]]*(async[[:space:]]+)?def[[:space:]]+([A-Za-z_][A-Za-z0-9_]*).*/\1:\3/' || true)
                ;;
        esac
    done < <(
        if [[ -n "$selected_file" ]]; then
            printf '%s\0' "$selected_file"
        else
            find "$scan_root" -path "$scan_root/.git" -prune -o \
                \( -name 'Makefile' -o -name '*.sh' -o -name '*.py' \) \
                -type f -print0 | sort -z
        fi
    )
}

# validate_functions
# ------------------
# Validate inline Bash function line counts in this handler.
validate_functions() { # 32
    local -r target_file="$1"
    local -r scan_root="$(dirname -- "$target_file")"
    local failures=0 file line declaration count actual

    while IFS= read -r -d '' file; do
        while IFS=: read -r line declaration; do
            count=$(printf '%s\n' "$declaration" | sed -nE 's/.*\{[[:space:]]*#[[:space:]]*([0-9]+).*/\1/p')
            if [[ -z "$count" ]]; then
                printf 'ERR %s:%s (function declaration must end with: { # line_count)\n' \
                    "${file#$scan_root/}" "$line" >&2
                ((failures += 1))
                continue
            fi
            actual=$(awk -v start="$line" '
                NR > start && /^}$/ {
                    print NR - start + 1
                    exit
                }
            ' "$file")
            if [[ "$actual" != "$count" ]]; then
                printf 'ERR %s:%s (documented %s lines, counted %s)\n' \
                    "${file#$scan_root/}" "$line" "$count" "${actual:-unknown}" >&2
                ((failures += 1))
            fi
        done < <(grep --line-number --extended-regexp \
            '^[[:alnum:]_]+\(\)[[:space:]]*\{' "$file" || true)
    done < <(
        printf '%s\0' "$target_file"
    )
    return "$failures"
}

# validate_single_file
# --------------------
# Validate one supported Bash script or Markdown file.
validate_single_file() { # 49
    local -r scan_root="$ROOT"
    local -r file="$1"
    local failures=0
    local target link line_number content reference

    [[ -f "$file" ]] || fail 1 "file does not exist: $file"
    case "$file" in
        *.sh)
            if ! bash -n "$file"; then
                printf 'ERR %s (Bash syntax check failed)\n' "$file" >&2
                ((failures += 1))
            fi
            validate_functions "$file" || failures=$((failures + $?))
            ;;
        *.md)
            if (( $(awk '/^```|^~~~/ { fenced = !fenced } END { print fenced + 0 }' "$file") != 0 )); then
                printf 'ERR %s (unclosed fenced code block)\n' "$file" >&2
                ((failures += 1))
            fi
            while IFS=: read -r line_number content; do
                link=$(printf '%s\n' "$content" | sed -E 's/.*\]\(([^)#]+).*/\1/')
                [[ -n "$link" && "$link" != http* && "$link" != mailto:* ]] || continue
                target="$(dirname -- "$file")/$link"
                [[ -e "$target" ]] || {
                    printf 'ERR %s:%s (broken Markdown path: %s)\n' \
                        "$file" "$line_number" "$link" >&2
                    ((failures += 1))
                }
            done < <(grep --line-number --extended-regexp '\]\([^)#]+(\#[^)]*)?\)' "$file" || true)
            while IFS= read -r reference; do
                [[ -e "$scan_root/$reference" ]] || {
                    printf 'ERR %s (stale or missing script reference: %s)\n' \
                        "$file" "$reference" >&2
                    ((failures += 1))
                }
            done < <(grep --only-matching --no-filename \
                --extended-regexp '(LLM/scripts|OGS/utils/Leonardo|OGS/utils/\.local)/[A-Za-z0-9_.-]+\.sh' \
                "$file" | sort -u || true)
            ;;
        *)
            fail 2 "single-file validation supports Bash scripts (*.sh) and Markdown (*.md): $file"
            ;;
    esac

    (( failures == 0 )) ||
        fail 1 "single-file validation failed with $failures issue(s)"
    printf 'Validation passed: %s\n' "$file"
}

validate() { # 44
    local -r scan_root="$1"
    local -a required=(
        "$scan_root/AGENTS.md"
        "$scan_root/LLM/README.md"
        "$scan_root/LLM/00_governance/scope.md"
        "$scan_root/LLM/00_governance/decisions.md"
        "$scan_root/LLM/00_governance/open_questions.md"
        "$scan_root/LLM/01_context/pipeline_map.md"
        "$scan_root/LLM/01_context/glossary.md"
        "$scan_root/LLM/02_prompts/code_review.md"
        "$scan_root/LLM/03_workflows/experiment_lifecycle.md"
        "$scan_root/LLM/05_evaluations/rubric.md"
        "$scan_root/LLM/templates/experiment.md"
        "$scan_root/LLM/.gitignore"
        "$scan_root/LLM/scripts/handler.sh"
    )
    local failures=0 file

    for file in "${required[@]}"; do
        if [[ -s "$file" ]]; then
            printf 'OK  %s\n' "${file#$scan_root/}"
        else
            printf 'ERR %s (missing or empty)\n' "${file#$scan_root/}" >&2
            ((failures += 1))
        fi
    done

    if [[ ! -x "$scan_root/LLM/scripts/handler.sh" ]]; then
        printf 'ERR LLM/scripts/handler.sh is not executable\n' >&2
        ((failures += 1))
    fi

    validate_markdown "$scan_root" || failures=$((failures + $?))
    validate_script_references "$scan_root" || failures=$((failures + $?))
    validate_bash "$scan_root" || failures=$((failures + $?))
    validate_functions "$scan_root/LLM/scripts/handler.sh" ||
        failures=$((failures + $?))
    adr_lint

    (( failures == 0 )) ||
        fail 1 "validation failed with $failures issue(s)"
    printf '\nValidation passed: %d required files checked.\n' "${#required[@]}"
}

# main
# ----
# Parse the command and dispatch the requested operation.
main() { # 148
    local command="${1:-}"
    local scan_root="$ROOT"
    local file_path=
    local dry_run=false
    local format=table

    require_command date
    require_command printf

    # Command dispatcher
    case "$command" in
        adr)
            shift
            case "${1:-}" in
                init)
                    shift
                    (( $# == 0 )) || fail 2 "unknown adr init option: $1"
                    adr_initialize
                    adr_update_index
                    ;;
                new)
                    shift
                    (( $# > 0 )) || fail 2 "Usage: $SCRIPT adr new <title>"
                    adr_create "$*"
                    ;;
                update)
                    shift
                    (( $# == 0 )) || fail 2 "unknown adr update option: $1"
                    adr_update_index
                    ;;
                -h|--help|"")
                    usage
                    ;;
                *)
                    fail 2 "unknown adr command: $1"
                    ;;
            esac
            ;;
        init)
            shift
            if [[ "${1:-}" == "--dry-run" ]]; then
                dry_run=true
                shift
            fi
            (( $# == 0 )) || fail 2 "unknown init option: $1"
            initialize "$dry_run"
            ;;
        navigate)
            shift
            local scripts=false
            while [[ $# -gt 0 ]]; do
                case "$1" in
                    --root)
                        (( $# >= 2 )) || fail 2 "--root requires a directory argument"
                        scan_root="$2"
                        shift 2
                        ;;
                    --file)
                        (( $# >= 2 )) || fail 2 "--file requires a file argument"
                        file_path="$2"
                        shift 2
                        ;;
                    --format)
                        (( $# >= 2 )) || fail 2 "--format requires a value"
                        format="$2"
                        shift 2
                        ;;
                    --scripts)
                        scripts=true
                        shift
                        ;;
                    -h|--help)
                        usage
                        return 0
                        ;;
                    --)
                        shift
                        break
                        ;;
                    *)
                        fail 2 "unknown navigate option: $1"
                        ;;
                esac
            done
            (( $# == 0 )) || fail 2 "unexpected navigate argument: $1"
            if [[ -n "$file_path" ]]; then
                file_path="$(cd -- "$(dirname -- "$file_path")" 2>/dev/null && pwd)/$(basename -- "$file_path")" ||
                    fail 1 "could not resolve file: $file_path"
                [[ -f "$file_path" ]] || fail 1 "file does not exist: $file_path"
                navigate_scripts "$(dirname -- "$file_path")" "$file_path"
            else
                local requested_root="$scan_root"
                scan_root="$(cd -- "$requested_root" 2>/dev/null && pwd)" ||
                    fail 1 "could not resolve navigation root: $requested_root"
                case "$format" in
                    table) navigation_rows "$scan_root" ;;
                    tsv) navigation_tsv "$scan_root" ;;
                    *) fail 2 "unsupported navigation format: $format" ;;
                esac
            fi
            if [[ "$scripts" == true ]]; then
                [[ -n "$file_path" ]] || navigate_scripts "$scan_root"
            fi
            ;;
        validate)
            shift
            while [[ $# -gt 0 ]]; do
                case "$1" in
                    --root)
                        (( $# >= 2 )) || fail 2 "--root requires a directory argument"
                        scan_root="$2"
                        shift 2
                        ;;
                    --file)
                        (( $# >= 2 )) || fail 2 "--file requires a file argument"
                        file_path="$2"
                        shift 2
                        ;;
                    -h|--help) usage; return 0 ;;
                    *) fail 2 "unknown validate option: $1" ;;
                esac
            done
            if [[ -n "$file_path" ]]; then
                local requested_file="$file_path"
                file_path="$(cd -- "$(dirname -- "$requested_file")" 2>/dev/null && pwd)/$(basename -- "$requested_file")" ||
                    fail 1 "could not resolve file: $requested_file"
                validate_single_file "$file_path"
            else
                local requested_root="$scan_root"
                scan_root="$(cd -- "$requested_root" 2>/dev/null && pwd)" ||
                    fail 1 "could not resolve validation root: $requested_root"
                validate "$scan_root"
            fi
            ;;
        -h|--help)
            usage
            ;;
        "")
            usage >&2
            fail 2 "a command is required"
            ;;
        *)
            usage >&2
            fail 2 "unknown command: $command"
            ;;
    esac
}

main "$@"
