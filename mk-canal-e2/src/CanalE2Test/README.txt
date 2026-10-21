MK Canal+ E2 0.5.7 - VOD TEST
Pomysl i projekt: MK

Independent CANAL+ client for Octagon SF8008 / ARMv7, OpenATV / Python 3.
The user confirmed picture and sound in 0.1.2. Playback selection and native
player operation are retained. The newer account/update UI still requires
receiver-side validation; no new clean-receiver test is claimed.

Install:
  opkg update
  opkg install /tmp/MK_Canal_E2_0.5.7.ipk
Restart the Enigma2 interface and open Plugins -> MK Canal+ E2.
 - OK: choose an advertised video/audio bitrate, resolution, frame rate and codec.
 - CH+/CH- or up/down during TV: zap using the nearest matching quality.
 - Green: show a pairing code for https://connect.canalplus.com/ .
 - Yellow: refresh channels with the saved CANAL+ session.
 - Blue: check for a new version from the project's public GitHub folder.
 - INFO/EPG: show the current and following programme with CANAL+ metadata.
 - EXIT: return; during playback stop and restore the previous service.
The menu labels match the remote-control button colors. The icon is a white
plus and MK mark on a black background.
Version 0.3.3 preserves the square mark in OpenATV's 100x40 plugin-menu
slot with transparent side margins. The in-app logo is enlarged to 128x128.
The external plugin browser skin controls its own icon slot size.
Source file timestamps also invalidate stale Python bytecode after updates.

Updates are installed only after selecting Install in the update screen.
The client verifies HTTPS project URL, size, SHA256, package name, version,
architecture and plugin-only file paths before running native opkg. It then
checks the installed package status. No force-overwrite or automatic GUI
restart is used. Restart can be chosen after a successful installation.
Existing session and channel data under /etc/canal-e2 are preserved.
Version 0.3.3 accepts normal opkg user/hold flags when confirming installation.
Incomplete installs and reinstreq states are still rejected. The running old
updater from 0.3.0-0.3.2 may report installed_version_not_confirmed once during
this transition. Restart the Enigma2 interface and check the displayed version.
If it is still older, inspect opkg status before retrying.

No E2iPlayer/Kodi/ArchivCZSK application or earlier /tmp scripts are needed.
PyCryptodome and Python HTML support are declared as IPK dependencies; public player/DRM dependencies
are downloaded on first playback and checked against pinned hashes.
At least 120 MB free space is needed during initial player setup. The player
cache is under /var/lib/canal-e2; system exteplayer3 is not replaced.

Only SF8008 playback is confirmed. The current runtime targets ARMv7, not
MIPS or native 64-bit receivers. Automatic session renewal and playback
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

Version 0.4.0 adds only now/next EPG from CANAL+ globalchannels metadata.
Channel IDs are matched exactly. The receiver probe confirmed title, subTitle,
timecodes start and millisecond duration. No long synopsis was present in the
shown sample; missing descriptions are not invented. INFO/EPG opens details.
A separate process fetches metadata; /tmp/mk-canal-epg.json caches at most two
programmes per channel for up to 120 seconds or until a programme boundary.
Times use the receiver's configured timezone. Expired programmes are not shown
as currently airing. The new GUI still requires receiver-side verification.

Version 0.5.0 is a separate VOD TEST build, not yet the automatic update.
The home menu includes live television, films, series, documentaries, children,
originals, collections, sport and title search. Movie details, season selectors,
episode lists, pagination, back navigation and descriptions use CANAL+ metadata.
Public catalogue/episode data was checked against the official website.
Authenticated HAPI playset/view playback, VOD licensing, search/pagination via
Hodor, native pause and seeking still require receiver validation. Developer
host access to Hodor/HAPI returns HTTP 403; local contract tests are not a real
account playback test. See VOD_TEST.md in the public repository.

VOD controls: green pause/resume; left/right seek 30 seconds; INFO description.
The player confirms pause/resume before changing the UI state. A movie ending
returns to its catalogue. No Kodi/E2iPlayer imports, purchase calls or decrypted
media files are introduced. Only single-period DASH is supported in this test.
The visible public catalogue may include items outside the user's subscription.
VOD rights are checked at playback. External-app titles require that service.
Continue using /tmp/canal_e2_playback_report.json for sanitized error reports.

HAPI protocol reference: public GPL CanalPLUS-VOD 1.7.5.11 by mbebe, mariusz89b,
hevet. This is an independent implementation; the Kodi application is not used.

Version 0.5.1 fixes catalogue HTTP 403 on the receiver by using the exact
standard browser User-Agent that passed the user's public connectivity probe.
Films and series returned HTTP 200 with catalogue data using that header.
Catalogue failures now include the HTTP status in the UI. This does not
constitute confirmation of authenticated VOD playback or licensing.

Version 0.5.2 adds live channel switching without leaving the player. CH+ and
UP select the next listed channel; CH- and DOWN select the previous one, with
wraparound. Repeated presses coalesce to the latest selection. The old worker
fully exits before a new player is started; EXIT cancels a pending switch.
The original Enigma service is restored only when leaving this player screen.

The VOD adapter now also uses the standard browser User-Agent. The receiver's
0.5.1 VOD attempt was refused with HTTP 403 at playset; resolution in this new
build still needs receiver testing. Playset HTTP failures automatically add
vod_http_diagnostic to /tmp/canal_e2_playback_report.json. Only allowlisted
field names, numeric service codes and message hint tags are saved. No raw
message, account token, media URL or licence response is included. No separate
probe file is needed for reporting a normal VOD attempt.

Version 0.5.4 corrects VOD signed manifest URLs: append the packager suffix to
the path, preserving the original query bytes and duplicate parameters.
Provider DASH URLs retain their order and take priority over derived URLs.
VOD uses one browser User-Agent for HAPI, manifest, track initialization,
manifest refresh and native playback. CDN requests carry no account headers.
Default live TV HTTP and native User-Agent values are retained.

The user confirmed live TV after a full reboot. Their 0.5.2 VOD request now
reaches the manifest stage but returns HTTP 503. The report adds candidate
type, query presence, status, content type/size and parse result without
saving URLs, query tokens or response bodies. Receiver verification of the
new VOD request is still required; the cause of that 503 is not yet confirmed.

Version 0.5.4 (VOD TEST): includes Widevine-labelled playback offers instead of
filtering them out, prefers DASH, and recognises DASH URLs by the service MIME
type even without an .mpd suffix. Reports fixed format labels and counts only.
After a DASH failure, checks the original Smooth manifest once. Smooth is
not implemented by the current isolated player; a confirmed Smooth response
shows an explicit unsupported-format message. Receiver VOD remains unverified.

Version 0.5.5 (VOD TEST): preserves the service licence URL query exactly;
does not collapse repeated fields, re-encode signatures or overwrite a supplied
drmType. Reports bounded JSON HTTP failure codes and fixed hint labels only.
Successful licence bodies never go to the error inspector. The receiver's
0.5.4 test loaded DASH and encrypted video/audio init; licence returned HTTP
403. VOD playback is still not confirmed. No DRM refusal is bypassed.

Version 0.5.6 (VOD TEST): select individual manifest video/audio combinations
before playback, including same-height bitrates, frame rates and AAC/Dolby.
Keep both selected tracks in manifest refreshes. Reuse quality properties on zap.
VOD view preserves the complete offered descriptor and requests embedded media;
each manifest is paired with its media-specific licence when provided.
The previous receiver test still returned licence HTTP 403; this revision needs
receiver validation and does not claim working movie playback.

Version 0.5.7 (VOD TEST): fixes OpenATV TypeError after confirming quality.
The Enigma console binding receives text and length rather than bytes. This
also fixes pause, resume and seek command delivery. The UI test double now
rejects bytes like the observed receiver binding, so this regression is covered.
Playback after this fix still needs receiver confirmation.
