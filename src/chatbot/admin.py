from django.contrib import admin
from .models import LawDocument, LawProvision

@admin.register(LawDocument)
class LawDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'document_number', 'effective_date', 'source_file')
    search_fields = ('title', 'document_number')

@admin.register(LawProvision)
class LawProvisionAdmin(admin.ModelAdmin):
    list_display = ('article_number', 'provision_id', 'article_title', 'status', 'document')
    list_filter = ('document', 'status', 'article_number')
    search_fields = ('content', 'article_title')
    list_per_page = 20
    raw_id_fields = ('document',)