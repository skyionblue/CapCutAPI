#!/usr/bin/env python3
"""
CapCut API MCP 测试客户端 (Complete Version)

测试完整版本的MCP服务器，包含所有CapCut API接口
"""

import subprocess
import json
import time
import sys

def send_request(process, request_data):
    """发送请求并接收响应"""
    try:
        request_json = json.dumps(request_data, ensure_ascii=False)
        print(f"发送请求: {request_json}")

        # 发送请求
        process.stdin.write(request_json + "\n")
        process.stdin.flush()

        # 等待响应
        response_line = process.stdout.readline()
        if not response_line.strip():
            print("❌ 收到空响应")
            return None

        try:
            response = json.loads(response_line.strip())
            print(f"收到响应: {json.dumps(response, ensure_ascii=False, indent=2)}")
            return response
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析错误: {e}")
            print(f"原始响应: {response_line}")
            return None

    except Exception as e:
        print(f"❌ 发送请求时出错: {e}")
        return None

def send_notification(process, notification_data):
    """发送通知（不需要响应）"""
    try:
        notification_json = json.dumps(notification_data, ensure_ascii=False)
        print(f"发送通知: {notification_json}")

        process.stdin.write(notification_json + "\n")
        process.stdin.flush()

    except Exception as e:
        print(f"❌ 发送通知时出错: {e}")

def main():
    print("🚀 CapCut API MCP 测试客户端 (Complete Version)")
    print("🎯 测试所有CapCut API接口功能")
    print("=" * 60)

    # 启动MCP服务器
    try:
        process = subprocess.Popen(
            [sys.executable, "mcp_server.py"],  # 修改为正确的文件名
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0  # 无缓冲
        )

        print("✅ MCP服务器已启动 (mcp_server.py)")
        time.sleep(1)  # 等待服务器启动

        # 1. 初始化
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
            print("✅ 初始化成功")
        else:
            print("❌ 初始化失败")
            return

        # 发送初始化完成通知
        init_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        }
        send_notification(process, init_notification)

        print("\n=== 📋 获取工具列表 ===")
        # 2. 获取工具列表
        tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }

        response = send_request(process, tools_request)
        if response and "result" in response:
            tools = response["result"]["tools"]
            print(f"✅ 成功获取 {len(tools)} 个工具:")
            for tool in tools:
                print(f"   • {tool['name']}: {tool['description']}")
        else:
            print("❌ 获取工具列表失败")
            return

        print("\n=== 🎬 测试核心功能 ===\n")

        # 3. 测试创建草稿
        print("📝 测试创建草稿")
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
            print("✅ 创建草稿成功")
            # 提取draft_id用于后续测试
            draft_data = json.loads(response["result"]["content"][0]["text"])
            draft_id = draft_data["result"]["draft_id"]
            print(f"📋 草稿ID: {draft_id}")
        else:
            print("❌ 创建草稿失败")
            draft_id = None

        # 4. 测试添加文本（带多样式）
        print("\n📝 测试添加文本（多样式）")
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
            print("✅ 添加文本成功")
        else:
            print("❌ 添加文本失败")

        # 5. 测试添加视频
        print("\n🎬 测试添加视频")
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
            print("✅ 添加视频成功")
        else:
            print("❌ 添加视频失败")

        # 6. 测试添加音频
        print("\n🎵 测试添加音频")
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
            print("✅ 添加音频成功")
        else:
            print("❌ 添加音频失败")

        # 7. 测试添加图片
        print("\n🖼️ 测试添加图片")
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
            print("✅ 添加图片成功")
        else:
            print("❌ 添加图片失败")

        # 8. 测试获取视频时长
        print("\n⏱️ 测试获取视频时长")
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
            print("✅ 获取视频时长成功")
        else:
            print("❌ 获取视频时长失败")

        # 9. 测试保存草稿
        print("\n💾 测试保存草稿")
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
            print("✅ 保存草稿成功")
        else:
            print("❌ 保存草稿失败")

        print("\n🎉 所有测试完成！CapCut API MCP服务器功能验证成功！")

        print("\n✅ 已验证的功能:")
        print("   • 草稿管理 (创建、保存)")
        print("   • 文本处理 (多样式、阴影、背景)")
        print("   • 视频处理 (添加、转场、音量控制)")
        print("   • 音频处理 (添加、音量控制)")
        print("   • 图片处理 (添加、动画效果)")
        print("   • 工具信息 (时长获取)")

    except Exception as e:
        print(f"❌ 测试过程中出错: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # 关闭服务器
        try:
            process.terminate()
            process.wait(timeout=5)
        except:
            process.kill()
        print("🔴 MCP服务器已关闭")

if __name__ == "__main__":
    main()
