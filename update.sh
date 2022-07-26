#!/bin/bash
set -e

# determine inital and target versions
initial_version="`./bw-dev runweb python manage.py instance_version --current`"
target_version="`./bw-dev runweb python manage.py instance_version --target`"

initial_version="`echo $initial_version | tail -n 1 | xargs`"
target_version="`echo $target_version | tail -n 1 | xargs`"
if [[ "$initial_version" = "$target_version" ]]; then
    echo "Already up to date; version $initial_version"
    exit
fi

echo "---------------------------------------"
echo "Updating from version: $initial_version"
echo ".......... to version: $target_version"
echo "---------------------------------------"

function version_gt() { test "$(printf '%s\n' "$@" | sort -V | head -n 1)" != "$1"; }

# execute scripts between initial and target
for version in `ls -A updates/ | sort -V `; do
    if version_gt $initial_version $version; then
        # too early
        continue
    fi
    if version_gt $version $target_version; then
        # too late
        continue
    fi
    echo "Running tasks for version $version"
    ./updates/$version
done

./bw-dev runweb python manage.py instance_version --update
echo "✨ ----------- Done! --------------- ✨"
