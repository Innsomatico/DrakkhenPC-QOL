# restore.ps1 [good|stock]  - put the game back to a known state.
#   good  (default) = last build confirmed working in game: compass + map + readable spell font
#   stock            = pristine unmodded files
# Saves are never touched. A copy of them sits in _backup\saves\ .
param([ValidateSet('good','stock')][string]$What = 'good')

$game = Split-Path -Parent $PSScriptRoot
$src  = if ($What -eq 'good') { Join-Path $game '_backup\good' } else { Join-Path $game '_backup\original' }
$files = @('DRAKM.CC1', 'RESI_VGA.6C0', 'MAP.DRK')

foreach ($f in $files) {
    $from = Join-Path $src $f
    if (-not (Test-Path $from)) {
        # MAP.DRK has no stock version - it is a file we added, so remove it when going stock.
        if ($What -eq 'stock' -and $f -eq 'MAP.DRK') {
            Remove-Item (Join-Path $game $f) -ErrorAction SilentlyContinue
            "removed  $f (not part of the stock game)"
        } else {
            Write-Warning "missing $from"
        }
        continue
    }
    Copy-Item $from (Join-Path $game $f) -Force
    "restored $f"
}
"`nGame is now: $What"
