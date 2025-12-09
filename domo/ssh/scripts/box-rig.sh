#!/bin/bash
# Quick connect to Box-Rig via Tailscale SSH
# Usage: ./box-rig.sh [command]

if [ $# -eq 0 ]; then
    tailscale ssh boxhead@box-rig
else
    tailscale ssh boxhead@box-rig "$@"
fi
