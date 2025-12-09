# Quick connect to Box-Rex via Tailscale SSH
# Usage: .\box-rex.ps1 [command]

param(
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$Command
)

if ($Command) {
    tailscale ssh boxhead@box-rex $Command
} else {
    tailscale ssh boxhead@box-rex
}
