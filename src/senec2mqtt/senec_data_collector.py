"""
Modul to collect data from device
"""
import asyncio
import logging
import queue
import threading
import time
from typing import Optional, List

import aiohttp
from pysenec import Senec


class SenecDataCollector(threading.Thread):
    """
    This class is a thread based data collector,
    to handle the pysenec asyncio requirements and put the raw data into a synchronous queue.
    """

    def __init__(self, senec_ip: str, interval_s: int = 60):
        """
        Constructor

        :param senec_ip: IP Address of the senec device
        :param interval_s: Interval in seconds to collect data
        """

        super().__init__()
        self._host_ip = senec_ip
        self._interval_s = interval_s
        if interval_s < 60:
            logging.warning("The logging interval is below the recommended period time (1 min),\n"
                            "may this leads to trouble with the device connection to the cloud!")
        if interval_s < 10:
            raise ValueError("No interval below 10 sec allowed!")

        self._stop_event = threading.Event()
        self._queue = queue.Queue()

    def stop(self) -> None:
        """
        Abort the thread asap
        """
        logging.debug("Stop event set")
        self._stop_event.set()

    def run(self) -> None:
        """
        Thread loop with periodic call of "_collect_data"

        """
        logging.debug("collection thread started")
        while not self._stop_event.is_set():
            self._queue.put(self._collect_data())

            time.sleep(self._interval_s)
        logging.debug("collection thread stopped")

    def _collect_data(self) -> dict:
        """
        Core Function, calls the async function "run"
        and put the return value into a thread safe queue

        """
        async def run(host):
            """
            Simple async connect and collect function around the pysenec device

            :param host: ip address of the device
            :return: raw parameter as dict
            """
            async with aiohttp.ClientSession() as session:
                senec = Senec(host, session)
                # only call "update" to avoid reading the system information to often (see pysenec for details)
                await senec.update()
            # use raw status to get information about the 3 phases and more
            return senec.raw_status

        # todo: remove me
        self.stop()

        # pysenec uses async, so use this to sync the data
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        collected_data = loop.run_until_complete(asyncio.gather(run(host=self._host_ip)))
        loop.close()
        if len(collected_data) != 1:
            raise RuntimeError(f"Expect exact one set of data from pysenec instance, but got: {len(collected_data)}!")

        logging.debug("data collected")

        return collected_data[0]

    def available_data(self) -> int:
        """
        Return the amount of available data

        :return: queue size
        """
        return self._queue.qsize()

    def get_data(self, block=True) -> Optional[dict]:
        """
        Get a single data dict

        :param block: wait until next data arrive
        :return: data as dict or None if blocking is false and no data in queue
        """
        try:
            return self._queue.get(block=block)
        except queue.Empty:
            return None

    def get_all_data(self) -> List[dict]:
        """
        Return all data sets in queue as list

        :return: list with all data sets
        """
        data_list: List[dict] = []
        while True:
            data = self.get_data(block=False)
            if data is not None:
                data_list.append(data)
            else:
                break
        return data_list


if __name__ == '__main__':
    logging.basicConfig(filename='example.log', filemode='w', level=logging.DEBUG)
    ip_addr = "192.168.178.49"
    interval_s = 30 # int(input("Enter Period Time [s]:"))

    sdc = SenecDataCollector(senec_ip=ip_addr, interval_s=interval_s)
    sdc.start()
    time.sleep(5)
    sdc.stop()
    sdc.join(interval_s)

    print(sdc.available_data())
    print(sdc.get_all_data())
