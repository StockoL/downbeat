# Reaching the laptop from the iPad

School Wi-Fi keeps devices apart, and iOS only installs an offline web app from a site with a
real HTTPS certificate. Tailscale solves both: it joins the laptop and the iPad into a private
network that works across any Wi-Fi, and gives the laptop a name with a real certificate.
Downbeat itself only listens on the laptop (127.0.0.1); Tailscale is the single way in.

## Once

1. **Install Tailscale** on the laptop (tailscale.com/download, Windows) and on the iPad
   (App Store). Sign in to both with the same personal account.
2. **Keep it personal.** Use your own account, not a school one: pupil names never pass
   through anyone else's network.
3. **In the Tailscale admin console** (login.tailscale.com/admin/dns): turn on **MagicDNS**,
   then **HTTPS Certificates**.
4. **On the laptop**, in the `downbeat` folder:

   ```powershell
   .\tools\tailscale-check.ps1
   tailscale serve --bg 8000
   .\tools\install-server-task.ps1
   Start-ScheduledTask -TaskName "Downbeat server"
   ```

   The check prints the laptop's name, like `teacher-laptop.tail1234.ts.net`, and saves it for
   Downbeat. `tailscale serve` puts HTTPS in front of Downbeat; `--bg` keeps it on across restarts.
   The server task starts Downbeat whenever you sign in to Windows.
5. **On the iPad**, open `https://teacher-laptop.tail1234.ts.net` in Safari, sign in, then
   Share → **Add to Home Screen**. Open it from the Home Screen from then on.

## Checking it

`.\tools\tailscale-check.ps1` again at any time. On the iPad, the Tailscale app should show the
laptop as connected.

## Undoing it

`tailscale serve --bg off`, `Unregister-ScheduledTask -TaskName "Downbeat server"`, and delete
`local\hosts.txt`. Downbeat goes back to answering the laptop only.
