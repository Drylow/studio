// First-party Windows companion. The website hands one short-lived connection
// to this PC through an explicitly registered protocol, never a shared queue.
// No uploads, cookies export, arbitrary commands or browser security overrides.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Net.WebSockets;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;

namespace EdgerunnersStudio
{
    public sealed class ConnectionLink
    {
        public string RequestId;
        public string Token;
        public static ConnectionLink Parse(string value)
        {
            Match match = Regex.Match(value ?? "", "^edgerunners-studio://connect/(pc-local-[a-f0-9]{32})\\?token=([a-f0-9]{64})$");
            if (!match.Success) throw new ClientFailure("invalid_request");
            return new ConnectionLink { RequestId = match.Groups[1].Value, Token = match.Groups[2].Value };
        }
    }

    public sealed class ClientFailure : Exception
    {
        public readonly string Code;
        public ClientFailure(string code) { Code = code; }
    }

    public static class Identity
    {
        public static string StudioChannel(string value)
        {
            Uri url;
            if (!Uri.TryCreate(value, UriKind.Absolute, out url) || url.Scheme != "https" ||
                url.Host != "studio.youtube.com" || !String.IsNullOrEmpty(url.UserInfo) || !url.IsDefaultPort) return "";
            Match match = Regex.Match(url.AbsolutePath, "^/channel/(UC[A-Za-z0-9_-]{22})(?:/[^?#]*)?$");
            return match.Success ? match.Groups[1].Value : "";
        }
        public static bool NavigationMatches(string expected, object[] links)
        {
            int count = 0;
            foreach (object link in links)
            {
                string channel = StudioChannel(Convert.ToString(link));
                if (channel == "") continue;
                if (channel != expected) return false;
                count++;
            }
            return count >= 2;
        }
        public static bool DebuggerAddress(string value, int port, string kind)
        {
            Uri url;
            return Uri.TryCreate(value, UriKind.Absolute, out url) && url.Scheme == "ws" &&
                url.Host == "127.0.0.1" && url.Port == port && url.UserInfo == "" &&
                Regex.IsMatch(url.AbsolutePath, "^/devtools/" + kind + "/[A-Za-z0-9_-]+$");
        }
    }

    public sealed class Companion : Form
    {
        const string Studio = "https://edgerunners.fr";
        readonly JavaScriptSerializer json = new JavaScriptSerializer { MaxJsonLength = 65536 };
        readonly HttpClient server = new HttpClient(new HttpClientHandler { AllowAutoRedirect = false }) { Timeout = TimeSpan.FromSeconds(15) };
        readonly HttpClient local = new HttpClient(new HttpClientHandler { UseProxy = false, AllowAutoRedirect = false }) { Timeout = TimeSpan.FromSeconds(5) };
        readonly Label label = new Label();
        readonly ConnectionLink link;
        string expected = "";
        string device = "";
        string channelTitle = "";
        Process chrome;
        Mutex channelLock;
        bool ownsLock;
        bool finished;
        bool stopping;
        bool browserVisible;
        int port;
        double deadline;

        [DllImport("user32.dll")] static extern bool EnumWindows(WindowCallback callback, IntPtr parameter);
        delegate bool WindowCallback(IntPtr window, IntPtr parameter);
        [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr window);
        [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr window, out uint processId);
        [DllImport("user32.dll")] static extern bool ShowWindowAsync(IntPtr window, int command);
        [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr window);

        public Companion(ConnectionLink value)
        {
            link = value;
            Text = "Edgerunners Studio · Connexion YouTube";
            ClientSize = new Size(440, 150);
            StartPosition = FormStartPosition.CenterScreen;
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            BackColor = Color.FromArgb(16, 24, 33);
            label.ForeColor = Color.White;
            label.Font = new Font("Segoe UI", 11);
            label.Dock = DockStyle.Fill;
            label.Padding = new Padding(20);
            label.Text = "L’assistant est ouvert sur ce PC.\r\nPréparation de la connexion…";
            Controls.Add(label);
            Shown += async delegate { await Run(); };
            FormClosing += delegate(object sender, FormClosingEventArgs args) {
                if (!finished) {
                    args.Cancel = true;
                    stopping = true;
                    label.Text = "Arrêt de la connexion…";
                }
            };
        }

        public static double Timestamp()
        {
            return (DateTime.UtcNow - new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc)).TotalSeconds;
        }

        static string StringField(Dictionary<string, object> data, string key)
        {
            object value;
            return data.TryGetValue(key, out value) && value is string ? (string)value : "";
        }

        static object[] ArrayValue(object value)
        {
            object[] array = value as object[];
            if (array != null) return array;
            ArrayList list = value as ArrayList;
            return list == null ? null : list.ToArray();
        }

        void CheckStopped()
        {
            if (stopping) throw new ClientFailure("cancelled");
        }

        async Task<Dictionary<string, object>> Call(string action, Dictionary<string, object> body)
        {
            string path = Studio + "/api/studio/pc-local/" + link.RequestId + "/" + action;
            HttpRequestMessage request = new HttpRequestMessage(body == null ? HttpMethod.Get : HttpMethod.Post, path);
            request.Headers.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", link.Token);
            if (body != null) request.Content = new StringContent(json.Serialize(body), Encoding.UTF8, "application/json");
            using (HttpResponseMessage response = await server.SendAsync(request))
            {
                if (!response.IsSuccessStatusCode) throw new ClientFailure("expired_request");
                string raw = await response.Content.ReadAsStringAsync();
                if (raw.Length > 16384) throw new ClientFailure("invalid_request");
                return json.Deserialize<Dictionary<string, object>>(raw);
            }
        }

        async Task Progress(string status, string code, bool navigation)
        {
            await Call("progress", new Dictionary<string, object> {
                {"status", status}, {"code", code}, {"device_id", device},
                {"expected_channel_id", expected}, {"channel_id", navigation ? expected : ""},
                {"browser_visible", browserVisible}, {"navigation_verified", navigation}
            });
        }

        static string ChromeExecutable()
        {
            foreach (string name in new string[] { "PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA" })
            {
                string folder = Environment.GetEnvironmentVariable(name);
                if (String.IsNullOrEmpty(folder)) continue;
                string path = Path.Combine(folder, "Google", "Chrome", "Application", "chrome.exe");
                if (File.Exists(path)) return path;
            }
            throw new ClientFailure("chrome_missing");
        }

        static string OwnFolder(string path)
        {
            if (Directory.Exists(path) && (File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0)
                throw new ClientFailure("unsafe_profile");
            Directory.CreateDirectory(path);
            return path;
        }

        IntPtr OwnChromeWindow()
        {
            IntPtr found = IntPtr.Zero;
            if (chrome == null || chrome.HasExited) return found;
            EnumWindows(delegate(IntPtr window, IntPtr ignored) {
                uint pid;
                GetWindowThreadProcessId(window, out pid);
                if (pid == (uint)chrome.Id && IsWindowVisible(window)) { found = window; return false; }
                return true;
            }, IntPtr.Zero);
            return found;
        }

        async Task<object> Evaluate(string address, string expression)
        {
            if (!Identity.DebuggerAddress(address, port, "page")) throw new ClientFailure("browser_failed");
            using (ClientWebSocket socket = new ClientWebSocket())
            using (CancellationTokenSource limit = new CancellationTokenSource(TimeSpan.FromSeconds(8)))
            {
                await socket.ConnectAsync(new Uri(address), limit.Token);
                byte[] command = Encoding.UTF8.GetBytes(json.Serialize(new Dictionary<string, object> {
                    {"id", 1}, {"method", "Runtime.evaluate"}, {"params", new Dictionary<string, object> {
                        {"expression", expression}, {"returnByValue", true}
                    }}
                }));
                await socket.SendAsync(new ArraySegment<byte>(command), WebSocketMessageType.Text, true, limit.Token);
                for (int i = 0; i < 30; i++)
                {
                    byte[] buffer = new byte[4096];
                    using (MemoryStream output = new MemoryStream())
                    {
                        WebSocketReceiveResult received;
                        do {
                            received = await socket.ReceiveAsync(new ArraySegment<byte>(buffer), limit.Token);
                            if (received.MessageType == WebSocketMessageType.Close) return null;
                            output.Write(buffer, 0, received.Count);
                            if (output.Length > 65536) throw new ClientFailure("browser_failed");
                        } while (!received.EndOfMessage);
                        Dictionary<string, object> response = json.Deserialize<Dictionary<string, object>>(Encoding.UTF8.GetString(output.ToArray()));
                        object id;
                        if (!response.TryGetValue("id", out id) || Convert.ToInt32(id) != 1) continue;
                        object result;
                        if (!response.TryGetValue("result", out result)) return null;
                        Dictionary<string, object> outer = result as Dictionary<string, object>;
                        if (outer == null || !outer.TryGetValue("result", out result)) return null;
                        Dictionary<string, object> inner = result as Dictionary<string, object>;
                        return inner != null && inner.TryGetValue("value", out result) ? result : null;
                    }
                }
                return null;
            }
        }

        async Task Run()
        {
            string failure = "";
            try
            {
                if (!Environment.UserInteractive || Process.GetCurrentProcess().SessionId == 0)
                    throw new ClientFailure("desktop_not_interactive");
                Dictionary<string, object> manifest = await Call("manifest", null);
                CheckStopped();
                expected = StringField(manifest, "channel_id");
                channelTitle = StringField(manifest, "channel_title");
                if (!Regex.IsMatch(expected, "^UC[A-Za-z0-9_-]{22}$")) throw new ClientFailure("invalid_request");
                deadline = Convert.ToDouble(manifest["deadline"]);
                if (deadline <= Timestamp() || deadline > Timestamp() + 1205) throw new ClientFailure("expired_request");
                channelLock = new Mutex(false, "Local\\EdgerunnersStudio.Channel." + expected);
                try { ownsLock = channelLock.WaitOne(0); } catch (AbandonedMutexException) { ownsLock = true; }
                if (!ownsLock) throw new ClientFailure("browser_busy");
                string root = OwnFolder(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "EdgerunnersStudio"));
                string state = OwnFolder(Path.Combine(root, "state"));
                string devicePath = Path.Combine(state, "device-id");
                if (File.Exists(devicePath) && (File.GetAttributes(devicePath) & FileAttributes.ReparsePoint) != 0)
                    throw new ClientFailure("unsafe_profile");
                if (!File.Exists(devicePath)) File.WriteAllText(devicePath, Guid.NewGuid().ToString("N"), Encoding.ASCII);
                device = File.ReadAllText(devicePath, Encoding.ASCII).Trim();
                if (!Regex.IsMatch(device, "^[a-f0-9]{32}$")) throw new ClientFailure("unsafe_profile");
                await Progress("waiting", "preparing_browser", false);
                label.Text = "Connexion de " + channelTitle + "\r\nOuverture d’une fenêtre Chrome dédiée…";
                string profiles = OwnFolder(Path.Combine(state, "profiles"));
                string profile = OwnFolder(Path.Combine(profiles, expected));
                string active = Path.Combine(profile, "DevToolsActivePort");
                if (File.Exists(active))
                {
                    int existing;
                    string[] lines = File.ReadAllLines(active);
                    if (lines.Length > 0 && Int32.TryParse(lines[0], out existing) && existing >= 1024 && existing <= 65535)
                    {
                        try { await local.GetStringAsync("http://127.0.0.1:" + existing + "/json/version"); throw new ClientFailure("browser_busy"); }
                        catch (ClientFailure) { throw; } catch { }
                    }
                    File.Delete(active);
                }
                ProcessStartInfo start = new ProcessStartInfo(ChromeExecutable(),
                    "--new-window --user-data-dir=\"" + profile + "\" --remote-debugging-address=127.0.0.1 --remote-debugging-port=0 --no-first-run --no-default-browser-check https://studio.youtube.com/");
                start.UseShellExecute = false;
                start.CreateNoWindow = false;
                start.WindowStyle = ProcessWindowStyle.Normal;
                chrome = Process.Start(start);
                double opening = Math.Min(deadline, Timestamp() + 30);
                while (Timestamp() < opening && !chrome.HasExited)
                {
                    CheckStopped();
                    IntPtr window = OwnChromeWindow();
                    if (window != IntPtr.Zero && File.Exists(active))
                    {
                        string[] lines = File.ReadAllLines(active);
                        if (lines.Length > 0 && Int32.TryParse(lines[0], out port) && port >= 1024 && port <= 65535)
                        {
                            ShowWindowAsync(window, 9);
                            SetForegroundWindow(window);
                            browserVisible = true;
                            break;
                        }
                    }
                    await Task.Delay(500);
                }
                if (!browserVisible) throw new ClientFailure("browser_not_visible");
                await Progress("waiting", "sign_in", false);
                label.Text = "Chrome est ouvert sur ce PC.\r\nConnecte-toi à YouTube puis choisis " + channelTitle + ".\r\nAucune vidéo ne sera envoyée.";
                WindowState = FormWindowState.Minimized;
                double until = Math.Min(deadline, Timestamp() + 600);
                bool otherChannel = false;
                while (Timestamp() < until)
                {
                    CheckStopped();
                    if (chrome.HasExited) throw new ClientFailure("browser_closed");
                    object[] targets = ArrayValue(json.DeserializeObject(await local.GetStringAsync("http://127.0.0.1:" + port + "/json/list")));
                    if (targets != null) foreach (object item in targets)
                    {
                        Dictionary<string, object> target = item as Dictionary<string, object>;
                        if (target == null || StringField(target, "type") != "page") continue;
                        string actual = Identity.StudioChannel(StringField(target, "url"));
                        if (actual == "") continue;
                        if (actual != expected) { otherChannel = true; continue; }
                        string expression = "(() => {const app=document.querySelector('ytcp-app'); return app && app.getClientRects().length ? [...document.querySelectorAll('ytcp-navigation-drawer a[href]')].map(a=>a.href) : []})()";
                        object[] navigation = ArrayValue(await Evaluate(StringField(target, "webSocketDebuggerUrl"), expression));
                        if (navigation != null && Identity.NavigationMatches(expected, navigation))
                        {
                            await Progress("ready", "dashboard_confirmed", true);
                            label.Text = "Connexion confirmée : " + channelTitle + ".\r\nRetourne dans Edgerunners Studio.\r\nAucune vidéo n’a été publiée.";
                            return;
                        }
                    }
                    await Task.Delay(2000);
                }
                throw new ClientFailure(otherChannel ? "wrong_channel" : "sign_in_timeout");
            }
            catch (Exception error)
            {
                ClientFailure known = error as ClientFailure;
                string code = known == null ? "browser_failed" : known.Code;
                failure = code;
                label.Text = Message(code);
            }
            finally
            {
                if (chrome != null && !chrome.HasExited) try {
                    // Let this dedicated profile flush its own session to disk.
                    chrome.CloseMainWindow();
                    if (!chrome.WaitForExit(3000)) chrome.Kill();
                } catch { }
                if (ownsLock) channelLock.ReleaseMutex();
                if (channelLock != null) channelLock.Dispose();
                finished = true;
                WindowState = FormWindowState.Normal;
                Activate();
            }
            if (failure != "" && device != "" && ownsLock)
                try { await Progress("failed", failure, false); } catch { }
            if (stopping) Close();
        }

        static string Message(string code)
        {
            if (code == "chrome_missing") return "Google Chrome n’est pas installé.\r\nInstalle Chrome puis relance depuis le studio.";
            if (code == "browser_busy") return "Cette chaîne est déjà ouverte par l’assistant.\r\nFerme cette fenêtre dédiée puis relance depuis le studio.";
            if (code == "wrong_channel") return "La chaîne ouverte est différente.\r\nRelance puis choisis la bonne chaîne via ta photo → Changer de compte.";
            if (code == "sign_in_timeout") return "La connexion n’a pas été terminée.\r\nRelance depuis le studio et connecte-toi dans la nouvelle fenêtre Chrome.";
            if (code == "expired_request" || code == "invalid_request") return "Ce lien de connexion a expiré ou est invalide.\r\nRetourne sur edgerunners.fr et relance la connexion.";
            if (code == "desktop_not_interactive" || code == "browser_not_visible") return "Chrome n’a pas pu s’afficher sur ce bureau Windows.\r\nOuvre ta session Windows puis relance depuis le studio.";
            return "La connexion a été interrompue.\r\nRetourne dans le studio pour voir le résultat et relancer.";
        }

        [STAThread]
        public static void Main(string[] args)
        {
            ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12;
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            try {
                if (args.Length != 1) throw new ClientFailure("invalid_request");
                Application.Run(new Companion(ConnectionLink.Parse(args[0])));
            } catch { MessageBox.Show("Ouvre edgerunners.fr → Chaînes → Connecter avec mon PC.", "Edgerunners Studio", MessageBoxButtons.OK, MessageBoxIcon.Information); }
        }
    }
}
