; Variables needed at the command line:
; VERSION         - the version of MESH we're building (example: 3.4.5)
; VERSION_DISK    - the windows-safe version of MESH we're building
;                   This needs to be a valid filename on windows (no : , etc),
;                   but could represent a development build.
; FORKNAME        - The username of the MESH fork we're building off of.

!include nsProcess.nsh
!include LogicLib.nsh
; HM NIS Edit Wizard helper defines
!define PRODUCT_NAME "MESH"
!define PRODUCT_VERSION "${VERSION}"
!define PRODUCT_PUBLISHER "The Natural Capital Project"
!define PRODUCT_WEB_SITE "http://www.naturalcapitalproject.org"
!define MUI_COMPONENTSPAGE_NODESC
!define PACKAGE_NAME "${PRODUCT_NAME} ${PRODUCT_VERSION}"

SetCompressor zlib
!define MUI_WELCOMEFINISHPAGE_BITMAP "images\mesh_banner_vertical.bmp"
!define MUI_UNWELCOMEFINISHPAGE_BITMAP "images\mesh_banner_vertical.bmp"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP "images\mesh_banner_horizontal.bmp"
!define MUI_UNHEADERIMAGE_BITMAP "images\mesh_banner_horizontal.bmp"
!define MUI_UNICON "${NSISDIR}\Contrib\Graphics\Icons\orange-uninstall.ico"

; MUI 1.67 compatible ------
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"
!include "FileFunc.nsh"
!include "nsDialogs.nsh"
!include "genesis.nsh"

; MUI Settings
!define MUI_ABORTWARNING

; Add an advanced options control for the welcome page.
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\LICENSE.txt"
!insertmacro MUI_PAGE_COMPONENTS
Page Custom BaseDataFunction BaseDataFunctionLeave
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; MUI Uninstaller settings---------------
!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

; Language files
!insertmacro MUI_LANGUAGE "English"

; MUI end ------

Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "MESH_${FORKNAME}${VERSION_DISK}_Setup.exe"
InstallDir "C:\MESH_${VERSION_DISK}"
ShowInstDetails show

; This function allows us to test to see if a process is currently running.
; If the process name passed in is actually found, a message box is presented
; and the uninstaller should quit.
!macro CheckProgramRunning process_name
    ${nsProcess::FindProcess} "${process_name}.exe" $R0
    Pop $R0

    StrCmp $R0 603 +3
        MessageBox MB_OK|MB_ICONEXCLAMATION "MESH is still running.  Please close all MESH windows and try again."
        Abort
!macroend

!define LVM_GETITEMCOUNT 0x1004
!define LVM_GETITEMTEXT 0x102D

Function DumpLog
    Exch $5
    Push $0
    Push $1
    Push $2
    Push $3
    Push $4
    Push $6

    FindWindow $0 "#32770" "" $HWNDPARENT
    GetDlgItem $0 $0 1016
    StrCmp $0 0 exit
    FileOpen $5 $5 "w"
    StrCmp $5 "" exit
        SendMessage $0 ${LVM_GETITEMCOUNT} 0 0 $6
        System::Alloc ${NSIS_MAX_STRLEN}
        Pop $3
        StrCpy $2 0
        System::Call "*(i, i, i, i, i, i, i, i, i) i \
            (0, 0, 0, 0, 0, r3, ${NSIS_MAX_STRLEN}) .r1"
        loop: StrCmp $2 $6 done
            System::Call "User32::SendMessageA(i, i, i, i) i \
            ($0, ${LVM_GETITEMTEXT}, $2, r1)"
            System::Call "*$3(&t${NSIS_MAX_STRLEN} .r4)"
            FileWrite $5 "$4$\r$\n"
            IntOp $2 $2 + 1
            Goto loop
        done:
            FileClose $5
            System::Free $1
            System::Free $3
    exit:
        Pop $6
        Pop $4
        Pop $3
        Pop $2
        Pop $1
        Pop $0
        Exch $5
FunctionEnd

Function .onInit
 System::Call 'kernel32::CreateMutexA(i 0, i 0, t "MESH ${VERSION}") i .r1 ?e'
 Pop $R0

 StrCmp $R0 0 +3
   MessageBox MB_OK|MB_ICONEXCLAMATION "A MESH ${VERSION} installer is already running."
   Abort
FunctionEnd

Function Un.onInit
    !insertmacro CheckProgramRunning "mesh"
FunctionEnd

Section "MESH" Section_MESH_Tool
  SetShellVarContext all
  SectionIn RO ;require this section

  !define SMPATH "$SMPROGRAMS\${PACKAGE_NAME}"
  !define MESH_ICON "$INSTDIR\bin\icons\mesh_logo_64.ico"

  ; Write the uninstaller to disk
  SetOutPath "$INSTDIR"
  !define UNINSTALL_PATH "$INSTDIR\Uninstall_${VERSION_DISK}.exe"
  writeUninstaller "${UNINSTALL_PATH}"

  ; Create start  menu shortcuts.
  ; These shortcut paths are set in the appropriate places based on the SetShellVarConext flag.
  ; This flag is automatically set based on the MULTIUSER installation mode selected by the user.

  CreateDirectory "${SMPATH}"
  CreateShortCut "${SMPATH}\MESH ${VERSION}.lnk" "$INSTDIR\mesh.bat" "" "${MESH_ICON}"

  ; Write registry keys for convenient uninstallation via add/remove programs.
  ; Inspired by the example at
  ; nsis.sourceforge.net/A_simple_installer_with_start_menu_shortcut_and_uninstaller
  !define REGISTRY_PATH "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_PUBLISHER} ${PRODUCT_NAME} ${PRODUCT_VERSION}"
  WriteRegStr HKLM "${REGISTRY_PATH}" "DisplayName"          "${PRODUCT_NAME} ${PRODUCT_VERSION}"
  WriteRegStr HKLM "${REGISTRY_PATH}" "UninstallString"      "${UNINSTALL_PATH}"
  WriteRegStr HKLM "${REGISTRY_PATH}" "QuietUninstallString" "${UNINSTALL_PATH} /S"
  WriteRegStr HKLM "${REGISTRY_PATH}" "InstallLocation"      "$INSTDIR"
  WriteRegStr HKLM "${REGISTRY_PATH}" "DisplayIcon"          "${MESH_ICON}"
  WriteRegStr HKLM "${REGISTRY_PATH}" "Publisher"            "${PRODUCT_PUBLISHER}"
  WriteRegStr HKLM "${REGISTRY_PATH}" "URLInfoAbout"         "${PRODUCT_WEB_SITE}"
  WriteRegStr HKLM "${REGISTRY_PATH}" "DisplayVersion"       "${PRODUCT_VERSION}"
  WriteRegDWORD HKLM "${REGISTRY_PATH}" "NoModify" 1
  WriteRegDWORD HKLM "${REGISTRY_PATH}" "NoRepair" 1


  ; Actually install the information we want to disk.
  SetOutPath "$INSTDIR"
  File ..\LICENSE.txt
  File /r ..\dist\mesh\*

  ; Write the install log to a text file on disk.
  StrCpy $0 "$INSTDIR\install_log.txt"
  Push $0
  Call DumpLog

SectionEnd

var basedataFile
var basedataFromLocal
LangString BASE_DATA ${LANG_ENGLISH} "Base Data"
Section "-$(BASE_DATA)" BaseDataPage
AddSize "1500000"
; Parameter 2 is the location (relative to the installation directory) where the data should be unzipped.
!insertmacro DownloadIfEmpty "$basedataFile" "$INSTDIR" "http://data.naturalcapitalproject.org/mesh-releases/0.8.6/base_data_0.8.6.zip" "basedata.zip"
SectionEnd

LangString BASE_DATA_LABEL ${LANG_ENGLISH} "Select an option to download base data"
Function BaseDataFunction
    !insertmacro DataPage ${BaseDataPage} "" "$(BASE_DATA_LABEL)" $basedataFile $basedataFromLocal
FunctionEnd
Function BaseDataFunctionLeave
    !insertmacro DataPageLeave $basedataFile $basedataFromLocal
FunctionEnd

Section "uninstall"
  ; Need to enforce execution level as admin.  See
  ; nsis.sourceforge.net/Shortcuts_removal_fails_on_Windows_Vista
  SetShellVarContext all
  rmdir /r "$SMPROGRAMS\${PACKAGE_NAME}"

  ; Delete the installation directory on disk
  rmdir /r "$INSTDIR"

  ; Delete the entire registry key for this version of RIOS.
  DeleteRegKey HKLM "${REGISTRY_PATH}"
SectionEnd
