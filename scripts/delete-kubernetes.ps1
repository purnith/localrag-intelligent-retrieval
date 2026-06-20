param(
    [string]$ClusterName = "localrag"
)

$ErrorActionPreference = "Stop"
$KindCommand = (Get-Command kind -ErrorAction SilentlyContinue).Source
if (-not $KindCommand) {
    $KindCommand = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" `
        -Recurse -Filter kind.exe -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $KindCommand) {
    throw "Required command 'kind' is not installed or not available on PATH."
}

& $KindCommand delete cluster --name $ClusterName
