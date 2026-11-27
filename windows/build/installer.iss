; PyCmd for Windows - the installer (Inno Setup 6).
;
; Per-user, no administrator: the app goes to %LOCALAPPDATA%\Programs\PyCmd,
; like VS Code's user installer, and your things stay where they always were,
; in %LOCALAPPDATA%\PyCmd - the uninstaller never touches them.
;
; The same AppId every release, so a new installer updates the installed copy
; in place. Run silently (/VERYSILENT) it closes a running PyCmd, replaces it,
; and starts it again: that is how the in-app updater installs an update.
;
; Built in CI:  iscc /DAppVersion=5.9 /DSourceExe=..\..\dist-windows\build\PyCmd.exe installer.iss

#ifndef AppVersion
  #define AppVersion "0.0"
#endif
#ifndef SourceExe
  #define SourceExe "..\..\dist-windows\build\PyCmd.exe"
#endif

[Setup]
AppId={{6B0F6B8E-2E9A-4C61-9C3E-5079434D5059}
AppName=PyCmd
AppVersion={#AppVersion}
AppVerName=PyCmd {#AppVersion}
AppPublisher=Exp_Studio
AppPublisherURL=https://pycmd.pages.dev
AppSupportURL=https://pycmd.pages.dev
DefaultDirName={localappdata}\Programs\PyCmd
DefaultGroupName=PyCmd
DisableProgramGroupPage=yes
DisableDirPage=auto
DisableReadyPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\..\dist-windows\build
OutputBaseFilename=PyCmd-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
UninstallDisplayIcon={app}\PyCmd.exe
UninstallDisplayName=PyCmd
CloseApplications=force
RestartApplications=no
VersionInfoVersion={#AppVersion}
VersionInfoProductName=PyCmd

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Put PyCmd on the desktop"; GroupDescription: "Shortcuts:"

[Files]
Source: "{#SourceExe}"; DestDir: "{app}"; DestName: "PyCmd.exe"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\PyCmd"; Filename: "{app}\PyCmd.exe"; Comment: "PyCmd - one console, run anything"
Name: "{autodesktop}\PyCmd"; Filename: "{app}\PyCmd.exe"; Tasks: desktopicon

[Run]
; After a normal install: a box to tick. After a silent update: straight back in.
Filename: "{app}\PyCmd.exe"; Description: "Start PyCmd"; Flags: nowait postinstall skipifsilent
Filename: "{app}\PyCmd.exe"; Parameters: "--updated"; Flags: nowait; Check: ShouldRelaunch

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Code]
{ A silent install - an update from inside PyCmd - starts it again, unless
  /nolaunch=1 is passed: the CI test installs and uninstalls with no window. }
function ShouldRelaunch(): Boolean;
begin
  Result := WizardSilent and (ExpandConstant('{param:nolaunch|0}') <> '1');
end;
