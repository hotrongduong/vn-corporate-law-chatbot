from sentence_transformers import SentenceTransformer
import torch

class EmbeddingModel:
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingModel, cls).__new__(cls)
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            model_name = 'bkai-foundation-models/vietnamese-bi-encoder'

            print(f"INFO: Đang tải mô hình '{model_name}' lên thiết bị '{device}'...")
            cls._model = SentenceTransformer(model_name, device=device)
            print("INFO: Tải mô hình embedding thành công.")
        return cls._instance

    def get_model(self):
        return self._model

embedding_model_loader = EmbeddingModel()

def get_embedding_model():
    return embedding_model_loader.get_model()
