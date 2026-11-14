/* Imprimo.exe – starts runtime\pythonw.exe app\main.py (no console window). */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <wchar.h>

int WINAPI wWinMain(HINSTANCE hInst, HINSTANCE hPrev, PWSTR args, int show)
{
    static wchar_t dir[32768], py[32768], script[32768], line[32768];
    DWORD n = GetModuleFileNameW(NULL, dir, 32767);
    if (n == 0 || n >= 32767) return 1;
    wchar_t *slash = wcsrchr(dir, L'\\');
    if (slash) *slash = 0;

    _snwprintf(py, 32767, L"%ls\\runtime\\pythonw.exe", dir);
    _snwprintf(script, 32767, L"%ls\\app\\main.py", dir);
    if (GetFileAttributesW(py) == INVALID_FILE_ATTRIBUTES || GetFileAttributesW(script) == INVALID_FILE_ATTRIBUTES) {
        MessageBoxW(NULL,
            L"The \"runtime\" or \"app\" folder is missing.\n"
            L"Extract the whole ZIP into one folder and start Imprimo.exe from there "
            L"(not directly from the ZIP file).\n\n"
            L"Chýbajú priečinky „runtime“ alebo „app“.\n"
            L"Rozbaľ celý ZIP do jedného priečinka a spusti Imprimo.exe odtiaľ "
            L"(nie priamo zo ZIP súboru).",
            L"Imprimo", MB_ICONERROR | MB_OK);
        return 1;
    }
    _snwprintf(line, 32767, L"\"%ls\" -E -s \"%ls\" %ls", py, script, args ? args : L"");

    STARTUPINFOW si; PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof si); si.cb = sizeof si;
    ZeroMemory(&pi, sizeof pi);
    if (!CreateProcessW(py, line, NULL, NULL, FALSE, 0, NULL, dir, &si, &pi)) {
        wchar_t msg[512];
        _snwprintf(msg, 511, L"Could not start runtime\\pythonw.exe (error %lu).\n"
                             L"Nepodarilo sa spustiť runtime\\pythonw.exe (chyba %lu).",
                   GetLastError(), GetLastError());
        MessageBoxW(NULL, msg, L"Imprimo", MB_ICONERROR | MB_OK);
        return 1;
    }
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    return 0;
}
