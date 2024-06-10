import asyncio
import logging
import os
from datetime import date, datetime, timedelta

import matplotlib.pyplot as plt
import yaml
from aiohttp import ClientSession, ClientTimeout
from requests.exceptions import HTTPError, ReadTimeout
from thclient import TreeherderClient

project_root = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(project_root, "config", "config.yml")

logging.basicConfig(level=logging.INFO)

RETRY_LIMIT = 3  # Number of retries for requests
RETRY_DELAY = 5  # Delay in seconds between retries


class Config:
    def __init__(self, config_path):
        self.config_path = config_path

    def load(self):
        with open(self.config_path) as file:
            return yaml.load(file, Loader=yaml.FullLoader)


class TreeherderClientWrapper:
    def __init__(self, server_url, timeout):
        self.client = TreeherderClient(server_url=server_url, timeout=timeout)
        self.timeout = timeout

    async def fetch_data(self, repo, symbol, group_symbol, tier, result):
        dataset = []
        retry_count = 0

        while retry_count < RETRY_LIMIT:
            try:
                pushes = self.client.get_pushes(
                    project=repo,
                    count=100,
                    enddate=date.today().isoformat(),
                    startdate=(date.today() - timedelta(days=1)).isoformat(),
                )
                break  # Exit loop if successful
            except (ReadTimeout, HTTPError) as e:
                logging.error(f"Error fetching pushes (attempt {retry_count + 1}/{RETRY_LIMIT}): {e}")
                retry_count += 1
                await asyncio.sleep(RETRY_DELAY)  # Wait before retrying

        if retry_count == RETRY_LIMIT:
            logging.error(f"Failed to fetch pushes for {repo} after {RETRY_LIMIT} attempts")
            return dataset

        if pushes:
            push_ids = [push["id"] for push in sorted(pushes, key=lambda push: push["id"])]
            tasks = [self.fetch_jobs(repo, push_id, symbol, group_symbol, tier, result) for push_id in push_ids]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, list):
                    dataset.extend(result)

        return dataset

    async def fetch_jobs(self, repo, push_id, symbol, group_symbol, tier, result):
        jobs = []
        retry_count = 0

        while retry_count < RETRY_LIMIT:
            try:
                jobs = self.client.get_jobs(
                    project=repo,
                    push_id=push_id,
                    tier=tier,
                    job_type_symbol=symbol,
                    result=result,
                    job_group_symbol=group_symbol
                )
                break  # Exit loop if successful
            except (ReadTimeout, HTTPError) as e:
                logging.error(f"Error fetching jobs (attempt {retry_count + 1}/{RETRY_LIMIT}): {e}")
                retry_count += 1
                await asyncio.sleep(RETRY_DELAY)  # Wait before retrying

        if retry_count == RETRY_LIMIT:
            logging.error(f"Failed to fetch jobs for push {push_id} after {RETRY_LIMIT} attempts")
            return jobs

        dataset = []
        for current_job in jobs:
            job_start = datetime.fromtimestamp(current_job["start_timestamp"])
            job_end = datetime.fromtimestamp(current_job["end_timestamp"])
            duration = (job_end - job_start).total_seconds() / 60

            dataset.append(
                {
                    "task": symbol,
                    "group": group_symbol,
                    "tier": tier,
                    "result": result,
                    "push_id": push_id,
                    "job_id": current_job["id"],
                    "duration": duration,
                    "repo": repo,
                }
            )

        return dataset


async def main():
    config = Config(config_path)
    configs = config.load()

    treeherder_client = TreeherderClientWrapper(
        server_url="https://treeherder.mozilla.org",
        timeout=120  # Increasing the timeout to 120 seconds
    )

    async with ClientSession(timeout=ClientTimeout(total=treeherder_client.timeout)) as session:
        tasks = []
        for project in configs["projects"]:
            ui_test_durations = []
            build_durations = []
            test_durations = []

            repo = project["repository"]

            for task in project["tasks"]:
                symbol = task["symbol"]
                group_symbol = task["group_symbol"]
                tier = task["tier"]
                result = task["result"]

                task_data = await treeherder_client.fetch_data(
                    repo, symbol, group_symbol, tier, result
                )

                if "ui-test" in task["name"]:
                    ui_test_durations.extend(task_data)
                elif "build" in task["name"]:
                    build_durations.extend(task_data)
                elif "test-apk" in task["name"]:
                    test_durations.extend(task_data)

            tasks.append((project, ui_test_durations, build_durations, test_durations))

        for project, ui_test_durations, build_durations, test_durations in tasks:
            if ui_test_durations:
                sample_number_ui = list(range(1, len(ui_test_durations) + 1))
                ui_test_duration_times = [item["duration"] for item in ui_test_durations]

                plt.plot(
                    sample_number_ui,
                    ui_test_duration_times,
                    label="UI Test Duration",
                    marker="o",
                )

            if build_durations:
                sample_number_build = list(range(1, len(build_durations) + 1))
                build_duration_times = [item["duration"] for item in build_durations]

                plt.plot(
                    sample_number_build,
                    build_duration_times,
                    label="Build Duration",
                    marker="x",
                )

            if test_durations:
                sample_number_test = list(range(1, len(test_durations) + 1))
                test_duration_times = [item["duration"] for item in test_durations]

                plt.plot(
                    sample_number_test,
                    test_duration_times,
                    label="Unit Test Duration",
                    marker="s",
                )

            if not ui_test_durations and not build_durations and not test_durations:
                logging.error(f"No data found for {repo}")
            else:
                plt.title(f"CI Duration Times by Sampling Size in {repo}")
                plt.xlabel("Sample Number")
                plt.ylabel("Duration (minutes)")
                plt.legend()
                plt.savefig(f"durations-{project['name']}.png")
                plt.clf()


if __name__ == "__main__":
    asyncio.run(main())
