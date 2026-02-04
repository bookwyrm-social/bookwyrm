#!/usr/bin/env bash
# These tests are written to run in their own container, using the same image as the
# actual postgres service. To run: `docker-compose up --build`
set -euo pipefail

source /weed.sh

ERROR_COUNT=0
FAILURE_COUNT=0

# compare two sorted files
function compare_files {
    local expected="$1"
    local actual="$2"

    declare -a missing
    local missing_index=0
    declare -a extra
    local extra_index=0

    old_ifs="$IFS"
    IFS=$'\n'
    for line in $(diff --suppress-common-lines "$expected" "$actual"); do
        if [[ $line =~ ^\< ]]; then
            missing[missing_index]=${line:1}
            missing_index=$((missing_index + 1))
        elif [[ $line =~ ^\> ]]; then
            extra[extra_index]=${line:1}
            extra_index=$((extra_index + 1))
        fi
    done
    IFS="$old_ifs"

    if [[ $((missing_index + extra_index)) -gt 0 ]]; then
        echo 'fail'

        if [[ missing_index -gt 0 ]]; then
            echo -e "\\t$missing_index missing files:"

            for index in $(seq 0 $((missing_index - 1))); do
                echo -e "\\t\\t${missing[index]}"
            done
        fi

        if [[ extra_index -gt 0 ]]; then
            echo -e "\\t$extra_index extra files:"

            for index in $(seq 0 $((extra_index - 1))); do
                echo -e "\\t\\t${extra[index]}"
            done
        fi

        FAILURE_COUNT=$((FAILURE_COUNT + 1))

        return 1
    fi
}

# This is a wrapper function that handles creating a directory with test files in it,
# running weed_directory (as the function, as a dry run, then finally actually-deleting
# files), marking the test as failed/errored as necessary, then cleaning up after
# itself. the first three arguments passed are the thresholds to pass into
# weed_directory. The remaining arguments are names of files to create for the test.
# Bash isn't great at passing arrays so instead of separately passing in a list of
# expected results, flag the files you expect to be deleted by prepending "DELETE:"
# to the path.
function perform_test {
    echo "${FUNCNAME[1]}" | sed 's/^test_\(.*\)$/\1/' | tr '_\n' ' :'
    echo -en '\t'

    local daily_threshold="$1"
    shift
    local weekly_threshold="$1"
    shift
    local monthly_threshold="$1"
    shift

    # We might as well name the files we're using for running tests in as inflamatory a
    # way as possible to increase the chances that bad filtering by weed_directory
    # results in tests failing.
    local expected="/testing/expected/backup__2020-02-02.sql"
    local actual="/testing/backup__2020-02-02.sql.actual"
    local remaining="/testing/remainbackup__2020-02-02.sql"
    local temp="/testing/backup__2020-TE-MP.sql"

    # create test files
    mkdir -p /testing/expected
    if [[ -e "$expected" ]]; then
        rm "$expected"
    fi
    touch "$expected"
    echo -e "$expected\\n$actual\\n$remaining\\n$temp" > "$remaining"
    while [[ "$#" -gt 0 ]]; do
        if [[ "$1" =~ ^DELETE: ]]; then
            path="/testing/${1:7}"
            echo "$path" >> "$expected"
        else
            path="/testing/$1"
            echo "$path" >> "$remaining"
        fi

        directory=$(dirname "$path")
        mkdir -p "$directory"
        touch "$path"

        shift
    done
    # We don't make any promise about the order files will be listed in by
    # weed_directory (it is currently reverse-chronological). We should sort the output
    # and the expected file instead of forcing tests to list files in that order (or
    # causing tests to fail if weed_directory's order changes)
    sort "$expected" > "$temp"
    mv "$temp" "$expected"
    sort "$remaining" > "$temp"
    mv "$temp" "$remaining"

    # Part one: call the function directly
    set +e
    (
        weed_directory \
            "/testing" \
            "$daily_threshold" \
            "$weekly_threshold" \
            "$monthly_threshold" \
            2> "$temp" \
        | sort > "$actual"
    )
    local result="$?"
    set -e

    if [[ "$result" -ne 0 ]]; then
        echo 'error'
        ERROR_COUNT=$((ERROR_COUNT + 1))
        if [[ -s "$temp" ]]; then
            echo 'stderr:'
            cat "$temp"
        fi
    else
        set +e
        compare_files "$expected" "$actual"
        result="$?"
        set -e

        if [[ "$result" -eq 0 ]]; then
            # Part two: as a script with the dry-run flag (-l)
            set +e
            (
                "/weed.sh" \
                "-d" "$daily_threshold" \
                "-w" "$weekly_threshold" \
                "-m" "$monthly_threshold" \
                "-l" \
                "/testing" \
                2> "$temp" \
                | sort > "$actual"
            )
            local result="$?"
            set -e

            if [[ "$result" -ne 0 ]]; then
                echo 'error'
                ERROR_COUNT=$((ERROR_COUNT + 1))
                if [[ -s "$temp" ]]; then
                    echo 'stderr:'
                    cat "$temp"
                fi
            else
                set +e
                compare_files "$expected" "$actual"
                result="$?"
                set -e

                if [[ "$result" -eq 0 ]]; then
                    # Part three: let's try actually deleting files
                    set +e
                    (
                        "/weed.sh" \
                        "-d" "$daily_threshold" \
                        "-w" "$weekly_threshold" \
                        "-m" "$monthly_threshold" \
                        "/testing" \
                        2> "$temp"
                    )
                    local result="$?"
                    set -e

                    if [[ "$result" -ne 0 ]]; then
                        echo 'error'
                        ERROR_COUNT=$((ERROR_COUNT + 1))
                        if [[ -s "$temp" ]]; then
                            echo 'stderr:'
                            cat "$temp"
                        fi
                    else
                        find /testing -type f | sort > "$actual"

                        set +e
                        compare_files "$remaining" "$actual"
                        result="$?"
                        set -e

                        if [[ "$result" -eq 0 ]]; then
                            echo 'pass'
                        elif [[ -s "$temp" ]]; then
                            echo 'stderr:'
                            cat "$temp"
                        fi
                    fi
                elif [[ -s "$temp" ]]; then
                    echo 'stderr:'
                    cat "$temp"
                fi
            fi
        elif [[ -s "$temp" ]]; then
            echo 'stderr:'
            cat "$temp"
        fi
    fi
    rm -rf /testing
}

# actual tests
function test_shellcheck {
    echo -en 'running shellcheck on scripts:\t'
    shellcheck /weed.sh
    # Test the tests too! Writing bash is hard
    shellcheck -x /testing-entrypoint.sh
    echo 'pass'
}

function test_empty_directory {
    perform_test 1 2 3
}

function test_single_file {
    perform_test 1 2 3 "backup__2021-02-02.sql"
}

function test_keep_everything {
    perform_test -1 0 0 "backup__2021-02-02.sql" "backup__2021-02-01.sql" "backup__2021-01-31.sql"
}

function test_keep_one {
    perform_test 1 0 0 "backup__2021-02-02.sql" "DELETE:backup__2021-02-01.sql" "DELETE:backup__2021-01-31.sql"
}

function test_weekly {
    # weed.sh follows ISO 8601 and uses %W for day of week, so Monday is the first day
    # of the week.
    # backup__2021-03-08.sql: Monday (keep)
    # backup__2021-03-07.sql: Sunday (keep)
    # backup__2021-02-28.sql: Sunday (keep)
    # backup__2021-02-22.sql: Monday (delete)
    # backup__2021-02-20.sql: Saturday (keep)
    # backup__2021-02-16.sql: Tuesday (delete)
    # backup__2021-02-15.sql: Monday (delete)
    # backup__2021-02-14.sql: Sunday (keep)
    # backup__2020-02-14.sql: Sunday (same week of year) (keep)
    perform_test 0 -1 0 \
        "backup__2021-03-08.sql" \
        "backup__2021-03-07.sql" \
        "backup__2021-02-28.sql" \
        "DELETE:backup__2021-02-22.sql" \
        "backup__2021-02-20.sql" \
        "DELETE:backup__2021-02-16.sql" \
        "DELETE:backup__2021-02-15.sql" \
        "backup__2021-02-14.sql" \
        "backup__2020-02-14.sql"
}

function test_monthly {
    perform_test 1 0 -1 \
        "backup__2021-03-08.sql" \
        "DELETE:backup__2021-03-07.sql" \
        "backup__2021-02-28.sql" \
        "DELETE:backup__2021-02-22.sql" \
        "DELETE:backup__2021-02-20.sql" \
        "DELETE:backup__2021-02-16.sql" \
        "DELETE:backup__2021-02-15.sql" \
        "DELETE:backup__2021-02-14.sql" \
        "backup__2021-01-14.sql" \
        "backup__2020-01-13.sql"
}

function test_annual {
    perform_test 0 0 0 \
        "backup__2021-03-08.sql" \
        "DELETE:backup__2021-03-07.sql" \
        "DELETE:backup__2021-02-28.sql" \
        "DELETE:backup__2021-02-22.sql" \
        "DELETE:backup__2021-02-20.sql" \
        "DELETE:backup__2021-02-16.sql" \
        "DELETE:backup__2021-02-15.sql" \
        "DELETE:backup__2021-02-14.sql" \
        "DELETE:backup__2021-01-14.sql" \
        "backup__2020-01-13.sql" \
        "backup__2019-12-31.sql" \
        "DELETE:backup__2019-01-13.sql"
}

# Will not pass while maxdepth is set to 1.
function skip_test_sort_order {
    perform_test 0 0 1 \
        "a/backup__2021-03-08.sql" \
        "DELETE:b/backup__2021-03-07.sql" \
        "DELETE:a/backup__2021-02-28.sql" \
        "DELETE:b/backup__2021-02-22.sql" \
        "DELETE:a/backup__2021-02-20.sql" \
        "DELETE:b/backup__2021-02-16.sql" \
        "DELETE:a/backup__2021-02-15.sql" \
        "DELETE:b/backup__2021-02-14.sql" \
        "DELETE:a/backup__2021-01-14.sql" \
        "b/backup__2020-01-13.sql" \
        "a/backup__2019-12-31.sql" \
        "DELETE:b/backup__2019-01-13.sql"
}

function test_ignore_subdirectories {
    perform_test 0 0 0 "a/backup__2021-03-08.sql" "backup__2021-03-07.sql"
}

function test_standard {
    perform_test 14 4 1 \
        "backup__2021-03-08.sql" \
        "backup__2021-03-07.sql" \
        "backup__2021-03-06.sql" \
        "backup__2021-03-05.sql" \
        "backup__2021-03-04.sql" \
        "backup__2021-03-03.sql" \
        "backup__2021-03-02.sql" \
        "backup__2021-03-01.sql" \
        "backup__2021-02-28.sql" \
        "backup__2021-02-27.sql" \
        "backup__2021-02-26.sql" \
        "backup__2021-02-25.sql" \
        "backup__2021-02-24.sql" \
        "backup__2021-02-23.sql" \
        "DELETE:backup__2021-02-22.sql" \
        "backup__2021-02-21.sql" \
        "DELETE:backup__2021-02-20.sql" \
        "DELETE:backup__2021-02-19.sql" \
        "DELETE:backup__2021-02-18.sql" \
        "DELETE:backup__2021-02-17.sql" \
        "DELETE:backup__2021-02-16.sql" \
        "DELETE:backup__2021-02-15.sql" \
        "backup__2021-02-14.sql" \
        "DELETE:backup__2021-02-13.sql" \
        "DELETE:backup__2021-02-12.sql" \
        "DELETE:backup__2021-02-11.sql" \
        "DELETE:backup__2021-02-10.sql" \
        "DELETE:backup__2021-02-09.sql" \
        "DELETE:backup__2021-02-08.sql" \
        "backup__2021-02-07.sql" \
        "DELETE:backup__2021-02-06.sql" \
        "DELETE:backup__2021-02-05.sql" \
        "DELETE:backup__2021-02-04.sql" \
        "DELETE:backup__2021-02-03.sql" \
        "DELETE:backup__2021-02-02.sql" \
        "DELETE:backup__2021-02-01.sql" \
        "backup__2021-01-31.sql" \
        "DELETE:backup__2021-01-30.sql" \
        "DELETE:backup__2021-01-29.sql" \
        "DELETE:backup__2021-01-28.sql" \
        "DELETE:backup__2021-01-27.sql" \
        "DELETE:backup__2021-01-26.sql" \
        "DELETE:backup__2021-01-25.sql" \
        "DELETE:backup__2021-01-24.sql" \
        "DELETE:backup__2021-01-23.sql" \
        "DELETE:backup__2021-01-22.sql" \
        "DELETE:backup__2021-01-21.sql" \
        "DELETE:backup__2021-01-20.sql" \
        "DELETE:backup__2021-01-19.sql" \
        "DELETE:backup__2021-01-18.sql" \
        "DELETE:backup__2021-01-17.sql" \
        "DELETE:backup__2021-01-16.sql" \
        "DELETE:backup__2021-01-15.sql" \
        "DELETE:backup__2021-01-14.sql" \
        "DELETE:backup__2021-01-13.sql" \
        "DELETE:backup__2021-01-12.sql" \
        "DELETE:backup__2021-01-11.sql" \
        "DELETE:backup__2021-01-10.sql" \
        "DELETE:backup__2021-01-09.sql" \
        "DELETE:backup__2021-01-08.sql" \
        "DELETE:backup__2021-01-07.sql" \
        "DELETE:backup__2021-01-06.sql" \
        "DELETE:backup__2021-01-05.sql" \
        "DELETE:backup__2021-01-04.sql" \
        "DELETE:backup__2021-01-03.sql" \
        "DELETE:backup__2021-01-02.sql" \
        "DELETE:backup__2021-01-01.sql" \
        "backup__2020-12-31.sql"
}

function tests {
    # Run all functions named test_... in this file in definition order
    count=0
    while read -r test; do
        eval "$test"
        count=$((count + 1))
    done < <(awk '$1 == "function" && $2 ~ "^test_" {print $2}' "${BASH_SOURCE[0]}")

    echo "------------------"
    echo "$((count - ERROR_COUNT - FAILURE_COUNT))/$count tests passed"
    if [[ $((FAILURE_COUNT + ERROR_COUNT)) -gt 0 ]]; then
        if [[ "$ERROR_COUNT" -gt 0 ]]; then
            echo "$ERROR_COUNT tests errored"
        fi

        if [[ "$FAILURE_COUNT" -gt 0 ]]; then
            echo "$FAILURE_COUNT tests failed"
        fi
        echo 'failure'
    else
        echo 'success'
    fi
}

if [ "${BASH_SOURCE[0]}" -ef "$0" ]; then
    trap 'echo -e "\\terror (in ${FUNCNAME[1]} ${BASH_SOURCE[1]}:${BASH_LINENO[1]})\naborting"' EXIT
    tests
    trap - EXIT

    if [[ $((FAILURE_COUNT + ERROR_COUNT)) -gt 0 ]]; then
        exit 1
    fi
fi