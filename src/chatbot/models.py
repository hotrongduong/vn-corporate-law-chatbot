# src/chatbot/models.py
from django.db import models
import uuid

class LawDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField("Tiêu đề văn bản", max_length=500, unique=True)
    document_number = models.CharField("Số hiệu văn bản", max_length=100, blank=True, null=True)
    publication_date = models.DateField("Ngày ban hành", blank=True, null=True)
    effective_date = models.DateField("Ngày có hiệu lực", blank=True, null=True)
    source_file = models.CharField("Tên file gốc", max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Văn bản Luật"
        verbose_name_plural = "Các Văn bản Luật"


class LawProvision(models.Model):
    class ProvisionStatus(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Có hiệu lực'
        AMENDED = 'AMENDED', 'Được sửa đổi'
        REPEALED = 'REPEALED', 'Bị bãi bỏ'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(LawDocument, on_delete=models.CASCADE, related_name='provisions', verbose_name="Thuộc văn bản")

    chapter_info = models.CharField("Thông tin Chương", max_length=500, blank=True, null=True)
    section_info = models.CharField("Thông tin Mục", max_length=500, blank=True, null=True)
    article_number = models.IntegerField("Số Điều")
    article_title = models.CharField("Tiêu đề Điều", max_length=1000)
    provision_id = models.CharField("Số Khoản/Điểm", max_length=50, blank=True, null=True, help_text="Ví dụ: '1', '2', '3.a', '3.b'")
    
    content = models.TextField("Nội dung chính")

    status = models.CharField("Trạng thái hiệu lực", max_length=20, choices=ProvisionStatus.choices, default=ProvisionStatus.ACTIVE)
    modification_note = models.TextField("Ghi chú sửa đổi", blank=True, null=True, help_text="Ví dụ: Sửa đổi, bổ sung bởi Luật số 76/2025/QH15")
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Điều {self.article_number}, Khoản/Điểm {self.provision_id or ''}"

    class Meta:
        verbose_name = "Điều/Khoản Luật"
        verbose_name_plural = "Các Điều/Khoản Luật"
        ordering = ['document', 'article_number', 'id']
        unique_together = ('document', 'article_number', 'provision_id')