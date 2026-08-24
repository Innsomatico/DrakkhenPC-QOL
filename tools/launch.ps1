Get-Process DOSBox -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Process -FilePath "C:\Program Files\GOG Galaxy\Games\Drakkhen\DOSBOX\DOSBox.exe" -WorkingDirectory "C:\Program Files\GOG Galaxy\Games\Drakkhen\DOSBOX" -ArgumentList '-conf "..\dosbox_drakkhen.conf" -conf "..\dosbox_drakkhen_single.conf" -conf "..\_tools\dev.conf" -noconsole'
Start-Sleep 6
