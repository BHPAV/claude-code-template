#!/bin/bash
# Quick connect to Box-Rex via Tailscale SSH
# Usage: ./box-rex.sh [command]

if [ $# -eq 0 ]; then
    tailscale ssh boxhead@box-rex
else
    tailscale ssh boxhead@box-rex "$@"
fi
