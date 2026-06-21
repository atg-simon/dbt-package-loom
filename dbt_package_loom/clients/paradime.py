# Copyright 2023 Nicholas Yager and Contributors. Adapted under Apache 2.0.
import logging
import os
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ParadimeReferenceConfig(BaseModel):
    schedule_name: str
    api_endpoint: Optional[str] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    command_index: Optional[int] = None


class ParadimeClient:
    def __init__(self, config: ParadimeReferenceConfig) -> None:
        self.config = config
        self.api_key = config.api_key or os.environ.get("PARADIME_API_KEY")
        self.api_secret = config.api_secret or os.environ.get("PARADIME_API_SECRET")
        self.api_endpoint = config.api_endpoint or os.environ.get(
            "PARADIME_API_ENDPOINT"
        )
        missing = [
            name
            for name, val in [
                ("api_key", self.api_key),
                ("api_secret", self.api_secret),
                ("api_endpoint", self.api_endpoint),
            ]
            if not val
        ]
        if missing:
            raise ValueError(
                f"Paradime credentials missing: {', '.join(missing)}. "
                "Set via config or PARADIME_API_KEY / PARADIME_API_SECRET / PARADIME_API_ENDPOINT."
            )

    def get_latest_manifest(self) -> dict:
        try:
            from paradime import Paradime  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "paradime-io is required: pip install dbt-package-loom[paradime]"
            ) from exc

        client = Paradime(
            api_key=self.api_key,
            api_secret=self.api_secret,
            api_endpoint=self.api_endpoint,
        )
        return client.bolt.get_latest_manifest_json(
            self.config.schedule_name,
            self.config.command_index,
        )
