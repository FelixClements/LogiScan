using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

internal static class Program
{
    [STAThread]
    static int Main()
    {
        string kit = AppDomain.CurrentDomain.BaseDirectory.TrimEnd(
            Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        Directory.SetCurrentDirectory(kit);
        string python = Path.Combine(kit, "runtime", "python", "python.exe");
        string pythonw = Path.Combine(kit, "runtime", "python", "pythonw.exe");
        string installBat = Path.Combine(kit, "scripts", "install.bat");

        if (!File.Exists(python))
        {
            RunInstall(installBat, kit);
            if (!File.Exists(python))
            {
                MessageBox.Show(
                    "This USB copy was never prepared on a trusted PC with internet.\n\n" +
                    "On a PC with internet run scripts\\prepare.ps1, then copy this folder to the stick.",
                    "LogiScan",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error);
                return 1;
            }
        }

        if (!PythonImportOk(python, kit, "tkinter"))
        {
            RunPythonModule(python, kit, "logiscan.tcltk");
            if (!PythonImportOk(python, kit, "tkinter"))
            {
                MessageBox.Show(
                    "Tcl/Tk is not in this kit (vendor\\tcltk missing).\n\n" +
                    "Re-run scripts\\prepare.ps1 on a trusted PC.",
                    "LogiScan",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error);
                return 1;
            }
        }

        if (!PythonImportOk(python, kit, "rapidocr"))
        {
            RunInstall(installBat, kit);
        }

        return StartGui(pythonw, kit);
    }

    static void RunInstall(string installBat, string kit)
    {
        if (!File.Exists(installBat))
        {
            return;
        }
        var psi = new ProcessStartInfo
        {
            FileName = installBat,
            WorkingDirectory = kit,
            UseShellExecute = true,
        };
        using (var proc = Process.Start(psi))
        {
            if (proc != null)
            {
                proc.WaitForExit();
            }
        }
    }

    static bool PythonImportOk(string python, string kit, string module)
    {
        var psi = new ProcessStartInfo
        {
            FileName = python,
            Arguments = "-c \"import " + module + "\"",
            WorkingDirectory = kit,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        psi.EnvironmentVariables["PYTHONPATH"] = kit;
        using (var proc = Process.Start(psi))
        {
            if (proc == null)
            {
                return false;
            }
            proc.WaitForExit();
            return proc.ExitCode == 0;
        }
    }

    static void RunPythonModule(string python, string kit, string module)
    {
        var psi = new ProcessStartInfo
        {
            FileName = python,
            Arguments = "-m " + module,
            WorkingDirectory = kit,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        psi.EnvironmentVariables["PYTHONPATH"] = kit;
        using (var proc = Process.Start(psi))
        {
            if (proc != null)
            {
                proc.WaitForExit();
            }
        }
    }

    static int StartGui(string pythonw, string kit)
    {
        if (!File.Exists(pythonw))
        {
            MessageBox.Show(
                "pythonw.exe is missing next to python.exe.",
                "LogiScan",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            return 1;
        }
        string tcl = Path.Combine(kit, "runtime", "python", "tcl", "tcl8.6");
        string tk = Path.Combine(kit, "runtime", "python", "tcl", "tk8.6");
        var psi = new ProcessStartInfo
        {
            FileName = pythonw,
            Arguments = "-m logiscan.gui",
            WorkingDirectory = kit,
            UseShellExecute = false,
            RedirectStandardError = true,
            CreateNoWindow = true,
        };
        psi.EnvironmentVariables["PYTHONPATH"] = kit;
        psi.EnvironmentVariables["TCL_LIBRARY"] = tcl;
        psi.EnvironmentVariables["TK_LIBRARY"] = tk;
        using (var proc = Process.Start(psi))
        {
            if (proc == null)
            {
                return 1;
            }
            if (proc.WaitForExit(2000))
            {
                string err = proc.StandardError.ReadToEnd();
                if (proc.ExitCode != 0)
                {
                    MessageBox.Show(
                        string.IsNullOrWhiteSpace(err) ? ("GUI exited " + proc.ExitCode) : err,
                        "LogiScan",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Error);
                    return proc.ExitCode;
                }
            }
        }
        return 0;
    }
}
