import argparse
from typing import List
import logging
import time
import sys
import datahub.metadata.schema_classes as models
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.ingestion.graph.client import DatahubClientConfig, DataHubGraph
from datahub.metadata._schema_classes import DataProcessInstancePropertiesClass, AuditStampClass
from model import Model
from base_ml_entity import _BaseMLEntity
from dataset import DataSetModel
logger = logging.getLogger(__name__)
class Run(_BaseMLEntity):

    models: List[Model] = []
    input_datasets:List[DataSetModel] = []
    output_datasets:List[DataSetModel] = []

    def __init__(self,
                 run_id: str,
                 name: str,
                 client: DataHubGraph):
        self.run_id = run_id
        self.name = name
        self.client = client
        self.dpi_urn = f"urn:li:dataProcessInstance:{run_id}"

        self.dpi_subtypes = models.SubTypesClass(typeNames=["ML Training Run"])

        # Create the properties aspect
        self.dpi_props = DataProcessInstancePropertiesClass(
            name=name,
            created=AuditStampClass(
                time=int(time.time() * 1000), actor="urn:li:corpuser:datahub"
            ),
        )

        self._emit()

    def _emit(self):
        mcps = [
            MetadataChangeProposalWrapper(entityUrn=str(self.dpi_urn), aspect=self.dpi_props),
            MetadataChangeProposalWrapper(entityUrn=str(self.dpi_urn), aspect=self.dpi_subtypes),
        ]
        with client:
            for mcp in mcps:
                logger.debug(f"Emitting {mcp}")
                self.client.emit(mcp)

        logger.info(f"Emitted mcps: {len(mcps)}")

    def add_model(self, model):
        self.models(model)

    def add_input_dataset(self, dataset):
        self.input_datasets.append(dataset)

    def add_input_dataset(self, dataset):
        self.output_datasets.append(dataset)


if __name__ == "__main__":
    # Example usage
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", default="", help="DataHub access token")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout, format='%(asctime)s - %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')

    client = DataHubGraph(
        DatahubClientConfig(
            server="http://localhost:8080",
            token=args.token,
            extra_headers={"Authorization": f"Bearer {args.token}"},
        )
    )

    run = Run(
        run_id="simple_training_run_3",
        name="Simple Training Run 3",
        client=client
    )



