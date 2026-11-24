' Collegamenti sul desktop dell'utente.
'   cscript crea_collegamenti.vbs C:\denoising_live   crea i collegamenti
'   cscript crea_collegamenti.vbs /rimuovi              li cancella (disinstalla.bat)
Dim sh, fso, dest, desk, voci, i, lnk, p
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
dest = WScript.Arguments(0)
desk = sh.SpecialFolders("Desktop")
voci = Array("denoising_live (Digidata)", "avvia.bat", _
             "Diagnostica Digidata", "diagnostica.bat", _
             "denoising_live (simulazione)", "avvia_simulazione.bat")
For i = 0 To UBound(voci) Step 2
  p = desk & "\" & voci(i) & ".lnk"
  If LCase(dest) = "/rimuovi" Then
    If fso.FileExists(p) Then
      fso.DeleteFile p
      WScript.Echo "  rimosso: " & voci(i)
    End If
  Else
    Set lnk = sh.CreateShortcut(p)
    lnk.TargetPath = dest & "\" & voci(i + 1)
    lnk.WorkingDirectory = dest
    lnk.Save
    WScript.Echo "  collegamento: " & voci(i)
  End If
Next
