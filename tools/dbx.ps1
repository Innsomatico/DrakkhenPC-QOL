# DOSBox driver: dbx.ps1 [keys...] ; keys in SendKeys syntax, each arg sent with 400ms gap; then screenshot to $env:DBX_OUT
Add-Type -AssemblyName System.Drawing; Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System; using System.Runtime.InteropServices;
public class Dbx {
 [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f);
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out R r);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, IntPtr p);
 [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint a, uint b, bool f);
 [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
 [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
 public struct R { public int L,T,Ri,B; }
 public static void Focus(IntPtr h) {
   uint fg = GetWindowThreadProcessId(GetForegroundWindow(), IntPtr.Zero); uint me = GetCurrentThreadId();
   AttachThreadInput(me, fg, true); ShowWindow(h, 9); SetForegroundWindow(h); AttachThreadInput(me, fg, false);
 }
}
"@
$p = Get-Process DOSBox | Select-Object -First 1; $h = $p.MainWindowHandle
$ws = New-Object -ComObject WScript.Shell
for ($t=0; $t -lt 10 -and [Dbx]::GetForegroundWindow() -ne $h; $t++) { $ws.AppActivate($p.Id) | Out-Null; [Dbx]::Focus($h); Start-Sleep -Milliseconds 300 }
# Focus can legitimately fail (another window grabbed it). Do NOT throw: a capture without keys is
# still useful, and throwing here used to look exactly like a hung game.
$focused = [Dbx]::GetForegroundWindow() -eq $h
if (-not $focused) { Write-Warning "could not focus DOSBox - skipping keys, capturing anyway" }
if ($focused) { foreach ($k in $args) { [System.Windows.Forms.SendKeys]::SendWait($k); Start-Sleep -Milliseconds 400 } }
Start-Sleep -Milliseconds 1500
$r = New-Object Dbx+R; [Dbx]::GetWindowRect($h,[ref]$r) | Out-Null
$bmp = New-Object System.Drawing.Bitmap(($r.Ri-$r.L),($r.B-$r.T)); $g=[System.Drawing.Graphics]::FromImage($bmp); $g.CopyFromScreen($r.L,$r.T,0,0,$bmp.Size)
$out = if ($env:DBX_OUT) { $env:DBX_OUT } else { "C:\Program Files\GOG Galaxy\Games\Drakkhen\_tools\shot.png" }
$bmp.Save($out); "fg=$([Dbx]::GetForegroundWindow() -eq $h) title=$($p.MainWindowTitle) -> $out"
