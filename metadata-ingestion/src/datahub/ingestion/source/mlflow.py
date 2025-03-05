import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable, List, Optional, TypeVar, Union

from mlflow import MlflowClient
from mlflow.entities import Experiment, Run
from mlflow.entities.model_registry import ModelVersion, RegisteredModel
from mlflow.store.entities import PagedList
from pydantic.fields import Field

import datahub.emitter.mce_builder as builder
from datahub.api.entities.dataprocess.dataprocess_instance import (
    DataProcessInstance,
)
from datahub.configuration.source_common import EnvConfigMixin
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.mcp_builder import ContainerKey
from datahub.ingestion.api.common import PipelineContext
from datahub.ingestion.api.decorators import (
    SupportStatus,
    capability,
    config_class,
    platform_name,
    support_status,
)
from datahub.ingestion.api.source import (
    MetadataWorkUnitProcessor,
    SourceCapability,
    SourceReport,
)
from datahub.ingestion.api.workunit import MetadataWorkUnit
from datahub.ingestion.source.common.subtypes import MLAssetSubTypes
from datahub.ingestion.source.state.stale_entity_removal_handler import (
    StaleEntityRemovalHandler,
    StaleEntityRemovalSourceReport,
)
from datahub.ingestion.source.state.stateful_ingestion_base import (
    StatefulIngestionConfigBase,
    StatefulIngestionSourceBase,
)
from datahub.metadata.schema_classes import (
    AuditStampClass,
    BrowsePathsV2Class,
    ContainerClass,
    ContainerPropertiesClass,
    DataPlatformInstanceClass,
    DataProcessInstanceOutputClass,
    DataProcessInstancePropertiesClass,
    DataProcessInstanceRunEventClass,
    DataProcessInstanceRunResultClass,
    DataProcessRunStatusClass,
    GlobalTagsClass,
    MetadataAttributionClass,
    MLHyperParamClass,
    MLMetricClass,
    MLModelGroupPropertiesClass,
    MLModelPropertiesClass,
    MLTrainingRunPropertiesClass,
    SubTypesClass,
    TagAssociationClass,
    TagPropertiesClass,
    TimeStampClass,
    VersionPropertiesClass,
    VersionSetPropertiesClass,
    VersionTagClass,
    _Aspect,
)
from datahub.metadata.urns import (
    DataPlatformUrn,
    VersionSetUrn,
)
from datahub.sdk.container import Container
from datahub.ingestion.graph.client import DataHubGraph, get_default_graph

T = TypeVar("T")


class ContainerKeyWithId(ContainerKey):
    id: str


class MLflowConfig(StatefulIngestionConfigBase, EnvConfigMixin):
    tracking_uri: Optional[str] = Field(
        default=None,
        description=(
            "Tracking server URI. If not set, an MLflow default tracking_uri is used"
            " (local `mlruns/` directory or `MLFLOW_TRACKING_URI` environment variable)"
        ),
    )
    registry_uri: Optional[str] = Field(
        default=None,
        description=(
            "Registry server URI. If not set, an MLflow default registry_uri is used"
            " (value of tracking_uri or `MLFLOW_REGISTRY_URI` environment variable)"
        ),
    )
    model_name_separator: str = Field(
        default="_",
        description="A string which separates model name from its version (e.g. model_1 or model-1)",
    )
    base_external_url: Optional[str] = Field(
        default=None,
        description=(
            "Base URL to use when constructing external URLs to MLflow."
            " If not set, tracking_uri is used if it's an HTTP URL."
            " If neither is set, external URLs are not generated."
        ),
    )


@dataclass
class MLflowRegisteredModelStageInfo:
    name: str
    description: str
    color_hex: str


@platform_name("MLflow")
@config_class(MLflowConfig)
@support_status(SupportStatus.TESTING)
@capability(
    SourceCapability.DESCRIPTIONS,
    "Extract descriptions for MLflow Registered Models and Model Versions",
)
@capability(SourceCapability.TAGS, "Extract tags for MLflow Registered Model Stages")
class MLflowSource(StatefulIngestionSourceBase):
    platform = "mlflow"
    registered_model_stages_info = (
        MLflowRegisteredModelStageInfo(
            name="Production",
            description="Production Stage for an ML model in MLflow Model Registry",
            color_hex="#308613",
        ),
        MLflowRegisteredModelStageInfo(
            name="Staging",
            description="Staging Stage for an ML model in MLflow Model Registry",
            color_hex="#FACB66",
        ),
        MLflowRegisteredModelStageInfo(
            name="Archived",
            description="Archived Stage for an ML model in MLflow Model Registry",
            color_hex="#5D7283",
        ),
        MLflowRegisteredModelStageInfo(
            name="None",
            description="None Stage for an ML model in MLflow Model Registry",
            color_hex="#F2F4F5",
        ),
    )

    def __init__(self, ctx: PipelineContext, config: MLflowConfig):
        super().__init__(config, ctx)
        self.ctx = ctx
        self.config = config
        self.report = StaleEntityRemovalSourceReport()
        self.client = MlflowClient(
            tracking_uri=self.config.tracking_uri,
            registry_uri=self.config.registry_uri,
        )
        self.graph = get_default_graph()

    def get_report(self) -> SourceReport:
        return self.report

    def get_workunit_processors(self) -> List[Optional[MetadataWorkUnitProcessor]]:
        return [
            *super().get_workunit_processors(),
            StaleEntityRemovalHandler.create(
                self, self.config, self.ctx
            ).workunit_processor,
        ]

    def get_workunits_internal(self) -> Iterable[MetadataWorkUnit]:
        yield from self._get_tags_workunits()
        yield from self._get_experiment_workunits()
        yield from self._get_ml_model_workunits()

    def _get_tags_workunits(self) -> Iterable[MetadataWorkUnit]:
        """
        Create tags for each Stage in MLflow Model Registry.
        """
        for stage_info in self.registered_model_stages_info:
            tag_urn = self._make_stage_tag_urn(stage_info.name)
            tag_properties = TagPropertiesClass(
                name=self._make_stage_tag_name(stage_info.name),
                description=stage_info.description,
                colorHex=stage_info.color_hex,
            )
            wu = self._create_workunit(urn=tag_urn, aspect=tag_properties)
            yield wu

    def _make_stage_tag_urn(self, stage_name: str) -> str:
        tag_name = self._make_stage_tag_name(stage_name)
        tag_urn = builder.make_tag_urn(tag_name)
        return tag_urn

    def _make_stage_tag_name(self, stage_name: str) -> str:
        return f"{self.platform}_{stage_name.lower()}"

    def _create_workunit(self, urn: str, aspect: _Aspect) -> MetadataWorkUnit:
        """
        Utility to create an MCP workunit.
        """
        return MetadataChangeProposalWrapper(
            entityUrn=urn,
            aspect=aspect,
        ).as_workunit()

    def _get_experiment_workunits(self) -> Iterable[MetadataWorkUnit]:
        experiments = self._get_mlflow_experiments()
        for experiment in experiments:
            yield from self._get_experiment_container_workunit(experiment)

            runs = self._get_mlflow_runs_from_experiment(experiment)
            if runs:
                for run in runs:
                    yield from self._get_run_workunits(experiment, run)

    def _get_experiment_custom_properties(self, experiment):
        experiment_custom_props = getattr(experiment, "tags", {}) or {}
        experiment_custom_props.pop("mlflow.note.content", None)
        experiment_custom_props["artifacts_location"] = experiment.artifact_location
        return experiment_custom_props

    def _get_experiment_container_workunit(
        self, experiment: Experiment
    ) -> Iterable[MetadataWorkUnit]:
        experiment_container = Container(
            container_key=ContainerKeyWithId(
                platform=str(DataPlatformUrn(platform_name=self.platform)),
                id=experiment.name,
            ),
            subtype=MLAssetSubTypes.MLFLOW_EXPERIMENT,
            display_name=experiment.name,
            description=experiment.tags.get("mlflow.note.content"),
        )

        yield MetadataChangeProposalWrapper(
            entityUrn=str(experiment_container.urn),
            aspect=SubTypesClass(typeNames=[str(experiment_container.subtype)]),
        ).as_workunit()

        yield MetadataChangeProposalWrapper(
            entityUrn=str(experiment_container.urn),
            aspect=ContainerPropertiesClass(
                name=experiment_container.display_name,
                description=experiment_container.description,
                customProperties=self._get_experiment_custom_properties(experiment),
            ),
        ).as_workunit()

        yield MetadataChangeProposalWrapper(
            entityUrn=str(experiment_container.urn),
            aspect=BrowsePathsV2Class(path=[]),
        ).as_workunit()

        yield MetadataChangeProposalWrapper(
            entityUrn=str(experiment_container.urn),
            aspect=DataPlatformInstanceClass(
                platform=str(DataPlatformUrn(self.platform)),
            ),
        ).as_workunit()

    def _get_run_metrics(self, run: Run) -> List[MLMetricClass]:
        return [
            MLMetricClass(name=k, value=str(v)) for k, v in run.data.metrics.items()
        ]

    def _get_run_params(self, run: Run) -> List[MLHyperParamClass]:
        return [
            MLHyperParamClass(name=k, value=str(v)) for k, v in run.data.params.items()
        ]

    def _convert_run_result_type(
        self, status: str
    ) -> DataProcessInstanceRunResultClass:
        if status == "FINISHED":
            return DataProcessInstanceRunResultClass(
                type="SUCCESS", nativeResultType=self.platform
            )
        elif status == "FAILED":
            return DataProcessInstanceRunResultClass(
                type="FAILURE", nativeResultType=self.platform
            )
        else:
            return DataProcessInstanceRunResultClass(
                type="SKIPPED", nativeResultType=self.platform
            )

    def _get_run_workunits(
        self, experiment: Experiment, run: Run
    ) -> Iterable[MetadataWorkUnit]:
        experiment_key = ContainerKeyWithId(
            platform=str(DataPlatformUrn(self.platform)), id=experiment.name
        )

        data_process_instance = DataProcessInstance(
            id=run.info.run_id,
            orchestrator=self.platform,
            template_urn=None,
        )

        created_time = run.info.start_time or int(time.time() * 1000)
        created_actor = (
            f"urn:li:platformResource:{run.info.user_id}" if run.info.user_id else ""
        )

        yield MetadataChangeProposalWrapper(
            entityUrn=str(data_process_instance.urn),
            aspect=DataProcessInstancePropertiesClass(
                name=run.info.run_name or run.info.run_id,
                created=AuditStampClass(
                    time=created_time,
                    actor=created_actor,
                ),
                externalUrl=self._make_external_url_from_run(experiment, run),
                customProperties=getattr(run, "tags", {}) or {},
            ),
        ).as_workunit()

        yield MetadataChangeProposalWrapper(
            entityUrn=str(data_process_instance.urn),
            aspect=ContainerClass(container=experiment_key.as_urn()),
        ).as_workunit()

        model_versions = self.get_mlflow_model_versions_from_run(run.info.run_id)
        if model_versions:
            model_version_urn = self._make_ml_model_urn(model_versions[0])
            yield MetadataChangeProposalWrapper(
                entityUrn=str(data_process_instance.urn),
                aspect=DataProcessInstanceOutputClass(outputs=[model_version_urn]),
            ).as_workunit()

        metrics = self._get_run_metrics(run)
        hyperparams = self._get_run_params(run)
        yield MetadataChangeProposalWrapper(
            entityUrn=str(data_process_instance.urn),
            aspect=MLTrainingRunPropertiesClass(
                hyperParams=hyperparams,
                trainingMetrics=metrics,
                outputUrls=[run.info.artifact_uri],
                id=run.info.run_id,
            ),
        ).as_workunit()

        if run.info.end_time:
            duration_millis = run.info.end_time - run.info.start_time

            yield MetadataChangeProposalWrapper(
                entityUrn=str(data_process_instance.urn),
                aspect=DataProcessInstanceRunEventClass(
                    status=DataProcessRunStatusClass.COMPLETE,
                    timestampMillis=run.info.end_time,
                    result=DataProcessInstanceRunResultClass(
                        type=self._convert_run_result_type(run.info.status).type,
                        nativeResultType=self.platform,
                    ),
                    durationMillis=duration_millis,
                ),
            ).as_workunit()

        yield MetadataChangeProposalWrapper(
            entityUrn=str(data_process_instance.urn),
            aspect=DataPlatformInstanceClass(
                platform=str(DataPlatformUrn(self.platform))
            ),
        ).as_workunit()

        yield MetadataChangeProposalWrapper(
            entityUrn=str(data_process_instance.urn),
            aspect=SubTypesClass(typeNames=[MLAssetSubTypes.MLFLOW_TRAINING_RUN]),
        ).as_workunit()

    def _get_mlflow_registered_models(self) -> Iterable[RegisteredModel]:
        """
        Get all Registered Models in MLflow Model Registry.
        """
        registered_models: Iterable[RegisteredModel] = (
            self._traverse_mlflow_search_func(
                search_func=self.client.search_registered_models,
            )
        )
        return registered_models

    def _get_mlflow_experiments(self) -> Iterable[Experiment]:
        experiments: Iterable[Experiment] = self._traverse_mlflow_search_func(
            search_func=self.client.search_experiments,
        )
        return experiments

    def _get_mlflow_runs_from_experiment(self, experiment: Experiment) -> Iterable[Run]:
        runs: Iterable[Run] = self._traverse_mlflow_search_func(
            search_func=self.client.search_runs,
            experiment_ids=[experiment.experiment_id],
        )
        return runs

    @staticmethod
    def _traverse_mlflow_search_func(
        search_func: Callable[..., PagedList[T]],
        **kwargs: Any,
    ) -> Iterable[T]:
        """
        Utility to traverse an MLflow search_* functions which return PagedList.
        """
        next_page_token = None
        while True:
            paged_list = search_func(page_token=next_page_token, **kwargs)
            yield from paged_list.to_list()
            next_page_token = paged_list.token
            if not next_page_token:
                return

    def _get_latest_version(self, registered_model: RegisteredModel) -> Optional[str]:
        return (
            str(registered_model.latest_versions[0].version)
            if registered_model.latest_versions
            else None
        )

    def _get_ml_group_workunit(
        self,
        registered_model: RegisteredModel,
    ) -> MetadataWorkUnit:
        """
        Generate an MLModelGroup workunit for an MLflow Registered Model.
        """
        ml_model_group_urn = self._make_ml_model_group_urn(registered_model)
        ml_model_group_properties = MLModelGroupPropertiesClass(
            customProperties=registered_model.tags,
            description=registered_model.description,
            created=TimeStampClass(
                time=registered_model.creation_timestamp, actor=None
            ),
            lastModified=TimeStampClass(
                time=registered_model.last_updated_timestamp,
                actor=None,
            ),
            version=VersionTagClass(
                versionTag=self._get_latest_version(registered_model),
                metadataAttribution=MetadataAttributionClass(
                    time=registered_model.last_updated_timestamp,
                    actor="urn:li:corpuser:datahub",
                ),
            ),
        )
        wu = self._create_workunit(
            urn=ml_model_group_urn,
            aspect=ml_model_group_properties,
        )
        return wu

    def _make_ml_model_group_urn(self, registered_model: RegisteredModel) -> str:
        urn = builder.make_ml_model_group_urn(
            platform=self.platform,
            group_name=registered_model.name,
            env=self.config.env,
        )
        return urn

    def _get_mlflow_model_versions(
        self,
        registered_model: RegisteredModel,
    ) -> Iterable[ModelVersion]:
        """
        Get all Model Versions for each Registered Model.
        """
        filter_string = f"name = '{registered_model.name}'"
        model_versions: Iterable[ModelVersion] = self._traverse_mlflow_search_func(
            search_func=self.client.search_model_versions,
            filter_string=filter_string,
        )
        return model_versions

    def get_mlflow_model_versions_from_run(self, run_id):
        filter_string = f"run_id = '{run_id}'"

        model_versions: Iterable[ModelVersion] = self._traverse_mlflow_search_func(
            search_func=self.client.search_model_versions,
            filter_string=filter_string,
        )

        return list(model_versions)

    def _get_mlflow_run(self, model_version: ModelVersion) -> Union[None, Run]:
        """
        Get a Run associated with a Model Version. Some MVs may exist without Run.
        """
        if model_version.run_id:
            run = self.client.get_run(model_version.run_id)
            return run
        else:
            return None

    def _get_ml_model_workunits(self) -> Iterable[MetadataWorkUnit]:
        """
        Traverse each Registered Model in Model Registry and generate a corresponding workunit.
        """
        registered_models = self._get_mlflow_registered_models()
        for registered_model in registered_models:
            version_set_urn = self._get_version_set_urn(registered_model)
            yield self._get_ml_group_workunit(registered_model)
            model_versions = self._get_mlflow_model_versions(registered_model)
            if len(list(model_versions)) > 0:
                for model_version in model_versions:
                    run = self._get_mlflow_run(model_version)
                    yield self._get_ml_model_properties_workunit(
                        registered_model=registered_model,
                        model_version=model_version,
                        run=run,
                    )
                    yield self._get_ml_model_version_properties_workunit(
                        model_version=model_version,
                        version_set_urn=version_set_urn,
                    )
                    yield self._get_global_tags_workunit(model_version=model_version)
                yield self._get_version_latest(
                    registered_model=registered_model,
                    version_set_urn=version_set_urn,
                )

    def _get_version_set_urn(self, registered_model: RegisteredModel) -> VersionSetUrn:
        version_set_urn = VersionSetUrn(
            id=f"{registered_model.name}",
            entity_type="mlModel",
        )

        return version_set_urn

    def _get_version_latest(
            self, registered_model: RegisteredModel, version_set_urn: VersionSetUrn
    ) -> MetadataWorkUnit:

        latest_model_version = registered_model.latest_versions[0]
        latest_ml_model_urn = self._make_ml_model_urn(latest_model_version)
        version_set_properties = VersionSetPropertiesClass(
            latest=str(
                latest_ml_model_urn
            ),
            versioningScheme="LEXICOGRAPHIC_STRING",
        )

        wu = MetadataChangeProposalWrapper(
            entityUrn=str(version_set_urn),
            aspect=version_set_properties,
        ).as_workunit()

        # does the latest ml model versioned?
        # model_version_properties = self.graph.get_aspect(entity_urn=latest_ml_model_urn, aspect_type=VersionPropertiesClass)
        # print("LATEST MODEL URN", latest_ml_model_urn)
        # print("MODEL VERSION PROPERTIES", model_version_properties)
        # print("---------")

        return wu

    def _get_ml_model_version_properties_workunit(
        self,
        model_version: ModelVersion,
        version_set_urn: VersionSetUrn,
    ) -> MetadataWorkUnit:
        ml_model_urn = self._make_ml_model_urn(model_version)

        # get mlmodel name from ml model urn
        ml_model_version_properties = VersionPropertiesClass(
            version=VersionTagClass(
                versionTag=str(model_version.version),
                metadataAttribution=MetadataAttributionClass(
                    time=model_version.creation_timestamp,
                    actor="urn:li:corpuser:datahub",
                ),
            ),
            versionSet=str(version_set_urn),
            sortId=str(model_version.version).zfill(10),
            aliases=[
                VersionTagClass(versionTag=alias) for alias in model_version.aliases
            ],
        )

        wu = MetadataChangeProposalWrapper(
            entityUrn=str(ml_model_urn),
            aspect=ml_model_version_properties,
        ).as_workunit()

        return wu

    def _get_ml_model_properties_workunit(
        self,
        registered_model: RegisteredModel,
        model_version: ModelVersion,
        run: Union[None, Run],
    ) -> MetadataWorkUnit:
        """
        Generate an MLModel workunit for an MLflow Model Version.
        Every Model Version is a DataHub MLModel entity associated with an MLModelGroup corresponding to a Registered Model.
        If a model was registered without an associated Run then hyperparams and metrics are not available.
        """
        ml_model_group_urn = self._make_ml_model_group_urn(registered_model)
        ml_model_urn = self._make_ml_model_urn(model_version)

        if run:
            # Use the same metrics and hyperparams from the run
            hyperparams = self._get_run_params(run)
            training_metrics = self._get_run_metrics(run)
            run_urn = DataProcessInstance(
                id=run.info.run_id,
                orchestrator=self.platform,
            ).urn

            training_jobs = [str(run_urn)] if run_urn else []
        else:
            hyperparams = None
            training_metrics = None
            training_jobs = []

        created_time = model_version.creation_timestamp
        created_actor = (
            f"urn:li:platformResource:{model_version.user_id}"
            if model_version.user_id
            else None
        )
        model_version_tags = [f"{k}:{v}" for k, v in model_version.tags.items()]

        ml_model_properties = MLModelPropertiesClass(
            customProperties=model_version.tags,
            externalUrl=self._make_external_url(model_version),
            lastModified=TimeStampClass(
                time=model_version.last_updated_timestamp,
                actor=None,
            ),
            description=model_version.description,
            created=TimeStampClass(
                time=created_time,
                actor=created_actor,
            ),
            hyperParams=hyperparams,
            trainingMetrics=training_metrics,
            tags=model_version_tags,
            groups=[ml_model_group_urn],
            trainingJobs=training_jobs,
        )
        wu = self._create_workunit(urn=ml_model_urn, aspect=ml_model_properties)
        return wu

    def _make_ml_model_urn(self, model_version: ModelVersion) -> str:
        urn = builder.make_ml_model_urn(
            platform=self.platform,
            model_name=f"{model_version.name}{self.config.model_name_separator}{model_version.version}",
            env=self.config.env,
        )
        return urn

    def _get_base_external_url_from_tracking_uri(self) -> Optional[str]:
        if isinstance(
            self.client.tracking_uri, str
        ) and self.client.tracking_uri.startswith("http"):
            return self.client.tracking_uri
        else:
            return None

    def _make_external_url(self, model_version: ModelVersion) -> Optional[str]:
        """
        Generate URL for a Model Version to MLflow UI.
        """
        base_uri = (
            self.config.base_external_url
            or self._get_base_external_url_from_tracking_uri()
        )
        if base_uri:
            return f"{base_uri.rstrip('/')}/#/models/{model_version.name}/versions/{model_version.version}"
        else:
            return None

    def _make_external_url_from_run(
        self, experiment: Experiment, run: Run
    ) -> Union[None, str]:
        base_uri = self.client.tracking_uri
        if base_uri.startswith("http"):
            return f"{base_uri.rstrip('/')}/#/experiments/{experiment.experiment_id}/runs/{run.info.run_id}"
        else:
            return None

    def _get_global_tags_workunit(
        self,
        model_version: ModelVersion,
    ) -> MetadataWorkUnit:
        """
        Associate a Model Version Stage with a corresponding tag.
        """
        global_tags = GlobalTagsClass(
            tags=[
                TagAssociationClass(
                    tag=self._make_stage_tag_urn(model_version.current_stage),
                ),
            ]
        )
        wu = self._create_workunit(
            urn=self._make_ml_model_urn(model_version),
            aspect=global_tags,
        )
        return wu

    @classmethod
    def create(cls, config_dict: dict, ctx: PipelineContext) -> "MLflowSource":
        config = MLflowConfig.parse_obj(config_dict)
        return cls(ctx, config)
