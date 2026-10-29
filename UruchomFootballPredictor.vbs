
Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

projectPath = FSO.GetParentFolderName(WScript.ScriptFullName)
frontendPath = FSO.BuildPath(projectPath, "frontend")
pythonPath = FSO.BuildPath(projectPath, "backend\venv\Scripts\pythonw.exe")

WshShell.CurrentDirectory = frontendPath

WshShell.Run """" & pythonPath & """ -m main", 0, False
