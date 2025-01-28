import argparse
from typing import Optional, List
import logging
import sys
import datahub.metadata.schema_classes as models
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.ingestion.graph.client import DatahubClientConfig, DataHubGraph
from datahub.metadata.urns import ContainerUrn, DataPlatformUrn
from base_ml_entity import _BaseMLEntity
from run import Run

logger = logging.getLogger(__name__)
class Experiment(_BaseMLEntity):

    run_ids: List[str] = None

    def __init__(self,
                 experiment_id: str,
                 name: str,
                 description: str,
                 platform: str,
                 custom_properties: dict,
                 created_time: Optional[int] = None ,
                 last_modified_time: Optional[int] = None,
                 client: DataHubGraph = None):
        super().__init__()

        self.experiment_id = experiment_id
        self.name = name
        self.description = description
        self.platform = platform
        self.custom_properties = custom_properties
        self.client = client

        self.experiment_urn = ContainerUrn(guid=self.experiment_id)
        self.platform_urn = DataPlatformUrn(platform_name=self.platform)
        self.container_subtype = models.SubTypesClass(typeNames=["ML Experiment"])
        self.container_info = models.ContainerPropertiesClass(
            name=self.name,
            description=self.description,
            customProperties=self.custom_properties,
            created=models.TimeStampClass(
                time=created_time, actor="urn:li:corpuser:datahub"
            ),
            lastModified=models.TimeStampClass(
                time=last_modified_time, actor="urn:li:corpuser:datahub"
            )
        )
        self.browse_path = models.BrowsePathsV2Class(path=[])
        self.platform_instance = models.DataPlatformInstanceClass(
            platform=str(self.platform_urn),
        )

        self._emit()


    def _emit(self):
        # Generate metadata change proposal
        mcps = MetadataChangeProposalWrapper.construct_many(
            entityUrn=str(self.experiment_urn),
            aspects=[self.container_subtype, self.container_info, self.browse_path, self.platform_instance],
        )

        with self.client:
            for mcp in mcps:
                logger.debug(f"emitting {mcp}")
                self.client.emit(mcp)
        logger.debug(f"finished emitting {len(mcps)} mcps")

    def _create_new_run_index(self, run_id: str) -> int:
        run_ind = len(self.run_ids) + 1
        return f"urn:li:dataProcessInstance:{run_id}-{run_ind}"

    def create_run(self, run_id: str, name: str):
        # TODO: CREATE relationship between experiment and run here

        run_id = self._create_new_run_index(run_id)

        run = Run(
            run_id=run_id,
            name=name,
            client=self.client
        )
        self.run_ids.append(run_id)
        return run


    # def create_run(self,
    #               name:str,
    #               created_time: int,
    #               custom_properties: dict,
    #               training_run_properties,
    #               run_result,
    #               start_time,
    #               end_time
    #               ):
    #
    #     run_id = self._create_new_run_id()
    #
    #     run = Run(
    #         run_id=run_id,
    #         properties=models.DataProcessInstancePropertiesClass(
    #             name=name,
    #             created=models.AuditStampClass(
    #                 time=created_time, actor="urn:li:corpuser:datahub"
    #             ),
    #             customProperties=custom_properties,
    #         ),
    #         training_run_properties=training_run_properties,
    #         run_result=run_result,
    #         start_timestamp=start_time,
    #         end_timestamp=end_time,
    #         client=self.client
    #     )
    #     self.run_ids.append(run_id)
    #     return run


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

    experiment = Experiment(experiment_id="airline_forecast_experiment",
                     name="Airline Forecast Experiment",
                     description="Experiment for forecasting airline passengers",
                     platform="mlflow",
                     custom_properties={"experiment_type": "forecasting"},
                     created_time=1628580000000,
                     last_modified_time=1628580000000,
                     client=client)




