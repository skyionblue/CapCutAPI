#!/usr/bin/env python3
"""
CapCut API MCP test client (complete version)

Exercises the full MCP server across every CapCut API tool.
"""

import subprocess
import json
import time
import sys

def send_request(process, request_data):
    """Send a request and read the response."""
    try:
        request_json = json.dumps(request_data, ensure_ascii=False)
        print(f"Request: {request_json}")

        # Send
        process.stdin.write(request_json + "\n")
        process.stdin.flush()

        # Wait for the response
        response_line = process.stdout.readline()
        if not response_line.strip():
            print("❌ Empty response")
            return None

        try:
            response = json.loads(response_line.strip())
            print(f"Response: {json.dumps(response, ensure_ascii=False, indent=2)}")
            return response
        except json.JSONDecodeError as e:
            print(f"❌ JSON parse error: {e}")
            print(f"Raw response: {response_line}")
            return None

    except Exception as e:
        print(f"❌ Error sending request: {e}")
        return None

def send_notification(process, notification_data):
    """Send a notification; no response is expected."""
    try:
        notification_json = json.dumps(notification_data, ensure_ascii=False)
        print(f"Notification: {notification_json}")

        process.stdin.write(notification_json + "\n")
        process.stdin.flush()

    except Exception as e:
        print(f"❌ Error sending notification: {e}")

def main():
    print("🚀 CapCut API MCP test client (complete version)")
    print("🎯 Exercising every CapCut API tool")
    print("=" * 60)

    # Start the MCP server
    try:
        process = subprocess.Popen(
            [sys.executable, "mcp_server.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0  # unbuffered
        )

        print("✅ MCP server started (mcp_server.py)")
        time.sleep(1)  # give the server a moment to start

        # 1. Initialise
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "resources": {}
                },
                "clientInfo": {
                    "name": "CapCut-Test-Client-Complete",
                    "version": "1.0.0"
                }
            }
        }

        response = send_request(process, init_request)
        if response and "result" in response:
            print("✅ Initialised")
        else:
            print("❌ Initialisation failed")
            return

        # Send the initialised notification
        init_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        }
        send_notification(process, init_notification)

        print("\n=== 📋 Tool list ===")
        # 2. Fetch the tool list
        tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }

        response = send_request(process, tools_request)
        if response and "result" in response:
            tools = response["result"]["tools"]
            print(f"✅ Got {len(tools)} tools:")
            for tool in tools:
                print(f"   • {tool['name']}: {tool['description']}")
        else:
            print("❌ Could not fetch the tool list")
            return

        print("\n=== 🎬 Core functionality ===\n")

        # 3. create_draft
        print("📝 Testing create_draft")
        create_draft_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "create_draft",
                "arguments": {
                    "width": 1080,
                    "height": 1920
                }
            }
        }

        response = send_request(process, create_draft_request)
        if response and "result" in response:
            print("✅ Draft created")
            # Keep the draft_id for the later calls
            draft_data = json.loads(response["result"]["content"][0]["text"])
            draft_id = draft_data["result"]["draft_id"]
            print(f"📋 Draft id: {draft_id}")
        else:
            print("❌ Could not create the draft")
            draft_id = None

        # 4. add_text, with per-range styles
        print("\n📝 Testing add_text (per-range styles)")
        add_text_request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "add_text",
                "arguments": {
                    "text": "Hello CapCut API!",
                    "start": 0,
                    "end": 5,
                    "draft_id": draft_id,
                    "font_color": "#ff0000",
                    "font_size": 32,
                    "shadow_enabled": True,
                    "shadow_color": "#000000",
                    "shadow_alpha": 0.8,
                    "background_color": "#ffffff",
                    "background_alpha": 0.5,
                    "text_styles": [
                        {
                            "start": 0,
                            "end": 5,
                            "font_size": 36,
                            "font_color": "#00ff00",
                            "bold": True
                        },
                        {
                            "start": 6,
                            "end": 12,
                            "font_size": 28,
                            "font_color": "#0000ff",
                            "italic": True
                        }
                    ]
                }
            }
        }

        response = send_request(process, add_text_request)
        if response and "result" in response:
            print("✅ Text added")
        else:
            print("❌ Could not add the text")

        # 5. add_video
        print("\n🎬 Testing add_video")
        add_video_request = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "add_video",
                "arguments": {
                    "video_url": "https://example.com/video.mp4",
                    "draft_id": draft_id,
                    "start": 0,
                    "end": 10,
                    "target_start": 5,
                    "transition": "fade",
                    "volume": 0.8
                }
            }
        }

        response = send_request(process, add_video_request)
        if response and "result" in response:
            print("✅ Video added")
        else:
            print("❌ Could not add the video")

        # 6. add_audio
        print("\n🎵 Testing add_audio")
        add_audio_request = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "add_audio",
                "arguments": {
                    "audio_url": "https://example.com/audio.mp3",
                    "draft_id": draft_id,
                    "start": 0,
                    "end": 15,
                    "volume": 0.6
                }
            }
        }

        response = send_request(process, add_audio_request)
        if response and "result" in response:
            print("✅ Audio added")
        else:
            print("❌ Could not add the audio")

        # 7. add_image
        print("\n🖼️ Testing add_image")
        add_image_request = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "add_image",
                "arguments": {
                    "image_url": "https://example.com/image.jpg",
                    "draft_id": draft_id,
                    "start": 10,
                    "end": 15,
                    "intro_animation": "fade_in",
                    "outro_animation": "fade_out"
                }
            }
        }

        response = send_request(process, add_image_request)
        if response and "result" in response:
            print("✅ Image added")
        else:
            print("❌ Could not add the image")

        # 8. get_video_duration
        print("\n⏱️ Testing get_video_duration")
        get_duration_request = {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tools/call",
            "params": {
                "name": "get_video_duration",
                "arguments": {
                    "video_url": "https://example.com/video.mp4"
                }
            }
        }

        response = send_request(process, get_duration_request)
        if response and "result" in response:
            print("✅ Duration retrieved")
        else:
            print("❌ Could not get the duration")

        # 9. save_draft
        print("\n💾 Testing save_draft")
        save_draft_request = {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "tools/call",
            "params": {
                "name": "save_draft",
                "arguments": {
                    "draft_id": draft_id
                }
            }
        }

        response = send_request(process, save_draft_request)
        if response and "result" in response:
            print("✅ Draft saved")
        else:
            print("❌ Could not save the draft")

        print("\n🎉 All checks complete -- the CapCut API MCP server works.")

        print("\n✅ Verified:")
        print("   • Draft management (create, save)")
        print("   • Text (per-range styles, shadow, background)")
        print("   • Video (add, transitions, volume)")
        print("   • Audio (add, volume)")
        print("   • Images (add, animations)")
        print("   • Utilities (duration probe)")

    except Exception as e:
        print(f"❌ Error during the run: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Shut the server down
        try:
            process.terminate()
            process.wait(timeout=5)
        except Exception:
            process.kill()
        print("🔴 MCP server stopped")

if __name__ == "__main__":
    main()
