import argparse
import time
import logging
from typing import List

import datahub.metadata.schema_classes as models
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.ingestion.graph.client import DatahubClientConfig, DataHubGraph
from datahub.metadata._urns.urn_defs import MlModelGroupUrn

from base_ml_entity import _BaseMLEntity
from model import Model

logger = logging.getLogger(__name__)
class Model_Group(_BaseMLEntity):

    models: List[Model] = None

    def __init__(self,
                 group_id: str,
                 name: str,
                 description: str,
                 platform: str,
                 custom_properties: dict =None,
                 client: DataHubGraph = None):
        super().__init__()
        self.group_id = group_id
        self.name = name
        self.description = description
        self.custom_properties = custom_properties
        self.platform = platform
        self.client = client
        # expose created_time / last_modified_time
        self.model_group_urn = MlModelGroupUrn(platform=platform, name=group_id)

        current_time = int(time.time() * 1000)
        self.model_group_info = models.MLModelGroupPropertiesClass(
            name=name,
            description=description,
            customProperties=custom_properties,
            created=models.TimeStampClass(
                time=current_time, actor="urn:li:corpuser:datahub"
            ),
            lastModified=models.TimeStampClass(
                time=current_time, actor="urn:li:corpuser:datahub"
            ),
        )

        self._emit()


    def _emit(self):
        mcp = MetadataChangeProposalWrapper(
            entityUrn=str(self.model_group_urn),
            entityType="mlModelGroup",
            aspectName="mlModelGroupProperties",
            aspect=self.model_group_info,
            changeType=models.ChangeTypeClass.UPSERT,
        )
        with client:
            client.emit(mcp)
            logger.info(f"Model group {self.group_id} created successfully!")
            logger.info(f"Model group URN: {self.model_group_urn}")



    def create_model(self,
                  model_id:str,
                  name:str,
                  description:str,
                  platform:str,
                  version:str
                  ):
        model = Model(
            model_id=model_id,
            name=name,
            description=description,
            platform=platform,
            version="1.0")

        models.append(model)
        return model


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

    model_group =  Model_Group(
        group_id="airline_forecast_models",
        name="Airline Forecast Models",
        description="ML models for airline passenger forecasting",
        platform="mlflow",
        custom_properties={"stage": "production", "team": "data_science"},
        client=client
    )




