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
; Built in CI:  iscc /DAppVersion=6.1 /DSourceDir=<repo>\dist-windows\onedir\PyCmd installer.iss

#ifndef AppVersion
  #define AppVersion "0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\..\dist-windows\onedir\PyCmd"
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

[InstallDelete]
; A clean _internal every update: nothing left over from the version before.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
; 6.1: the folder build, not the one-file exe - it starts faster and never
; unpacks into %TEMP%, so a vanished _MEI folder cannot stop it starting.
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\PyCmd"; Filename: "{app}\PyCmd.exe"; Comment: "PyCmd - one console, run anything"
; Always, on every install and update: 5.9 made it an option that silent installs and
; updates never ticked, so most people had no desktop shortcut at all.
Name: "{autodesktop}\PyCmd"; Filename: "{app}\PyCmd.exe"; Comment: "PyCmd - one console, run anything"

[Run]
; After a normal install: a box to tick. After a silent update: straight back in.
Filename: "{app}\PyCmd.exe"; Description: "Start PyCmd"; Flags: nowait postinstall skipifsilent
Filename: "{app}\PyCmd.exe"; Parameters: "--updated"; Flags: nowait; Check: ShouldRelaunch

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Code]
{ Whatever started this installer - an older PyCmd, mid-update - may have left
  its one-file bootloader's variables in our environment. Programs we start
  (the new PyCmd, below) would inherit them and look for Python in the old
  PyCmd's deleted temp folder: "Failed to load Python DLL". Drop them first. }
function SetEnvironmentVariable(lpName: String; lpValue: String): BOOL;
  external 'SetEnvironmentVariableW@kernel32.dll stdcall';
function RemoveEnvironmentVariable(lpName: String; lpValue: Cardinal): BOOL;
  external 'SetEnvironmentVariableW@kernel32.dll stdcall';
function ResetDllDirectory(lpPathName: Cardinal): BOOL;
  external 'SetDllDirectoryW@kernel32.dll stdcall';

function InitializeSetup(): Boolean;
begin
  RemoveEnvironmentVariable('_PYI_APPLICATION_HOME_DIR', 0);
  RemoveEnvironmentVariable('_PYI_ARCHIVE_FILE', 0);
  RemoveEnvironmentVariable('_PYI_PARENT_PROCESS_LEVEL', 0);
  RemoveEnvironmentVariable('_PYI_SPLASH_IPC', 0);
  RemoveEnvironmentVariable('_MEIPASS2', 0);
  RemoveEnvironmentVariable('TCL_LIBRARY', 0);
  RemoveEnvironmentVariable('TK_LIBRARY', 0);
  SetEnvironmentVariable('PYINSTALLER_RESET_ENVIRONMENT', '1');
  ResetDllDirectory(0);
  Result := True;
end;

function ShouldRelaunch(): Boolean;
begin
  Result := WizardSilent and (ExpandConstant('{param:nolaunch|0}') <> '1');
end;
