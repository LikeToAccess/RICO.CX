from time import perf_counter
from collections.abc import Callable


def timer(function: Callable) -> Callable:
	def wrapper(*args, **kwargs):
		tic = perf_counter()
		result = function(*args, **kwargs)
		toc = perf_counter()
		print(f"{function.__name__} took {toc - tic:0.2f} second{'' if toc - tic == 1 else 's'}.")
		return result
	return wrapper
