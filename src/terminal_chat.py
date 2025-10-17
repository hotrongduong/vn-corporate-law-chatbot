import requests
import json
import os
import sys
from dotenv import load_dotenv

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dotenv_path = os.path.join(project_root, '.env')

if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
else:
    print(f"Cảnh báo: Không tìm thấy file .env tại {dotenv_path}")

# --- Cấu hình API Endpoint ---
# Sử dụng biến môi trường hoặc giá trị mặc định
CHATBOT_API_URL = os.getenv("CHATBOT_API_URL", "http://web:8000/api/chatbot/ask/")

def ask_chatbot(question):
    """Gửi câu hỏi đến API chatbot và trả về câu trả lời."""
    payload = json.dumps({"question": question})
    headers = {'Content-Type': 'application/json'}

    print(f"DEBUG: Đang gửi yêu cầu đến {CHATBOT_API_URL}") # In debug
    try:
        response = requests.post(CHATBOT_API_URL, headers=headers, data=payload, timeout=90) # Tăng timeout lên 90 giây
        print(f"DEBUG: Nhận được mã trạng thái: {response.status_code}") # In debug
        # print(f"DEBUG: Nội dung phản hồi thô: {response.text}") # In debug phản hồi thô

        response.raise_for_status() # Ném lỗi nếu mã trạng thái không phải 2xx

        data = response.json()
        answer = data.get("answer", "Lỗi: Không nhận được câu trả lời hợp lệ.")
        sources = data.get("sources", [])

        # Định dạng nguồn để hiển thị
        source_texts = []
        if sources:
            source_texts.append("\n   Nguồn tham khảo:")
            for src in sources:
                 source_texts.append(
                     f"    - Điều {src.get('article', '?')}, Khoản {src.get('provision', 'N/A')} "
                     f"(Điểm tương đồng: {src.get('score', 0):.2f})"
                 )

        return answer + "\n" + "\n".join(source_texts)

    except requests.exceptions.Timeout:
        return "Lỗi: Yêu cầu đến chatbot bị quá thời gian (hơn 90 giây)."
    except requests.exceptions.ConnectionError as e:
         return f"Lỗi kết nối: Không thể kết nối đến {CHATBOT_API_URL}. Bạn đã chạy 'docker compose up -d' chưa? Chi tiết lỗi: {e}"
    except requests.exceptions.HTTPError as e:
         # In ra nội dung lỗi chi tiết hơn từ server
         error_content = e.response.text
         try:
             # Thử phân tích JSON nếu có
             error_json = e.response.json()
             if 'error' in error_json:
                 error_content = error_json['error']
         except json.JSONDecodeError:
             pass # Giữ nguyên error_content nếu không phải JSON
         return f"Lỗi HTTP từ API: {e.response.status_code} {e.response.reason}. Nội dung lỗi: {error_content}"
    except requests.exceptions.RequestException as e:
        return f"Lỗi yêu cầu API không xác định: {e}"
    except json.JSONDecodeError:
        # In ra nội dung không hợp lệ nhận được
        return f"Lỗi: Phản hồi từ API không phải là JSON hợp lệ. Nội dung nhận được:\n{response.text}"
    except Exception as e:
        # Bắt các lỗi không mong muốn khác
        import traceback
        return f"Lỗi không xác định trong quá trình xử lý: {e}\n{traceback.format_exc()}"


if __name__ == "__main__":
    print("\n🤖 Chatbot Luật Doanh nghiệp sẵn sàng!")
    print("   Nhập câu hỏi của bạn hoặc gõ 'quit' để thoát.")
    print("-" * 30)

    while True:
        try:
            user_input = input("👤 Bạn: ")
            # Thoát nếu người dùng nhập quit, exit, bye hoặc để trống
            if user_input.lower().strip() in ['quit', 'exit', 'bye', '']:
                print("\n👋 Tạm biệt!")
                break

            print("\n⏳ Đang tìm kiếm và tạo câu trả lời...")
            bot_response = ask_chatbot(user_input)
            print(f"\n🤖 Chatbot: {bot_response}")
            print("=" * 70)

        except EOFError: # Xử lý khi nhấn Ctrl+D
            print("\n👋 Tạm biệt!")
            break
        except KeyboardInterrupt: # Xử lý khi nhấn Ctrl+C
             print("\n👋 Tạm biệt!")
             break