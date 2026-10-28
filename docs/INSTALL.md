# Installing the app

Downbeat runs on your laptop. You open it in a browser, and you can install it so it behaves like an ordinary app: its own icon, its own window, straight to Today when you open it. On the iPad, installing it is also what lets it work with the Wi-Fi off.

| Device | Browser | Address | Needs Tailscale |
| --- | --- | --- | --- |
| The Windows laptop | Microsoft Edge (or Chrome) | `http://127.0.0.1:8000` | No |
| The iPad | Safari | `https://<your-laptop>.<tailnet>.ts.net` | Yes |

## Before you start

1. **Downbeat is installed and serving** on the laptop: `.\tools\serve.ps1` is running, or the server task starts it when you sign in to Windows (`.\tools\install-server-task.ps1`, once). See [OPERATIONS.md](OPERATIONS.md).
2. **You have an account.** The first visit opens the first-run setup, which creates it.

## On the Windows laptop

1. Open **Microsoft Edge** and go to `http://127.0.0.1:8000`. Sign in.
2. Install it. Either:
   - click the **App available** icon at the right-hand end of the address bar, then **Install**; or
   - open the **⋯** menu → **Apps** → **Install this site as an app**, then **Install**.
3. Edge asks where to put it. Tick **Pin to taskbar** (and **Pin to Start** or **Create desktop shortcut** if you like), then **Allow**.

Downbeat now opens in its own window from the taskbar. In **Chrome** it is the same idea: the install icon in the address bar, or **⋮** → **Cast, save and share** → **Install page as app**.

Use the address exactly as written, `http://127.0.0.1:8000`. Browsers only install from a secure address, and the laptop's own address counts as secure; the laptop's address on the school network doesn't.

**To remove it:** open it, then **⋯** → **App settings** → **Uninstall**. Or go to `edge://apps` in Edge. Nothing is deleted from Downbeat: the app is only a window onto it.

## On the iPad

The iPad reaches the laptop through Tailscale, which gives the laptop an address with a real HTTPS certificate. iOS will only install an app that works offline from an address like that. Do steps 1 to 4 of [TAILSCALE.md](TAILSCALE.md) first: they take about ten minutes, once. They give you the laptop's address, something like `https://teacher-laptop.tail1234.ts.net`.

1. Check the **Tailscale** app on the iPad shows the laptop as connected, and the laptop is awake with Downbeat running.
2. Open **Safari** and go to the laptop's `ts.net` address. Use Safari: it is the browser that installs apps on an iPad.
3. **Add it to the Home Screen.** Tap the **Share** button (the square with an arrow pointing up, at the top right on an iPad), scroll down, tap **Add to Home Screen**, keep the name **Downbeat**, and tap **Add**.
4. **Open it from the Home Screen** and sign in. An app on the Home Screen keeps its own sign-in, separate from Safari's, so it asks once more. It then stays signed in for 120 days.
5. **Open today's lessons once** while the laptop is in reach. Each page you open is saved on the iPad, so those lessons then work with the Wi-Fi off.

From now on, always open Downbeat from its Home Screen icon, not from Safari: the icon is the installed app, with the offline copy and its own queue of captures.

**To check it works offline:** follow [TESTING.md](TESTING.md#on-the-real-ipad). In short: turn the Wi-Fi off, record a few things in a lesson, see "saved on this device" on the bar, turn the Wi-Fi on, and see them reach the laptop.

**Updates** arrive by themselves: the next time the app opens with the laptop in reach, it fetches the new version.

**To remove it:** press and hold the icon → **Remove App** (or **Delete Bookmark**) → **Delete**. Captures not yet sent to the laptop are lost with it, so open it once with the laptop in reach first, until the bar shows nothing waiting.

## If something doesn't work

| What you see | What to do |
| --- | --- |
| No install icon or menu item on the laptop | Use `http://127.0.0.1:8000`, not another address, and not a private (InPrivate) window. Reload the page once after signing in. |
| The laptop app says it can't connect | Downbeat isn't running: start `.\tools\serve.ps1`, or sign out of Windows and back in if the server task is installed. |
| No **Add to Home Screen** in the iPad's Share sheet | Scroll further down the sheet. If it still isn't there, tap **Edit Actions** and add it. Make sure you are in Safari. |
| The iPad shows a certificate warning | You are on the wrong address. Use the `https://…ts.net` address that `.\tools\tailscale-check.ps1` prints, not `127.0.0.1` or a number. |
| The iPad says "Not reachable" | Open the Tailscale app and check the laptop is connected; check the laptop is awake and Downbeat is running. Pages opened earlier while connected still work. |
| The iPad asks to sign in again | Expected the first time you open the installed app (step 4). After that, only if you sign out or 120 days pass. |
| The bar says "Sign in to send 3" | Your sign-in has ended. Sign in again; the waiting captures are sent then, not lost. |
