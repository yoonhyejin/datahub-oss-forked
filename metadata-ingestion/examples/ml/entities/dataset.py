import argparse
import logging
from datahub.ingestion.graph.client import DatahubClientConfig, DataHubGraph
from mlflow.data import Dataset
from base_ml_entity import _BaseMLEntity
from datahub.api.entities.dataset.dataset import Dataset

logger = logging.getLogger(__name__)
class DataSetModel(_BaseMLEntity):


    def __init__(self,
                 platform: str,
                 name:str,
                 client: DataHubGraph = None):
       super().__init__()
       self.platform = platform
       self.name = name
       self._emit()


    def emit(self):
        dataset = Dataset(id=self.name, platform=self.platform, name=self.name)
        mcps = list(dataset.generate_mcp())
        mcps = list(dataset.generate_mcp())
        self._emit_mcps(mcps)

if __name__ == "__main__":
    # Example usage
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", default="", help="DataHub access token")
    args = parser.parse_args()

    client = DataHubGraph(
        DatahubClientConfig(
            server="http://localhost:8080",
            token=args.token,
            extra_headers={"Authorization": f"Bearer {args.token}"},
        )
    )

    dataset =  DataSetModel(
        platform="snowflake",
        name="iris_input",
        client=client
    )



