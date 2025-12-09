# Quick connect to Box-Rig via Tailscale SSH
# Usage: .\box-rig.ps1 [command]

param(
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$Command
)

if ($Command) {
    tailscale ssh boxhead@box-rig $Command
} else {
    tailscale ssh boxhead@box-rig
}
