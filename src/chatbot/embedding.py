from sentence_transformers import SentenceTransformer
import torch
import torch.quantization
class EmbeddingModel:
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            print("INFO: Đang khởi tạo instance EmbeddingModel...")
            cls._instance = super(EmbeddingModel, cls).__new__(cls)
            device = 'cpu'
            model_name = 'bkai-foundation-models/vietnamese-bi-encoder'

            print(f"INFO: Đang tải mô hình '{model_name}' lên thiết bị '{device}'...")
            original_model = SentenceTransformer(model_name, device=device)
            print("INFO: Tải mô hình embedding thành công.")

            # -- start dynamic quantization --
            print(f"INFO: Đang áp dụng Quantization Động (int8) cho mô hình...")
            try:
                transformer_module = original_model._first_module()
                quantized_model_transformer = torch.quantization.quantize_dynamic(
                    transformer_module,
                    {torch.nn.Linear},
                    dtype=torch.qint8
                )
                original_model._modules['_modules']['0'] = quantized_model_transformer()

                cls._model = original_model
                print("INFO: Áp dụng Quantization Động thành công.")
            except Exception as e:
                print(f"WARNING: Không thể áp dụng Quantization Động: {e}. Sử dụng mô hình gốc.")
                cls._model = original_model
    
        return cls._instance

    def get_model(self):
        if self._model is None:
            raise RuntimeError("Mô hình chưa được khởi tạo!")
        return self._model

embedding_model_loader = EmbeddingModel()

def get_embedding_model():
    return embedding_model_loader.get_model()
