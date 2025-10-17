import os
from django.core.management.base import BaseCommand
from chatbot.models import LawProvision
from chatbot.embedding import get_embedding_model
from qdrant_client import QdrantClient, models

# --- Configs ---
QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "luat_doanh_nghiep_v1")

class Command(BaseCommand):
    help = "Tạo vector embeddings từ LawProvision và nạp vào Qdrant."

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Bắt đầu quá trình tạo vector và nạp vào Qdrant..."))

        # -- embedding model loading --
        try:
            model = get_embedding_model()
            vector_size = model.get_sentence_embedding_dimension()
            self.stdout.write(f"Kích thước vector: {vector_size}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Lỗi khi tải mô hình embedding: {e}"))

            return

        # -- connect to qdrant --
        try:
            qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
            qdrant_client.get_collections()
            self.stdout.write(f"Kết nối thành công tới Qdrant tại {QDRANT_HOST}:{QDRANT_PORT}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Lỗi khi tạo/tái tạo collection Qdrant: {e}"))
            return
        
        # --- ensuring collection exists ---
        try:
            collection_exists = False
            try:
                qdrant_client.get_collection(collection_name=QDRANT_COLLECTION)
                collection_exists = True
                self.stdout.write(f"Collection '{QDRANT_COLLECTION}' đã tồn tại.")
            except Exception as e:
                 if "not found" in str(e).lower() or "doesn't exist" in str(e).lower() or "status_code=404" in str(e).lower():
                    self.stdout.write(f"Collection '{QDRANT_COLLECTION}' chưa tồn tại.")
                    collection_exists = False
                 else:
                    self.stdout.write(self.style.ERROR(f"Lỗi không mong đợi khi kiểm tra collection: {e}"))
                    return

            if not collection_exists:
                self.stdout.write(f"Đang tạo collection '{QDRANT_COLLECTION}'...")
                qdrant_client.create_collection(
                    collection_name=QDRANT_COLLECTION,
                    vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE), # <-- Sử dụng vector_size đã định nghĩa
                )
                self.stdout.write(f"Đã tạo collection '{QDRANT_COLLECTION}' thành công.")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Lỗi trong quá trình đảm bảo collection tồn tại: {e}"))
            return

        # -- get all provisions from PostgreSQL --
        all_provisions = list(LawProvision.objects.all())
        if not all_provisions:
            self.stdout.write(self.style.WARNING("Không tìm thấy điều khoản nào trong PostgreSQL để tạo embedding."))
            return
        
        # -- create embedding for content --
        self.stdout.write(f"Đang tạo embeddings cho {len(all_provisions)} điều khoản (có thể mất vài phút)...")
        try:
            contents_to_embed = [
                f"Điều {p.article_number} {p.article_title or ''}, Khoản {p.provision_id or 'chung'}: {p.content}"
                for p in all_provisions
            ]
            vectors = model.encode(contents_to_embed, show_progress_bar=True, batch_size=32)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Lỗi trong quá trình tạo embedding: {e}"))
            return

        # -- preparing and loading data to qdrant
        self.stdout.write("Chuẩn bị tải dữ liệu vector lên Qdrant...")
        points_to_upload = []
        for i, p in enumerate(all_provisions):
            points_to_upload.append(
                models.PointStruct(
                    id=str(p.id),
                    vector=vectors[i].tolist(),
                    payload={"postgres_id": str(p.id)}
                )
            )

        try:
            batch_size = 100
            for i in range(0, len(points_to_upload), batch_size):
                batch = points_to_upload[i: i+batch_size]
                qdrant_client.upsert(
                    collection_name=QDRANT_COLLECTION,
                    points=batch,
                    wait=True
                )
                self.stdout.write(f"    -> Đã tải lên {min(i + batch_size, len(points_to_upload))}/{len(points_to_upload)} điểm.")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Lỗi khi tải dữ liệu lên Qdrant: {e}"))
            return
        
        self.stdout.write(self.style.SUCCESS(f"Hoàn thành! Đã nạp thành công {len(all_provisions)} vector vào Qdrant."))