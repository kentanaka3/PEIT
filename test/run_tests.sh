#!/usr/bin/env bash
# =============================================================================
# PEIT Test Runner (test/run_tests.sh)
#
# Production-grade, reproducible test runner for the PEIT test suites.
# Executes 11 test suites (schema, core, ledger, cli, dashboard, profiler,
# server, mobile sync, ocr parser, ocr canvas, ocr benchmark) with clean
# reporting, timing, and exit codes.
# =============================================================================

set -euo pipefail

readonly SCRIPT="$(basename -- "${BASH_SOURCE[0]}")"
readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

# Color codes (disabled if NO_COLOR is set or output is not a terminal)
if [[ -t 1 ]] && [[ -z "${NO_COLOR:-}" ]]; then
    readonly C_RESET='\033[0m'
    readonly C_BOLD='\033[1m'
    readonly C_GREEN='\033[32m'
    readonly C_RED='\033[31m'
    readonly C_YELLOW='\033[33m'
    readonly C_BLUE='\033[34m'
    readonly C_CYAN='\033[36m'
else
    readonly C_RESET=""
    readonly C_BOLD=""
    readonly C_GREEN=""
    readonly C_RED=""
    readonly C_YELLOW=""
    readonly C_BLUE=""
    readonly C_CYAN=""
fi

# Print an informational message with cyan formatting.
log_info() { # 3
    printf "${C_CYAN}[INFO]${C_RESET} %s\n" "$*"
}

# Print a warning message to standard error with yellow formatting.
log_warn() { # 3
    printf "${C_YELLOW}[WARN]${C_RESET} %s\n" "$*" >&2
}

# Print an error message to standard error with red formatting.
log_error() { # 3
    printf "${C_RED}[ERROR]${C_RESET} %s\n" "$*" >&2
}

# Print usage instructions and available test suite options.
usage() { # 40
    cat <<EOF
${C_BOLD}NAME${C_RESET}
    ${SCRIPT} - PEIT test automation and test suite runner

${C_BOLD}SYNOPSIS${C_RESET}
    ${SCRIPT} [OPTIONS] [--] [TEST_TARGETS...]

${C_BOLD}DESCRIPTION${C_RESET}
    Executes Python test suites for the Personal Economic Inflation Tracker.
    Automatically configures PYTHONPATH and reports execution timing.

${C_BOLD}SUITES${C_RESET}
    all           Run all test suites (schema, core, ledger, cli, dashboard, profiler, server, mobile, ocr, ocr_canvas, ocr_benchmark) [default]
    schema        Run canonical SSOT schema and contract tests (test/test_schema.py)
    core          Run core price index and schema tests (test/test_core.py)
    ledger        Run ledger, cache, and financial balance tests (test/test_ledger.py)
    cli           Run command-line interface integration tests (test/test_cli.py)
    dashboard     Run multi-graph dashboard and visualization tests (test/test_dashboard.py)
    profiler      Run profile generator & market dynamics tests (test/test_profiler.py)
    server        Run synchronization daemon REST API tests (test/test_server.py)
    mobile        Run mobile client sync & hash compatibility tests (test/test_mobile_sync.py)
    ocr           Run OCR and bilingual receipt parser prototype tests (test/test_ocr.py)
    ocr_canvas    Run synthetic receipt image generator & distortion tests (test/test_ocr_canvas.py)
    ocr_benchmark Run real photo benchmark suite & econometric evaluation tests (test/test_ocr_benchmark.py)

${C_BOLD}OPTIONS${C_RESET}
    -a, --all               Run all test suites.
    -s, --suite <name>      Run a specific suite: schema, core, ledger, cli, dashboard, profiler, server, mobile, ocr, ocr_canvas, ocr_benchmark, or all.
    -k, --keyword <pattern> Run tests matching the given keyword expression.
    -v, --verbose           Run pytest with verbose output (-vv).
    -q, --quiet             Run pytest with minimal output (-q).
    -l, --list              List test suites, test files, and test case counts.
    -c, --coverage          Collect code coverage if pytest-cov is installed.
    -h, --help              Show this help message and exit.

${C_BOLD}EXAMPLES${C_RESET}
    bash test/${SCRIPT} --all
    bash test/${SCRIPT} -s ledger
    bash test/${SCRIPT} -s cli -v
    bash test/${SCRIPT} -k "deterministic"
    bash test/${SCRIPT} test/test_ledger.py::test_t1_1_deterministic_entry_id_consistency
EOF
}

# Detect and return the appropriate pytest invocation command.
find_pytest_runner() { # 14
    if command -v pytest >/dev/null 2>&1; then
        echo "pytest"
        return 0
    elif command -v python3 >/dev/null 2>&1 && python3 -m pytest --version >/dev/null 2>&1; then
        echo "python3 -m pytest"
        return 0
    elif command -v python >/dev/null 2>&1 && python -m pytest --version >/dev/null 2>&1; then
        echo "python -m pytest"
        return 0
    fi
    log_error "pytest is not found in PATH or active Python environment."
    return 1
}

# List available test suites, test files, and individual test counts.
list_test_suites() { # 34
    printf "${C_BOLD}%-10s %-25s %-12s %s${C_RESET}\n" "SUITE" "FILE" "TEST CASES" "DESCRIPTION"
    printf "%-10s %-25s %-12s %s\n" "----------" "-------------------------" "------------" "--------------------------------------------------"

    local -r suites=("schema" "core" "ledger" "cli" "dashboard" "profiler" "server" "mobile" "ocr" "ocr_canvas" "ocr_benchmark")
    local -r files=("test/test_schema.py" "test/test_core.py" "test/test_ledger.py" "test/test_cli.py" "test/test_dashboard.py" "test/test_profiler.py" "test/test_server.py" "test/test_mobile_sync.py" "test/test_ocr.py" "test/test_ocr_canvas.py" "test/test_ocr_benchmark.py")
    local -r descs=(
        "Canonical SSOT schema definitions, column sequences & hashes"
        "Core receipt schema validation & index algorithms"
        "Signed ledger, dual SQLite cache, balances & filters"
        "CLI parsing, commands, output formats & error handling"
        "Multi-graph dashboard visualizer, tabs, KPI metrics & CLI"
        "Profile generator, market dynamics & CLI integration"
        "Local synchronization daemon REST API & push sync"
        "Mobile client sync payload & hash parity verification"
        "OCR spatial clustering, bilingual parsing & balance checks"
        "Synthetic receipt image generator & distortion pipeline"
        "Real photo benchmark suite & econometric evaluation"
    )

    local total_tests=0
    local i file count desc suite

    for i in "${!suites[@]}"; do
        suite="${suites[$i]}"
        file="${files[$i]}"
        desc="${descs[$i]}"
        if [[ -f "${PROJECT_ROOT}/${file}" ]]; then
            count=$(grep -cE '^[[:space:]]*def test_' "${PROJECT_ROOT}/${file}" || echo 0)
        else
            count=0
        fi
        total_tests=$((total_tests + count))
        printf "%-10s %-25s %-12s %s\n" "$suite" "$file" "$count" "$desc"
    done

    printf "%-10s %-25s %-12s %s\n" "----------" "-------------------------" "------------" "--------------------------------------------------"
    printf "${C_BOLD}%-10s %-25s %-12s %s${C_RESET}\n" "TOTAL" "11 files" "$total_tests" "Full test suite coverage"
}

# Map a suite name to its corresponding test file path.
resolve_suite_targets() { # 42
    local -r suite_name="$1"
    case "$suite_name" in
        all)
            echo "test/test_schema.py test/test_core.py test/test_ledger.py test/test_cli.py test/test_dashboard.py test/test_profiler.py test/test_server.py test/test_mobile_sync.py test/test_ocr.py test/test_ocr_canvas.py test/test_ocr_benchmark.py"
            ;;
        schema)
            echo "test/test_schema.py"
            ;;
        core)
            echo "test/test_core.py"
            ;;
        ledger)
            echo "test/test_ledger.py"
            ;;
        cli)
            echo "test/test_cli.py"
            ;;
        dashboard)
            echo "test/test_dashboard.py"
            ;;
        profiler)
            echo "test/test_profiler.py"
            ;;
        server)
            echo "test/test_server.py"
            ;;
        mobile)
            echo "test/test_mobile_sync.py"
            ;;
        ocr)
            echo "test/test_ocr.py"
            ;;
        ocr_canvas)
            echo "test/test_ocr_canvas.py"
            ;;
        ocr_benchmark)
            echo "test/test_ocr_benchmark.py"
            ;;
        *)
            log_error "Unknown test suite: '${suite_name}'. Allowed: all, schema, core, ledger, cli, dashboard, profiler, server, mobile, ocr, ocr_canvas, ocr_benchmark."
            return 1
            ;;
    esac
}

# Check if pytest-cov is installed in the active Python environment.
check_coverage_support() { # 8
    if command -v python3 >/dev/null 2>&1 && python3 -c "import pytest_cov" >/dev/null 2>&1; then
        return 0
    elif command -v python >/dev/null 2>&1 && python -c "import pytest_cov" >/dev/null 2>&1; then
        return 0
    fi
    return 1
}

# Execute the test suite with timing, formatted reporting, and exit code propagation.
run_tests() { # 40
    local -r runner="$1"
    shift
    local -a test_args=("$@")

    local -r start_epoch=$(date +%s)
    local -r start_iso=$(date '+%Y-%m-%d %H:%M:%S')

    printf "${C_BOLD}======================================================================${C_RESET}\n"
    printf "${C_BOLD}PEIT Test Execution Started${C_RESET}: %s\n" "$start_iso"
    printf "Project Root: %s\n" "$PROJECT_ROOT"
    printf "PYTHONPATH:   %s\n" "${PROJECT_ROOT}/src"
    printf "Runner:       %s\n" "$runner"
    printf "Arguments:    %s\n" "${test_args[*]}"
    printf "${C_BOLD}======================================================================${C_RESET}\n"

    export PYTHONPATH="${PROJECT_ROOT}/src:${PYTHONPATH:-}"

    local exit_code=0
    if [[ "$runner" == "pytest" ]]; then
        pytest "${test_args[@]}" || exit_code=$?
    else
        python3 -m pytest "${test_args[@]}" || exit_code=$?
    fi

    local -r end_epoch=$(date +%s)
    local -r duration=$((end_epoch - start_epoch))

    printf "\n${C_BOLD}======================================================================${C_RESET}\n"
    if [[ $exit_code -eq 0 ]]; then
        printf "${C_GREEN}${C_BOLD}[PASS] ALL TESTS PASSED SUCCESSFULLY${C_RESET}\n"
    else
        printf "${C_RED}${C_BOLD}[FAIL] TEST SUITE FAILED (exit code %d)${C_RESET}\n" "$exit_code"
    fi
    printf "Duration:     %d second(s)\n" "$duration"
    printf "Finished:     %s\n" "$(date '+%Y-%m-%d %H:%M:%S')"
    printf "${C_BOLD}======================================================================${C_RESET}\n"

    return "$exit_code"
}

# Parse command line options and orchestrate the test runner execution.
main() { # 106
    local suite="all"
    local keyword=""
    local verbosity=""
    local list_mode=false
    local coverage_mode=false
    local -a custom_targets=()

    while [[ $# -gt 0 ]]; do
        case "$1" in
            -h|--help)
                usage
                exit 0
                ;;
            -a|--all)
                suite="all"
                shift
                ;;
            -s|--suite)
                [[ $# -ge 2 ]] || { log_error "--suite requires a suite name"; exit 2; }
                suite="$2"
                shift 2
                ;;
            --suite=*)
                suite="${1#*=}"
                shift
                ;;
            -k|--keyword)
                [[ $# -ge 2 ]] || { log_error "--keyword requires a pattern"; exit 2; }
                keyword="$2"
                shift 2
                ;;
            --keyword=*)
                keyword="${1#*=}"
                shift
                ;;
            -v|--verbose)
                verbosity="-vv"
                shift
                ;;
            -q|--quiet)
                verbosity="-q"
                shift
                ;;
            -l|--list)
                list_mode=true
                shift
                ;;
            -c|--coverage)
                coverage_mode=true
                shift
                ;;
            --)
                shift
                custom_targets+=("$@")
                break
                ;;
            -*)
                log_error "Unknown option: '$1'. Use --help for usage."
                exit 2
                ;;
            *)
                custom_targets+=("$1")
                shift
                ;;
        esac
    done

    if [[ "$list_mode" == true ]]; then
        list_test_suites
        exit 0
    fi

    local runner
    runner=$(find_pytest_runner) || exit 127

    local -a pytest_flags=()
    if [[ -n "$verbosity" ]]; then
        pytest_flags+=("$verbosity")
    fi

    if [[ -n "$keyword" ]]; then
        pytest_flags+=("-k" "$keyword")
    fi

    if [[ "$coverage_mode" == true ]]; then
        if check_coverage_support; then
            log_info "Coverage collection enabled via pytest-cov."
            pytest_flags+=("--cov=src" "--cov-report=term-missing")
        else
            log_warn "pytest-cov is not installed in the active environment. Running without coverage."
        fi
    fi

    local -a targets=()
    if [[ ${#custom_targets[@]} -gt 0 ]]; then
        targets=("${custom_targets[@]}")
    else
        local resolved
        resolved=$(resolve_suite_targets "$suite") || exit 2
        read -r -a targets <<< "$resolved"
    fi

    cd "$PROJECT_ROOT"
    run_tests "$runner" "${pytest_flags[@]}" "${targets[@]}"
}

main "$@"
