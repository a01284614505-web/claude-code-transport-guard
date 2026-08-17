#!/usr/bin/env bash
printf 'CCGUARD_PROMPT=%s\n' "${CCGUARD_PROMPT:-unset}"
printf 'CCGUARD_GATE=%s\n' "${CCGUARD_GATE:-unset}"
printf 'ARGS'
printf ' <%s>' "$@"
printf '\n'
