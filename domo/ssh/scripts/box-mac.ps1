# Quick connect to Box-Mac via Tailscale SSH
# Usage: .\box-mac.ps1 [command]

param(
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$Command
)

if ($Command) {
    tailscale ssh boxhead@box-mac-1 $Command
} else {
    tailscale ssh boxhead@box-mac-1
}
