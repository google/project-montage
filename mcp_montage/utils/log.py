# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Logging configuration for the application."""

import logging.config
import os
import time

import yaml
from shared.constants import LOG_TO_FILE, LOGGING_LEVEL

enable_file_logging = LOG_TO_FILE
date = time.strftime("%Y-%m-%d")

if enable_file_logging:
  try:
    os.makedirs(f"./logs/{date}", exist_ok=True)
  except OSError:
    enable_file_logging = False

CONFIG_YAML = f"""\
version: 1
disable_existing_loggers: False

formatters:
  default:
    format: "%(asctime)s %(levelname)-10s %(filename)s:%(lineno)d (%(funcName)s) :: %(message)s"
    datefmt: "%Y-%m-%dT%H:%M:%S%z"


handlers:
  console:
    class: logging.StreamHandler
    level: {LOGGING_LEVEL}
    formatter: default
    stream: ext://sys.stdout

  app_file_handler:
    class: logging.FileHandler
    level: DEBUG
    formatter: default
    filename: ./logs/{date}/server.log
    mode: a

root:
  level: DEBUG
  handlers: [console, app_file_handler]
"""  # noqa: E501

_config = yaml.safe_load(CONFIG_YAML)

if not enable_file_logging:
  # Remove file handler from handlers
  if "app_file_handler" in _config.get("handlers", {}):
    del _config["handlers"]["app_file_handler"]

  if "root" in _config:
    handlers = _config["root"].get("handlers", [])
    if "app_file_handler" in handlers:
      handlers.remove("app_file_handler")

logging.config.dictConfig(_config)


def get_logger() -> logging.Logger:
  app_logger = logging.getLogger()
  return app_logger
