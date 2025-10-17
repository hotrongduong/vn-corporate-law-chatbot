# src/chatbot/management/commands/ingest_law_data.py

import re
from django.core.management.base import BaseCommand
from django.db import transaction
from chatbot.models import LawDocument, LawProvision

# --- Cấu hình ---
FILE_PATH = '/app/data/67_VBHN-VPQH_671127.txt'
DOCUMENT_TITLE = "Luật Doanh nghiệp (Văn bản hợp nhất 67/VBHN-VPQH)"
DOCUMENT_NUMBER = "67/VBHN-VPQH"

def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'\[\w+\]', '', text)
    text = text.replace('\uffef', '').replace('\ufeff', '')
    text = re.sub(r'\s+', ' ', text).strip()
    return text

class Command(BaseCommand):
    help = 'Xử lý và nạp dữ liệu từ văn bản luật vào cơ sở dữ liệu (phiên bản ổn định).'

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 Bắt đầu quá trình nạp dữ liệu luật...'))

        # --- 1. Tạo hoặc lấy văn bản luật gốc ---
        document, created = LawDocument.objects.update_or_create(
            title=DOCUMENT_TITLE,
            defaults={'document_number': DOCUMENT_NUMBER, 'source_file': FILE_PATH.split('/')[-1]}
        )
        if created:
            self.stdout.write(f"✅ Đã tạo mới văn bản: '{document.title}'")
        else:
            self.stdout.write(f"🔍 Sử dụng văn bản đã có: '{document.title}'. Đang xóa các điều khoản cũ...")
            LawProvision.objects.filter(document=document).delete()
            self.stdout.write("🗑️  Xóa dữ liệu cũ thành công.")

        # --- 2. Đọc file ---
        try:
            with open(FILE_PATH, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"❌ LỖI: Không tìm thấy file tại '{FILE_PATH}'."))
            return
        
        self.stdout.write("📖 Đọc file thành công. Bắt đầu bóc tách...")

        # --- 3. Bóc tách dữ liệu theo phương pháp mới ---
        # Regex để tìm tất cả các loại khối: Chương, Mục, Điều, Khoản, Điểm
        pattern = re.compile(
            r'^(?:(Chương\s+[A-Z]+)\n(.*?)\n|'  # Group 1, 2: Chương
            r'^(Mục\s+\d+)\n(.*?)\n|'          # Group 3, 4: Mục
            r'^(Điều\s+(\d+)\.\s+(.*?))\n|'    # Group 5, 6, 7: Điều
            r'^\s*(\d+)\.\s+(.*)|'              # Group 8, 9: Khoản
            r'^\s*([a-zđ])\)\s+(.*))',         # Group 10, 11: Điểm
            re.MULTILINE
        )

        provisions_to_create = []
        last_pos = 0
        current_context = {
            "chapter": "", "section": "", "article_number": 0, "article_title": ""
        }
        
        # Bỏ qua phần header của văn bản
        content_start = re.search(r'Chương I', content).start()
        
        for match in pattern.finditer(content[content_start:]):
            start, end = match.span()
            
            # Xử lý văn bản nằm giữa các match (thường là nội dung của Điều/Khoản)
            intermediate_text = clean_text(content[content_start + last_pos : content_start + start])
            if intermediate_text:
                # Đây là nội dung thuộc về Điều trước đó nhưng không có số Khoản
                 if current_context["article_number"] > 0:
                    provisions_to_create.append(LawProvision(
                        document=document, chapter_info=current_context["chapter"], section_info=current_context["section"],
                        article_number=current_context["article_number"], article_title=current_context["article_title"],
                        provision_id=None, content=intermediate_text
                    ))

            # Phân loại và cập nhật context
            if match.group(1): # Chương
                current_context["chapter"] = clean_text(f"{match.group(1)} {match.group(2)}")
                current_context["section"] = ""
            elif match.group(3): # Mục
                current_context["section"] = clean_text(f"{match.group(3)} {match.group(4)}")
            elif match.group(5): # Điều
                current_context["article_number"] = int(match.group(6))
                current_context["article_title"] = clean_text(match.group(7))
            elif match.group(8): # Khoản
                provisions_to_create.append(LawProvision(
                    document=document, chapter_info=current_context["chapter"], section_info=current_context["section"],
                    article_number=current_context["article_number"], article_title=current_context["article_title"],
                    provision_id=match.group(8), content=clean_text(match.group(9))
                ))
            elif match.group(10): # Điểm
                # Tìm khoản gần nhất để ghép ID
                last_clause_num = "unknown"
                for p in reversed(provisions_to_create):
                    if p.article_number == current_context["article_number"] and p.provision_id and '.' not in p.provision_id:
                        last_clause_num = p.provision_id
                        break
                
                provisions_to_create.append(LawProvision(
                    document=document, chapter_info=current_context["chapter"], section_info=current_context["section"],
                    article_number=current_context["article_number"], article_title=current_context["article_title"],
                    provision_id=f"{last_clause_num}.{match.group(10)}", content=clean_text(match.group(11))
                ))

            last_pos = end

        # Kiểm tra trùng lặp trước khi lưu
        seen_keys = set()
        unique_provisions = []
        for p in provisions_to_create:
            key = (p.document_id, p.article_number, p.provision_id)
            if key in seen_keys:
                self.stdout.write(self.style.WARNING(f"⚠️  Cảnh báo: Bỏ qua bản ghi trùng lặp - Điều {p.article_number}, Khoản {p.provision_id}"))
                continue
            seen_keys.add(key)
            unique_provisions.append(p)

        self.stdout.write(f"📊 Bóc tách hoàn tất. Chuẩn bị lưu {len(unique_provisions)} điều khoản vào database...")
        LawProvision.objects.bulk_create(unique_provisions)
        self.stdout.write(self.style.SUCCESS(f'🎉 Hoàn thành! Đã nạp thành công {len(unique_provisions)} điều/khoản luật.'))