import logging
from typing import Optional, cast
from zhipuai import ZhipuAI
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

logger = logging.getLogger(__name__)


class ZhiPuAIEmbeddingFunction(EmbeddingFunction[Documents]):
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = "https://open.bigmodel.cn/api/paas/v4/embeddings",
        model_name: str = "embedding-2"
    ):
        try:
            import zhipuai
        except ImportError:
            raise ValueError(
                "The zhipuai python package is not installed. Please install it with `pip install zhipuai`"
            )

        # If the api key is still not set, raise an error
        if api_key is None:
            raise ValueError(
                "Please provide an ZhipuAI API key."
            )

        self._client = ZhipuAI(api_key=api_key, base_url=api_base).embeddings
        self._model_name = model_name

    def __call__(self, input: Documents) -> Embeddings:
        """
        Generate the embeddings for the given `input`.

        Args:
            input (Documents): A list of texts to get embeddings for.

        Returns:
            Embeddings: The embeddings for the given input sorted by index
        """
        # replace newlines, which can negatively affect performance.
        input = [t.replace("\n", " ") for t in input]

        # Call the Embedding API
        embeddings = self._client.create(input=input, model=self._model_name).data

        # Sort resulting embeddings by index
        sorted_embeddings = sorted(
            embeddings, key=lambda e: e.index  # type: ignore
        )

        # Return just the embeddings
        return cast(
            Embeddings, [result.embedding for result in sorted_embeddings]
        )
