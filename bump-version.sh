#!/bin/bash

NOW="$(date +'%B %d, %Y')"
RED="\033[1;31m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
BLUE="\033[1;34m"
PURPLE="\033[1;35m"
CYAN="\033[1;36m"
WHITE="\033[1;37m"
RESET="\033[0m"

LATEST_HASH=`git log --pretty=format:'%h' -n 1`

QUESTION_FLAG="${GREEN}?"
WARNING_FLAG="${YELLOW}!"
NOTICE_FLAG="${CYAN}❯"

# ADJUSTMENTS_MSG="${QUESTION_FLAG} ${CYAN}Now you can make adjustments to ${WHITE}CHANGELOG.md${CYAN}. Then press enter to continue."
PUSHING_MSG="${NOTICE_FLAG} Pushing new version to the ${WHITE}origin${CYAN}..."

if [ -f VERSION ]; then
    BASE_STRING=`cat VERSION`
    BASE_LIST=(`echo $BASE_STRING | tr '.' ' '`)
    V_MAJOR=${BASE_LIST[0]}
    V_MINOR=${BASE_LIST[1]}
    V_PATCH=${BASE_LIST[2]}
    echo -e "${NOTICE_FLAG} Current version: ${WHITE}$BASE_STRING"
    echo -e "${NOTICE_FLAG} Latest commit hash: ${WHITE}$LATEST_HASH"
    V_MINOR=$((V_MINOR + 1))
    V_PATCH=0
    SUGGESTED_VERSION="$V_MAJOR.$V_MINOR.$V_PATCH"
    echo -ne "${QUESTION_FLAG} ${CYAN}Enter a version number [${WHITE}$SUGGESTED_VERSION${CYAN}]: "
    read INPUT_STRING
    if [ "$INPUT_STRING" = "" ]; then
        INPUT_STRING=$SUGGESTED_VERSION
    fi
    echo -e "${NOTICE_FLAG} Will set new version to be ${WHITE}$INPUT_STRING"
    echo $INPUT_STRING > VERSION
#    echo "## $INPUT_STRING ($NOW)" > tmpfile
#    git log --pretty=format:"  - %s" "v$BASE_STRING"...HEAD >> tmpfile
#    echo "" >> tmpfile
#    echo "" >> tmpfile
#    cat CHANGELOG.md >> tmpfile
#    mv tmpfile CHANGELOG.md
#    echo -e "$ADJUSTMENTS_MSG"
#    read
    echo -e "$PUSHING_MSG"
#    git add CHANGELOG.md VERSION
    git commit -m "Bump version to ${INPUT_STRING}."
    git tag -a -m "Tag version ${INPUT_STRING}." "v$INPUT_STRING"
    git push origin --tags
else
    echo -e "${WARNING_FLAG} Could not find a VERSION file."
    echo -ne "${QUESTION_FLAG} ${CYAN}Do you want to create a version file and start from scratch? [${WHITE}y${CYAN}]: "
    read RESPONSE
    if [ "$RESPONSE" = "" ]; then RESPONSE="y"; fi
    if [ "$RESPONSE" = "Y" ]; then RESPONSE="y"; fi
    if [ "$RESPONSE" = "Yes" ]; then RESPONSE="y"; fi
    if [ "$RESPONSE" = "yes" ]; then RESPONSE="y"; fi
    if [ "$RESPONSE" = "YES" ]; then RESPONSE="y"; fi
    if [ "$RESPONSE" = "y" ]; then
        echo "0.1.0" > VERSION
        echo "## 0.1.0 ($NOW)" > CHANGELOG.md
#        git log --pretty=format:"  - %s" >> CHANGELOG.md
#        echo "" >> CHANGELOG.md
#        echo "" >> CHANGELOG.md
#        echo -e "$ADJUSTMENTS_MSG"
#        read
        echo -e "$PUSHING_MSG"
        git add VERSION CHANGELOG.md
        git commit -m "Add VERSION and CHANGELOG.md files, Bump version to v0.1.0."
        git tag -a -m "Tag version 0.1.0." "v0.1.0"
        git push origin --tags
    fi
fi

echo -e "${NOTICE_FLAG} Finished."
