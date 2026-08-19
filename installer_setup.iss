[Setup]
AppId={{9C7693B9-32D5-4EC0-A0A1-6C19AA44FA5F}}
AppName=Groove Trainer by Anton Shcherbakov
AppVersion=1.0.1
AppPublisher=Anton Shcherbakov
AppPublisherURL=https://github.com/antonshcherbakov
DefaultDirName={autopf}\Groove Trainer
DefaultGroupName=Groove Trainer by Anton Shcherbakov
DisableProgramGroupPage=yes
OutputDir=dist_installers\windows
OutputBaseFilename=GrooveTrainer-Windows-Setup
SetupIconFile=app_icon.ico
WizardSmallImageFile=packaging\windows\wizard-small.bmp
WizardImageFile=packaging\windows\wizard.bmp
WizardImageStretch=yes
UninstallDisplayIcon={app}\GrooveTrainer.exe
UninstallDisplayName=Groove Trainer by Anton Shcherbakov
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
Source: "dist\GrooveTrainer.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "logo.png"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Groove Trainer"; Filename: "{app}\GrooveTrainer.exe"; IconFilename: "{app}\app_icon.ico"; IconIndex: 0
Name: "{group}\{cm:UninstallProgram,Groove Trainer}"; Filename: "{uninstallexe}"; IconFilename: "{app}\app_icon.ico"; IconIndex: 0
Name: "{autodesktop}\Groove Trainer"; Filename: "{app}\GrooveTrainer.exe"; IconFilename: "{app}\app_icon.ico"; IconIndex: 0; Tasks: desktopicon

[Run]
Filename: "{app}\GrooveTrainer.exe"; Description: "{cm:LaunchProgram,Groove Trainer}"; Flags: nowait postinstall skipifsilent
