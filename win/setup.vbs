Option Explicit
Dim shell, files, script, command, result
Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")
script = files.BuildPath(files.GetParentFolderName(WScript.ScriptFullName), "setup.ps1")
command = """" & shell.ExpandEnvironmentStrings("%SystemRoot%") & "\System32\WindowsPowerShell\v1.0\powershell.exe"" -NoProfile -STA -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & script & """"
On Error Resume Next
result = shell.Run(command, 0, True)
If Err.Number <> 0 Then
    MsgBox "Nie mozna uruchomic instalatora. " & Err.Description, 16, "FFmpeg Convert"
ElseIf result <> 0 Then
    MsgBox "Instalator nie mogl wystartowac. Sprawdz, czy caly projekt zostal rozpakowany i PowerShell jest dostepny.", 16, "FFmpeg Convert"
End If
