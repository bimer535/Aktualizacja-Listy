MK Canal+ E2 0.3.0
Pomysl i projekt: MK

Independent CANAL+ client for Octagon SF8008 / ARMv7, OpenATV / Python 3.
The user confirmed picture and sound in 0.1.2. Playback selection and native
player operation are retained. The newer account/update UI still requires
receiver-side validation; no new clean-receiver test is claimed.

Install:
  opkg update
  opkg install /tmp/MK_Canal_E2_0.3.0.ipk
Restart the Enigma2 interface and open Plugins -> MK Canal+ E2.
 - OK: play the selected channel, using the highest granted quality up to 1080p.
 - Green: show a pairing code for https://connect.canalplus.com/ .
 - Yellow: refresh channels with the saved CANAL+ session.
 - Blue: check for a new version from the project's public GitHub folder.
 - EXIT: return; during playback stop and restore the previous service.
The menu labels match the remote-control button colors. The icon is a white
plus and MK mark on a black background.

Updates are installed only after selecting Install in the update screen.
The client verifies HTTPS project URL, size, SHA256, package name, version,
architecture and plugin-only file paths before running native opkg. It then
checks the installed package status. No force-overwrite or automatic GUI
restart is used. Restart can be chosen after a successful installation.
Existing session and channel data under /etc/canal-e2 are preserved.

No E2iPlayer/Kodi/ArchivCZSK application or earlier /tmp scripts are needed.
PyCryptodome is declared as an IPK dependency; public player/DRM dependencies
are downloaded on first playback and checked against pinned hashes.
At least 120 MB free space is needed during initial player setup. The player
cache is under /var/lib/canal-e2; system exteplayer3 is not replaced.

Only SF8008 playback is confirmed. The current runtime targets ARMv7, not
MIPS or native 64-bit receivers. EPG, automatic session renewal and playback
through key rotation are not implemented. Re-pair with the green button if
manual session renewal is needed. 1080p is not guaranteed by this client.

On playback failure, share only /tmp/canal_e2_playback_report.json.
Never upload /etc/canal-e2/session.json or live.json.

Media stays encrypted until normal in-memory decoding by the player.
No decrypted stream, key file or native FFmpeg/player log is written.
The license key dictionary is passed to the child process in its arguments;
the local root account can inspect process arguments. It is never printed
to the Enigma2 console. A localhost-only temporary endpoint supplies the
filtered encrypted DASH manifest and closes when playback ends.

Remove UI prototype:
  opkg remove enigma2-plugin-extensions-canale2test
The existing CANAL+ session and isolated runtime cache are retained.

Public dependencies (downloaded at runtime, not included in this package):
 - tools_cenc public source, GPL-2.0:
   https://github.com/archivczsk/archivczsk-doplnky
   commit 0adcaead1cc7b3688ee72627f6810a2453794fd7
   Files and SHA256 values are pinned by canal_drm_demo.py.
 - exteplayer3, GPL-2.0, public ARMv7 package 183:
   https://github.com/skyjet18/exteplayer3
   commit 00aaa894db78a5c71c325d7cab1ea9ba5855024d
   ipk/exteplayer3_183_armv7ahf.ipk
   SHA256 c920ddc6fe6f8d1a77916ef9f842f4072483e8fec189a059563c784dc7ee22ce
   The package includes patched FFmpeg libraries; corresponding public project:
   https://github.com/skyjet18/FFmpeg
   Local RPATH strings are changed to $ORIGIN/../lib for isolation.

All Python source for this prototype is included. License: GPL-2.0, see LICENSE.

Version 0.1.2 lists video heights covered by the already granted license. If
the requested video key is absent, it tries the highest covered rendition
up to the requested height and verifies that rendition's initialization.
The UI and report display the actual selected height. The filtered MPD is
pinned to this rendition, including when multiple codecs share one height.
No new DRM identity or device profile is introduced for this quality choice.
