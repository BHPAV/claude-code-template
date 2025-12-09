#!/bin/bash
# Quick connect to Box-Mac via Tailscale SSH
# Usage: ./box-mac.sh [command]

if [ $# -eq 0 ]; then
    tailscale ssh boxhead@box-mac-1
else
    tailscale ssh boxhead@box-mac-1 "$@"
fi
