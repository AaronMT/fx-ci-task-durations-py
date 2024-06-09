import logging
import os
from datetime import date, datetime, timedelta

import matplotlib
import matplotlib.pyplot as plt
import yaml
from thclient import TreeherderClient

project_root = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(project_root, "config", "config.yml")

logging.basicConfig()


class Config:
    def __init__(self, config_path):
        self.config_path = config_path

    def load(self):
        with open(self.config_path) as file:
            return yaml.load(file, Loader=yaml.FullLoader)


class TreeherderClientWrapper:
    def __init__(self, server_url):
        self.client = TreeherderClient(server_url=server_url)

    def fetch_data(self, repo, symbol, group_symbol, tier, result):
        dataset = []
        try:
            pushes = self.client.get_pushes(
                project=repo,
                symbol=symbol,
                group_symbol=group_symbol,
                tier=tier,
                count=100,
                enddate=date.today().isoformat(),
                startdate=date.today() - timedelta(days=1),
            )
        except Exception as e:
            logging.error(f"Error fetching pushes: {e}")
            return dataset

        if pushes:
            for current_push in sorted(pushes, key=lambda push: push["id"]):
                jobs = self.client.get_jobs(
                    project=repo,
                    push_id=current_push["id"],
                    job_type_symbol=symbol,
                    result=result,
                    job_group_symbol=group_symbol,
                    tier=tier,
                )
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
                            "push_id": current_push["id"],
                            "job_id": current_job["id"],
                            "duration": duration,
                            "repo": repo,
                        }
                    )

        return dataset


def main():
    config = Config(config_path)
    configs = config.load()

    treeherder_client = TreeherderClientWrapper(
        server_url="https://treeherder.mozilla.org"
    )

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

            task_data = treeherder_client.fetch_data(
                repo, symbol, group_symbol, tier, result
            )

            if "ui-test" in task["name"]:
                ui_test_durations.extend(task_data)
            elif "build" in task["name"]:
                build_durations.extend(task_data)
            elif "test-apk" in task["name"]:
                test_durations.extend(task_data)

            # Plot UI Test Durations
            if ui_test_durations:
                sample_number_ui = list(range(1, len(ui_test_durations) + 1))
                ui_test_duration_times = [
                    item["duration"] for item in ui_test_durations
                ]

                plt.plot(
                    sample_number_ui,
                    ui_test_duration_times,
                    label="UI Test Duration",
                    marker="o",
                )

            # Plot Build Durations
            if build_durations:
                sample_number_build = list(range(1, len(build_durations) + 1))
                build_duration_times = [item["duration"] for item in build_durations]

                plt.plot(
                    sample_number_build,
                    build_duration_times,
                    label="Build Duration",
                    marker="x",
                )

            # Plot Test Durations
            if test_durations:
                sample_number_test = list(range(1, len(test_durations) + 1))
                test_duration_times = [item["duration"] for item in test_durations]

                plt.plot(
                    sample_number_test,
                    test_duration_times,
                    label="Unit Test Duration",
                    marker="s",
                )

            plt.title("CI Duration Times by Sampling Size")
            plt.xlabel("Sample Number")
            plt.ylabel("Duration (minutes)")
            plt.legend()
            plt.show()


if __name__ == "__main__":
    main()
