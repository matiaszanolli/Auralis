# Auralis User Guide

Auralis is a desktop music player for your own music files. It plays your library and can apply
automatic mastering to the sound as you listen. Everything runs on your computer: your files are
never uploaded anywhere.

To get Auralis, see the downloads section of the [project README](../../README.md).

## Contents

1. [First launch](#first-launch)
2. [Adding music](#adding-music)
3. [Browsing your library](#browsing-your-library)
4. [Playing music and the queue](#playing-music-and-the-queue)
5. [Auto-Mastering](#auto-mastering)
6. [Playlists, favourites and editing tracks](#playlists-favourites-and-editing-tracks)
7. [Settings](#settings)
8. [Keyboard shortcuts](#keyboard-shortcuts)
9. [Where your data lives](#where-your-data-lives)
10. [Troubleshooting](#troubleshooting)

---

## First launch

Auralis opens with an empty library and a drop area that reads **Drag & Drop Music Folder**. The
window has four parts:

- **Sidebar** (left): the Library views, your playlists, and **Settings**. The arrow at the top
  collapses it.
- **Top bar**: a search box, a grid/list switch on the Songs and Favourites views, and a small
  status dot that shows whether Auralis is connected to its audio engine.
- **Main area**: the current view. On Songs, Favourites and Albums, a panel on the right shows the
  **Auto-Mastering** switch and a picture of the music's character.
- **Player bar** (bottom): what is playing, the progress bar, the transport controls, volume and
  the queue button.

Auralis starts in the dark theme. You can switch to the light theme in **Settings → Interface**,
or with the theme button at the bottom of the sidebar.

On installed builds Auralis checks for updates a few seconds after it starts. If one is found it
asks whether to download it; choose **Later** to keep using the current version.

## Adding music

Auralis reads music from folders on your disk. It finds files in these formats: WAV, FLAC, AIFF,
AU, MP3, M4A, AAC, OGG, WMA and Opus.

**From the empty library.** Click the drop area, or drop a folder on it. Either way Auralis opens
the folder picker so you can choose your music folder, then scans it. A message reports how
many tracks were added, and how many files failed or were skipped.

**From Settings.** Open **Settings → Library**:

1. Under **Scan Folders**, click **Add Folder** and pick a folder.
2. The folder is added to the list and Auralis scans it.
3. Click **Scan Now** at any time to rescan every folder in the list.

To stop watching a folder, click the delete icon next to it and confirm **Remove**. The files stay
on your disk; the folder's tracks leave your library.

**Automatic rescans.** In **Settings → Library**, switch on **Auto-scan library** and choose a
**Scan Interval** (every minute up to every 24 hours). Auralis then picks up new files in your scan
folders on its own.

**Audio analysis.** After tracks are added, Auralis analyses each one in the background. Progress
is shown as **Audio analysis** in **Settings → Library**. Analysis powers the track-character
panel, **Find Similar Tracks**, and the mastering itself. If some tracks are still waiting, click
**Analyse remaining**.

## Browsing your library

The sidebar's **Library** section has four views:

| View | What it shows |
|------|---------------|
| **Songs** | Every track in your library |
| **Albums** | A grid of albums. Sort by **A-Z**, **Year** or **Era**. A **Recently Touched** row lists albums you opened lately. Open an album to see its tracks. |
| **Artists** | Your artists. Open one to see **Albums** and **All Tracks** tabs. |
| **Favourites** | Tracks you have marked as favourites |

Under **Playlists** in the sidebar are your playlists; click one to open it.

**Grid or list.** On Songs and Favourites, the switch in the top bar changes between a grid of
cards and a list.

**Search.** Type in the top-bar box (**Search tracks, albums, artists...**). Results narrow as you
type, and the search applies to the view you are on. Clear it with the **x** in the box or
**Escape**. Press **/** to jump to the box.

**Right-click or "More options".** Every track has a menu, opened by right-clicking it or by its
**More options** button. On Songs it offers **Play Now**, **Add to Queue**, **Add to Playlist**,
**Find Similar Tracks** and **Edit Metadata**. Some views add **Add to Favourites** / **Remove from
Favourites**, **Go to Album**, **Go to Artist** and **Track Info**.

**Find Similar Tracks** opens a window listing tracks in your library that sound like the one you
chose; click a result to play it.

**Selecting several tracks.** Tick the box that appears at the left of a track, or press
**Ctrl+A** (**Cmd+A** on macOS) to select the whole list. A bar appears with **Add to Playlist**,
**Add to Queue** and **Toggle Favorite**. On the Favourites view it also offers **Remove from
Favorites**. **Escape** or the **x** clears the selection.

## Playing music and the queue

**Play a track.** Click it. Click the playing track again, or use the play button on its row, to
pause.

**The player bar.**

- **Progress bar**: click or drag to seek. When it has focus, the arrow keys move one second and
  **Home** / **End** jump to the start or end. A thin indicator shows when audio is still buffering
  or seeking.
- **Previous track**, **Play** / **Pause**, **Next track**.
- **Volume**: a slider and a mute button.
- **Toggle queue** (the note icon at the right): opens and closes the queue.

**The queue** lists what will play next. In it you can:

- turn **Shuffle** on or off, and set **Repeat** to off, all tracks or one track;
- drag a track to reorder it, or press **Alt+Up** / **Alt+Down** on a focused track;
- remove a track with its **Remove from queue** button, or **Delete** / **Backspace** on a focused
  track;
- clear everything with **Clear queue** (you are asked to confirm: **Clear the entire queue?**).

**Add to the queue** from a track's menu (**Add to Queue**) or the selection bar. When a track
ends, the next one in the queue starts.

If Auralis restarts its audio engine while something is playing, it shows a notice that your queue
and playback position were reset.

## Auto-Mastering

Auto-Mastering applies mastering to the music as it plays. It adapts to each track, based on the
analysis of the track itself. Your files are not changed.

**Turn it on or off** with the **Auto-Mastering** switch at the top of the right-hand panel
(Songs, Favourites and Albums views). Under the switch, the text says **Enhancing playback** when it
is on and **Original audio** when it is off. If turning it on or off fails, a message says so and
the switch returns to its previous state.

Changing the switch while a track is playing restarts that track's audio from the current position
with or without mastering, so the change is heard right away. The setting also applies to the next
tracks you play.

**The character panel.** Below the switch, the panel draws the playing track's sonic character
from its analysis: a waveform, a glowing arc, mood tags, a **calm to aggressive** energy field and
short descriptions. It is titled **Track Character** while a track is playing; in the Albums view,
hovering over an album shows that album's combined **Album Character**. While analysis is still
running you will see **Analyzing track character...**, and **Fingerprint not available for this
track** if analysis could not produce a result. The panel is a picture of the music, not a control:
it has no sliders.

**Defaults.** **Settings → Enhancement** holds the stored defaults:

- **Default Preset**: **Adaptive** is the only preset.
- **Auto-enhance playback**: apply enhancement to all tracks.
- **Enhancement Intensity**: how strongly it is applied, from 0 to 100 %.

## Playlists, favourites and editing tracks

**Create a playlist.** In the sidebar's **Playlists** section, use the **Create playlist** button.
Give it a **Playlist Name** and an optional **Description**. Add tracks from a track's menu
(**Add to Playlist**, then pick a playlist or create a new one) or from the selection bar.

**Manage a playlist.** The playlist's menu in the sidebar offers **Play Playlist**, **Edit
Playlist** and **Delete Playlist**. Opening a playlist shows its tracks and a **Play** button.

**Favourites.** Mark an album with the heart button on its page, or select tracks and use **Toggle
Favorite** in the selection bar. Favourites appear in the **Favourites** view.

**Edit Metadata.** Choose **Edit Metadata** from a track's menu to change its **Title**, **Artist**,
**Album Artist**, **Album**, **Genre**, **Year**, **Track #**, **Disc #**, **Composer** and
**Comment**, then **Save**. The changes are written to the audio file's tags, so back up files you
cannot replace.

## Settings

Open **Settings** from the bottom of the sidebar or with **Ctrl+,**. The window has six tabs.
Edits are saved when you click **Save Changes**; **Cancel**, **Escape** or clicking outside
discards them. The **Theme** choice is the exception and applies at once. **Reset to Defaults**
restores every setting. Adding or removing a scan folder and **Scan Now** take effect
immediately.

| Tab | What you can change |
|-----|---------------------|
| **Library** | **Scan Folders** (**Add Folder**, remove), **Scan Now** with live scan progress, **Audio analysis** progress and **Analyse remaining**, **Auto-scan library** and **Scan Interval** |
| **Playback** | **Default Volume** |
| **Audio** | **Output Device** (currently only **Default**), **Bit Depth** (16, 24, 32-bit) and **Sample Rate** (44.1, 48, 96, 192 kHz). These are saved preferences; during playback Auralis follows each track's own sample rate. |
| **Interface** | **Theme** (**Dark** or **Light**), **Show visualizations** (the animated starfield background), **Mini player on close** (saved, but the app does not act on it yet) |
| **Enhancement** | **Default Preset**, **Auto-enhance playback**, **Enhancement Intensity** |
| **Advanced** | **Cache Size (MB)** for processed audio, live **Cache Statistics**, **Max Concurrent Scans**, **Enable analytics**, **Debug mode**, and a **Danger Zone** |

**Reset Library** in the Danger Zone deletes every track, album, artist, playlist, analysis result
and playback-history entry from Auralis's library. Your audio files on disk are not touched. You
are asked to confirm, and the window reloads with an empty library.

## Keyboard shortcuts

Press **?** to open the shortcuts list. Shortcuts do not fire while you are typing in a text box.

| Key | Action |
|-----|--------|
| **Space** | Play / pause |
| **Right arrow** / **Left arrow** | Next / previous track |
| **Up arrow** / **Down arrow** | Volume up / down by 10 |
| **M** | Mute / unmute |
| **1**, **2**, **3** | Show Songs, Albums, Artists |
| **/** | Focus the search box |
| **Escape** | Clear the search, or close Settings |
| **?** | Show the shortcuts list |
| **Ctrl+,** | Open Settings |
| **Ctrl+A** (**Cmd+A** on macOS) | Select all tracks in the list |
| **Escape** | Clear the track selection |

On the focused progress bar the arrow keys seek one second and **Home** / **End** jump to the
ends. In the queue, **Alt+Up** / **Alt+Down** reorder the focused track and **Delete** removes it.

## Where your data lives

Auralis keeps its data in a hidden **.auralis** folder in your home folder. It holds:

- **library.db**: your library, playlists, favourites and settings;
- folders for album artwork, analysis results and the processed-audio cache;
- **library.backup_...db** files: automatic copies made before the library database is upgraded.

Your music files stay where they are, and Auralis does not move or copy them. Deleting the
**.auralis** folder while Auralis is closed resets it to a fresh install.

## Troubleshooting

**The status dot (top right).** **Connected** means all is well. **Connecting** and
**Disconnected** appear while Auralis reconnects to its audio engine, which it retries on its own.
**Connection lost** means it gave up; restart Auralis.

**A box titled "Auralis startup failed" appears and Auralis closes.** The audio engine could not
start. Start Auralis again, and if it keeps happening, restart your computer or reinstall the app.

**My library is empty after adding a folder.** Check **Settings → Library** for a failed-scan
message. The scan reports files it could not read and folders it could not open. Make sure the
folder contains files in the supported formats, and use **Scan Now** to try again.

**New files are not showing up.** Use **Scan Now**, or switch on **Auto-scan library**.

**A track will not play, or says the file is not found.** The file was moved, renamed or sits on a
drive that is not connected. Restore it or rescan.

**Playback stutters or keeps buffering.** Mastering is processed as the track plays; a slow or busy
computer can fall behind. Turn **Auto-Mastering** off to compare, close heavy applications, and
check **Settings → Advanced → Cache Statistics**.

**The track-character panel never fills in.** The track has not been analysed yet. Open
**Settings → Library** and click **Analyse remaining**.

**Nothing moves in the background.** **Show visualizations** in **Settings → Interface** is off, or
your system is set to reduce motion.

**Starting over.** To remove everything Auralis knows about your library without touching your
music, use **Settings → Advanced → Reset Library**.

For bugs and feature requests, see the project's issue tracker linked from the
[README](../../README.md).
