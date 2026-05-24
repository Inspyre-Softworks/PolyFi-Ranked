#define MyAppId "{{7A5106B6-0E93-47E8-907D-E0F20DF6ABFD}"
#define MyAppName "PolyFi: Ranked"
#define MyAppPublisher "Inspyre Softworks"
#define MyAppExeName "polyfi-ranked.exe"
#define MySetupIconFile AddBackslash(SourcePath) + "..\..\build\windows\polyfi-ranked-setup.ico"
#define MyWizardImageFile AddBackslash(SourcePath) + "..\..\build\windows\polyfi-ranked-wizard.png"
#define MyWizardSmallImageFile AddBackslash(SourcePath) + "..\..\build\windows\polyfi-ranked-wizard-small.png"

#ifndef MyAppVersion
  #error MyAppVersion must be provided, for example /DMyAppVersion=1.0.0-dev.9
#endif

#ifndef MyAppDistDir
  #error MyAppDistDir must point at the PyInstaller onedir folder.
#endif

#ifndef MyInstallerOutputDir
  #define MyInstallerOutputDir AddBackslash(SourcePath) + "..\..\dist\installer"
#endif

#define MyInstallerBaseName "polyfi-ranked-setup-" + MyAppVersion

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\PolyFi-Ranked
DefaultGroupName=PolyFi Ranked
DisableProgramGroupPage=yes
DisableDirPage=no
OutputDir={#MyInstallerOutputDir}
OutputBaseFilename={#MyInstallerBaseName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupIconFile={#MySetupIconFile}
WizardImageFile={#MyWizardImageFile}
WizardSmallImageFile={#MyWizardSmallImageFile}
WizardSmallImageBackColor=none
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
ChangesEnvironment=yes

[Tasks]
Name: "startmenuicons"; Description: "Create Start Menu shortcuts"; GroupDescription: "Windows shortcuts:"
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
Name: "addtopath"; Description: "Add PolyFi to the system PATH"; GroupDescription: "Windows integrations:"
Name: "startupshortcut"; Description: "Start PolyFi automatically when I sign in"; GroupDescription: "Windows integrations:"; Flags: unchecked
Name: "wifitasks"; Description: "Install Wi-Fi helper tasks for adapter control (may prompt for approval)"; GroupDescription: "Windows integrations:"; Flags: unchecked

[Files]
Source: "{#MyAppDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourcePath}\..\..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourcePath}\..\..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourcePath}\..\..\scripts\manage_install_record.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourcePath}\..\..\scripts\manage_windows_path.ps1"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\PolyFi Ranked"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--tray --show-splash"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"; Comment: "Launch PolyFi in the system tray"; Tasks: startmenuicons
Name: "{group}\PolyFi Ranked Console"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"; Comment: "Open the PolyFi command-line launcher"; Tasks: startmenuicons
Name: "{autodesktop}\PolyFi Ranked"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--tray --show-splash"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-ExecutionPolicy Bypass -NoProfile -File ""{app}\manage_windows_path.ps1"" -Mode Add -InstallDir ""{app}"""; StatusMsg: "Adding PolyFi to PATH..."; Tasks: addtopath; Flags: runhidden waituntilterminated
Filename: "{app}\{#MyAppExeName}"; Parameters: "windows startup install --force"; WorkingDir: "{app}"; StatusMsg: "Installing Startup Programs shortcut..."; Tasks: startupshortcut; Flags: runhidden waituntilterminated
Filename: "{app}\{#MyAppExeName}"; Parameters: "windows wifi-tasks install"; WorkingDir: "{app}"; StatusMsg: "Installing Wi-Fi helper tasks..."; Tasks: wifitasks; Flags: hidewizard runhidden waituntilterminated
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "{code:GetInstallRecordParameters}"; StatusMsg: "Recording installed features..."; Flags: runhidden waituntilterminated
Filename: "{group}\PolyFi Ranked"; Description: "Launch PolyFi in the system tray"; Flags: nowait postinstall shellexec skipifsilent unchecked; Tasks: startmenuicons
Filename: "{app}\{#MyAppExeName}"; Parameters: "--tray --show-splash"; Description: "Launch PolyFi in the system tray"; Flags: nowait postinstall skipifsilent unchecked; Tasks: not startmenuicons

[UninstallRun]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-ExecutionPolicy Bypass -NoProfile -File ""{app}\manage_windows_path.ps1"" -Mode Remove -InstallDir ""{app}"""; RunOnceId: "RemovePolyFiPath"; Flags: runhidden waituntilterminated skipifdoesntexist
Filename: "{app}\{#MyAppExeName}"; Parameters: "windows uninstall"; WorkingDir: "{app}"; RunOnceId: "RemovePolyFiWindowsIntegrations"; Flags: runhidden waituntilterminated skipifdoesntexist

[Code]
function BoolToLower(Value: Boolean): String;
begin
  if Value then
    Result := 'true'
  else
    Result := 'false';
end;

function GetInstallRecordParameters(Param: String): String;
begin
  Result :=
    '-ExecutionPolicy Bypass -NoProfile -File "' + ExpandConstant('{app}\manage_install_record.ps1') + '"' +
    ' -Mode Write' +
    ' -InstallMode "inno-setup"' +
    ' -InstallRoot "' + ExpandConstant('{app}') + '"' +
    ' -AppExecutable "' + ExpandConstant('{app}\{#MyAppExeName}') + '"' +
    ' -AddToPath ' + BoolToLower(WizardIsTaskSelected('addtopath')) +
    ' -DesktopShortcut ' + BoolToLower(WizardIsTaskSelected('desktopicon')) +
    ' -ScheduledLogonTask false' +
    ' -StartMenu ' + BoolToLower(WizardIsTaskSelected('startmenuicons')) +
    ' -StartupShortcut ' + BoolToLower(WizardIsTaskSelected('startupshortcut')) +
    ' -WifiTasks ' + BoolToLower(WizardIsTaskSelected('wifitasks'));
end;
