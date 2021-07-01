#!/usr/bin/env python3
"""
A script for performing restarts of the ag-chain-cosmos service (Agoric node).

Finds the service logs when the service was started and when the first block was received from the chain.
Calculates the difference between them and displays.

Args:
   `n` - numbers of restarts

Example::

     $ sudo ./agoric_restarter.py

Output::

    Restart #1: 0:00:18.444228
    Restart #2: 0:00:17.258119
    Restart #3: 0:00:16.693717
    ________________________________________
    Restarts: 3, Total time: 0:00:52.396064
    min: 0:00:16.693717, max: 0:00:18.444228, avg: 0:00:17.465355
"""
import json
import subprocess
import re
import argparse
import sys
import time
import threading
import datetime as dt
import itertools as it
from typing import List, Generator

parser = argparse.ArgumentParser()

# ag-chain-cosmos.service
SERVICE_NAME = "ag-chain-cosmos.service"
START_MESSAGE = ".*Started Agoric Cosmos daemon.$"
END_MESSAGE = ".*block-manager: block \d+ begin$"


class ProgressBar:
    """
    Progress Bar for waiting process
    """
    def __init__(self, desc="Loading", timeout=0.1) -> None:
        """
        Args:
            desc (str, optional): The progress bar's description. Defaults to "Loading".
            timeout (float, optional): Sleep time between prints. Defaults to 0.1.
        """
        self.desc = desc
        self.timeout = timeout

        self._thread = threading.Thread(target=self._animate, daemon=True)
        self.steps = ["⢿", "⣻", "⣽", "⣾", "⣷", "⣯", "⣟", "⡿"]
        self.done = False

    def start(self) -> "ProgressBar":
        """
        Start a tread for display a progress bar.

        Returns:
            ProgressBar: This instance.
        """
        self._thread.start()
        return self

    def _animate(self) -> None:
        for c in it.cycle(self.steps):
            if self.done:
                break
            print(f"\r{self.desc} {c}", flush=True, end="")
            time.sleep(self.timeout)

    def stop(self, end: str = "") -> None:
        """
        Stop the tread and print result as `Loading value`

        Args:
            end (str, optional): The value to display at the end of the process. Defaults to empty string.
        """
        self.done = True
        print("\r" + len(self.desc) * " ", end="", flush=True)
        print(f"\r{self.desc} {end}", flush=True)


def restart_service() -> None:
    """
    Restart service using systemd.
    """
    return_code = subprocess.call(["systemctl", "restart", SERVICE_NAME])
    if return_code != 0:
        print(f"service `{SERVICE_NAME}` exited with code {return_code}")
        sys.exit(1)


def read_json(line: str) -> dict:
    """
    Convert string to json.

    Args:
        line (str): json string.

    Returns:
        dict: new dict object.
    """
    return json.loads(line)


def read_log() -> Generator[dict, None, None]:
    """
    Reading the service log using journalctl in real time.

    Yields:
         dict: log line.
    """
    cmd = f"journalctl -u {SERVICE_NAME} -o json -n 2 --output-fields=MESSAGE -f"
    process = subprocess.Popen(
        cmd.split(), stdout=subprocess.PIPE, universal_newlines=True
    )
    while True:
        output = process.stdout.readline()
        yield read_json(output)


def check_message() -> dt.timedelta:
    """
    Find in the logs the start time of the service and
    the time when the first block was received from the chain.
    Calculate the time (restart time).

    Returns:
        timedelta: restart time.
    """
    start_timestamp = 0
    for msg in read_log():
        timestamp = dt.datetime.fromtimestamp(
            int(msg["__REALTIME_TIMESTAMP"]) / 10 ** 6
        )
        message = msg["MESSAGE"]
        # print(f'{timestamp}, {message}')

        if not (isinstance(message, str)):
            continue

        if re.match(START_MESSAGE, message):
            start_timestamp = timestamp
            # print(f"--start found {timestamp}")
        elif start_timestamp and re.match(END_MESSAGE, message):
            # print(f"--end found {timestamp}")
            restart = timestamp - start_timestamp
            return restart


def print_results(restarts: List[dt.timedelta]) -> None:
    """
    Display the results of restarts

    Args:
        restarts (list[timedelta]): list of time deltas for restarts.
    """
    min_time = min(restarts)
    max_time = max(restarts)
    total_time = sum(restarts, dt.timedelta())
    r = len(restarts)
    avg_time = total_time / r
    print("_" * 40)
    print(f"Restarts: {r}, Total time: {total_time}")
    print(f"min: {min_time}, max: {max_time}, avg: {avg_time}")


def restart_by_count(count: int) -> List[dt.timedelta]:
    """
    Restart the service n times.

    Args:
        count (int): numbers of restarts.
    """
    restart_timedelta = []
    for num in range(1, count + 1):
        msg = f"Restart #{num}:"
        pb_thread = ProgressBar(msg).start()
        restart_service()
        r = check_message()
        restart_timedelta.append(r)
        pb_thread.stop(end=str(r))
    return restart_timedelta


def main(count: int) -> None:
    """
    Restart the service and get the time results.

    Args:
        count (int): numbers of restarts.
    """
    restarts = restart_by_count(count)
    print_results(restarts)


if __name__ == "__main__":
    parser.add_argument(
        "-n", "--numbers", type=int, default=1, help="numbers of restarts"
    )
    args = parser.parse_args()
    main(count=args.numbers)
