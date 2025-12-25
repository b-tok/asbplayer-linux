#!/usr/bin/env python3
"""
asbplayer Native Messaging Host for Firefox Audio Recording
Handles system-level audio recording for DRM-protected content
"""

import sys
import json
import struct
import subprocess
import tempfile
import base64
import os
import time
import re
from pathlib import Path


def log(message):
    """Log to stderr for debugging (visible in Firefox's Browser Console)"""
    print(f"[asbplayer-audio-host] {message}", file=sys.stderr, flush=True)


def send_message(message):
    """Send a message to the extension via stdout"""
    encoded_content = json.dumps(message).encode("utf-8")
    encoded_length = struct.pack("=I", len(encoded_content))
    sys.stdout.buffer.write(encoded_length)
    sys.stdout.buffer.write(encoded_content)
    sys.stdout.buffer.flush()


def read_message():
    """Read a message from the extension via stdin"""
    raw_length = sys.stdin.buffer.read(4)
    if len(raw_length) == 0:
        return None
    message_length = struct.unpack("=I", raw_length)[0]
    message = sys.stdin.buffer.read(message_length).decode("utf-8")
    return json.loads(message)


class AudioSystem:
    """Detects and manages audio system (PipeWire or PulseAudio)"""

    @staticmethod
    def detect():
        """Detect which audio system is running"""
        try:
            # Check if PipeWire is running
            result = subprocess.run(
                ["systemctl", "--user", "is-active", "pipewire"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                log("Detected PipeWire audio system")
                return "pipewire"
        except Exception as e:
            log(f"Error checking PipeWire: {e}")

        try:
            # Check if PulseAudio is running
            result = subprocess.run(["pulseaudio", "--check"], capture_output=True)
            if result.returncode == 0:
                log("Detected PulseAudio audio system")
                return "pulseaudio"
        except Exception as e:
            log(f"Error checking PulseAudio: {e}")

        log("No supported audio system detected, defaulting to PipeWire")
        return "pipewire"


class FirefoxAudioRecorder:
    """Records audio from Firefox using system-level audio capture"""

    def __init__(self):
        self.audio_system = AudioSystem.detect()

    def find_firefox_sink(self):
        """Find the Firefox audio sink/stream"""
        # Try multiple times to find Firefox stream (it may take a moment to appear after playback starts)
        max_attempts = 5
        for attempt in range(max_attempts):
            if self.audio_system == "pipewire":
                result = self._find_firefox_sink_pipewire()
            else:
                result = self._find_firefox_sink_pulseaudio()

            if result is not None:
                return result

            if attempt < max_attempts - 1:
                log(f"Firefox stream not found, waiting 200ms and retrying (attempt {attempt + 1}/{max_attempts})")
                time.sleep(0.2)

        log("Firefox stream not found after all retry attempts")
        return None

    def _find_firefox_sink_pipewire(self):
        """Find Firefox sink using PipeWire commands"""
        try:
            # Use pw-dump to get all nodes
            result = subprocess.run(
                ["pw-dump"], capture_output=True, text=True, timeout=5
            )

            if result.returncode != 0:
                log(f"pw-dump failed: {result.stderr}")
                return None

            import json

            # Debug: check if output is truncated
            stdout_len = len(result.stdout)
            log(f"pw-dump output length: {stdout_len} bytes")

            try:
                nodes = json.loads(result.stdout)
            except json.JSONDecodeError as e:
                log(f"JSON decode error: {e}")
                log(f"Last 200 chars of output: {result.stdout[-200:]}")
                return None

            log(f"Scanning {len(nodes)} PipeWire nodes for Firefox")

            # Look for Firefox stream
            firefox_nodes_found = 0
            nodes_checked = 0
            node_ids_checked = []
            for node in nodes:
                if node.get("type") != "PipeWire:Interface:Node":
                    continue

                node_id_for_log = node.get("id", "?")
                node_ids_checked.append(str(node_id_for_log))
                nodes_checked += 1
                info = node.get("info", {})
                props = info.get("props", {})

                # Check if this is a Firefox stream
                app_name = props.get("application.name", "")
                app_process = props.get("application.process.binary", "")

                # Debug: log every node with an application name
                if app_name:
                    log(f"Found node with app: {app_name} (type: {node.get('type')})")

                app_name_lower = app_name.lower() if app_name else ""
                app_process_lower = app_process.lower() if app_process else ""

                if "firefox" in app_name_lower or "firefox" in app_process_lower:
                    firefox_nodes_found += 1
                    node_id = info.get("id")
                    log(f"Firefox node found! Checking IDs... info.id={node_id}")

                    if node_id is None:
                        node_id = node.get("id")
                        log(f"Using root level id: {node_id}")

                    if node_id is None:
                        # Fallback to object serial if available
                        node_id = props.get("object.serial")
                        log(f"Using object.serial as fallback: {node_id}")

                    node_name = props.get("node.name", "")
                    node_state = info.get("state", "unknown")
                    media_class = props.get("media.class", "unknown")
                    object_serial = props.get("object.serial")

                    log(f"Found Firefox PipeWire node: id={node_id}, name={node_name}, state={node_state}, class={media_class}, serial={object_serial}")

                    if node_id is None:
                        log("WARNING: Node ID is None, skipping this node")
                        continue

                    # For PulseAudio compatibility (parecord --monitor-stream), we need object.serial, not node id
                    # object.serial corresponds to the PulseAudio sink-input ID
                    if object_serial:
                        log(f"Returning node serial {object_serial} for PulseAudio compatibility")
                        return str(object_serial)
                    else:
                        log(f"WARNING: No object.serial found, falling back to node id {node_id}")
                        return str(node_id)

            log(f"Checked {nodes_checked} PipeWire nodes (out of {len(nodes)} total)")
            log(f"Node IDs checked: {', '.join(node_ids_checked)}")
            if firefox_nodes_found > 0:
                log(f"Found {firefox_nodes_found} Firefox node(s) but all had None as node ID")
            else:
                log("No Firefox PipeWire stream found")
            return None

        except Exception as e:
            log(f"Error finding Firefox PipeWire sink: {e}")
            import traceback
            log(f"Traceback: {traceback.format_exc()}")
            return None

    def _find_firefox_sink_pulseaudio(self):
        """Find Firefox sink using PulseAudio commands"""
        try:
            # Use pactl to list sink inputs
            result = subprocess.run(
                ["pactl", "list", "sink-inputs"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                log(f"pactl failed: {result.stderr}")
                return None

            # Parse pactl output to find Firefox
            current_id = None
            for line in result.stdout.split("\n"):
                # Look for Sink Input #
                id_match = re.match(r"Sink Input #(\d+)", line)
                if id_match:
                    current_id = id_match.group(1)

                # Look for application.process.binary or application.name
                if current_id and (
                    "application.process.binary" in line or "application.name" in line
                ):
                    if "firefox" in line.lower():
                        log(f"Found Firefox PulseAudio sink input: {current_id}")
                        return current_id

            log("No Firefox PulseAudio sink input found")
            return None

        except Exception as e:
            log(f"Error finding Firefox PulseAudio sink: {e}")
            return None

    def record_audio(self, duration_ms, encode_mp3=False):
        """
        Record audio from Firefox for the specified duration

        Args:
            duration_ms: Duration in milliseconds
            encode_mp3: Whether to encode as MP3 (currently returns WAV)

        Returns:
            dict with success status and base64 audio data or error message
        """
        log(f"Recording audio for {duration_ms}ms (MP3: {encode_mp3})")

        # Find Firefox audio stream
        firefox_sink = self.find_firefox_sink()

        if not firefox_sink:
            return {
                "success": False,
                "error": "Could not find Firefox audio stream. Make sure Firefox is playing audio.",
            }

        # Create temporary file for recording
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            tmp_path = tmp_file.name

        try:
            # Record audio
            if self.audio_system == "pipewire":
                success = self._record_pipewire(firefox_sink, tmp_path, duration_ms)
            else:
                success = self._record_pulseaudio(firefox_sink, tmp_path, duration_ms)

            if not success:
                return {"success": False, "error": "Audio recording failed"}

            # Read and encode the audio file
            with open(tmp_path, "rb") as f:
                audio_data = f.read()

            audio_base64 = base64.b64encode(audio_data).decode("utf-8")

            log(f"Successfully recorded {len(audio_data)} bytes")

            return {"success": True, "audioBase64": audio_base64, "format": "wav"}

        except Exception as e:
            log(f"Error during recording: {e}")
            return {"success": False, "error": str(e)}
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except:
                pass

    def _record_pipewire(self, node_id, output_path, duration_ms):
        """Record audio using PipeWire (via PulseAudio compatibility layer)"""
        duration_sec = duration_ms / 1000.0
        # Add a safety margin for process cleanup
        max_wait_time = duration_sec + 5.0

        try:
            log(f"Starting PipeWire recording from node {node_id} for {duration_sec}s")

            # Use parecord with monitor-stream to record from the application's output
            # This works through PulseAudio compatibility even when PipeWire is running
            # The node_id from PipeWire corresponds to a PulseAudio sink input
            process = subprocess.Popen(
                [
                    "parecord",
                    f"--monitor-stream={node_id}",
                    "--format=s16le",
                    "--rate=48000",
                    "--channels=2",
                    "--raw",
                    output_path + ".raw",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            raw_path = output_path + ".raw"

            # Wait for the specified duration
            start_time = time.time()
            time.sleep(duration_sec)

            # Stop recording
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                log("PipeWire process didn't terminate, killing it")
                process.kill()
                process.wait()

            # Check total time didn't exceed our safety limit
            elapsed = time.time() - start_time
            if elapsed > max_wait_time:
                log(f"WARNING: Recording took longer than expected: {elapsed:.1f}s")

            if not os.path.exists(raw_path) or os.path.getsize(raw_path) == 0:
                log("PipeWire recording produced no output")
                return False

            # Convert raw PCM data to WAV
            try:
                import wave

                with open(raw_path, "rb") as raw_file:
                    pcm_data = raw_file.read()

                with wave.open(output_path, "wb") as wav_file:
                    wav_file.setnchannels(2)
                    wav_file.setsampwidth(2)  # 16-bit samples
                    wav_file.setframerate(48000)
                    wav_file.writeframes(pcm_data)

                log(
                    f"PipeWire recording completed successfully ({len(pcm_data)} bytes raw, {os.path.getsize(output_path)} bytes wav)"
                )
                return True
            except Exception as convert_error:
                log(f"Failed to convert raw audio to WAV: {convert_error}")
                return False

        except Exception as e:
            log(f"PipeWire recording error: {e}")
            return False
        finally:
            try:
                if os.path.exists(raw_path):
                    os.unlink(raw_path)
            except Exception as cleanup_error:
                log(f"Failed to clean up raw file: {cleanup_error}")

    def _record_pulseaudio(self, sink_input, output_path, duration_ms):
        """Record audio using PulseAudio"""
        duration_sec = duration_ms / 1000.0
        # Add a safety margin for process cleanup
        max_wait_time = duration_sec + 5.0

        try:
            log(
                f"Starting PulseAudio recording from sink input {sink_input} for {duration_sec}s"
            )

            # Use parecord to record from the sink input's monitor
            # We need to record from the sink that this input is connected to
            process = subprocess.Popen(
                [
                    "parecord",
                    "--format=s16le",
                    "--rate=44100",
                    "--channels=2",
                    output_path,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # Wait for the specified duration
            start_time = time.time()
            time.sleep(duration_sec)

            # Stop recording
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                log("PulseAudio process didn't terminate, killing it")
                process.kill()
                process.wait()

            # Check total time didn't exceed our safety limit
            elapsed = time.time() - start_time
            if elapsed > max_wait_time:
                log(f"WARNING: Recording took longer than expected: {elapsed:.1f}s")

            # Check if file was created and has content
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                log(
                    f"PulseAudio recording completed successfully ({os.path.getsize(output_path)} bytes)"
                )
                return True
            else:
                log("PulseAudio recording produced no output")
                return False

        except Exception as e:
            log(f"PulseAudio recording error: {e}")
            return False


def handle_message(message):
    """Handle incoming messages from the extension"""
    command = message.get("command")

    if command == "ping":
        # Health check
        send_message(
            {"success": True, "message": "pong", "audioSystem": AudioSystem.detect()}
        )

    elif command == "record":
        # Record audio
        duration = message.get("duration", 5000)  # Default 5 seconds
        encode_mp3 = message.get("encodeMp3", False)

        recorder = FirefoxAudioRecorder()
        result = recorder.record_audio(duration, encode_mp3)
        send_message(result)

    else:
        send_message({"success": False, "error": f"Unknown command: {command}"})


def main():
    """Main loop for the native messaging host"""
    log("asbplayer audio host started")

    try:
        while True:
            message = read_message()
            if message is None:
                log("No message received, exiting")
                break

            log(f"Received message: {message.get('command', 'unknown')}")
            handle_message(message)

    except Exception as e:
        log(f"Error in main loop: {e}")
        send_message({"success": False, "error": str(e)})

    log("asbplayer audio host exiting")


if __name__ == "__main__":
    main()
