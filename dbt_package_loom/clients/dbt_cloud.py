# Copyright 2023 Nicholas Yager and Contributors. Adapted under Apache 2.0.
import logging
import os
from typing import Optional

import requests
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class DbtCloudReferenceConfig(BaseModel):
    account_id: int
    job_id: int
    api_endpoint: str = "https://cloud.getdbt.com/api/v2"
    step: Optional[int] = None


class DbtCloud:
    def __init__(self, config: DbtCloudReferenceConfig) -> None:
        self.config = config
        self.token = os.environ.get("DBT_CLOUD_API_TOKEN")
        if not self.token:
            raise ValueError("DBT_CLOUD_API_TOKEN environment variable is required")

    def get_latest_manifest(self) -> dict:
        headers = {"Authorization": f"Token {self.token}"}
        runs_url = (
            f"{self.config.api_endpoint}/accounts/{self.config.account_id}/runs/"
        )
        params = {
            "job_definition_id": self.config.job_id,
            "status": 10,
            "order_by": "-finished_at",
            "limit": 1,
        }
        response = requests.get(runs_url, headers=headers, params=params)
        response.raise_for_status()
        runs = response.json().get("data", [])
        if not runs:
            raise ValueError(
                f"No successful runs found for job {self.config.job_id}"
            )
        run_id = runs[0]["id"]
        logger.debug("Using dbt Cloud run %s for job %s", run_id, self.config.job_id)

        artifact_url = (
            f"{self.config.api_endpoint}/accounts/{self.config.account_id}"
            f"/runs/{run_id}/artifacts/manifest.json"
        )
        artifact_params = {}
        if self.config.step is not None:
            artifact_params["step"] = self.config.step
        response = requests.get(artifact_url, headers=headers, params=artifact_params)
        response.raise_for_status()
        return response.json()
