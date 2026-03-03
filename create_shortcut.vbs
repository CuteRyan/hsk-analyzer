Set ws = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
desktop = ws.SpecialFolders("Desktop")
base = fso.GetParentFolderName(WScript.ScriptFullName)

Set sc1 = ws.CreateShortcut(desktop & "\HSK Listening.lnk")
sc1.TargetPath = base & "\open_listening.bat"
sc1.WorkingDirectory = base
sc1.WindowStyle = 7
sc1.Save

Set sc2 = ws.CreateShortcut(desktop & "\HSK Vocabulary.lnk")
sc2.TargetPath = base & "\open_vocabulary.bat"
sc2.WorkingDirectory = base
sc2.WindowStyle = 7
sc2.Save

Set sc3 = ws.CreateShortcut(desktop & "\HSK Menu.lnk")
sc3.TargetPath = base & "\hsk.bat"
sc3.WorkingDirectory = base
sc3.WindowStyle = 1
sc3.Save
