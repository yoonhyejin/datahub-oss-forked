import argparse

from datahub.ingestion.graph.client import DataHubGraph
from datahub.ingestion.graph.config import DatahubClientConfig

from entities.experiment import Experiment
from entities.model_group import Model_Group
from entities.dataset import DataSetModel

if __name__ == "__main__":
    # Example usage
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True, help="DataHub access token")
    args = parser.parse_args()

    client = DataHubGraph(
        DatahubClientConfig(
            server="http://localhost:8080",
            token=args.token,
            extra_headers={"Authorization": f"Bearer {args.token}"},
        )
    )

    # Create Experiment
    experiment = Experiment(experiment_id="airline_forecast_experiment",
                            name="Airline Forecast Experiment",
                            description="Experiment for forecasting airline passengers",
                            platform="mlflow",
                            custom_properties={"experiment_type": "forecasting"},
                            client=client)

    # Create Run from Experiments
    run = experiment.create_run(
        run_id="simple_training_run",
        name="Simple Training Run")

    # Create Model Group
    model_group = Model_Group(
        group_id="airline_forecast_models_group",
        name="Airline Forecast Models Group",
        description="Group of models for airline passenger forecasting",
        time=1628580000000
    )

    # Create Model from ModelGroup
    model = model_group.create_model(
        model_id="arima_model_1",
        name="ARIMA Model 1",
        description="ARIMA model for airline passenger forecasting",
        platform="mlflow",
        version="1.0"
    )

    # ADD model and datasets to RUN
    run.add_model(model)
    run.add_input_datasets(DataSetModel(
        platform="snowflake",
        name="iris_input",
    ))
    run.add_output_datasets(DataSetModel(
        platform="snowflake",
        name="iris_ouptut",
    ))


