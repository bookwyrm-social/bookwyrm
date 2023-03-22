#!/usr/bin/env bash
# Weed old backups. See HELP for details.
# Tests for this script can be found in:
# bookwyrm/postgres-docker/tests/testing-entrypoint.sh
set -euo pipefail

DAILY_THRESHOLD=14
WEEKLY_THRESHOLD=4
MONTHLY_THRESHOLD=-1

HELP="\
NAME

weed -- remove old backups from the backups directory

SYNOPSIS

weed.sh [-d threshold] [-w threshold] [-m threshold] [-l] backup_directory

DESCRIPTION

Reduce the number of backups by only keeping a certain number of daily backups before \
reducing the frequency to weekly, monthly, and then finaly annually.

For each threshold, setting it to 0 will skip that frequency (e.g., setting weekly to \
0 will mean backups go directly from daily to monthly), and setting it to -1 will \
never reduce backups to a lower frequency (e.g., setting weekly to -1 will mean \
backups never are reduced to monthly backups).

-d threshold: Store this many daily backups before switching to weekly \
(default $DAILY_THRESHOLD)

-w threshold: Store this many weekly backups before switching to monthly \
(default $WEEKLY_THRESHOLD)

-m threshold: Store this many monthly backups before switching to annual \
(default $MONTHLY_THRESHOLD)

-l: Dry run. List the files that would be deleted.
"

# fail <message>
# Write a message to stderr then exit
function fail {
    echo -e "weed: $1" >&2
    exit 1
}

# parse_threshold <hopefully-a-number>
# Thresholds should be a non-negative number (or -1 for no threshold)
function parse_threshold {
    if [[ ! $1 =~ ^-?[0-9]+$ || $1 -lt -1 ]]; then
        fail "Invalid threshold: $1"
    fi

    echo "$1"
}

# weed_directory <directory> <daily_threshold> <weekly_threshold> <monthly_threshold>
# List files to be deleted
function weed_directory {
    local directory=$1
    local daily_threshold=$2
    local weekly_threshold=$3
    local monthly_threshold=$4

    local count=0
    local thresholds=("$daily_threshold" "$weekly_threshold" "$monthly_threshold" -1)
    local date_formats=("%Y %m %d" "%Y %W" "%Y %m" "%Y")
    local index=0
    local last_date=""
    local last_format=""
    local date=""

    # We would like to loop through all the backup files in the backup directory in
    # reverse-chronological order. Bookwyrm backup files are named such that
    # chronological and lexical order match. So we should be safe to find all backup
    # files and reverse sort them. We should be terrified of deleting a backup an
    # instance maintainer wants to keep, so we will be extra cautious. We're ignoring
    # any subdirectories in case someone moves an important backup into a meaningfully
    # named folder. We are also prepending the date to the path before sorting so that
    # the ordering would be correct even if we were allowed to find backup files in
    # subdirectories where chronological and lexical order don't match.
    for date_file in $(
        find "$directory" \
            -maxdepth 1 \
            -name 'backup_[a-z]*_[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]\.sql' \
        | sed 's/\(^.*backup_[a-z]*_\([0-9-]*\)\.sql$\)/\2\1/' \
        | sort --reverse
    ); do
        date="${date_file:0:10}"
        file="${date_file:10}"
        date="${date_file:0:10}"
        file="${date_file:10}"

        # We can't fall off the end because we set annual backups to unlimited. It seems
        # unlikely that instance maintainers would have enough concern about the space
        # one backup/year takes to warrant supporting a cutoff.
        while [[ ${thresholds[index]} -ne -1 && $count -ge ${thresholds[index]} ]]; do
            index=$((index + 1))
            last_format=""
            count=0
        done

        if [[ -z "$last_date" ]]; then
            count=$((count + 1))
            last_date=$date
            last_format=""
        else
            if [[ -z "$last_format" ]]; then
                last_format=$(date --date="$last_date" +"${date_formats[index]}")
            fi

            format=$(date --date="$date" +"${date_formats[index]}")

            if [[ "$format" == "$last_format" ]]; then
                echo "$file"
            else
                count=$((count + 1))
                last_date="$date"
                last_format="$format"
            fi
        fi
    done
}

function main(){
    local daily_threshold=$DAILY_THRESHOLD
    local weekly_threshold=$WEEKLY_THRESHOLD
    local monthly_threshold=$MONTHLY_THRESHOLD
    local dry_run=""

    while getopts "hd:w:m:l" OPTION; do
        case "$OPTION" in
            h)
                echo "$HELP";
                exit
                ;;
            d)
                daily_threshold=$(parse_threshold "$OPTARG")
                ;;
            w)
                weekly_threshold=$(parse_threshold "$OPTARG")
                ;;
            m)
                monthly_threshold=$(parse_threshold "$OPTARG")
                ;;
            l)
                dry_run="true"
                ;;
            :)
                fail "Missing argument for '$OPTARG'. To see help run: weed.sh -h"
                ;;
            ?)
                fail "Unknown option '$OPTION'. To see help run: weed.sh -h"
        esac
    done
    shift "$((OPTIND - 1))"

    if [[ $# -ne 1 ]]; then
        fail "expected a single argument, directory"
    fi

    local count=0
    for file in $(weed_directory "$1" "$daily_threshold" "$weekly_threshold" "$monthly_threshold"); do
        count=$((count + 1))
        if [[ -n "$dry_run" ]]; then
            echo "$file"
        else
            echo "deleting $file" >&2
            rm "$file"
        fi
    done

    if [[ -n "$dry_run" ]]; then
        optional_words="would be "
    else
        optional_words=""
    fi
    echo -e "$count files ${optional_words}deleted" >&2
}

if [ "${BASH_SOURCE[0]}" -ef "$0" ]; then
    main "$@"
fi
