#define AppName GetEnv("APP_NAME")
#if AppName == ""
  #error "APP_NAME must be set by live_bot/build.bat"
#endif
#define AppVersion "1.0.0"
#define AppExeName AppName + ".exe"

[Setup]
AppId={{B8137D04-6221-4C68-A622-10507EF8C3D1}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Igneel
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#SourcePath}\dist
OutputBaseFilename={#AppName}Setup
SetupIconFile={#SourcePath}\igneel.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "{#SourcePath}\dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Code]
var
  EnvPage: TWizardPage;
  EnvMemo: TNewMemo;

function IsDigits(const Value: string): Boolean;
var
  I: Integer;
begin
  Result := Value <> '';
  for I := 1 to Length(Value) do
    if (Value[I] < '0') or (Value[I] > '9') then
    begin
      Result := False;
      Exit;
    end;
end;

function EnvValueForValidation(const Value: string): string;
var
  I: Integer;
  Quote: Char;
begin
  Result := Trim(Value);
  if Result = '' then
    Exit;

  if (Result[1] = '"') or (Result[1] = '''') then
  begin
    Quote := Result[1];
    for I := 2 to Length(Result) do
      if (Result[I] = Quote) and (Result[I - 1] <> '\') then
      begin
        Result := Copy(Result, 2, I - 2);
        Exit;
      end;
    Result := '';
    Exit;
  end;

  for I := 1 to Length(Result) do
    if (Result[I] = '#') and
       ((I = 1) or (Result[I - 1] = ' ') or (Result[I - 1] = #9)) then
    begin
      Result := Trim(Copy(Result, 1, I - 1));
      Exit;
    end;
end;

function FindEnvValue(const Name: string): string;
var
  Lines: TStringList;
  I: Integer;
  Line: string;
  Key: string;
  Separator: Integer;
begin
  Result := '';
  Lines := TStringList.Create;
  try
    Lines.Text := EnvMemo.Text;
    for I := 0 to Lines.Count - 1 do
    begin
      Line := Trim(Lines[I]);
      if Line <> '' then
        if Line[1] <> '#' then
        begin
          Separator := Pos('=', Line);
          if Separator > 0 then
          begin
            Key := Trim(Copy(Line, 1, Separator - 1));
            if Uppercase(Key) = Uppercase(Name) then
              Result := EnvValueForValidation(
                Copy(Line, Separator + 1, Length(Line) - Separator)
              );
          end;
        end;
    end;
  finally
    Lines.Free;
  end;
end;

function ValidateEnv: Boolean;
var
  LoginValue: string;
  TerminalPath: string;
begin
  Result := False;

  TerminalPath := FindEnvValue('TERMINAL_PATH');
  if TerminalPath = '' then
  begin
    MsgBox('TERMINAL_PATH is required. Enter the full path to your broker''s terminal64.exe.', mbError, MB_OK);
    Exit;
  end;
  if not FileExists(TerminalPath) then
  begin
    MsgBox('TERMINAL_PATH must point to an existing terminal64.exe file:' + #13#10 + TerminalPath, mbError, MB_OK);
    Exit;
  end;
  if FindEnvValue('LOGIN') = '' then
  begin
    MsgBox('LOGIN is required and must have a value.', mbError, MB_OK);
    Exit;
  end;
  if FindEnvValue('PASSWORD') = '' then
  begin
    MsgBox('PASSWORD is required and must have a value.', mbError, MB_OK);
    Exit;
  end;
  if FindEnvValue('SERVER') = '' then
  begin
    MsgBox('SERVER is required and must have a value.', mbError, MB_OK);
    Exit;
  end;

  LoginValue := FindEnvValue('LOGIN');
  if not IsDigits(LoginValue) then
  begin
    MsgBox('LOGIN must contain digits only.', mbError, MB_OK);
    Exit;
  end;

  Result := True;
end;

procedure InitializeWizard;
begin
  EnvPage := CreateCustomPage(
    wpSelectDir,
    'Environment settings',
    'Enter or paste standard KEY=value lines. Set TERMINAL_PATH to the full path of the terminal64.exe installed by your broker. These values will be saved in a local .env file beside the application.'
  );
  EnvMemo := TNewMemo.Create(WizardForm);
  EnvMemo.Parent := EnvPage.Surface;
  EnvMemo.SetBounds(0, 0, EnvPage.SurfaceWidth, EnvPage.SurfaceHeight);
  EnvMemo.ScrollBars := ssVertical;
  EnvMemo.WordWrap := True;
  EnvMemo.Text :=
    'TERMINAL_PATH=' + #13#10 +
    'LOGIN=' + #13#10 +
    'PASSWORD=' + #13#10 +
    'SERVER=' + #13#10 +
    'TELEGRAM_BOT_TOKEN=' + #13#10 +
    'TELEGRAM_CHAT_ID=' + #13#10 +
    'TELEGRAM_REPORT_ON_START=false' + #13#10 +
    'QUANTNOON_SIGNAL=false';
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = EnvPage.ID then
    Result := ValidateEnv;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  EnvPath: string;
begin
  if CurStep = ssPostInstall then
  begin
    EnvPath := ExpandConstant('{app}\.env');
    if not SaveStringToFile(EnvPath, UTF8Encode(EnvMemo.Text), False) then
      RaiseException('Unable to write the .env configuration file. Check that the install folder is writable.');
  end;
end;
