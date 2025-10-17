import os
import json
import logging
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from qdrant_client import QdrantClient, models
import google.generativeai as genai

from .embedding import get_embedding_model
from .models import LawProvision

# -- configure logging --
logger = logging.getLogger(__name__)

# -- configuration --
QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = os.getenv("QDRANT_PORT", 6333)
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "luat_doanh_nghiep_v1")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# -- initialize clients --
qdrant_client = None
embedding_model = None
gemini_model = None
initialization_error = None

try:
    if not GEMINI_API_KEY:
        raise ValueError("Không tìm thấy GEMINI_API_KEY trong biến môi trường.")
    
    logger.info("Đang khởi tạo Qdrant client...")
    qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    qdrant_client.get_collections()
    logger.info("Khởi tạo Qdrant client thành công.")

    logger.info("Đang khởi tạo mô hình embedding...")
    embedding_model = get_embedding_model()
    logger.info("Khởi tạo mô hình embedding thành công.")
    
    logger.info("Đang cấu hình Gemini API...")
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-2.5-pro')
    logger.info("Khởi tạo mô hình Gemini thành công.")

except Exception as e:
    logger.exception(f"LỖI NGHIÊM TRỌNG: Lỗi trong quá trình khởi tạo client: {e}")
    initialization_error = str(e)

@method_decorator(csrf_exempt, name='dispatch')
class ChatbotAPIView(View):
    def post(self, request, *args, **kwargs):
        if initialization_error:
            logger.error(f"Dịch vụ chatbot không sẵn sàng do lỗi khởi tạo: {initialization_error}")
            return JsonResponse({"error": f"Dịch vụ chatbot không sẵn sàng: {initialization_error}"}, status=503)

        # -- request analyzing --
        try:
            data = json.loads(request.body)
            query = data.get('question')
            if not query or not isinstance(query, str) or not query.strip():
                logger.warning("Nhận được yêu cầu không hợp lệ: Thiếu hoặc 'question' rỗng.")
                return HttpResponseBadRequest("Yêu cầu không hợp lệ: Thiếu hoặc 'question' rỗng.")   
            logger.info(f"Nhận được câu hỏi: {query}")
        except json.JSONDecodeError:
            logger.warning("Nhận được yêu cầu không hợp lệ: JSON không hợp lệ.")
            return HttpResponseBadRequest("Yêu cầu không hợp lệ: JSON không hợp lệ.")

        # -- rag (retrieval-augmented generation) process --
        try:
            # -- prompt embedding -- 
            logger.debug("Đang tạo embedding cho câu hỏi...")
            query_vector = embedding_model.encode(query).tolist()
            logger.debug("Tạo embedding câu hỏi thành công.")

            # -- qdrant vector searching --
            logger.debug("Đang tìm kiếm điều khoản liên quan trong Qdrant...")
            search_result = qdrant_client.search(
                collection_name=QDRANT_COLLECTION,
                query_vector=query_vector,
                limit=5
            )
            hit_ids = [hit.id for hit in search_result]
            logger.info(f"Tìm thấy {len(hit_ids)} ID điều khoản liên quan trong Qdrant.")
            logger.debug(f"Các ID liên quan: {hit_ids}")

            # -- get content from postgresql --
            relevant_provisions = LawProvision.objects.filter(id__in=hit_ids)
            if not relevant_provisions:
                logger.warning("Không tìm thấy điều khoản nào trong PostgreSQL khớp với ID từ Qdrant.")
                answer = "Tôi không tìm thấy điều khoản luật nào liên quan trực tiếp đến câu hỏi của bạn."
                sources = []
            else:
                logger.debug(f"Lấy được {relevant_provisions.count()} điều khoản từ PostgreSQL.")

                # -- building context and prompt for gemini --
                context_parts = []
                for i, p in enumerate(relevant_provisions):
                    context_prefix = f"Trích đoạn {i+1} (Lấy từ "
                    if p.chapter_info: context_prefix += f"{p.chapter_info}, "
                    if p.section_info: context_prefix += f"{p.section_info}, "
                    context_prefix += f"Điều {p.article_number}, Khoản {p.provision_id or 'chung'}):"
                    context_parts.append(f"{context_prefix}\n{p.content}")
                context = "\n\n".join(context_parts)
                prompt = f"""Dựa vào các trích đoạn sau từ Luật Doanh nghiệp Việt Nam: {context} 
                Hãy trả lời câu hỏi sau của người dùng một cách cực kìkì chi tiết, đầy đủ, 
                chính xác, không cắt bớt và CHỈ sử dụng thông tin từ các trích đoạn đã cung cấp. 
                Luôn trả lời bằng tiếng Việt. Nếu thông tin không có trong trích đoạn, 
                hãy trả lời "Tôi không tìm thấy thông tin liên quan trong các điều khoản được cung cấp.". 
                Không được suy diễn hoặc thêm thông tin bên ngoài. Câu hỏi: "{query}" Trả lời:"""
                logger.debug(f"Prompt đã tạo cho Gemini:\n{prompt}")

                # -- gemini api calling --
                logger.info("Đang gọi Gemini API...")
                try:
                    response = gemini_model.generate_content(prompt)
                    answer = response.text
                    logger.info("Nhận được câu trả lời từ Gemini.")
                    logger.debug(f"Phản hồi thô từ Gemini: {answer}")
                except Exception as gen_e:
                    logger.exception(f"Lỗi khi gọi Gemini API: {gen_e}")
                    answer = "Xin lỗi, tôi gặp sự cố khi tạo câu trả lời. Tuy nhiên, tôi tìm thấy các điều khoản sau có liên quan:\n" + "\n".join([f"- Điều {p.article_number}, Khoản {p.provision_id or 'chung'}" for p in relevant_provisions])
                # -- source information preparing --
                sources = [
                    {
                        "id": str(p.id),
                        "document": p.document.title,
                        "chapter": p.chapter_info or "N/A",
                        "section": p.section_info or "N/A",
                        "article": p.article_number,
                        "provision": p.provision_id or "N/A",
                        "score": next((hit.score for hit in search_result if hit.id == str(p.id)), None)
                    } for p in relevant_provisions
                ]
        except Exception as e:
            logger.exception(f"Lỗi trong quy trình RAG: {e}")
            return JsonResponse({"error": "Đã xảy ra lỗi trong quá trình xử lý yêu cầu."}, status=500)

        # -- send a respose --
        response_data = {
            "question": query,
            "answer": answer.strip(),
            "sources": sources
        }
        logger.info("Đang gửi phản hồi cho client.")
        logger.debug(f"Dữ liệu phản hồi: {response_data}")
        return JsonResponse(response_data)