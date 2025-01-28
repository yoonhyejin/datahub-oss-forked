import argparse
import logging
from typing import List

import datahub.metadata.schema_classes as models
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.ingestion.graph.client import DatahubClientConfig, DataHubGraph
from datahub.metadata._urns.urn_defs import MlModelUrn, VersionSetUrn

from base_ml_entity import _BaseMLEntity

logger = logging.getLogger(__name__)
class Model(_BaseMLEntity):

    models: List[str] = None

    def __init__(self,
                 model_id: str,
                 name: str,
                 description: str,
                 platform: str,
                 version: str,
                 client: DataHubGraph = None):
       super().__init__()
       self.model_urn = MlModelUrn(platform=platform, name=model_id)
       self.version_set_urn = VersionSetUrn(
           id=f"mlmodel_{model_id}_versions", entity_type="mlModel"
       )

       # Create model properties
       self.model_properties = models.MLModelPropertiesClass(
           name=name,
           description=description,
       )

       # Create version properties
       self.version_properties = models.VersionPropertiesClass(
           version=models.VersionTagClass(versionTag=version),
           versionSet=str(self.version_set_urn),
           sortId="AAAAAAAA",
       )

       # Create version set properties
       self.version_set_properties = models.VersionSetPropertiesClass(
           latest=str(self.model_urn),
           versioningScheme="ALPHANUMERIC_GENERATED_BY_DATAHUB",
       )

       self._emit()


    def _emit(self):
        mcps = [
            MetadataChangeProposalWrapper(
                entityUrn=str(self.model_urn),
                entityType="mlModel",
                aspectName="mlModelProperties",
                aspect=self.model_properties,
                changeType=models.ChangeTypeClass.UPSERT,
            ),
            MetadataChangeProposalWrapper(
                entityUrn=str(self.version_set_urn),
                entityType="versionSet",
                aspectName="versionSetProperties",
                aspect=self.version_set_properties,
                changeType=models.ChangeTypeClass.UPSERT,
            ),
            MetadataChangeProposalWrapper(
                entityUrn=str(self.model_urn),
                entityType="mlModel",
                aspectName="versionProperties",
                aspect=self.version_properties,
                changeType=models.ChangeTypeClass.UPSERT,
            ),
        ]

        with client:
            for mcp in mcps:
                client.emit(mcp)



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

    model =  Model(
        model_id="arima_model_1",
        name="ARIMA Model 1",
        description="ARIMA model for airline passenger forecasting",
        platform="mlflow",
        version="1.0")




