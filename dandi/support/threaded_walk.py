# Derived from <https://gist.github.com/jart/0a71cde3ca7261f77080a3625a21672b>

# Copyright 2016 The TensorFlow Authors. All Rights Reserved.
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
# ==============================================================================

import logging
import os.path
from pathlib import Path
import threading
from typing import Any, Callable, Iterable, Optional, Union

log = logging.getLogger(__name__)


def threaded_walk(
    dirpath: Union[str, Path],
    func: Optional[Callable[[Path], Any]] = None,
    threads: int = 60,
) -> Iterable[Any]:
    if not os.path.isdir(dirpath):
        return
    lock = threading.Lock()
    on_input = threading.Condition(lock)
    on_output = threading.Condition(lock)
    tasks = 1
    paths = [Path(dirpath)]
    output: list = []

    def worker() -> None:
        nonlocal tasks
        while True:
            with lock:
                while True:
                    if not tasks:
                        output.append(None)
                        on_output.notify()
                        return
                    if not paths:
                        on_input.wait()
                        continue
                    path = paths.pop()
                    break
            try:
                for p in path.iterdir():
                    if p.is_dir():
                        with lock:
                            tasks += 1
                            paths.append(p)
                            on_input.notify()
                    else:
                        item = func(p) if func is not None else p
                        with lock:
                            output.append(item)
                            on_output.notify()
            except Exception:
                log.exception("Error scanning directory %s", path)
            finally:
                with lock:
                    tasks -= 1
                    if not tasks:
                        on_input.notify_all()

    workers = [
        threading.Thread(
            target=worker, name=f"threaded_walk {i} {dirpath}", daemon=True
        )
        for i in range(threads)
    ]
    for w in workers:
        w.start()
    while threads or output:
        with lock:
            while not output:
                on_output.wait()
            item = output.pop()
        if item:
            yield item
        else:
            threads -= 1
