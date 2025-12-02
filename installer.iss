; Pharma-POS-AI Windows Installer
; Created by: Evans Ahiadzi - VexaAI

#define MyAppName "Pharma-POS-AI"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "VexaAI"
#define MyAppURL "https://vexaai.com"

[Setup]
AppId={{A7B9C3D1-E5F4-4A2B-8C9D-1E2F3A4B5C6D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=Pharma-POS-AI-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"
Name: "quicklaunchicon"; Description: "Create a &Quick Launch icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
; Copy entire project
Source: "backend\*"; DestDir: "{app}\backend"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "frontend\*"; DestDir: "{app}\frontend"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "database\*"; DestDir: "{app}\database"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "docker-compose.yml"; DestDir: "{app}"; Flags: ignoreversion
Source: ".env.example"; DestDir: "{app}"; Flags: ignoreversion
Source: "start.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "stop.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "backup.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "uninstall-app.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.txt"; DestDir: "{app}"; Flags: ignoreversion isreadme

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\start.bat"; IconFilename: "{app}\icon.ico"
Name: "{group}\Stop {#MyAppName}"; Filename: "{app}\stop.bat"
Name: "{group}\Backup Database"; Filename: "{app}\backup.bat"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\start.bat"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\start.bat"; Tasks: quicklaunchicon

[Run]
; Check if Docker Desktop is installed
Filename: "powershell.exe"; \
  Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""if (!(Get-Command docker -ErrorAction SilentlyContinue)) {{ $result = [System.Windows.MessageBox]::Show('Docker Desktop is not installed. Would you like to download it now?', 'Docker Required', 'YesNo', 'Question'); if ($result -eq 'Yes') {{ Start-Process 'https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe' }} }}"""; \
  Flags: runhidden

; Create .env from example
Filename: "{app}\setup-env.bat"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated

; Ask to start the application
Filename: "{app}\start.bat"; Description: "Launch {#MyAppName} now"; Flags: postinstall nowait skipifsilent

[UninstallRun]
Filename: "{app}\uninstall-app.bat"; Flags: runhidden waituntilterminated

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Show completion message
    MsgBox('Installation complete!' + #13#10#13#10 + 
           'Access the system at: http://localhost:8080' + #13#10 +
           'API Docs: http://localhost:8000/docs' + #13#10#13#10 +
           'Default Login:' + #13#10 +
           'Username: admin' + #13#10 +
           'Password: admin123' + #13#10#13#10 +
           'IMPORTANT: Change the default password after first login!', 
           mbInformation, MB_OK);
  end;
end;