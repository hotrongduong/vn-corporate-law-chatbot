import requests
import json
import os
import sys
import time 
from dotenv import load_dotenv

# # Tìm thư mục gốc của dự án
# project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# dotenv_path = os.path.join(project_root, '.env')

# # Tải file .env nếu tồn tại
# if os.path.exists(dotenv_path):
#     load_dotenv(dotenv_path=dotenv_path)
#     # print(f"DEBUG: Đã tải biến môi trường từ: {dotenv_path}")
# else:
#     print(f"Cảnh báo: Không tìm thấy file .env tại {dotenv_path}")

# --- Cấu hình API Endpoint ---
CHATBOT_API_URL = os.getenv("CHATBOT_API_URL", "http://web:8000/api/chatbot/ask/")

def ask_chatbot(question):
    """Gửi câu hỏi đến API chatbot và trả về (câu trả lời, thời gian xử lý)."""
    payload = json.dumps({"question": question})
    headers = {'Content-Type': 'application/json'}

    # print(f"DEBUG: Đang gửi yêu cầu đến {CHATBOT_API_URL}")
    start_time = time.time() # <-- Bắt đầu đếm thời gian

    try:
        response = requests.post(CHATBOT_API_URL, headers=headers, data=payload, timeout=90)
        end_time = time.time() # <-- Kết thúc đếm thời gian
        response_time = end_time - start_time # <-- Tính thời gian

        print(f"DEBUG: Nhận được mã trạng thái: {response.status_code}")
        response.raise_for_status()

        data = response.json()
        answer = data.get("answer", "Lỗi: Không nhận được câu trả lời hợp lệ.")
        # Không xử lý sources nữa

        # Trả về cả câu trả lời và thời gian xử lý
        return answer, response_time

    except requests.exceptions.Timeout:
        end_time = time.time()
        return "Lỗi: Yêu cầu đến chatbot bị quá thời gian (hơn 90 giây).", end_time - start_time
    except requests.exceptions.ConnectionError as e:
         end_time = time.time()
         return f"Lỗi kết nối: Không thể kết nối đến {CHATBOT_API_URL}. Bạn đã chạy 'docker compose up -d' chưa? Chi tiết lỗi: {e}", end_time - start_time
    except requests.exceptions.HTTPError as e:
         end_time = time.time()
         error_content = e.response.text
         try:
             error_json = e.response.json()
             if 'error' in error_json: error_content = error_json['error']
         except json.JSONDecodeError: pass
         return f"Lỗi HTTP từ API: {e.response.status_code} {e.response.reason}. Nội dung lỗi: {error_content}", end_time - start_time
    except requests.exceptions.RequestException as e:
        end_time = time.time()
        return f"Lỗi yêu cầu API không xác định: {e}", end_time - start_time
    except json.JSONDecodeError:
        end_time = time.time()
        return f"Lỗi: Phản hồi từ API không phải là JSON hợp lệ. Nội dung nhận được:\n{response.text}", end_time - start_time
    except Exception as e:
        end_time = time.time()
        import traceback
        return f"Lỗi không xác định trong quá trình xử lý: {e}\n{traceback.format_exc()}", end_time - start_time


if __name__ == "__main__":
    print("\n🤖 Chatbot Luật Doanh nghiệp sẵn sàng!")
    print("   Nhập câu hỏi của bạn hoặc gõ 'quit' để thoát.")
    print("=" * 70)

    while True:
        try:
            user_input = input("👤 Bạn: ")
            if user_input.lower().strip() in ['quit', 'exit', 'bye', '']:
                print("\n👋 Tạm biệt!")
                break

            # print("\n⏳ Đang tìm kiếm và tạo câu trả lời...")
            bot_response, duration = ask_chatbot(user_input) # <-- Nhận cả thời gian
            print(f"\n🤖 Chatbot: {bot_response}")
            print(f"   (Thời gian phản hồi: {duration:.2f} giây)") # <-- Hiển thị thời gian
            print("=" * 70)

        except EOFError:
            print("\n👋 Tạm biệt!")
            break
        except KeyboardInterrupt:
             print("\n👋 Tạm biệt!")
             break