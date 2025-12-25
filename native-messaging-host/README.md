# asbplayer Native Messaging Host

This native messaging host enables asbplayer to record audio from DRM-protected content in Firefox on Linux.

## Why is this needed?

Firefox blocks the built-in `captureStream()` API for DRM-protected content (Netflix, Crunchyroll, etc.). To record audio from these sites for Anki cards, we need to use system-level audio recording via PipeWire or PulseAudio.

## Requirements

- **Python 3** (pre-installed on most Linux systems)
- **PipeWire** (default on Ubuntu 22.04+, Fedora 34+) or **PulseAudio** (older systems)
- **Firefox** browser

## Installation

### Quick Install

```bash
cd /home/boris/apps/asbplayer/native-messaging-host
./install.sh
```

The installer will:
- Copy the native messaging host manifest to `~/.mozilla/native-messaging-hosts/`
- Check your audio system (PipeWire or PulseAudio)
- Verify required tools are installed
- Make the Python script executable

### Manual Install

If you prefer to install manually:

1. **Make the Python script executable:**
   ```bash
   chmod +x asbplayer_audio_host.py
   ```

2. **Copy the manifest to Firefox's native messaging directory:**
   ```bash
   mkdir -p ~/.mozilla/native-messaging-hosts
   cp dev.asbplayer.audio.json ~/.mozilla/native-messaging-hosts/
   ```

3. **Update the path in the manifest:**
   Edit `~/.mozilla/native-messaging-hosts/dev.asbplayer.audio.json` and set the `path` field to the absolute path of `asbplayer_audio_host.py`

4. **Restart Firefox and reload the extension**

## Required Audio Tools

### For PipeWire (recommended)

Install PipeWire utilities:

**Ubuntu/Debian:**
```bash
sudo apt install pipewire-audio-client-libraries
```

**Fedora/RHEL:**
```bash
sudo dnf install pipewire-utils
```

**Arch Linux:**
```bash
sudo pacman -S pipewire
```

### For PulseAudio (fallback)

Install PulseAudio utilities:

**Ubuntu/Debian:**
```bash
sudo apt install pulseaudio-utils
```

**Fedora/RHEL:**
```bash
sudo dnf install pulseaudio-utils
```

**Arch Linux:**
```bash
sudo pacman -S pulseaudio
```

## Testing

After installation, test the native messaging host:

1. Open Firefox
2. Load the asbplayer extension
3. Navigate to a DRM-protected video site (e.g., Crunchyroll)
4. Try using the keyboard shortcut to mine a subtitle (Ctrl+Shift+X)

If the native host is working, you should see logs in the Browser Console (Ctrl+Shift+J) with `[asbplayer-audio-host]` prefix.

## Troubleshooting

### "Native messaging host not installed" notification

If you see this notification after installing:
1. Make sure you ran the install script or manually copied the manifest
2. Restart Firefox completely
3. Reload the extension from about:debugging

### Recording fails with "Could not find Firefox audio stream"

This happens when Firefox isn't actively playing audio:
1. Make sure the video is playing (not paused)
2. The video must be producing audio
3. Try unmuting the video if it's muted

### Audio system not detected

The script auto-detects PipeWire or PulseAudio. If neither is detected:
```bash
# Check if PipeWire is running
systemctl --user status pipewire

# Check if PulseAudio is running
pulseaudio --check && echo "PulseAudio is running"
```

### Permission denied errors

Make sure the Python script is executable:
```bash
chmod +x /home/boris/apps/asbplayer/native-messaging-host/asbplayer_audio_host.py
```

## Uninstallation

To remove the native messaging host:

```bash
rm ~/.mozilla/native-messaging-hosts/dev.asbplayer.audio.json
```

Then restart Firefox.

## How it works

1. When you use Ctrl+Shift+X or Ctrl+Shift+U on DRM-protected content, the extension detects that browser-based recording is blocked
2. The extension sends a message to the native messaging host via Firefox's native messaging API
3. The Python script detects your audio system (PipeWire or PulseAudio)
4. It finds the Firefox audio stream using `pw-dump` or `pactl`
5. It records audio using `pw-record` or `parecord`
6. The recorded audio is encoded as base64 and sent back to the extension
7. The extension uses this audio for your Anki card

## Privacy & Security

- The native messaging host **only** records audio from Firefox
- It **only** runs when explicitly requested by the extension
- All audio is temporarily stored and immediately deleted after encoding
- No audio is sent to external servers - everything stays on your machine
