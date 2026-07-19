"""
Parallelization Decorator
~~~~~~~~~~~~~~~~~~~~~~~~~~~

@parallelize decorator that maps a function over a list via the global
parallel processor (#4276).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from functools import partial, wraps
from typing import Any
from collections.abc import Callable

from .audio_processor import get_parallel_processor


def _parallelize_call_item(
    func: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any], item: Any
) -> Any:
    """Module-level helper for @parallelize — picklable by multiprocessing."""
    return func(item, *args, **kwargs)


def parallelize(max_workers: int | None = None) -> Callable[[Callable[[Any], Any]], Callable[[list[Any]], list[Any]]]:
    """Decorator to automatically parallelize a function over a list"""
    def decorator(func: Callable[[Any], Any]) -> Callable[[list[Any]], list[Any]]:
        @wraps(func)
        def wrapper(data_list: list[Any], *args: Any, **kwargs: Any) -> list[Any]:
            processor = get_parallel_processor()

            # Use functools.partial with a module-level function so the
            # callable is picklable for ProcessPoolExecutor (#3304).
            process_item = partial(_parallelize_call_item, func, args, kwargs)

            return processor.process_batch(data_list, process_item, max_workers)

        return wrapper
    return decorator
